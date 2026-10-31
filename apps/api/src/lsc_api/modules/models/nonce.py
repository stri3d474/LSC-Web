"""Server-issued single-use nonces for Play Integrity key release.

SECURITY(MODEL-04): the key-release integrity token must embed a nonce the
server issued and has not yet consumed. Nonces are high-entropy, stored as
SHA-256 with a short TTL, scoped to a (uid, version) pair, and consumed on use
so an integrity token cannot be replayed.

Issuing a nonce has no dedicated endpoint in C6; it is minted by the download
call (``GET /models/{v}/download``) and returned to the client, which forwards
it inside the integrity token it then submits to ``POST /models/{v}/key``.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import secrets
from typing import Any

from lsc_api.core.clock import Clock, iso_utc

_NONCES = "model_key_nonces"
_NONCE_TTL = dt.timedelta(minutes=5)
_NONCE_BYTES = 24  # 192 bits


def _sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class NonceStore:
    """Issues and consumes single-use integrity nonces."""

    def __init__(self, store: Any, clock: Clock) -> None:
        self._store = store
        self._clock = clock

    async def issue(self, *, uid: str, package_version: str) -> str:
        """Mint and persist a nonce bound to ``(uid, package_version)``.

        Outputs: the raw nonce (stored only as a hash). Failure modes:
        ``UpstreamError`` on store failure.
        """

        raw = secrets.token_urlsafe(_NONCE_BYTES)
        now = self._clock.now()
        await self._store.set(
            _NONCES,
            _sha256_hex(raw),
            {
                "uid": uid,
                "package_version": package_version,
                "expires_at": iso_utc(now + _NONCE_TTL),
                "consumed": False,
            },
        )
        return raw

    async def consume(self, *, uid: str, package_version: str, nonce: str) -> bool:
        """Validate and consume a nonce. Returns True only if valid and unused.

        Checks the nonce exists, is bound to the same uid and version, is not
        expired, and has not been consumed; then marks it consumed atomically.
        """

        key = _sha256_hex(nonce)
        now_iso = iso_utc(self._clock.now())

        def _apply(current: dict[str, Any] | None) -> tuple[dict[str, Any], bool]:
            if current is None:
                return {}, False
            if current.get("consumed", False):
                return current, False
            if current.get("uid") != uid or current.get("package_version") != package_version:
                return current, False
            if now_iso > str(current.get("expires_at", "")):
                return current, False
            updated = dict(current)
            updated["consumed"] = True
            return updated, True

        return await self._store.transact_update(_NONCES, key, _apply)
