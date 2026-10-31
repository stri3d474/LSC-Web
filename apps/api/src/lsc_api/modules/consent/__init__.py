"""Consent module: versioned, revocable consent purposes and history (C8)."""

from lsc_api.modules.consent.router import router
from lsc_api.modules.consent.service import ConsentService

__all__ = ["ConsentService", "router"]
