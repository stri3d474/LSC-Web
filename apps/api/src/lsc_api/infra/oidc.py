"""Google-signed OIDC token verification for Pub/Sub push endpoints.

SECURITY(RTDN-01): the Play RTDN push endpoint accepts a request only if it
carries a valid Google-signed OIDC token whose audience and service-account
email match the configured values. The notification body is never trusted as a
source of truth; it is only a trigger to re-query Play.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class OidcClaims:
    """Verified claims from a Google OIDC token."""

    email: str
    audience: str


class OidcVerifier(Protocol):
    """Verifies a Google-signed OIDC bearer token."""

    async def verify(self, token: str, *, expected_audience: str) -> OidcClaims:
        """Verify ``token`` against Google's public keys and the audience.

        Failure modes: ``AuthenticationError`` (401) if the signature, audience,
        issuer or expiry is invalid; ``UpstreamError`` if Google's keys cannot
        be fetched.
        """
        ...
