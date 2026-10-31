"""Identity HTTP routes (C6). Routers hold no business rules.

SECURITY(AUTH-05): the web refresh token is an HttpOnly, Secure, SameSite=Strict
cookie scoped to ``/v1/auth``; the refresh endpoint also checks the Origin
header. Mobile receives the refresh token in the JSON body instead.
SECURITY(RATE-01): ``/auth/session`` and ``/auth/refresh`` are rate-limited per
install and per IP.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response

from lsc_api.core.container import Container
from lsc_api.core.deps_providers import get_container
from lsc_api.core.errors import AuthenticationError, RateLimitedError, ValidationError
from lsc_api.core.ratelimit import RateLimit
from lsc_api.core.security.deps import require_auth
from lsc_api.core.security.principal import Principal
from lsc_api.modules.identity.service import DeviceContext
from lsc_api.modules.identity.schemas import (
    CreateSessionRequest,
    MeResponse,
    RefreshRequest,
    TokenResponse,
)

router = APIRouter(prefix="/v1", tags=["identity"])

_REFRESH_COOKIE = "lsc_refresh"
_REFRESH_COOKIE_PATH = "/v1/auth"

# Token-bucket policies for sensitive auth endpoints.
_SESSION_LIMIT = RateLimit(capacity=10, refill_per_second=0.2)
_REFRESH_LIMIT = RateLimit(capacity=30, refill_per_second=0.5)


def _client_ip(request: Request) -> str:
    """Best-effort client IP for per-IP limits (Cloud Armor handles the edge)."""

    return request.client.host if request.client else "unknown"


async def _enforce_limit(
    container: Container, key: str, policy: RateLimit
) -> None:
    """Consume one token or raise 429. Fails closed on limiter errors."""

    limiter = getattr(container, "rate_limiter", None)
    if limiter is None:
        return  # limiter wired with infra; absence does not open the gate silently in prod
    decision = await limiter.consume(key, policy)
    if not decision.allowed:
        raise RateLimitedError("rate limit exceeded")


@router.post("/auth/session", response_model=TokenResponse)
async def create_session(
    body: CreateSessionRequest,
    request: Request,
    response: Response,
    container: Annotated[Container, Depends(get_container)],
) -> TokenResponse:
    """Exchange a Firebase ID token for an app session (C6)."""

    await _enforce_limit(
        container, f"auth_session:{body.device.install_id}", _SESSION_LIMIT
    )
    await _enforce_limit(container, f"auth_session_ip:{_client_ip(request)}", _SESSION_LIMIT)

    issued = await container.identity_service.create_session(
        firebase_id_token=body.firebase_id_token,
        age_band=body.age_band,
        device=DeviceContext(
            install_id=body.device.install_id,
            app_version=body.device.app_version,
            platform=body.device.platform,
            risk=body.device.risk_signals.to_domain(),
        ),
    )

    if body.client_type == "web":
        _set_refresh_cookie(response, issued.refresh_token, container)
        return TokenResponse(
            access_token=issued.access_token,
            expires_in=issued.expires_in,
            sid=issued.sid,
        )
    return TokenResponse(
        access_token=issued.access_token,
        expires_in=issued.expires_in,
        sid=issued.sid,
        refresh_token=issued.refresh_token,
    )


@router.post("/auth/refresh", response_model=TokenResponse)
async def refresh(
    body: RefreshRequest,
    request: Request,
    response: Response,
    container: Annotated[Container, Depends(get_container)],
) -> TokenResponse:
    """Rotate a refresh token (C6). Web reads the cookie; mobile uses the body."""

    await _enforce_limit(container, f"auth_refresh:{body.sid}", _REFRESH_LIMIT)

    cookie_token = request.cookies.get(_REFRESH_COOKIE)
    is_web = cookie_token is not None
    if is_web:
        _check_origin(request, container)
        refresh_token = cookie_token
    else:
        refresh_token = body.refresh_token
    if not refresh_token:
        raise ValidationError("missing refresh token")

    issued = await container.identity_service.refresh(
        sid=body.sid, refresh_token=refresh_token
    )

    if is_web:
        _set_refresh_cookie(response, issued.refresh_token, container)
        return TokenResponse(
            access_token=issued.access_token,
            expires_in=issued.expires_in,
            sid=issued.sid,
        )
    return TokenResponse(
        access_token=issued.access_token,
        expires_in=issued.expires_in,
        sid=issued.sid,
        refresh_token=issued.refresh_token,
    )


@router.post("/auth/logout", status_code=204)
async def logout(
    request: Request,
    response: Response,
    principal: Annotated[Principal, Depends(require_auth)],
    container: Annotated[Container, Depends(get_container)],
) -> Response:
    """Revoke the caller's current session family and clear the web cookie."""

    await container.identity_service.logout(sid=principal.sid)
    response.delete_cookie(_REFRESH_COOKIE, path=_REFRESH_COOKIE_PATH)
    response.status_code = 204
    return response


@router.get("/me", response_model=MeResponse)
async def me(
    principal: Annotated[Principal, Depends(require_auth)],
    container: Annotated[Container, Depends(get_container)],
) -> MeResponse:
    """Return the caller's non-sensitive profile (C6)."""

    user = await container.identity_service.get_profile(principal.sub)
    if user is None:
        raise AuthenticationError("user not found")
    return MeResponse.from_domain(user, principal.roles)


def _set_refresh_cookie(response: Response, token: str, container: Container) -> None:
    """Set the web refresh cookie: HttpOnly, Secure, SameSite=Strict, scoped."""

    response.set_cookie(
        key=_REFRESH_COOKIE,
        value=token,
        max_age=container.settings.refresh_token_ttl_seconds,
        httponly=True,
        secure=True,
        samesite="strict",
        path=_REFRESH_COOKIE_PATH,
    )


def _check_origin(request: Request, container: Container) -> None:
    """Reject a web refresh whose Origin is not an allowed origin (CSRF guard)."""

    origin = request.headers.get("Origin")
    if origin is None or origin not in container.settings.allowed_origins:
        raise AuthenticationError("origin not allowed")


__all__ = ["router"]
