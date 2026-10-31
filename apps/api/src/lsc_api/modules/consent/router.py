"""Consent HTTP routes (C6). Routers hold no business rules."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Path

from lsc_api.core.clock import iso_utc
from lsc_api.core.deps_providers import (
    get_consent_service,
    get_container,
    get_identity_service,
)
from lsc_api.core.security.deps import public, require_auth
from lsc_api.core.security.principal import Principal
from lsc_api.modules.consent.schemas import (
    ConsentOut,
    ConsentsResponse,
    PurposeOut,
    PurposesResponse,
    SetConsentRequest,
    to_guardian_domain,
)
from lsc_api.modules.consent.service import ConsentService
from lsc_api.modules.identity.service import IdentityService

router = APIRouter(prefix="/v1", tags=["consent"])


@router.get(
    "/consents/purposes",
    response_model=PurposesResponse,
    dependencies=[Depends(public)],
)
async def get_purposes(
    service: Annotated[ConsentService, Depends(get_consent_service)],
) -> PurposesResponse:
    """Public catalog of consent purposes with current version and Spanish text."""

    return PurposesResponse(
        purposes=[PurposeOut.from_domain(p) for p in service.purposes()]
    )


@router.get("/consents", response_model=ConsentsResponse)
async def get_consents(
    principal: Annotated[Principal, Depends(require_auth)],
    service: Annotated[ConsentService, Depends(get_consent_service)],
) -> ConsentsResponse:
    """Return the caller's latest decision per purpose."""

    records = await service.current(principal.sub)
    return ConsentsResponse(consents=[ConsentOut.from_domain(r) for r in records])


@router.put("/consents/{purpose}", response_model=ConsentOut)
async def put_consent(
    body: SetConsentRequest,
    principal: Annotated[Principal, Depends(require_auth)],
    service: Annotated[ConsentService, Depends(get_consent_service)],
    identity: Annotated[IdentityService, Depends(get_identity_service)],
    container: Annotated[object, Depends(get_container)],
    purpose: Annotated[str, Path(min_length=1, max_length=64)],
) -> ConsentOut:
    """Append a grant or revocation for ``purpose`` for the caller.

    The user's age band is read server-side from the identity store (never from
    the request), so the guardian rule cannot be bypassed by the client.
    """

    from lsc_api.core.container import Container

    assert isinstance(container, Container)
    age_band = await identity.age_band_for(principal.sub)
    guardian = to_guardian_domain(
        body.guardian_authorization, iso_utc(container.clock.now())
    )
    record = await service.set_consent(
        user_id=principal.sub,
        age_band=age_band,
        purpose_key=purpose,
        version=body.version,
        granted=body.granted,
        guardian=guardian,
    )
    return ConsentOut.from_domain(record)


__all__ = ["router"]
