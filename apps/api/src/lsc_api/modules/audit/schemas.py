"""Audit response models (strict)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from lsc_api.modules.audit.domain import AuditEntry


class AuditEntryOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entry_id: str
    actor: str
    action: str
    target: str | None
    metadata: dict[str, Any]
    at: str
    prev_hash: str
    entry_hash: str

    @classmethod
    def from_domain(cls, e: AuditEntry) -> "AuditEntryOut":
        return cls(
            entry_id=e.entry_id,
            actor=e.actor,
            action=e.action,
            target=e.target,
            metadata=e.metadata,
            at=e.at,
            prev_hash=e.prev_hash,
            entry_hash=e.entry_hash,
        )


class AuditResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entries: list[AuditEntryOut]
