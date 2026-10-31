"""Ports (Protocols) the identity service depends on.

Injected so the Firebase verifier and the entitlements source can be swapped.
Concrete implementations: Firebase Admin SDK (verifier) and the billing module
(entitlements, from W03). Until W03, a default port returns the free tier.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class FirebaseIdentity:
    """Result of verifying a Firebase ID token.

    Attributes:
        uid: the Firebase user id (used as the app ``uid``).
        provider: sign-in provider (e.g. ``password``, ``google.com``,
            ``anonymous``).
        email_verified: whether the email is verified (required for the email
            provider).
        is_anonymous: whether this is an anonymous sign-in.
        has_second_factor: whether the token asserts a verified second factor
            (drives the ``mfa`` claim).
    """

    uid: str
    provider: str
    email_verified: bool
    is_anonymous: bool
    has_second_factor: bool


class FirebaseVerifier(Protocol):
    """Verifies Firebase ID tokens with revocation checking."""

    async def verify_id_token(self, id_token: str) -> FirebaseIdentity:
        """Verify ``id_token`` (checking revocation) and return its identity.

        Failure modes: ``AuthenticationError`` (401) if the token is invalid,
        expired, or revoked; ``UpstreamError`` if the Firebase service is
        unreachable.
        """
        ...


class EntitlementsPort(Protocol):
    """Resolves the server-authoritative tier for a user."""

    async def tier_for(self, uid: str) -> str:
        """Return the current tier for ``uid`` (``free`` by default).

        The client never influences this. Implemented by the billing module in
        W03; a default returns ``free``.
        """
        ...


class DefaultFreeEntitlements:
    """Default entitlements port: everyone is ``free`` until W03 wires billing."""

    async def tier_for(self, uid: str) -> str:  # noqa: ARG002 - uid unused by design
        return "free"
