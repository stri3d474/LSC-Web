"""Authentication and authorization dependencies.

SECURITY(AUTH-01): deny by default. Every route declares exactly one of these
dependencies. W01 fixes their signatures and fail-closed behavior; the token
verification body is implemented in W02 (it raises until then, so no route can
accidentally run unauthenticated).

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


async def _extract_principal(request: Request) -> Principal:
    """Verify the Bearer access token and return the principal.

    Implemented in W02 (JWT ES256 verification against the rotating keyring).
    Until then it fails closed so no protected route can run without auth.

    Failure modes: ``AuthenticationError`` (401) if the token is missing,
    malformed, expired, or signed by an unknown key.
    """

    raise AuthenticationError("token verification not yet implemented (W02)")


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
