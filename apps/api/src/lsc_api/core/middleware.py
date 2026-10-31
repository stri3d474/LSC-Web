"""HTTP middleware: request id, security headers, body-size limit, access log.

SECURITY(HDR-01): security headers on every response.
SECURITY(SIZE-01): request bodies are bounded.
SECURITY(LOG-01): the access log carries no PII, tokens or bodies.
Strict CORS (allow-list, no wildcard) is configured on the app in main.py.
"""

from __future__ import annotations

import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from lsc_api.core.errors import PayloadTooLargeError, generic_problem
from lsc_api.core.ids import new_id
from lsc_api.core.logging import get_logger

_LOG = get_logger("lsc_api.access")

# Applied to every response. HSTS is set only when served over TLS in prod.
_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "X-Frame-Options": "DENY",
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
    "Cache-Control": "no-store",
}


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Assign a request id and emit a PII-free access log line."""

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        request_id = request.headers.get("X-Request-Id") or new_id()
        request.state.request_id = request_id
        start = time.perf_counter()

        response = await call_next(request)

        duration_ms = round((time.perf_counter() - start) * 1000, 1)
        # Log method, path template, status and timing only. No query string,
        # no headers, no body.
        _LOG.info(
            "request",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=duration_ms,
        )
        response.headers["X-Request-Id"] = request_id
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Attach static security headers to every response."""

    def __init__(self, app: ASGIApp, *, is_prod: bool) -> None:
        super().__init__(app)
        self._is_prod = is_prod

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        response: Response = await call_next(request)
        for key, value in _SECURITY_HEADERS.items():
            response.headers.setdefault(key, value)
        if self._is_prod:
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=63072000; includeSubDomains; preload",
            )
        return response


class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    """Reject requests whose body exceeds ``max_body_bytes``.

    Checks the Content-Length header; streaming bodies without a length are
    also bounded by Starlette's receive buffer, but the explicit header check
    rejects oversized declared payloads early with problem+json.
    """

    def __init__(self, app: ASGIApp, *, max_body_bytes: int) -> None:
        super().__init__(app)
        self._max = max_body_bytes

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        content_length = request.headers.get("Content-Length")
        if content_length is not None:
            try:
                declared = int(content_length)
            except ValueError:
                declared = -1
            if declared > self._max:
                return generic_problem(
                    request,
                    PayloadTooLargeError.status,
                    PayloadTooLargeError.code,
                    PayloadTooLargeError.title,
                )
        return await call_next(request)
