"""Community module: vocabulary and consented corrections (W05)."""

from lsc_api.modules.community.review_service import ReviewService
from lsc_api.modules.community.router import router
from lsc_api.modules.community.service import CommunityService

__all__ = ["CommunityService", "ReviewService", "router"]
