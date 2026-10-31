"""Identity persistence: users, sessions (refresh families), org memberships.

SECURITY(AUTH-03): refresh tokens are stored only as SHA-256 hashes; install
ids are hashed too. Nothing here stores a plaintext token.
"""

from __future__ import annotations

from typing import Any

from lsc_api.modules.identity.domain import (
    RiskSignals,
    Session,
    User,
)

_USERS = "users"
_SESSIONS = "sessions"
_ORG_MEMBERS = "org_members"


class IdentityRepository:
    """Reads and writes users and refresh sessions."""

    def __init__(self, store: Any) -> None:
        self._store = store

    # --- Users. ---
    async def get_user(self, uid: str) -> User | None:
        """Return the user record or None."""

        doc = await self._store.get(_USERS, uid)
        return _to_user(uid, doc) if doc else None

    async def upsert_user(self, user: User) -> None:
        """Create or update a user with minimal fields (no email/name)."""

        await self._store.set(
            _USERS,
            user.uid,
            {
                "age_band": user.age_band,
                "roles": sorted(user.roles),
                "status": user.status,
                "created_at": user.created_at,
            },
        )

    async def roles_from_org_members(self, uid: str) -> frozenset[str]:
        """Return roles granted through organization memberships.

        Each ``org_members`` doc lists a user's role within an org. The union of
        those roles augments the roles stored on the user record.
        """

        rows, _ = await self._store.query(
            _ORG_MEMBERS, where=[("uid", "==", uid)], limit=100
        )
        roles: set[str] = set()
        for row in rows:
            role = row.get("role")
            if isinstance(role, str):
                roles.add(role)
        return frozenset(roles)

    # --- Sessions (refresh families). ---
    async def create_session(self, session: Session) -> None:
        """Persist a new refresh family."""

        await self._store.create(_SESSIONS, session.sid, _session_doc(session))

    async def get_session(self, sid: str) -> Session | None:
        """Return a session family or None."""

        doc = await self._store.get(_SESSIONS, sid)
        return _to_session(sid, doc) if doc else None

    async def rotate_session(
        self, sid: str, *, new_refresh_hash: str, last_used_at: str
    ) -> Session:
        """Atomically rotate a session's refresh hash, detecting reuse.

        The transaction advances ``refresh_hash`` and ``last_used_at``. Reuse
        detection (comparing the presented hash to the stored one) is performed
        by the service before calling this; this method assumes the caller has
        validated the presented token against the current hash inside the same
        logical step. To make rotation atomic against races, the update is done
        in a transaction keyed by ``sid``.
        Failure modes: ``ConflictError`` if the session disappeared;
        ``UpstreamError`` on store failure.
        """

        from lsc_api.core.errors import ConflictError

        def _apply(current: dict[str, Any] | None) -> tuple[dict[str, Any], Session]:
            if current is None:
                raise ConflictError("session not found")
            updated = dict(current)
            updated["refresh_hash"] = new_refresh_hash
            updated["last_used_at"] = last_used_at
            return updated, _to_session(sid, updated)

        return await self._store.transact_update(_SESSIONS, sid, _apply)

    async def revoke_session(self, sid: str) -> None:
        """Mark one session family revoked (logout or reuse detection)."""

        def _revoke(current: dict[str, Any] | None) -> tuple[dict[str, Any], None]:
            if current is None:
                return {}, None
            updated = dict(current)
            updated["revoked"] = True
            return updated, None

        await self._store.transact_update(_SESSIONS, sid, _revoke)

    async def revoke_all_for_user(self, uid: str) -> int:
        """Revoke every session family for a user; returns the count revoked."""

        rows, _ = await self._store.query(
            _SESSIONS, where=[("uid", "==", uid)], limit=100
        )
        count = 0
        for row in rows:
            sid = row.get("sid")
            if isinstance(sid, str) and not row.get("revoked", False):
                await self.revoke_session(sid)
                count += 1
        return count

    async def active_session_count(self, uid: str) -> int:
        """Count non-revoked session families for a user (for the per-user cap)."""

        rows, _ = await self._store.query(
            _SESSIONS, where=[("uid", "==", uid)], limit=100
        )
        return sum(1 for row in rows if not row.get("revoked", False))


# --- Mapping helpers. ---
def _to_user(uid: str, doc: dict[str, Any]) -> User:
    return User(
        uid=uid,
        age_band=str(doc.get("age_band", "unknown")),
        roles=frozenset(str(r) for r in doc.get("roles", [])),
        status=str(doc.get("status", "active")),
        created_at=str(doc.get("created_at", "")),
    )


def _session_doc(s: Session) -> dict[str, Any]:
    return {
        "sid": s.sid,
        "uid": s.uid,
        "refresh_hash": s.refresh_hash,
        "install_hash": s.install_hash,
        "app_version": s.app_version,
        "platform": s.platform,
        "risk": {
            "rooted": s.risk.rooted,
            "emulator": s.risk.emulator,
            "debugger": s.risk.debugger,
            "hooked": s.risk.hooked,
        },
        "created_at": s.created_at,
        "last_used_at": s.last_used_at,
        "expires_at": s.expires_at,
        "revoked": s.revoked,
    }


def _to_session(sid: str, doc: dict[str, Any]) -> Session:
    risk_raw = doc.get("risk", {}) or {}
    return Session(
        sid=sid,
        uid=str(doc["uid"]),
        refresh_hash=str(doc["refresh_hash"]),
        install_hash=str(doc.get("install_hash", "")),
        app_version=str(doc.get("app_version", "")),
        platform=str(doc.get("platform", "")),
        risk=RiskSignals(
            rooted=bool(risk_raw.get("rooted", False)),
            emulator=bool(risk_raw.get("emulator", False)),
            debugger=bool(risk_raw.get("debugger", False)),
            hooked=bool(risk_raw.get("hooked", False)),
        ),
        created_at=str(doc.get("created_at", "")),
        last_used_at=str(doc.get("last_used_at", "")),
        expires_at=str(doc.get("expires_at", "")),
        revoked=bool(doc.get("revoked", False)),
    )
