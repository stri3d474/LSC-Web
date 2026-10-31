"""Application-level rate limiting (token bucket).

Edge limits (DDoS, coarse per-IP) are handled by Cloud Armor; this limiter is
for per-account and per-install limits on sensitive endpoints (auth, key
release, corrections, links). SECURITY(RATE-01).

A ``RateLimiter`` Protocol lets the limiter be injected; a Firestore-backed
implementation applies a token bucket atomically inside a transaction.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from lsc_api.core.clock import Clock
from lsc_api.infra.firestore import DocumentStore


@dataclass(frozen=True)
class RateLimit:
    """A token-bucket policy.

    Attributes:
        capacity: maximum tokens (burst size).
        refill_per_second: tokens added per second (sustained rate).
    """

    capacity: int
    refill_per_second: float


@dataclass(frozen=True)
class RateLimitDecision:
    """Result of consuming one token."""

    allowed: bool
    remaining: int
    retry_after_seconds: float


class RateLimiter(Protocol):
    """Consumes one token from the bucket identified by ``key``."""

    async def consume(self, key: str, policy: RateLimit) -> RateLimitDecision:
        """Attempt to take one token; see implementations for semantics."""
        ...


class FirestoreTokenBucket:
    """Firestore-backed token bucket updated atomically per key.

    The bucket document stores ``tokens`` and ``updated_at_ms``. Each consume
    runs in a transaction: refill based on elapsed time, then take one token if
    available. SECURITY(RATE-01).
    """

    _COLLECTION = "rate_limits"

    def __init__(self, store: DocumentStore, clock: Clock) -> None:
        self._store = store
        self._clock = clock

    async def consume(self, key: str, policy: RateLimit) -> RateLimitDecision:
        """Take one token from ``key``'s bucket under ``policy``.

        Outputs: a ``RateLimitDecision``. ``allowed`` is False when the bucket is
        empty; ``retry_after_seconds`` estimates when one token will be free.
        Failure modes: ``UpstreamError`` if the document store transaction fails
        (callers should fail closed on sensitive endpoints).
        """

        now_ms = int(self._clock.now().timestamp() * 1000)

        def _txn(current: dict | None) -> tuple[dict, RateLimitDecision]:
            tokens = float(policy.capacity) if current is None else float(current["tokens"])
            last_ms = now_ms if current is None else int(current["updated_at_ms"])
            elapsed_s = max(0.0, (now_ms - last_ms) / 1000.0)
            tokens = min(policy.capacity, tokens + elapsed_s * policy.refill_per_second)

            if tokens >= 1.0:
                tokens -= 1.0
                decision = RateLimitDecision(True, int(tokens), 0.0)
            else:
                needed = 1.0 - tokens
                retry = needed / policy.refill_per_second if policy.refill_per_second else 60.0
                decision = RateLimitDecision(False, 0, retry)

            new_doc = {"tokens": tokens, "updated_at_ms": now_ms}
            return new_doc, decision

        return await self._store.transact_update(self._COLLECTION, key, _txn)
