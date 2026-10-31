"""Privacy module: data-subject export and deletion (W05, Ley 1581)."""

from lsc_api.modules.privacy.router import router
from lsc_api.modules.privacy.service import PrivacyService

__all__ = ["PrivacyService", "router"]
