"""Consent request/response models. Strict (extra=forbid), no raw dicts."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from lsc_api.modules.consent.domain import (
    ConsentPurpose,
    ConsentRecord,
    GuardianAuthorization,
)


class PurposeOut(BaseModel):
    """A purpose exposed publicly with its current version and Spanish text."""

    model_config = ConfigDict(extra="forbid")

    key: str
    version: int
    requires_guardian_for_minor: bool
    text_es: str

    @classmethod
    def from_domain(cls, p: ConsentPurpose) -> "PurposeOut":
        return cls(
            key=p.key,
            version=p.version,
            requires_guardian_for_minor=p.requires_guardian_for_minor,
            text_es=p.text_es,
        )


class PurposesResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    purposes: list[PurposeOut]


class GuardianAuthorizationIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    relationship: str = Field(min_length=1, max_length=100)


class SetConsentRequest(BaseModel):
    """Body for PUT /consents/{purpose}."""

    model_config = ConfigDict(extra="forbid")

    version: int = Field(ge=1)
    granted: bool
    guardian_authorization: GuardianAuthorizationIn | None = None


class ConsentOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    purpose: str
    version: int
    granted: bool
    at: str

    @classmethod
    def from_domain(cls, r: ConsentRecord) -> "ConsentOut":
        return cls(purpose=r.purpose, version=r.version, granted=r.granted, at=r.at)


class ConsentsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    consents: list[ConsentOut]


def to_guardian_domain(
    model: GuardianAuthorizationIn | None, confirmed_at: str
) -> GuardianAuthorization | None:
    """Convert the request guardian model to the domain type with a timestamp."""

    if model is None:
        return None
    return GuardianAuthorization(
        name=model.name, relationship=model.relationship, confirmed_at=confirmed_at
    )
