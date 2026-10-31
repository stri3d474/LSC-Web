"""Reviewer workflow for community corrections.

Approve/reject with a reason and bulk-export approved items as JSONL matching
the training repo's importer schema, delivered via a short-lived signed URL.
Every reviewer action is audited.
"""

from __future__ import annotations

import json
from datetime import timedelta

from lsc_api.core.clock import Clock, iso_utc
from lsc_api.core.errors import NotFoundError, ValidationError
from lsc_api.core.ids import new_id
from lsc_api.infra.storage import BlobStore, validate_ttl
from lsc_api.modules.audit.service import AuditService
from lsc_api.modules.community.domain import (
    CORRECTION_APPROVED,
    CORRECTION_PENDING,
    CORRECTION_REJECTED,
    CorrectionRecord,
)
from lsc_api.modules.community.repository import CommunityRepository

_EXPORT_TTL = timedelta(hours=1)


class ReviewService:
    """Reviewer actions over community corrections."""

    def __init__(
        self,
        repository: CommunityRepository,
        blobs: BlobStore,
        audit: AuditService,
        clock: Clock,
        *,
        exports_bucket: str,
    ) -> None:
        self._repo = repository
        self._blobs = blobs
        self._audit = audit
        self._clock = clock
        self._bucket = exports_bucket

    async def list_by_status(self, status: str) -> list[CorrectionRecord]:
        """List corrections in a given status (pending/approved/rejected/merged)."""

        return await self._repo.list_corrections(status)

    async def decide(
        self, *, actor_uid: str, correction_id: str, approve: bool, reason: str | None
    ) -> None:
        """Approve or reject a pending correction with a reason.

        Failure modes: ``NotFoundError`` if unknown; ``ValidationError`` if the
        correction is not pending.
        """

        record = await self._repo.get_correction(correction_id)
        if record is None:
            raise NotFoundError("correction not found")
        if record.status != CORRECTION_PENDING:
            raise ValidationError("only pending corrections can be decided")

        status = CORRECTION_APPROVED if approve else CORRECTION_REJECTED
        await self._repo.set_correction_status(
            correction_id,
            status=status,
            reason=reason,
            reviewed_at=iso_utc(self._clock.now()),
        )
        await self._audit.record(
            actor=actor_uid,
            action="correction.review",
            target=correction_id,
            metadata={"status": status},
        )

    async def export_approved(self, *, actor_uid: str) -> str:
        """Export approved corrections as JSONL and return a signed URL.

        Each line matches the training repo's importer schema: the pseudonymous
        contributor id, variant ids, tags and the blob object path (the training
        pipeline reads the blob from the datasets bucket). No uid is included.
        Failure modes: ``UpstreamError`` on storage failure.
        """

        approved = await self._repo.list_corrections(CORRECTION_APPROVED)
        lines = [
            json.dumps(
                {
                    "correction_id": r.correction_id,
                    "contributor_id": r.contributor_id,
                    "schema_version": r.schema_version,
                    "predicted_variant_id": r.predicted_variant_id,
                    "proposed_variant_id": r.proposed_variant_id,
                    "new_variant_proposal": r.new_variant_proposal,
                    "region": r.region,
                    "context": r.context,
                    "education_level": r.education_level,
                    "blob_object": r.blob_object,
                },
                ensure_ascii=False,
                separators=(",", ":"),
            )
            for r in approved
        ]
        payload = ("\n".join(lines) + ("\n" if lines else "")).encode("utf-8")
        object_name = f"corrections-export/{new_id()}.jsonl"
        await self._blobs.put_bytes(self._bucket, object_name, payload)

        validate_ttl(_EXPORT_TTL)
        url = await self._blobs.signed_url(
            self._bucket, object_name, method="GET", ttl=_EXPORT_TTL
        )
        await self._audit.record(
            actor=actor_uid,
            action="correction.export",
            metadata={"count": len(approved)},
        )
        return url
