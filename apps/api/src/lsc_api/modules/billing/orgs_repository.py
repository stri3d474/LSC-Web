"""Organization persistence: orgs, members, single-use verification codes.

SECURITY(VERIFY-01): verification codes are high-entropy, single-use and
expiring; only their SHA-256 hash is stored, never the raw code.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

_ORGS = "orgs"
_ORG_MEMBERS = "org_members"
_CODES = "verification_codes"


@dataclass(frozen=True)
class Org:
    """An organization (hospital, school, agency)."""

    org_id: str
    name: str
    seat_limit: int
    created_at: str


@dataclass(frozen=True)
class VerificationCode:
    """A single-use community-verification code (stored hashed)."""

    code_hash: str
    org_id: str
    expires_at: str
    redeemed: bool
    redeemed_by: str | None
    created_at: str


class OrgsRepository:
    """Reads and writes organizations, memberships and verification codes."""

    def __init__(self, store: Any) -> None:
        self._store = store

    async def get_org(self, org_id: str) -> Org | None:
        doc = await self._store.get(_ORGS, org_id)
        if not doc:
            return None
        return Org(
            org_id=org_id,
            name=str(doc["name"]),
            seat_limit=int(doc.get("seat_limit", 0)),
            created_at=str(doc.get("created_at", "")),
        )

    async def is_member_with_role(self, uid: str, org_id: str, role: str) -> bool:
        """Return whether ``uid`` holds ``role`` in ``org_id`` (ownership check)."""

        doc = await self._store.get(_ORG_MEMBERS, f"{org_id}:{uid}")
        return bool(doc) and doc.get("role") == role

    async def seat_count(self, org_id: str) -> int:
        """Count current members of an org (for seat-limit enforcement)."""

        rows, _ = await self._store.query(
            _ORG_MEMBERS, where=[("org_id", "==", org_id)], limit=100
        )
        return len(rows)

    async def create_code(self, code: VerificationCode) -> None:
        await self._store.create(
            _CODES,
            code.code_hash,
            {
                "org_id": code.org_id,
                "expires_at": code.expires_at,
                "redeemed": code.redeemed,
                "redeemed_by": code.redeemed_by,
                "created_at": code.created_at,
            },
        )

    async def get_code(self, code_hash: str) -> VerificationCode | None:
        doc = await self._store.get(_CODES, code_hash)
        if not doc:
            return None
        return VerificationCode(
            code_hash=code_hash,
            org_id=str(doc["org_id"]),
            expires_at=str(doc["expires_at"]),
            redeemed=bool(doc.get("redeemed", False)),
            redeemed_by=(str(doc["redeemed_by"]) if doc.get("redeemed_by") else None),
            created_at=str(doc.get("created_at", "")),
        )

    async def redeem_code(self, code_hash: str, uid: str) -> bool:
        """Atomically mark a code redeemed. Returns False if already redeemed.

        The transaction is the single-use guard: concurrent redemptions cannot
        both succeed.
        """

        def _apply(current: dict[str, Any] | None) -> tuple[dict[str, Any], bool]:
            if current is None:
                return {}, False
            if current.get("redeemed", False):
                return current, False
            updated = dict(current)
            updated["redeemed"] = True
            updated["redeemed_by"] = uid
            return updated, True

        return await self._store.transact_update(_CODES, code_hash, _apply)
