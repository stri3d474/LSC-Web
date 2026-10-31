"""Billing/entitlement/verification request/response models (strict)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from lsc_api.modules.billing.domain import Entitlement


class ProductOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: str
    tier: str
    features: list[str]


class ProductsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    products: list[ProductOut]
    account_id: str = Field(
        description="HMAC account id the client attaches to Play purchases."
    )


class PlayVerifyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: str = Field(min_length=1, max_length=128)
    purchase_token: str = Field(min_length=1, max_length=4096)


class EntitlementResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tier: str
    features: list[str]
    state: str
    expires_at: str | None
    as_of: str

    @classmethod
    def from_domain(cls, e: Entitlement) -> "EntitlementResponse":
        return cls(
            tier=e.tier,
            features=list(e.features),
            state=e.state,
            expires_at=e.expires_at,
            as_of=e.as_of,
        )


class RedeemRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=8, max_length=128)


class IssueCodeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
