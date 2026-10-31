"""Identity service: Firebase exchange, sessions, refresh rotation, roles.

SECURITY(AUTH-03): refresh tokens are opaque 256-bit random values; only their
SHA-256 hash is stored, they rotate on every use, and reuse of a consumed token
revokes the whole family. SECURITY(AUTH-04): roles and tier are resolved
server-side only; the client never supplies them.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import secrets
from dataclasses import dataclass

from lsc_api.core.clock import Clock, iso_utc
from lsc_api.core.errors import AuthenticationError
from lsc_api.core.ids import new_id
from lsc_api.core.security.tokens import TokenService
from lsc_api.modules.identity.domain import (
    ROLE_USER,
    RiskSignals,
    Session,
    User,
)
from lsc_api.modules.identity.ports import (
    EntitlementsPort,
    FirebaseVerifier,
)
from lsc_api.modules.identity.repository import IdentityRepository

# Maximum concurrent refresh families per user. The oldest is revoked when the
# cap is exceeded (session cap, SECURITY(AUTH-03)).
_MAX_SESSIONS_PER_USER = 10


def _sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class IssuedSession:
    """A newly issued access + refresh pair plus the session family id."""

    access_token: str
    refresh_token: str  # returned to the caller exactly once
    sid: str
    expires_in: int


@dataclass(frozen=True)
class DeviceContext:
    """Device fields recorded on a session (C6)."""

    install_id: str
    app_version: str
    platform: str
    risk: RiskSignals


class IdentityService:
    """Exchanges Firebase identities for the app's own sessions and tokens."""

    def __init__(
        self,
        repository: IdentityRepository,
        verifier: FirebaseVerifier,
        entitlements: EntitlementsPort,
        tokens: TokenService,
        clock: Clock,
        *,
        access_ttl_seconds: int,
        refresh_ttl_seconds: int,
    ) -> None:
        self._repo = repository
        self._verifier = verifier
        self._entitlements = entitlements
        self._tokens = tokens
        self._clock = clock
        self._access_ttl = access_ttl_seconds
        self._refresh_ttl = refresh_ttl_seconds

    async def age_band_for(self, uid: str) -> "object":
        """Return the stored age band for a user (used by the consent module).

        Returns ``AgeBand.UNKNOWN`` if the user is absent, so guardian-gated
        purposes fail closed.
        """

        from lsc_api.modules.consent.domain import AgeBand

        user = await self._repo.get_user(uid)
        if user is None:
            return AgeBand.UNKNOWN
        try:
            return AgeBand(user.age_band)
        except ValueError:
            return AgeBand.UNKNOWN

    async def create_session(
        self,
        *,
        firebase_id_token: str,
        age_band: str,
        device: DeviceContext,
        now: dt.datetime | None = None,
    ) -> IssuedSession:
        """Verify a Firebase identity and open a new session.

        Steps: verify the ID token (with revocation); require a verified email
        for the email provider; upsert a minimal user; resolve roles and tier
        server-side; mint an access token (C5) and an opaque refresh token;
        persist the refresh family (hashed); enforce the per-user cap.
        Failure modes: ``AuthenticationError`` (401) if the token is invalid or
        an email provider's email is unverified; ``UpstreamError`` on backend
        failure. The returned ``refresh_token`` is shown exactly once.
        """

        moment = now or self._clock.now()
        identity = await self._verifier.verify_id_token(firebase_id_token)

        # Email provider must have a verified email; anonymous is allowed.
        if identity.provider == "password" and not identity.email_verified:
            raise AuthenticationError("email not verified")

        existing = await self._repo.get_user(identity.uid)
        created_at = existing.created_at if existing else iso_utc(moment)
        # New users get the base role only. Existing roles are preserved; roles
        # are never taken from the client or the ID token.
        base_roles = existing.roles if existing else frozenset({ROLE_USER})
        band = existing.age_band if existing else age_band

        user = User(
            uid=identity.uid,
            age_band=band,
            roles=base_roles,
            status=existing.status if existing else "active",
            created_at=created_at,
        )
        await self._repo.upsert_user(user)

        resolved_roles = base_roles | await self._repo.roles_from_org_members(identity.uid)
        tier = await self._entitlements.tier_for(identity.uid)
        mfa = identity.has_second_factor

        # Enforce the per-user session cap before adding a new family.
        if await self._repo.active_session_count(identity.uid) >= _MAX_SESSIONS_PER_USER:
            await self._repo.revoke_all_for_user(identity.uid)

        sid = new_id()
        refresh_token = secrets.token_urlsafe(32)  # 256 bits
        session = Session(
            sid=sid,
            uid=identity.uid,
            refresh_hash=_sha256_hex(refresh_token),
            install_hash=_sha256_hex(device.install_id),
            app_version=device.app_version,
            platform=device.platform,
            risk=device.risk,
            created_at=iso_utc(moment),
            last_used_at=iso_utc(moment),
            expires_at=iso_utc(moment + dt.timedelta(seconds=self._refresh_ttl)),
        )
        await self._repo.create_session(session)

        access = self._tokens.issue(
            sub=identity.uid,
            sid=sid,
            roles=resolved_roles,
            tier=tier,
            mfa=mfa,
            now=moment,
        )
        return IssuedSession(
            access_token=access,
            refresh_token=refresh_token,
            sid=sid,
            expires_in=self._access_ttl,
        )

    async def refresh(
        self,
        *,
        sid: str,
        refresh_token: str,
        now: dt.datetime | None = None,
    ) -> IssuedSession:
        """Rotate a refresh token, issuing a new access + refresh pair.

        Reuse detection: if the presented token does not match the current
        stored hash, the family is revoked and the request fails. A revoked or
        expired family also fails. On success the refresh hash rotates so the
        old token can be used exactly once.
        Failure modes: ``AuthenticationError`` (401) for unknown/revoked/expired
        families or a token mismatch (which also revokes the family).
        """

        moment = now or self._clock.now()
        session = await self._repo.get_session(sid)
        if session is None or session.revoked:
            raise AuthenticationError("invalid session")

        if iso_utc(moment) > session.expires_at:
            await self._repo.revoke_session(sid)
            raise AuthenticationError("session expired")

        presented_hash = _sha256_hex(refresh_token)
        if not secrets.compare_digest(presented_hash, session.refresh_hash):
            # Reuse of a consumed token (or a forgery): revoke the whole family.
            await self._repo.revoke_session(sid)
            raise AuthenticationError("refresh token reuse detected")

        new_refresh = secrets.token_urlsafe(32)
        await self._repo.rotate_session(
            sid,
            new_refresh_hash=_sha256_hex(new_refresh),
            last_used_at=iso_utc(moment),
        )

        user = await self._repo.get_user(session.uid)
        base_roles = user.roles if user else frozenset({ROLE_USER})
        resolved_roles = base_roles | await self._repo.roles_from_org_members(session.uid)
        tier = await self._entitlements.tier_for(session.uid)
        # MFA is asserted only at session creation (from the Firebase second
        # factor); a plain refresh does not re-assert it.
        access = self._tokens.issue(
            sub=session.uid,
            sid=sid,
            roles=resolved_roles,
            tier=tier,
            mfa=False,
            now=moment,
        )
        return IssuedSession(
            access_token=access,
            refresh_token=new_refresh,
            sid=sid,
            expires_in=self._access_ttl,
        )

    async def get_profile(self, uid: str) -> User | None:
        """Return the stored user record (non-sensitive), or None if absent."""

        return await self._repo.get_user(uid)

    async def logout(self, *, sid: str) -> None:
        """Revoke one session family."""

        await self._repo.revoke_session(sid)

    async def logout_all(self, *, uid: str) -> int:
        """Revoke every session family for a user; returns the count revoked."""

        return await self._repo.revoke_all_for_user(uid)
