"""Model registry and distribution routes (C6). No business rules here.

SECURITY(MODEL-01..05): admin upload requires admin role + MFA and is size
capped; the key route fails closed and responds ``Cache-Control: no-store``;
signed URLs and keys never appear in logs.
"""

from __future__ import annotations

import base64
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Path, Query, Request, Response, UploadFile

from lsc_api.core.container import Container
from lsc_api.core.deps_providers import get_container
from lsc_api.core.errors import (
    NotFoundError,
    PayloadTooLargeError,
    RateLimitedError,
    ValidationError,
)
from lsc_api.modules.models.schemas import HeadInferRequest, HeadInferResponse
from lsc_api.core.ratelimit import RateLimit
from lsc_api.core.security.deps import require_auth, require_mfa, require_roles
from lsc_api.core.security.principal import Principal
from lsc_api.modules.identity.domain import ROLE_ADMIN
from lsc_api.modules.models.schemas import (
    ActivateRequest,
    DownloadResponse,
    DownloadTargetOut,
    KeyRequest,
    PackageOut,
    PackagesResponse,
)

router = APIRouter(prefix="/v1", tags=["models"])

# Admin upload cap (model packages are tens of MB; cap generously but bounded).
_MAX_PACKAGE_BYTES = 128 * 1024 * 1024
_KEY_LIMIT = RateLimit(capacity=10, refill_per_second=0.1)


async def _limit(container: Container, key: str, policy: RateLimit) -> None:
    limiter = getattr(container, "rate_limiter", None)
    if limiter is None:
        return
    decision = await limiter.consume(key, policy)
    if not decision.allowed:
        raise RateLimitedError("rate limit exceeded")


# --- Admin ---
@router.post("/admin/models", response_model=PackageOut)
async def admin_upload_model(
    request: Request,
    _admin: Annotated[Principal, Depends(require_roles(ROLE_ADMIN))],
    principal: Annotated[Principal, Depends(require_mfa)],
    container: Annotated[Container, Depends(get_container)],
    package: Annotated[UploadFile, File(description="Package zip (C2)")],
    data_key_b64: Annotated[str, Form(description="Base64 AES-256 data key")],
) -> PackageOut:
    """Receive, verify and register a model package as draft (admin + MFA)."""

    zip_bytes = await package.read(_MAX_PACKAGE_BYTES + 1)
    if len(zip_bytes) > _MAX_PACKAGE_BYTES:
        raise PayloadTooLargeError("package exceeds size limit")
    try:
        data_key = base64.b64decode(data_key_b64)
    except (ValueError, TypeError) as exc:
        raise ValidationError("data_key_b64 is not valid base64") from exc
    if len(data_key) != 32:
        raise ValidationError("data key must be 32 bytes (AES-256)")

    record = await container.model_service.register_package(
        actor_uid=principal.sub, zip_bytes=zip_bytes, data_key=data_key
    )
    return PackageOut.from_domain(record)


@router.post("/admin/models/{version}/activate", response_model=PackageOut)
async def admin_activate(
    body: ActivateRequest,
    _admin: Annotated[Principal, Depends(require_roles(ROLE_ADMIN))],
    principal: Annotated[Principal, Depends(require_mfa)],
    container: Annotated[Container, Depends(get_container)],
    version: Annotated[str, Path(min_length=1, max_length=64)],
) -> PackageOut:
    """Activate a package on a channel with a rollout percentage."""

    await container.model_service.activate(
        actor_uid=principal.sub,
        package_version=version,
        channel=body.channel,
        rollout_bp=body.rollout_bp,
        min_app_version=body.min_app_version,
    )
    return PackageOut.from_domain(await container.model_service.get_package(version))


@router.post("/admin/models/{version}/deactivate", response_model=PackageOut)
async def admin_deactivate(
    _admin: Annotated[Principal, Depends(require_roles(ROLE_ADMIN))],
    principal: Annotated[Principal, Depends(require_mfa)],
    container: Annotated[Container, Depends(get_container)],
    version: Annotated[str, Path(min_length=1, max_length=64)],
) -> PackageOut:
    """Deactivate a package."""

    await container.model_service.deactivate(
        actor_uid=principal.sub, package_version=version
    )
    return PackageOut.from_domain(await container.model_service.get_package(version))


