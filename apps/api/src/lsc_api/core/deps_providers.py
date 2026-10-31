"""FastAPI dependencies that expose container services to routers.

Routers depend on these functions (via ``Depends``) rather than importing
services or repositories directly, keeping the composition root in one place.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Request

if TYPE_CHECKING:
    # Type-only imports; runtime imports here would form an import cycle with
    # the module routers that import this file.
    from lsc_api.core.container import Container
    from lsc_api.core.security.tokens import TokenService
    from lsc_api.modules.audit.service import AuditService
    from lsc_api.modules.consent.service import ConsentService
    from lsc_api.modules.identity.service import IdentityService


def get_container(request: Request) -> Container:
    """Return the application container stored on ``app.state``.

    Failure modes: ``UpstreamError`` if the container is not attached (the app
    was built without infra wiring). Protected routes fail closed rather than
    proceeding without their services.
    """

    from lsc_api.core.errors import UpstreamError

    container = getattr(request.app.state, "container", None)
    if container is None:
        raise UpstreamError("service container not initialized")
    return container


def get_token_service(request: Request) -> TokenService:
    return get_container(request).token_service


def get_identity_service(request: Request) -> IdentityService:
    return get_container(request).identity_service


def get_consent_service(request: Request) -> ConsentService:
    return get_container(request).consent_service


def get_audit_service(request: Request) -> AuditService:
    return get_container(request).audit_service
