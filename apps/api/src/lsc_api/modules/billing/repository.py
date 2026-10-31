"""Billing persistence: purchases, community verification, entitlements cache.

SECURITY(BILL-02): purchases are keyed by the SHA-256 of the purchase token;
the raw token is never stored.
"""

from __future__ import annotations

from typing import Any

from lsc_api.modules.billing.domain import (
    CommunityVerification,
    Purchase,
)

_PURCHASES = "purchases"
_ENTITLEMENTS = "entitlements"  # cached computed entitlement per uid
_COMMUNITY = "community_verifications"


class BillingRepository:
    """Stores purchases and derived entitlement facts."""

    def __init__(self, store: Any) -> None:
        self._store = store

    # --- Purchases. ---
    async def upsert_purchase(self, purchase: Purchase) -> None:
        """Create or update a purchase keyed by its token hash."""

        await self._store.set(
            _PURCHASES,
            purchase.token_hash,
            {
                "uid": purchase.uid,
                "product_id": purchase.product_id,
                "tier": purchase.tier,
                "state": purchase.state,
                "expires_at": purchase.expires_at,
                "acknowledged": purchase.acknowledged,
                "updated_at": purchase.updated_at,
            },
        )

    async def get_purchase(self, token_hash: str) -> Purchase | None:
        doc = await self._store.get(_PURCHASES, token_hash)
        return _to_purchase(token_hash, doc) if doc else None

    async def purchases_for_user(self, uid: str) -> list[Purchase]:
        rows, _ = await self._store.query(
            _PURCHASES, where=[("uid", "==", uid)], limit=100
        )
        return [_to_purchase(r.get("_id", ""), r) for r in rows]

    # --- Community verification. ---
    async def add_community_verification(self, v: CommunityVerification) -> None:
        await self._store.set(
            _COMMUNITY,
            v.uid,
            {"org_id": v.org_id, "granted_at": v.granted_at},
        )

    async def community_verification(self, uid: str) -> CommunityVerification | None:
        doc = await self._store.get(_COMMUNITY, uid)
        if not doc:
            return None
        return CommunityVerification(
            uid=uid, org_id=str(doc["org_id"]), granted_at=str(doc["granted_at"])
        )

    # --- Entitlement cache. ---
    async def save_entitlement(self, uid: str, data: dict[str, Any]) -> None:
        await self._store.set(_ENTITLEMENTS, uid, data)

    async def get_entitlement(self, uid: str) -> dict[str, Any] | None:
        return await self._store.get(_ENTITLEMENTS, uid)


def _to_purchase(token_hash: str, doc: dict[str, Any]) -> Purchase:
    return Purchase(
        token_hash=token_hash,
        uid=str(doc["uid"]),
        product_id=str(doc["product_id"]),
        tier=str(doc["tier"]),
        state=str(doc["state"]),
        expires_at=(str(doc["expires_at"]) if doc.get("expires_at") else None),
        acknowledged=bool(doc.get("acknowledged", False)),
        updated_at=str(doc.get("updated_at", "")),
    )
