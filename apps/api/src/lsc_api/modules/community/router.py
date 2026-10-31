"""Community routes: vocabulary sync, corrections, reviewer workflow (C6)."""

from __future__ import annotations

import base64
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Response

from lsc_api.core.container import Container
from lsc_api.core.deps_providers import get_container
from lsc_api.core.errors import RateLimitedError, ValidationError
from lsc_api.core.ratelimit import RateLimit
from lsc_api.core.security.deps import require_auth, require_mfa, require_roles
from lsc_api.core.security.principal import Principal
from lsc_api.modules.community.domain import CorrectionInput
from lsc_api.modules.community.schemas import (
    ConceptIn,
    ConceptOut,
    CorrectionAccepted,
    CorrectionRequest,
    CorrectionsResponse,
    CorrectionOut,
    ExportUrlResponse,
    ReviewDecisionRequest,
    VocabularyResponse,
)
from lsc_api.modules.identity.domain import ROLE_ADMIN, ROLE_REVIEWER

router = APIRouter(prefix="/v1", tags=["community"])

_CORRECTION_LIMIT = RateLimit(capacity=20, refill_per_second=0.1)


async def _limit(container: Container, key: str, policy: RateLimit) -> None:
    limiter = getattr(container, "rate_limiter", None)
    if limiter is None:
        return
    decision = await limiter.consume(key, policy)
    if not decision.allowed:
        raise RateLimitedError("rate limit exceeded")


# --- Public-ish vocabulary sync (auth required). ---
@router.get("/vocabulary", response_model=VocabularyResponse)
async def vocabulary(
    principal: Annotated[Principal, Depends(require_auth)],
    container: Annotated[Container, Depends(get_container)],
    since: Annotated[int, Query(ge=0)] = 0,
) -> VocabularyResponse:
    """Return concept changes (including tombstones) since ``since``."""

    delta = await container.community_service.vocabulary_since(since)
    return VocabularyResponse(
        vocabulary_version=delta.vocabulary_version,
        concepts=[ConceptOut.from_domain(c) for c in delta.concepts],
    )


# --- Corrections (auth + consent, enforced in the service). ---
@router.post("/corrections", response_model=CorrectionAccepted)
async def submit_correction(
    body: CorrectionRequest,
    principal: Annotated[Principal, Depends(require_auth)],
    container: Annotated[Container, Depends(get_container)],
) -> CorrectionAccepted:
    """Submit a landmarks-only correction (consent verified server-side)."""

    await _limit(container, f"correction:{principal.sub}", _CORRECTION_LIMIT)

    blob: bytes | None = None
    if body.observed_sequence_f16_b64 is not None:
        try:
            blob = base64.b64decode(body.observed_sequence_f16_b64)
        except (ValueError, TypeError) as exc:
            raise ValidationError("observed_sequence_f16_b64 is not valid base64") from exc

    age_band = await container.identity_service.age_band_for(principal.sub)
    data = CorrectionInput(
        schema_version=body.schema_version,
        predicted_variant_id=body.predicted_variant_id,
        proposed_variant_id=body.proposed_variant_id,
        new_variant_proposal=(
            body.new_variant_proposal.model_dump() if body.new_variant_proposal else None
        ),
        region=body.region,
        context=body.context,
        education_level=body.education_level,
        observed_sequence=blob,
    )
    record = await container.community_service.submit_correction(
        uid=principal.sub, age_band=age_band, data=data
    )
    return CorrectionAccepted(correction_id=record.correction_id, status=record.status)


# --- Admin vocabulary CRUD. ---
@router.put("/admin/vocabulary/{concept_id}", response_model=ConceptOut)
async def admin_upsert_concept(
    body: ConceptIn,
    _role: Annotated[Principal, Depends(require_roles(ROLE_ADMIN, ROLE_REVIEWER))],
    principal: Annotated[Principal, Depends(require_mfa)],
    container: Annotated[Container, Depends(get_container)],
    concept_id: Annotated[str, Path(min_length=1, max_length=128)],
) -> ConceptOut:
    """Create or update a concept (admin/reviewer + MFA)."""

    if body.concept_id != concept_id:
        raise ValidationError("concept_id in path and body must match")
    stamped = await container.community_service.upsert_concept(
        actor_uid=principal.sub, concept=body.to_domain()
    )
    return ConceptOut.from_domain(stamped)


@router.delete("/admin/vocabulary/{concept_id}", status_code=204)
async def admin_delete_concept(
    _role: Annotated[Principal, Depends(require_roles(ROLE_ADMIN, ROLE_REVIEWER))],
    principal: Annotated[Principal, Depends(require_mfa)],
    container: Annotated[Container, Depends(get_container)],
    concept_id: Annotated[str, Path(min_length=1, max_length=128)],
) -> Response:
    """Tombstone a concept (admin/reviewer + MFA)."""

    await container.community_service.delete_concept(
        actor_uid=principal.sub, concept_id=concept_id
    )
    return Response(status_code=204)


# --- Reviewer workflow. ---
@router.get("/admin/corrections", response_model=CorrectionsResponse)
async def admin_list_corrections(
    _role: Annotated[Principal, Depends(require_roles(ROLE_ADMIN, ROLE_REVIEWER))],
    _mfa: Annotated[Principal, Depends(require_mfa)],
    container: Annotated[Container, Depends(get_container)],
    status: Annotated[str, Query(pattern="^(pending|approved|rejected|merged)$")] = "pending",
) -> CorrectionsResponse:
    """List corrections by status (admin/reviewer + MFA)."""

    records = await container.review_service.list_by_status(status)
    return CorrectionsResponse(
        corrections=[CorrectionOut.from_domain(r) for r in records]
    )


@router.post("/admin/corrections/{correction_id}/review", status_code=204)
async def admin_review_correction(
    body: ReviewDecisionRequest,
    _role: Annotated[Principal, Depends(require_roles(ROLE_ADMIN, ROLE_REVIEWER))],
    principal: Annotated[Principal, Depends(require_mfa)],
    container: Annotated[Container, Depends(get_container)],
    correction_id: Annotated[str, Path(min_length=1, max_length=64)],
) -> Response:
    """Approve or reject a pending correction (admin/reviewer + MFA)."""

    await container.review_service.decide(
        actor_uid=principal.sub,
        correction_id=correction_id,
        approve=body.approve,
        reason=body.reason,
    )
    return Response(status_code=204)


@router.post("/admin/corrections/export", response_model=ExportUrlResponse)
async def admin_export_corrections(
    _role: Annotated[Principal, Depends(require_roles(ROLE_ADMIN, ROLE_REVIEWER))],
    principal: Annotated[Principal, Depends(require_mfa)],
    container: Annotated[Container, Depends(get_container)],
) -> ExportUrlResponse:
    """Export approved corrections as JSONL and return a signed URL."""

    url = await container.review_service.export_approved(actor_uid=principal.sub)
    return ExportUrlResponse(url=url)


__all__ = ["router"]
