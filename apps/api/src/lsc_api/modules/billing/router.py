"""Billing, entitlements and verification routes (C6). No business rules here.

SECURITY(RTDN-01): the internal RTDN endpoint verifies the Google OIDC token
(audience + service-account email) before processing. SECURITY(VERIFY-01):
redeem and code issuing are rate-limited and audited.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Request, Response

from lsc_api.core.container import Container
from lsc_api.core.deps_providers import get_container
from lsc_api.core.errors import AuthenticationError, RateLimitedError
from lsc_api.core.ratelimit import RateLimit
from lsc_api.core.security.deps import require_auth, require_roles
from lsc_api.core.security.principal import Principal
from lsc_api.modules.billing.schemas import (
    EntitlementResponse,
    IssueCodeResponse,
    PlayVerifyRequest,
    ProductOut,
    ProductsResponse,
    RedeemRequest,
)
from lsc_api.modules.identity.domain import ROLE_INSTITUTION_ADMIN

router = APIRouter(prefix="/v1", tags=["billing"])

_REDEEM_LIMIT = RateLimit(capacity=5, refill_per_second=0.05)
_VERIFY_LIMIT = RateLimit(capacity=20, refill_per_second=0.2)


async def _limit(container: Container, key: str, policy: RateLimit) -> None:
    limiter = getattr(container, "rate_limiter", None)
    if limiter is None:
        return
    decision = await limiter.consume(key, policy)
    if not decision.allowed:
        raise RateLimitedError("rate limit exceeded")


@router.get("/billing/products", response_model=ProductsResponse)
async def products(
    principal: Annotated[Principal, Depends(require_auth)],
    container: Annotated[Container, Depends(get_container)],
) -> ProductsResponse:
    """Return the product catalog plus the caller's Play account id."""

    account_id = await container.billing_service.account_id_for(principal.sub)
    return ProductsResponse(
        products=[ProductOut(**p) for p in container.billing_service.products()],
        account_id=account_id,
    )


@router.post("/billing/play/verify", response_model=EntitlementResponse)
async def play_verify(
    body: PlayVerifyRequest,
    principal: Annotated[Principal, Depends(require_auth)],
    container: Annotated[Container, Depends(get_container)],
) -> EntitlementResponse:
    """Verify a Play purchase for the caller and return updated entitlements."""

    await _limit(container, f"play_verify:{principal.sub}", _VERIFY_LIMIT)
    await container.billing_service.verify_purchase(
        uid=principal.sub,
        product_id=body.product_id,
        purchase_token=body.purchase_token,
    )
    entitlement = await container.entitlements_service.compute(principal.sub)
    return EntitlementResponse.from_domain(entitlement)


@router.get("/me/entitlements", response_model=EntitlementResponse)
async def my_entitlements(
    principal: Annotated[Principal, Depends(require_auth)],
    container: Annotated[Container, Depends(get_container)],
) -> EntitlementResponse:
    """Return the caller's computed entitlement (C6)."""

    entitlement = await container.entitlements_service.compute(principal.sub)
    return EntitlementResponse.from_domain(entitlement)


@router.post("/internal/play/rtdn", status_code=204)
async def play_rtdn(
    request: Request,
    container: Annotated[Container, Depends(get_container)],
) -> Response:
    """Pub/Sub push endpoint for Play RTDN. OIDC-verified; body is a trigger."""

    verifier = getattr(container, "oidc_verifier", None)
    if verifier is None:
        raise AuthenticationError("rtdn verifier unavailable")

    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise AuthenticationError("missing oidc token")
    token = auth[len("Bearer ") :]
    claims = await verifier.verify(
        token, expected_audience=container.settings.rtdn_oidc_audience
    )
    if claims.email != container.settings.rtdn_service_account_email:
        raise AuthenticationError("unexpected service account")

    body = await request.json()
    purchase_token = _extract_purchase_token(body)
    if purchase_token is None:
        # Malformed trigger: acknowledge to avoid redelivery storms, do nothing.
        return Response(status_code=204)
    await container.billing_service.process_rtdn(purchase_token=purchase_token)
    return Response(status_code=204)


@router.post(
    "/verification/redeem",
    status_code=204,
    dependencies=[Depends(require_auth)],
)
async def redeem(
    body: RedeemRequest,
    request: Request,
    principal: Annotated[Principal, Depends(require_auth)],
    container: Annotated[Container, Depends(get_container)],
) -> Response:
    """Redeem a verification code (grants verified_deaf / community)."""

    await _limit(container, f"redeem:{principal.sub}", _REDEEM_LIMIT)
    await container.verification_service.redeem(uid=principal.sub, raw_code=body.code)
    return Response(status_code=204)


@router.post(
    "/orgs/{org_id}/verification-codes",
    response_model=IssueCodeResponse,
)
async def issue_code(
    principal: Annotated[Principal, Depends(require_roles(ROLE_INSTITUTION_ADMIN))],
    container: Annotated[Container, Depends(get_container)],
    org_id: Annotated[str, Path(min_length=1, max_length=64)],
) -> IssueCodeResponse:
    """Issue a single-use verification code for an org (institution_admin)."""

    code = await container.verification_service.issue_code(
        actor_uid=principal.sub, org_id=org_id
    )
    return IssueCodeResponse(code=code)


def _extract_purchase_token(body: object) -> str | None:
    """Pull the purchase token from a Pub/Sub push envelope.

    The envelope is ``{"message": {"data": base64(json)}}`` where the inner JSON
    is a Play developer notification. Returns None if the shape is unexpected.
    """

    import base64
    import json

    if not isinstance(body, dict):
        return None
    message = body.get("message")
    if not isinstance(message, dict):
        return None
    data = message.get("data")
    if not isinstance(data, str):
        return None
    try:
        decoded = json.loads(base64.b64decode(data).decode("utf-8"))
    except (ValueError, TypeError):
        return None
    if not isinstance(decoded, dict):
        return None
    sub = decoded.get("subscriptionNotification")
    if isinstance(sub, dict):
        token = sub.get("purchaseToken")
        return token if isinstance(token, str) else None
    return None


__all__ = ["router"]
