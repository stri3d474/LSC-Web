"""Admin audit-log routes (C6). Read-only; the panel verifies the chain."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from lsc_api.core.container import Container
from lsc_api.core.deps_providers import get_container
from lsc_api.core.security.deps import require_mfa, require_roles
from lsc_api.core.security.principal import Principal
from lsc_api.modules.audit.schemas import AuditEntryOut, AuditResponse
from lsc_api.modules.identity.domain import ROLE_ADMIN

router = APIRouter(prefix="/v1", tags=["audit"])


@router.get("/admin/audit", response_model=AuditResponse)
async def list_audit(
    _role: Annotated[Principal, Depends(require_roles(ROLE_ADMIN))],
    _mfa: Annotated[Principal, Depends(require_mfa)],
    container: Annotated[Container, Depends(get_container)],
    actor: Annotated[str | None, Query(max_length=64)] = None,
    action: Annotated[str | None, Query(max_length=64)] = None,
) -> AuditResponse:
    """List audit entries (admin + MFA). The panel verifies the hash chain."""

    entries = await container.audit_service.list_entries(actor=actor, action=action)
    return AuditResponse(entries=[AuditEntryOut.from_domain(e) for e in entries])


__all__ = ["router"]
