"""Audit persistence: append entries and read the chain head.

The repository keeps the chain's head (last entry hash) in a dedicated document
updated transactionally with each append, so concurrent appends cannot fork the
chain.
"""

from __future__ import annotations

from typing import Any

from lsc_api.modules.audit.domain import GENESIS_PREV_HASH, AuditEntry

_ENTRIES = "audit_log"
_HEAD_COLLECTION = "audit_log_head"
_HEAD_DOC = "head"


class AuditRepository:
    """Stores hash-chained audit entries in the document store."""

    def __init__(self, store: Any) -> None:
        # Typed as the DocumentStore Protocol at the call site; kept loose here
        # to avoid a hard import cycle with infra.
        self._store = store

    async def append(self, entry: AuditEntry) -> None:
        """Append one entry and advance the chain head atomically.

        The head document holds ``{"hash": <last entry hash>}``. The transaction
        verifies the entry's ``prev_hash`` matches the stored head before
        advancing it, rejecting out-of-order writes.
        Failure modes: ``ConflictError`` if ``prev_hash`` does not match the
        current head; ``UpstreamError`` on store failure.
        """

        from lsc_api.core.errors import ConflictError

        def _advance(current: dict[str, Any] | None) -> tuple[dict[str, Any], None]:
            head = GENESIS_PREV_HASH if current is None else str(current["hash"])
            if entry.prev_hash != head:
                raise ConflictError("audit chain head moved; retry append")
            return {"hash": entry.entry_hash}, None

        await self._store.transact_update(_HEAD_COLLECTION, _HEAD_DOC, _advance)
        await self._store.create(
            _ENTRIES,
            entry.entry_id,
            {
                "actor": entry.actor,
                "action": entry.action,
                "target": entry.target,
                "metadata": entry.metadata,
                "at": entry.at,
                "prev_hash": entry.prev_hash,
                "entry_hash": entry.entry_hash,
            },
        )

    async def head_hash(self) -> str:
        """Return the current chain head hash, or GENESIS if the log is empty."""

        doc = await self._store.get(_HEAD_COLLECTION, _HEAD_DOC)
        return GENESIS_PREV_HASH if doc is None else str(doc["hash"])
