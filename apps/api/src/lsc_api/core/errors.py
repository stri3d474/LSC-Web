"""Domain exception hierarchy mapped to RFC 9457 problem+json.

SECURITY(ERR-01): responses carry a stable machine-readable ``code`` and a
generic human message. They never expose stack traces, internal ids, or which
layer failed (steering: security.md output rules).
"""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse

PROBLEM_CONTENT_TYPE = "application/problem+json"


class DomainError(Exception):
    """Base class for all expected (mapped) application errors.

    Attributes:
        status: HTTP status code.
        code: stable, documented error code clients can switch on.
        title: short, generic human-readable title (no internals).
    """

    status: int = 500
    code: str = "internal_error"
    title: str = "Internal server error"

    def __init__(self, detail: str | None = None) -> None:
        super().__init__(detail or self.title)
        # ``detail`` is for server logs only; it is NOT placed in the response.
        self.detail = detail


class ValidationError(DomainError):
    status = 400
    code = "validation_error"
    title = "The request was invalid"


class AuthenticationError(DomainError):
    status = 401
    code = "unauthenticated"
    title = "Authentication is required"


class AuthorizationError(DomainError):
    status = 403
    code = "forbidden"
    title = "You do not have access to this resource"


class MfaRequiredError(DomainError):
    status = 403
    code = "mfa_required"
    title = "Multi-factor authentication is required"


class NotFoundError(DomainError):
    status = 404
    code = "not_found"
    title = "The resource was not found"


class ConflictError(DomainError):
    status = 409
    code = "conflict"
    title = "The request conflicts with the current state"


class PayloadTooLargeError(DomainError):
    status = 413
    code = "payload_too_large"
    title = "The request body is too large"


class RateLimitedError(DomainError):
    status = 429
    code = "rate_limited"
    title = "Too many requests"


class IntegrityCheckError(DomainError):
    status = 403
    code = "integrity_failed"
    title = "App integrity verification failed"


class UpstreamError(DomainError):
    status = 502
    code = "upstream_error"
    title = "A dependency is unavailable"


def problem_response(request: Request, error: DomainError) -> JSONResponse:
    """Render a ``DomainError`` as an RFC 9457 problem+json response.

    The body contains only ``type``, ``title``, ``status``, ``code`` and the
    request ``instance``. No detail, stack trace or internal id is included.
    """

    body = {
        "type": f"about:blank#{error.code}",
        "title": error.title,
        "status": error.status,
        "code": error.code,
        "instance": getattr(request.state, "request_id", None),
    }
    return JSONResponse(
        status_code=error.status,
        content=body,
        media_type=PROBLEM_CONTENT_TYPE,
    )


def generic_problem(request: Request, status: int, code: str, title: str) -> JSONResponse:
    """Build a problem+json for errors raised outside the DomainError hierarchy."""

    body = {
        "type": f"about:blank#{code}",
        "title": title,
        "status": status,
        "code": code,
        "instance": getattr(request.state, "request_id", None),
    }
    return JSONResponse(status_code=status, content=body, media_type=PROBLEM_CONTENT_TYPE)