@router.get("/admin/models", response_model=PackagesResponse)
async def admin_list(
    _admin: Annotated[Principal, Depends(require_roles(ROLE_ADMIN))],
    _mfa: Annotated[Principal, Depends(require_mfa)],
    container: Annotated[Container, Depends(get_container)],
) -> PackagesResponse:
    """List all packages."""

    records = await container.model_service.list_packages()
    return PackagesResponse(packages=[PackageOut.from_domain(r) for r in records])


# --- Distribution ---
@router.get("/models/latest")
async def models_latest(
    principal: Annotated[Principal, Depends(require_auth)],
    container: Annotated[Container, Depends(get_container)],
    app_version: Annotated[str, Query(min_length=1, max_length=64)],
    schema_version: Annotated[int, Query(ge=1)],
) -> Response:
    """Return the eligible active package's manifest bytes, unchanged (C2)."""

    manifest_bytes = await container.model_service.select_latest(
        uid=principal.sub, app_version=app_version, schema_version=schema_version
    )
    # Serve the exact stored bytes so the client verifies the original signature.
    return Response(
        content=manifest_bytes,
        media_type="application/json",
        headers={"Cache-Control": "no-store"},
    )


@router.get("/models/{version}/download", response_model=DownloadResponse)
async def models_download(
    principal: Annotated[Principal, Depends(require_auth)],
    container: Annotated[Container, Depends(get_container)],
    version: Annotated[str, Path(min_length=1, max_length=64)],
) -> DownloadResponse:
    """Return short-lived signed URLs for every blob plus an integrity nonce."""

    targets, nonce = await container.model_service.download_targets(
        uid=principal.sub, package_version=version
    )
    return DownloadResponse(
        targets=[DownloadTargetOut(name=t.name, url=t.url) for t in targets],
        integrity_nonce=nonce,
    )


@router.post("/models/{version}/key")
async def models_key(
    body: KeyRequest,
    principal: Annotated[Principal, Depends(require_auth)],
    container: Annotated[Container, Depends(get_container)],
    version: Annotated[str, Path(min_length=1, max_length=64)],
) -> Response:
    """Release the data key to a verified, entitled install. Fails closed."""

    await _limit(container, f"model_key:{principal.sub}:{version}", _KEY_LIMIT)
    await _limit(container, f"model_key_install:{body.install_id}:{version}", _KEY_LIMIT)

    key = await container.model_service.release_key(
        uid=principal.sub,
        package_version=version,
        integrity_token=body.integrity_token,
        nonce=body.nonce,
        install_id=body.install_id,
    )
    # Return the raw key base64-encoded; never cache or log it.
    return Response(
        content=base64.b64encode(key),
        media_type="application/octet-stream",
        headers={"Cache-Control": "no-store"},
    )


@router.post("/models/{version}/head:infer", response_model=HeadInferResponse)
async def models_head_infer(
    body: HeadInferRequest,
    principal: Annotated[Principal, Depends(require_auth)],
    container: Annotated[Container, Depends(get_container)],
    version: Annotated[str, Path(min_length=1, max_length=64)],
) -> HeadInferResponse:
    """Server-head inference for split models (head_mode=server).

    Available only when ``SERVER_HEAD_ENABLED`` is on and the version's head is
    loaded; otherwise returns 404. Inputs are never logged.
    """

    if not container.settings.server_head_enabled:
        raise NotFoundError("server head is not enabled")
    result = await container.model_service.head_infer(
        uid=principal.sub,
        package_version=version,
        embedding_b64=body.embedding_b64,
        top_k=body.top_k,
    )
    return HeadInferResponse(classes=result.classes, probs_bp=result.probs_bp)


__all__ = ["router"]
