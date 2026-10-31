"""Entitlements derivation. Implements the identity ``EntitlementsPort``.

SECURITY(ENT-01): the tier, feature set and state are derived only from
server-verified facts — Play purchases, community verification and organization
membership. The client is never consulted. The strongest active entitlement
wins (institutional > professional > community > free).
"""

from __future__ import annotations

from lsc_api.core.clock import Clock, iso_utc
from lsc_api.modules.billing.config import BillingCatalog
from lsc_api.modules.billing.domain import (
    STATE_ACTIVE,
    STATE_GRACE,
    Entitlement,
    purchase_entitlement_state,
    tier_rank,
)
from lsc_api.modules.billing.orgs_repository import OrgsRepository
from lsc_api.modules.billing.repository import BillingRepository


class EntitlementsService:
    """Computes a user's current entitlement from verified facts."""

    def __init__(
        self,
        billing_repo: BillingRepository,
        orgs_repo: OrgsRepository,
        catalog: BillingCatalog,
        clock: Clock,
    ) -> None:
        self._billing = billing_repo
        self._orgs = orgs_repo
        self._catalog = catalog
        self._clock = clock

    async def tier_for(self, uid: str) -> str:
        """Return the current tier name (``EntitlementsPort``)."""

        entitlement = await self.compute(uid)
        return entitlement.tier

    async def compute(self, uid: str) -> Entitlement:
        """Derive the full entitlement for ``uid``.

        Considers: active/grace Play purchases (by tier), community verification
        (tier ``community``), and institutional membership (tier
        ``institutional``). The highest-ranked active source wins. ``free`` is
        the floor. ``expires_at`` comes from the winning purchase when
        applicable.
        Outputs: an ``Entitlement`` with tier, features, state, expires_at,
        as_of. Failure modes: ``UpstreamError`` on store failure.
        """

        now = self._clock.now()
        as_of = iso_utc(now)

        best_tier = "free"
        best_state = STATE_ACTIVE
        best_expires: str | None = None
        best_rank = tier_rank("free")

        # Play purchases.
        for purchase in await self._billing.purchases_for_user(uid):
            ent_state = purchase_entitlement_state(purchase.state)
            if ent_state is None:
                continue
            # Expiry guard: an active/grace record past its expiry is expired.
            if purchase.expires_at and as_of > purchase.expires_at:
                continue
            rank = tier_rank(purchase.tier)
            if rank > best_rank:
                best_rank = rank
                best_tier = purchase.tier
                best_state = ent_state if ent_state != STATE_GRACE else STATE_GRACE
                best_expires = purchase.expires_at

        # Community verification (free, verified Deaf users).
        community = await self._billing.community_verification(uid)
        if community is not None:
            rank = tier_rank("community")
            if rank > best_rank:
                best_rank = rank
                best_tier = "community"
                best_state = STATE_ACTIVE
                best_expires = None

        features = self._catalog.features_for_tier(best_tier)
        return Entitlement(
            tier=best_tier,
            features=features,
            state=best_state if best_tier != "free" else STATE_ACTIVE,
            expires_at=best_expires,
            as_of=as_of,
        )
