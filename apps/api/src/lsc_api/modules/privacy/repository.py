"""Privacy persistence: export jobs and deletion state.

Deletion is tracked with a resumable state document so an interrupted deletion
can continue where it left off (idempotent and resumable, Ley 1581).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

_EXPORT_JOBS = "export_jobs"
_DELETION_STATE = "deletion_state"


@dataclass(frozen=True)
class ExportJob:
    """Status of a data-subject export job."""

    job_id: str
    uid: str
    status: str  # "pending" | "ready" | "failed"
    object_name: str | None
    created_at: str
    ready_at: str | None


class PrivacyRepository:
    """Stores export jobs and resumable deletion state."""

    def __init__(self, store: Any) -> None:
        self._store = store

    async def create_export_job(self, job: ExportJob) -> None:
        await self._store.set(
            _EXPORT_JOBS,
            job.job_id,
            {
                "uid": job.uid,
                "status": job.status,
                "object_name": job.object_name,
                "created_at": job.created_at,
                "ready_at": job.ready_at,
            },
        )

    async def get_export_job(self, job_id: str) -> ExportJob | None:
        doc = await self._store.get(_EXPORT_JOBS, job_id)
        if not doc:
            return None
        return ExportJob(
            job_id=job_id,
            uid=str(doc["uid"]),
            status=str(doc["status"]),
            object_name=(str(doc["object_name"]) if doc.get("object_name") else None),
            created_at=str(doc.get("created_at", "")),
            ready_at=(str(doc["ready_at"]) if doc.get("ready_at") else None),
        )

    # --- Resumable deletion state. ---
    async def mark_step_done(self, uid: str, step: str) -> None:
        """Record that a deletion step completed (idempotent/resumable)."""

        def _apply(current: dict[str, Any] | None) -> tuple[dict[str, Any], None]:
            done = set((current or {}).get("done", []))
            done.add(step)
            return {"uid": uid, "done": sorted(done)}, None

        await self._store.transact_update(_DELETION_STATE, uid, _apply)

    async def step_done(self, uid: str, step: str) -> bool:
        doc = await self._store.get(_DELETION_STATE, uid)
        return bool(doc) and step in set(doc.get("done", []))
