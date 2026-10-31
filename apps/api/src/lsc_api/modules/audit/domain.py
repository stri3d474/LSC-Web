"""Audit domain types and hash-chain computation (pure, no I/O).

SECURITY(AUDIT-01): entries are hash-chained. Each entry stores the previous
entry's hash and its own hash over a canonical serialization, so any tampering
with history is detectable.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

# The genesis previous-hash for the first entry in a chain.
GENESIS_PREV_HASH = "0" * 64


@dataclass(frozen=True)
class AuditEntry:
    """One immutable audit record.

    Attributes:
        entry_id: ULID of the entry.
        actor: id of the acting principal (never PII; the user id).
        action: stable action code, e.g. ``model.activate``.
        target: id of the affected object, or None.
        metadata: small, PII-free detail map.
        at: UTC ISO-8601 timestamp.
        prev_hash: hash of the previous entry (or GENESIS for the first).
        entry_hash: SHA-256 over the canonical content (see compute_hash).
    """

    entry_id: str
    actor: str
    action: str
    target: str | None
    metadata: dict[str, Any]
    at: str
    prev_hash: str
    entry_hash: str


def compute_hash(
    *,
    entry_id: str,
    actor: str,
    action: str,
    target: str | None,
    metadata: dict[str, Any],
    at: str,
    prev_hash: str,
) -> str:
    """Compute the SHA-256 chain hash for an entry.

    The input is canonical JSON (sorted keys, compact separators, UTF-8) over
    every field except ``entry_hash`` itself, which keeps the hash reproducible
    and order-independent. Failure modes: ``TypeError`` if ``metadata`` is not
    JSON-serializable.
    """

    payload = {
        "entry_id": entry_id,
        "actor": actor,
        "action": action,
        "target": target,
        "metadata": metadata,
        "at": at,
        "prev_hash": prev_hash,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
