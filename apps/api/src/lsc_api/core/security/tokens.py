"""Access-token issuing and verification (ES256 JWT, C5).

SECURITY(AUTH-02): claims are exactly those in C5: iss, aud, sub, sid, iat,
exp, kid (header), roles[], tier, mfa. The 15-minute lifetime is enforced here
and validated on every request.
"""

from __future__ import annotations

import datetime as dt

import jwt

from lsc_api.core.errors import AuthenticationError
from lsc_api.core.security.keyring import KeyRing
from lsc_api.core.security.principal import Principal

_ALG = "ES256"


class TokenService:
    """Issues and verifies short-lived access tokens."""

    def __init__(
        self,
        keyring: KeyRing,
        *,
        issuer: str,
        audience: str,
        ttl_seconds: int,
    ) -> None:
        self._keyring = keyring
        self._issuer = issuer
        self._audience = audience
        self._ttl = ttl_seconds

    def issue(
        self,
        *,
        sub: str,
        sid: str,
        roles: frozenset[str],
        tier: str,
        mfa: bool,
        now: dt.datetime,
    ) -> str:
        """Sign a new access token.

        Inputs: subject (user id), session family id, authoritative roles/tier
        (never client-supplied), the MFA flag, and the current time.
        Outputs: a compact JWS string.
        Failure modes: none under normal operation; signing errors propagate.
        """

        key = self._keyring.signing_key
        issued = int(now.timestamp())
        claims = {
            "iss": self._issuer,
            "aud": self._audience,
            "sub": sub,
            "sid": sid,
            "iat": issued,
            "exp": issued + self._ttl,
            "roles": sorted(roles),
            "tier": tier,
            "mfa": mfa,
        }
        return jwt.encode(claims, key.private_key, algorithm=_ALG, headers={"kid": key.kid})

    def verify(self, token: str) -> Principal:
        """Verify a token and return the authenticated principal.

        Validates signature (against the kid in the header, which must be an
        active key), issuer, audience and expiry.
        Failure modes: ``AuthenticationError`` (401) if the header is malformed,
        the kid is unknown, the signature is invalid, or any claim check fails.
        The specific reason is for server logs only.
        """

        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError as exc:
            raise AuthenticationError("malformed token header") from exc

        kid = header.get("kid")
        if not isinstance(kid, str):
            raise AuthenticationError("missing kid")
        key = self._keyring.verification_key(kid)
        if key is None:
            raise AuthenticationError("unknown signing key")

        try:
            claims = jwt.decode(
                token,
                key.private_key.public_key(),
                algorithms=[_ALG],
                issuer=self._issuer,
                audience=self._audience,
                options={"require": ["iss", "aud", "sub", "sid", "iat", "exp"]},
            )
        except jwt.PyJWTError as exc:
            raise AuthenticationError("token verification failed") from exc

        roles = claims.get("roles", [])
        if not isinstance(roles, list):
            raise AuthenticationError("invalid roles claim")

        return Principal(
            sub=str(claims["sub"]),
            sid=str(claims["sid"]),
            roles=frozenset(str(r) for r in roles),
            tier=str(claims.get("tier", "free")),
            mfa=bool(claims.get("mfa", False)),
        )
