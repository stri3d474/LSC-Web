"""Ports the privacy module depends on."""

from __future__ import annotations

from typing import Protocol


class FirebaseUserAdmin(Protocol):
    """Administrative operations on Firebase user accounts."""

    async def delete_user(self, uid: str) -> None:
        """Delete a Firebase user. Idempotent: a missing user is a no-op.

        Failure modes: ``UpstreamError`` on backend failure (so deletion can be
        retried/resumed).
        """
        ...
