"""Identity module: Firebase exchange, sessions, roles, MFA (C5)."""

from lsc_api.modules.identity.router import router
from lsc_api.modules.identity.service import IdentityService

__all__ = ["IdentityService", "router"]
