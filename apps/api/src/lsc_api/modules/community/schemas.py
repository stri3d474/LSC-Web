"""Community request/response models (strict)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from lsc_api.modules.community.domain import Concept, CorrectionRecord, Variant


class VariantModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    variant_id: str
    region_codes: list[str]
    contexts: list[str]
    education_level: Literal["school", "university", "unspecified"]
    tier: Literal["basic", "full"]

    def to_domain(self) -> Variant:
        return Variant(
            variant_id=self.variant_id,
            region_codes=tuple(self.region_codes),
            contexts=tuple(self.contexts),
            education_level=self.education_level,
            tier=self.tier,
        )

    @classmethod
    def from_domain(cls, v: Variant) -> "VariantModel":
        return cls(
            variant_id=v.variant_id,
            region_codes=list(v.region_codes),
            contexts=list(v.contexts),
            education_level=v.education_level,  # type: ignore[arg-type]
            tier=v.tier,  # type: ignore[arg-type]
        )


class ConceptIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    concept_id: str = Field(min_length=1, max_length=128)
    gloss: str = Field(min_length=1, max_length=256)
    es_text: str = Field(min_length=1, max_length=512)
    es_forms: list[str]
    variants: list[VariantModel]

    def to_domain(self) -> Concept:
        return Concept(
            concept_id=self.concept_id,
            gloss=self.gloss,
            es_text=self.es_text,
            es_forms=tuple(self.es_forms),
            variants=tuple(v.to_domain() for v in self.variants),
            vocabulary_version=0,  # stamped by the service
        )


class ConceptOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    concept_id: str
    gloss: str
    es_text: str
    es_forms: list[str]
    variants: list[VariantModel]
    vocabulary_version: int
    deleted: bool

    @classmethod
    def from_domain(cls, c: Concept) -> "ConceptOut":
        return cls(
            concept_id=c.concept_id,
            gloss=c.gloss,
            es_text=c.es_text,
            es_forms=list(c.es_forms),
            variants=[VariantModel.from_domain(v) for v in c.variants],
            vocabulary_version=c.vocabulary_version,
            deleted=c.deleted,
        )


class VocabularyResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vocabulary_version: int
    concepts: list[ConceptOut]


class NewVariantProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    concept_id: str | None = None
    gloss: str = Field(min_length=1, max_length=256)
    region_codes: list[str] = Field(default_factory=list)
    contexts: list[str] = Field(default_factory=list)
    education_level: Literal["school", "university", "unspecified"] = "unspecified"


class CorrectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = Field(ge=1)
    predicted_variant_id: str = Field(min_length=1, max_length=128)
    proposed_variant_id: str | None = Field(default=None, max_length=128)
    new_variant_proposal: NewVariantProposal | None = None
    region: str = Field(min_length=1, max_length=8)
    context: str = Field(min_length=1, max_length=8)
    education_level: Literal["school", "university", "unspecified"]
    # Base64 float16 landmark sequence; validated to exactly T*F*2 bytes.
    observed_sequence_f16_b64: str | None = Field(default=None, max_length=4_000_000)


class CorrectionAccepted(BaseModel):
    model_config = ConfigDict(extra="forbid")

    correction_id: str
    status: str


class CorrectionOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    correction_id: str
    status: str
    predicted_variant_id: str
    proposed_variant_id: str | None
    region: str
    context: str
    education_level: str
    created_at: str

    @classmethod
    def from_domain(cls, r: CorrectionRecord) -> "CorrectionOut":
        return cls(
            correction_id=r.correction_id,
            status=r.status,
            predicted_variant_id=r.predicted_variant_id,
            proposed_variant_id=r.proposed_variant_id,
            region=r.region,
            context=r.context,
            education_level=r.education_level,
            created_at=r.created_at,
        )


class CorrectionsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    corrections: list[CorrectionOut]


class ReviewDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approve: bool
    reason: str | None = Field(default=None, max_length=512)


class ExportUrlResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str
