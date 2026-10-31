"""Model registry request/response models (strict)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from lsc_api.modules.models.domain import PackageRecord


class ActivateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    channel: Literal["stable", "beta"]
    rollout_bp: int = Field(ge=0, le=10_000)
    min_app_version: str | None = None


class PackageOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    package_version: str
    profile: str
    schema_version: int
    min_app_version: str
    head_mode: str
    status: str
    channel: str | None
    rollout_bp: int
    created_at: str
    activated_at: str | None

    @classmethod
    def from_domain(cls, r: PackageRecord) -> "PackageOut":
        return cls(
            package_version=r.package_version,
            profile=r.profile,
            schema_version=r.schema_version,
            min_app_version=r.min_app_version,
            head_mode=r.head_mode,
            status=r.status,
            channel=r.channel,
            rollout_bp=r.rollout_bp,
            created_at=r.created_at,
            activated_at=r.activated_at,
        )


class PackagesResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    packages: list[PackageOut]


class DownloadTargetOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    url: str


class DownloadResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    targets: list[DownloadTargetOut]
    integrity_nonce: str = Field(
        description="Embed this nonce in the Play Integrity token sent to /key."
    )


class KeyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    integrity_token: str = Field(min_length=1, max_length=16384)
    nonce: str = Field(min_length=1, max_length=256)
    install_id: str = Field(min_length=1, max_length=256)


class HeadInferRequest(BaseModel):
    """Optional server-head inference (SERVER_HEAD_ENABLED)."""

    model_config = ConfigDict(extra="forbid")

    embedding_b64: str = Field(min_length=1, max_length=65536)
    top_k: int = Field(default=3, ge=1, le=20)


class HeadInferResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Probabilities are returned as integer basis points (no floats on the wire,
    # consistent with the C2 no-floats convention for model metadata).
    classes: list[int]
    probs_bp: list[int]
