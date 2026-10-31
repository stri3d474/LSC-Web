"""Privacy service: data-subject export and deletion (Ley 1581 habeas data).

SECURITY(PRIV-04): deletion is idempotent and resumable (each step is recorded
and skipped if already done). It revokes sessions, deletes the Firebase user,
deletes personal documents and (by default) pseudonymous contributions, but
keeps the consent history as pseudonymized legal evidence. Every deletion is
audited.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from lsc_api.core.clock import Clock, iso_utc
from lsc_api.core.ids import new_id
from lsc_api.core.security.pseudonym import PEPPER_SECRET_NAME, contributor_id
from lsc_api.infra.jobqueue import JobQueue
from lsc_api.infra.secrets import SecretStore
from lsc_api.modules.audit.service import AuditService
from lsc_api.modules.identity.repository import IdentityRepository
from lsc_api.modules.privacy.ports import FirebaseUserAdmin
from lsc_api.modules.privacy.repository import ExportJob, PrivacyRepository

if TYPE_CHECKING:
    from lsc_api.infra.storage import BlobStore

# Personal collections removed on deletion. Consent history is intentionally
# NOT in this list (kept pseudonymized as legal proof).
_PERSONAL_COLLECTIONS = ("users", "entitlements", "consents_current", "community_verifications")


@dataclass(frozen=True)
class DeletionResult:
    """Outcome summary of a deletion run."""

    steps_completed: list[str]


class PrivacyService:
    """Implements data-subject access/export and deletion."""

    def __init__(
        self,
        repository: PrivacyRepository,
        identity_repo: IdentityRepository,
        firebase_admin: FirebaseUserAdmin,
        jobs: JobQueue,
        secrets: SecretStore,
        audit: AuditService,
        blobs: "BlobStore",
        document_store: Any,
        clock: Clock,
        *,
        exports_bucket: str,
        datasets_bucket: str,
    ) -> None:
        self._repo = repository
        self._identity = identity_repo
        self._firebase = firebase_admin
        self._jobs = jobs
        self._secrets = secrets
        self._audit = audit
        self._blobs = blobs
        self._store = document_store
        self._clock = clock
        self._exports_bucket = exports_bucket
        self._datasets_bucket = datasets_bucket

    async def request_export(self, *, uid: str) -> ExportJob:
        """Create an export job and enqueue assembly.

        The job assembles profile, consent history, session metadata and a
        purchases summary into a zip in the exports bucket; the worker fills in
        the object and marks it ready (a 24 h signed URL is minted on read).
        """

        job_id = new_id()
        job = ExportJob(
            job_id=job_id,
            uid=uid,
            status="pending",
            object_name=None,
            created_at=iso_utc(self._clock.now()),
            ready_at=None,
        )
        await self._repo.create_export_job(job)
        await self._jobs.enqueue("data_export", {"job_id": job_id, "uid": uid})
        await self._audit.record(actor=uid, action="privacy.export_request", target=job_id)
        return job

    async def get_export(self, *, uid: str, job_id: str):
        """Return the export job status (and a 24 h signed URL when ready).

        Ownership checked: a user can only read their own export job.
        Failure modes: ``NotFoundError`` if unknown; ``AuthorizationError`` if
        the job belongs to another user.
        """

        from datetime import timedelta

        from lsc_api.core.errors import AuthorizationError, NotFoundError

        job = await self._repo.get_export_job(job_id)
        if job is None:
            raise NotFoundError("export job not found")
        if job.uid != uid:
            raise AuthorizationError("not your export job")

        url: str | None = None
        if job.status == "ready" and job.object_name:
            # Export URLs may live up to 24 h (data-subject convenience); this is
            # a deliberate exception to the 10-minute model-URL cap, scoped to
            # the exports bucket and a single object.
            url = await self._blobs.signed_url(
                self._exports_bucket,
                job.object_name,
                method="GET",
                ttl=timedelta(hours=24),
            )
        return job, url

    async def delete_account(
        self, *, uid: str, keep_contributions: bool
    ) -> DeletionResult:
        """Delete the account (idempotent, resumable).

        Steps (each recorded so a retry resumes): revoke all sessions, delete
        the Firebase user, delete personal documents, optionally delete
        pseudonymous contributions. Consent history is retained pseudonymized.
        """

        completed: list[str] = []

        if not await self._repo.step_done(uid, "sessions"):
            await self._identity.revoke_all_for_user(uid)
            await self._repo.mark_step_done(uid, "sessions")
        completed.append("sessions")

        if not await self._repo.step_done(uid, "firebase"):
            await self._firebase.delete_user(uid)
            await self._repo.mark_step_done(uid, "firebase")
        completed.append("firebase")

        if not await self._repo.step_done(uid, "personal_docs"):
            for collection in _PERSONAL_COLLECTIONS:
                await self._delete_user_docs(collection, uid)
            await self._repo.mark_step_done(uid, "personal_docs")
        completed.append("personal_docs")

        if not keep_contributions and not await self._repo.step_done(uid, "contributions"):
            pepper = await self._secrets.access(PEPPER_SECRET_NAME)
            cid = contributor_id(uid, pepper)
            await self._delete_contributions(cid)
            await self._repo.mark_step_done(uid, "contributions")
        if not keep_contributions:
            completed.append("contributions")

        await self._audit.record(
            actor=uid,
            action="privacy.delete_account",
            metadata={"kept_contributions": keep_contributions},
        )
        return DeletionResult(steps_completed=completed)

    async def _delete_user_docs(self, collection: str, uid: str) -> None:
        """Delete documents in ``collection`` belonging to ``uid``.

        Handles both uid-keyed documents (users, entitlements) and
        ``uid``-prefixed index docs; a missing document is a no-op.
        """

        await self._store.delete(collection, uid)
        rows, _ = await self._store.query(
            collection, where=[("uid", "==", uid)], limit=100
        )
        for row in rows:
            doc_id = row.get("_id") or row.get("id")
            if isinstance(doc_id, str):
                await self._store.delete(collection, doc_id)

    async def _delete_contributions(self, contributor_id_value: str) -> None:
        """Delete pseudonymous contributions for a contributor id."""

        rows, _ = await self._store.query(
            "corrections",
            where=[("contributor_id", "==", contributor_id_value)],
            limit=100,
        )
        for row in rows:
            cid = row.get("correction_id")
            if isinstance(cid, str):
                await self._store.delete("corrections", cid)
