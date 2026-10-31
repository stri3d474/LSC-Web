"""Privacy routes: data-subject export and deletion (C6, Ley 1581)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from lsc_api.core.container import Container
from lsc_api.core.deps_providers import get_container
from lsc_api.core.errors import ValidationError
from lsc_api.core.security.deps import require_auth
from lsc_api.core.security.principal import Principal
from lsc_api.modules.privacy.schemas import (
    DeleteAccountRequest,
    DeleteAccountResponse,
    ExportStatusResponse,
)

router = APIRouter(prefix="/v1", tags=["privacy"])


@router.get("/me/data-export", response_model=ExportStatusResponse)
async def data_export(
    principal: Annotated[Principal, Depends(require_auth)],
    container: Annotated[Container, Depends(get_container)],
    job_id: Annotated[str | None, Query(max_length=64)] = None,
) -> ExportStatusResponse:
    """Create an export job, or return the status/URL of an existing one.

    With no ``job_id`` a new export job is enqueued; with a ``job_id`` the
    caller's own job status (and a 24 h signed URL once ready) is returned.
    """

    if job_id is None:
        job = await container.privacy_service.request_export(uid=principal.sub)
        return ExportStatusResponse(job_id=job.job_id, status=job.status)

    job, url = await container.privacy_service.get_export(
        uid=principal.sub, job_id=job_id
    )
    return ExportStatusResponse(job_id=job.job_id, status=job.status, url=url)


@router.delete("/me", response_model=DeleteAccountResponse)
async def delete_me(
    body: DeleteAccountRequest,
    principal: Annotated[Principal, Depends(require_auth)],
    container: Annotated[Container, Depends(get_container)],
) -> DeleteAccountResponse:
    """Delete the caller's account (idempotent, resumable).

    Requires explicit confirmation. Consent history is retained pseudonymized as
    legal evidence; everything else personal is removed, and contributions are
    deleted unless the caller opts to keep them.
    """

    if not body.confirm:
        raise ValidationError("deletion requires explicit confirmation")
    result = await container.privacy_service.delete_account(
        uid=principal.sub, keep_contributions=body.keep_contributions
    )
    return DeleteAccountResponse(steps_completed=result.steps_completed)


__all__ = ["router"]
