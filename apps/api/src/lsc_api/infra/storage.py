"""Blob store abstraction (Cloud Storage with V4 signed URLs).

SECURITY(URL-01): signed URLs are short-lived (<= 10 min), scoped to a single
object, and least privilege. Buckets are private with uniform access.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Literal, Protocol

_MAX_SIGNED_URL_TTL = timedelta(minutes=10)


class BlobStore(Protocol):
    """Object storage with time-limited signed URLs."""

    async def signed_url(
        self,
        bucket: str,
        object_name: str,
        *,
        method: Literal["GET", "PUT"],
        ttl: timedelta,
    ) -> str:
        """Return a V4 signed URL for a single object.

        Failure modes: ``ValueError`` if ``ttl`` exceeds the 10-minute cap;
        ``UpstreamError`` if signing fails. Implementations must enforce the cap.
        """
        ...

    async def exists(self, bucket: str, object_name: str) -> bool:
        """Return whether an object exists."""
        ...

    async def put_bytes(self, bucket: str, object_name: str, data: bytes) -> None:
        """Upload raw bytes to a single object.

        Failure modes: ``UpstreamError`` on write failure.
        """
        ...

    async def get_bytes(self, bucket: str, object_name: str) -> bytes:
        """Download a single object's bytes (used for stored manifest bytes).

        Failure modes: ``NotFoundError`` if the object is missing;
        ``UpstreamError`` on read failure.
        """
        ...


def validate_ttl(ttl: timedelta) -> None:
    """Raise ``ValueError`` if ``ttl`` is non-positive or over the 10-minute cap."""

    if ttl <= timedelta(0):
        raise ValueError("signed URL ttl must be positive")
    if ttl > _MAX_SIGNED_URL_TTL:
        raise ValueError("signed URL ttl must not exceed 10 minutes")
