"""Billing service: products, Play purchase verification, RTDN processing.

SECURITY(BILL-01..04): subscription state always comes from a fresh Play query;
the obfuscated account id on the purchase must equal the caller's HMAC account
id (replay for another account fails); tokens are stored only as SHA-256; every
entitlement change is audited.
"""

from __future__ import annotations

import hashlib

from lsc_api.core.clock import Clock, iso_utc
from lsc_api.core.errors import UpstreamError, ValidationError
from lsc_api.core.security.accountid import account_id
from lsc_api.infra.play import PlayClient
from lsc_api.infra.secrets import SecretStore
from lsc_api.modules.audit.service import AuditService
from lsc_api.modules.billing.config import BillingCatalog
from lsc_api.modules.billing.domain import Purchase
from lsc_api.modules.billing.entitlements import EntitlementsService
from lsc_api.modules.billing.repository import BillingRepository

_PEPPER_SECRET = "pseudonymization-pepper"


def _sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class BillingService:
    """Verifies purchases against Play and updates entitlements."""

    def __init__(
        self,
        repository: BillingRepository,
        play: PlayClient,
        secrets: SecretStore,
        entitlements: EntitlementsService,
        audit: AuditService,
        catalog: BillingCatalog,
        clock: Clock,
        *,
        play_package_name: str,
    ) -> None:
        self._repo = repository
        self._play = play
        self._secrets = secrets
        self._entitlements = entitlements
        self._audit = audit
        self._catalog = catalog
        self._clock = clock
        self._package = play_package_name

    async def account_id_for(self, uid: str) -> str:
        """Return the HMAC account id the app attaches to Play purchases."""

        pepper = await self._secrets.access(_PEPPER_SECRET)
        return account_id(uid, pepper)

    def products(self) -> list[dict[str, object]]:
        """Return the public product catalog (product_id, tier, features)."""

        return [
            {"product_id": p.product_id, "tier": p.tier, "features": list(p.features)}
            for p in self._catalog.products.values()
        ]

    async def verify_purchase(
        self, *, uid: str, product_id: str, purchase_token: str
    ) -> None:
        """Verify a Play purchase and update the user's entitlements.

        Steps: confirm the product is known; query Play for the token; confirm
        the package name and that the purchase's obfuscated account id equals the
        caller's HMAC account id; acknowledge if needed; store the purchase keyed
        by SHA-256 of the token; recompute entitlements. Idempotent: re-verifying
        the same token updates the existing record. Pending purchases (cash
        methods) are stored as ``pending`` and grant nothing.
        Failure modes: ``ValidationError`` if the product is unknown or the
        account id does not match (replay for another account); ``UpstreamError``
        on Play failure.
        """

        product = self._catalog.product(product_id)
        if product is None:
            raise ValidationError("unknown product")

        sub = await self._play.get_subscription(self._package, purchase_token)
        expected_account = await self.account_id_for(uid)
        if sub.obfuscated_account_id != expected_account:
            # The token was initiated by (or replayed for) another account.
            raise ValidationError("purchase account mismatch")

        if sub.product_id != product_id:
            raise ValidationError("product mismatch")

        if sub.state == "active" and not sub.acknowledged:
            await self._play.acknowledge_subscription(self._package, purchase_token)
            acknowledged = True
        else:
            acknowledged = sub.acknowledged

        token_hash = _sha256_hex(purchase_token)
        purchase = Purchase(
            token_hash=token_hash,
            uid=uid,
            product_id=product_id,
            tier=product.tier,
            state=sub.state,
            expires_at=sub.expiry_time,
            acknowledged=acknowledged,
            updated_at=iso_utc(self._clock.now()),
        )
        await self._repo.upsert_purchase(purchase)
        await self._refresh_and_audit(uid, action="billing.verify", target=token_hash)

    async def process_rtdn(self, *, purchase_token: str) -> None:
        """Process a Play RTDN trigger by re-querying Play (idempotent).

        The RTDN body is treated only as a trigger; the authoritative state is
        the fresh Play response. Updates the stored purchase and recomputes
        entitlements for renewal/cancel/expiry/hold/grace/pause/revoke/
        pending-resolved. If the token is unknown locally, the purchase is still
        recorded from the Play response.
        Failure modes: ``UpstreamError`` on Play failure.
        """

        token_hash = _sha256_hex(purchase_token)
        existing = await self._repo.get_purchase(token_hash)
        sub = await self._play.get_subscription(self._package, purchase_token)

        product = self._catalog.product(sub.product_id)
        tier = product.tier if product else (existing.tier if existing else "free")
        uid = existing.uid if existing else None
        if uid is None:
            # No local record and RTDN carries no uid; nothing to attribute.
            raise UpstreamError("rtdn for unknown purchase token")

        purchase = Purchase(
            token_hash=token_hash,
            uid=uid,
            product_id=sub.product_id,
            tier=tier,
            state=sub.state,
            expires_at=sub.expiry_time,
            acknowledged=sub.acknowledged,
            updated_at=iso_utc(self._clock.now()),
        )
        await self._repo.upsert_purchase(purchase)
        await self._refresh_and_audit(uid, action="billing.rtdn", target=token_hash)

    async def _refresh_and_audit(self, uid: str, *, action: str, target: str) -> None:
        """Recompute and cache the entitlement, then write an audit entry."""

        entitlement = await self._entitlements.compute(uid)
        await self._repo.save_entitlement(
            uid,
            {
                "tier": entitlement.tier,
                "features": list(entitlement.features),
                "state": entitlement.state,
                "expires_at": entitlement.expires_at,
                "as_of": entitlement.as_of,
            },
        )
        await self._audit.record(
            actor=uid,
            action=action,
            target=target,
            metadata={"tier": entitlement.tier, "state": entitlement.state},
        )
