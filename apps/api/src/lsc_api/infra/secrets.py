"""Secret store abstraction (Secret Manager).

SECURITY(SEC-01): secrets live only in Secret Manager and are fetched by
name/version at runtime. They are never written to Firestore, logs, or config.
"""

from __future__ import annotations

from typing import Protocol


class SecretStore(Protocol):
    """Access to versioned secrets."""

    async def access(self, name: str, version: str = "latest") -> bytes:
        """Return the raw bytes of a secret version.

        Inputs: ``name`` (e.g. ``jwt-signing-<kid>``) and ``version``.
        Outputs: the secret payload as bytes; callers decode as needed.
        Failure modes: ``NotFoundError`` if the secret/version does not exist;
        ``UpstreamError`` on access failure. Never logs the value.
        """
        ...

    async def put(self, name: str, value: bytes) -> None:
        """Create or add a version to a secret (e.g. ``model-key-<version>``).

        The value is written only to Secret Manager, never to Firestore or logs.
        Failure modes: ``UpstreamError`` on write failure.
        """
        ...
