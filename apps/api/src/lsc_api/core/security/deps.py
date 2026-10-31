"""Authentication and authorization dependencies.

SECURITY(AUTH-01): deny by default. Every route declares exactly one of these
dependencies. Token verification uses the container's ``TokenService`` (C5
ES256 JWT). Failures return generic problem+json; the specific reason is logged
server-side only.

- ``require_auth``   -> a verified ``Principal`` or 401.
- ``require_roles``  -> factory; 403 unless the principal holds a listed role.
- ``require_mfa``    -> 403 unless the principal's token asserts ``mfa:true``.
- ``public``         -> explicit marker that a route is intentionally public.
"""

from __future__ import annotations

from typing import Annotated, Callable

from fastapi import Depends, Request

from lsc_api.core.errors import (
    AuthenticationError,
    AuthorizationError,
    MfaRequiredError,
)
from lsc_api.core.security.principal import Principal

_BEARER_PREFIX = "Bearer "


def _bearer_token(request: Request) -> str:
    """Extract the Bearer access token from the Authorization header.

    Failure modes: ``AuthenticationError`` (401) if the header is missing or not
    a Bearer token.
    """

    header = request.headers.get("Authorization")
    if not header or not header.startswith(_BEARER_PREFIX):
        raise AuthenticationError("missing bearer token")
    token = header[len(_BEARER_PREFIX) :].strip()
    if not token:
        raise AuthenticationError("empty bearer token")
    return token


async def _extract_principal(request: Request) -> Principal:
    """Verify the Bearer access token and return the principal.

    Uses the ``TokenService`` from the app container. Fails closed if the
    container is unavailable.
    Failure modes: ``AuthenticationError`` (401) for any missing/invalid token.
    """

    # Imported here to avoid a circular import at module load time.
    from lsc_api.core.deps_providers import get_token_service

    token = _bearer_token(request)
    try:
        service = get_token_service(request)
    except Exception as exc:  # noqa: BLE001 - container/wiring unavailable
        # Fail closed as unauthenticated rather than leaking a 5xx on protected
        # routes when the token service is not available.
        raise AuthenticationError("auth not available") from exc
    return service.verify(token)


async def require_auth(request: Request) -> Principal:
    """FastAPI dependency returning the verified ``Principal`` or raising 401."""

    return await _extract_principal(request)


def require_roles(*roles: str) -> Callable[[Request], object]:
    """Build a dependency that requires at least one of ``roles``.

    The returned dependency first authenticates (401 if unauthenticated) then
    checks membership (403 if the principal holds none of ``roles``).
    """

    async def _dependency(request: Request) -> Principal:
        principal = await _extract_principal(request)
        if not principal.has_any_role(roles):
            raise AuthorizationError("missing required role")
        return principal

    return _dependency


async def require_mfa(
    principal: Annotated[Principal, Depends(require_auth)],
) -> Principal:
    """Dependency requiring the access token to assert ``mfa:true`` (403 otherwise)."""

    if not principal.mfa:
        raise MfaRequiredError("second factor required for this action")
    return principal


async def public() -> None:
    """Explicit marker dependency for intentionally public routes (no auth)."""

    return None
