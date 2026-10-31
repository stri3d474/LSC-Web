"""Application factory.

Builds the FastAPI app: strict CORS, security middleware, problem+json error
handling, versioned routers mounted under ``/v1``, JWKS at the root path, and
liveness/readiness probes. OpenAPI/docs are disabled in production.

Feature routers are added by later specs (W02+). This factory wires only the
cross-cutting surface and proves every placeholder route declares an explicit
auth dependency (deny by default).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from lsc_api.config import Settings, get_settings
from lsc_api.core.errors import (
    DomainError,
    generic_problem,
    problem_response,
)
from lsc_api.core.logging import configure_logging, get_logger
from lsc_api.core.middleware import (
    BodySizeLimitMiddleware,
    RequestContextMiddleware,
    SecurityHeadersMiddleware,
)
from lsc_api.core.security.deps import public, require_auth

_LOG = get_logger("lsc_api.main")


def _build_health_router() -> APIRouter:
    """Liveness/readiness probes. Public and free of sensitive data."""

    router = APIRouter(tags=["health"])

    @router.get("/healthz", dependencies=[Depends(public)])
    async def healthz() -> dict[str, str]:
        """Liveness: the process is up. No dependency checks."""

        return {"status": "ok"}

    @router.get("/readyz", dependencies=[Depends(public)])
    async def readyz() -> dict[str, str]:
        """Readiness: ready to serve. Dependency checks added with infra wiring."""

        return {"status": "ready"}

    return router


def _build_v1_router() -> APIRouter:
    """The ``/v1`` surface. Feature routers are included by later specs.

    The placeholder below exists so the factory demonstrates the deny-by-default
    rule: every route declares an explicit auth dependency. It is replaced by
    real module routers in W02+.
    """

    router = APIRouter(prefix="/v1")

    # Placeholder protected route: proves the auth dependency wiring. Removed
    # when the identity module (W02) mounts the real /v1/me router.
    @router.get("/me/ping", dependencies=[Depends(require_auth)], include_in_schema=False)
    async def me_ping() -> dict[str, str]:
        return {"status": "authenticated"}

    return router


def _build_jwks_router() -> APIRouter:
    """JWKS endpoint at the root path (C6). Public. Populated in W02."""

    router = APIRouter(tags=["auth"])

    @router.get("/.well-known/jwks.json", dependencies=[Depends(public)])
    async def jwks() -> dict[str, list]:
        """Published verification keys. The keyring is implemented in W02."""

        # Deliberately empty until the keyring is wired; shape matches JWKS.
        return {"keys": []}

    return router


def _register_exception_handlers(app: FastAPI) -> None:
    """Map domain errors and unexpected errors to problem+json."""

    @app.exception_handler(DomainError)
    async def _domain_handler(request: Request, exc: DomainError) -> JSONResponse:
        # Log the internal detail; never return it to the client.
        _LOG.warning("domain_error", code=exc.code, status=exc.status)
        return problem_response(request, exc)

    @app.exception_handler(Exception)
    async def _unexpected_handler(request: Request, exc: Exception) -> JSONResponse:
        _LOG.error("unhandled_error", error_type=type(exc).__name__)
        return generic_problem(request, 500, "internal_error", "Internal server error")


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the FastAPI application.

    Inputs: optional ``settings`` (defaults to ``get_settings()``, which fails
    at startup if required configuration is missing).
    Outputs: a configured ``FastAPI`` app.
    Failure modes: ``pydantic.ValidationError`` from ``get_settings`` when
    configuration is missing or invalid (fail closed, no insecure defaults).
    """

    settings = settings or get_settings()
    configure_logging(is_prod=settings.is_prod)

    app = FastAPI(
        title="LSC Interpreter API",
        version="0.1.0",
        # Disable interactive docs and the schema in production.
        docs_url=None if settings.is_prod else "/docs",
        redoc_url=None,
        openapi_url=None if settings.is_prod else "/openapi.json",
    )

    # Middleware order (outermost first): request context -> security headers
    # -> body size -> CORS.
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(SecurityHeadersMiddleware, is_prod=settings.is_prod)
    app.add_middleware(BodySizeLimitMiddleware, max_body_bytes=settings.max_body_bytes)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.allowed_origins),  # explicit allow-list
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "X-Request-Id"],
        max_age=600,
    )

    _register_exception_handlers(app)

    app.include_router(_build_health_router())
    app.include_router(_build_jwks_router())
    app.include_router(_build_v1_router())

    return app
