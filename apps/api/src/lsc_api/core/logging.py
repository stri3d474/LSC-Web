"""Structured logging (structlog) with PII/secret redaction.

SECURITY(LOG-01): logs never contain PII, tokens, landmarks or message content.
A redaction processor drops or masks known-sensitive keys before rendering.
"""

from __future__ import annotations

import logging
from typing import Any

import structlog

# Keys whose values must never be emitted, regardless of level.
_REDACT_KEYS = frozenset(
    {
        "authorization",
        "access_token",
        "refresh_token",
        "id_token",
        "firebase_id_token",
        "password",
        "secret",
        "data_key",
        "cookie",
        "set-cookie",
        "email",
        "phone",
        "landmarks",
        "ciphertext",
        "message",
        "body",
    }
)
_MASK = "[redacted]"


def _redact(_logger: Any, _name: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    """Mask any key in ``_REDACT_KEYS`` (case-insensitive)."""

    for key in list(event_dict.keys()):
        if key.lower() in _REDACT_KEYS:
            event_dict[key] = _MASK
    return event_dict


def configure_logging(*, is_prod: bool) -> None:
    """Configure structlog for JSON (prod) or console (dev) output.

    Inputs: ``is_prod`` selects the renderer and minimum level.
    Outputs: none; configures the global structlog pipeline idempotently.
    """

    level = logging.INFO if is_prod else logging.DEBUG
    logging.basicConfig(format="%(message)s", level=level)

    renderer = (
        structlog.processors.JSONRenderer()
        if is_prod
        else structlog.dev.ConsoleRenderer(colors=False)
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            _redact,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a bound structlog logger."""

    return structlog.get_logger(name)
