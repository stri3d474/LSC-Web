"""Billing and entitlement domain types (C6, C7).

Tier precedence and entitlement derivation are pure functions here. Purchases,
community verification and organization membership are the only inputs; the
client is never a source of truth.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

# Entitlement lifecycle states (C6).
STATE_ACTIVE = "active"
STATE_PENDING = "pending"
STATE_GRACE = "grace"
STATE_EXPIRED = "expired"


class TierRank(IntEnum):
    """Ordering so the strongest active entitlement wins when several apply."""

    FREE = 0
    COMMUNITY = 1
    PROFESSIONAL = 2
    INSTITUTIONAL = 3


_TIER_TO_RANK = {
    "free": TierRank.FREE,
    "community": TierRank.COMMUNITY,
    "professional": TierRank.PROFESSIONAL,
    "institutional": TierRank.INSTITUTIONAL,
}


def tier_rank(tier: str) -> TierRank:
    """Return the rank for a tier name (unknown tiers rank as FREE)."""

    return _TIER_TO_RANK.get(tier, TierRank.FREE)


@dataclass(frozen=True)
class Purchase:
    """A stored Play purchase (C7 ``purchases``). Keyed by SHA-256 of the token.

    The raw purchase token is never stored (SECURITY(BILL-02)); ``token_hash``
    is its SHA-256.
    """

    token_hash: str
    uid: str
    product_id: str
    tier: str
    state: str  # normalized Play state
    expires_at: str | None
    acknowledged: bool
    updated_at: str


@dataclass(frozen=True)
class CommunityVerification:
    """Record that a user was granted the community tier (C7).

    Stores only the fact, the issuing org and the time — never medical proof.
    """

    uid: str
    org_id: str
    granted_at: str


@dataclass(frozen=True)
class Entitlement:
    """The computed entitlement returned by GET /me/entitlements."""

    tier: str
    features: tuple[str, ...]
    state: str
    expires_at: str | None
    as_of: str


# Play states that still grant access, mapped to an entitlement state.
_PLAY_STATE_TO_ENTITLEMENT: dict[str, str] = {
    "active": STATE_ACTIVE,
    "grace": STATE_GRACE,
    # pending (e.g. cash) grants nothing; handled explicitly below.
}


def purchase_entitlement_state(play_state: str) -> str | None:
    """Map a normalized Play state to an entitlement state, or None if it
    grants no access (pending, expired, revoked, canceled, on_hold, paused)."""

    return _PLAY_STATE_TO_ENTITLEMENT.get(play_state)
