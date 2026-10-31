"""Audit service: record administrative and security-relevant actions.

Other modules depend on this service (never the repository). Entries carry no
PII, tokens, landmarks or message content (SECURITY(LOG-01)/AUDIT-01).
"""

from __future__ import annotations

from typing import Any

from lsc_api.core.clock import Clock, iso_utc
from lsc_api.core.ids import new_id
from lsc_api.modules.audit.domain import AuditEntry, compute_hash
from lsc_api.modules.audit.repository import AuditRepository


class AuditService:
    """Creates hash-chained audit entries."""

    def __init__(self, repository: AuditRepository, clock: Clock) -> None:
        self._repo = repository
        self._clock = clock

    async def record(
        self,
        *,
        actor: str,
        action: str,
        target: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AuditEntry:
        """Append one audit entry chained to the current head.

        Inputs: ``actor`` (acting user id), ``action`` (stable code), optional
        ``target`` id and PII-free ``metadata``.
        Outputs: the created ``AuditEntry``.
        Failure modes: ``ConflictError`` if a concurrent append advanced the
        head (callers may retry); ``UpstreamError`` on store failure. Callers
        must not place PII or secrets in ``metadata``.
        """

        prev_hash = await self._repo.head_hash()
        entry_id = new_id()
        at = iso_utc(self._clock.now())
        meta = metadata or {}
        entry_hash = compute_hash(
            entry_id=entry_id,
            actor=actor,
            action=action,
            target=target,
            metadata=meta,
            at=at,
            prev_hash=prev_hash,
        )
        entry = AuditEntry(
            entry_id=entry_id,
            actor=actor,
            action=action,
            target=target,
            metadata=meta,
            at=at,
            prev_hash=prev_hash,
            entry_hash=entry_hash,
        )
        await self._repo.append(entry)
        return entry

    async def list_entries(
        self, *, actor: str | None = None, action: str | None = None
    ) -> list[AuditEntry]:
        """List audit entries for the admin panel (hash chain verified client-side)."""

        return await self._repo.list_entries(actor=actor, action=action)
