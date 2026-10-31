"""Community domain: concepts, variants, corrections (C2/C3).

Pure data carriers plus the vocabulary-change model. Concepts and variants mirror
the C2 ``variant_map`` fields; corrections are landmarks-only and never carry a
uid (Ley 1581 minimization).
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Correction lifecycle (reviewer workflow).
CORRECTION_PENDING = "pending"
CORRECTION_APPROVED = "approved"
CORRECTION_REJECTED = "rejected"
CORRECTION_MERGED = "merged"


@dataclass(frozen=True)
class Variant:
    """One signed form of a concept (C2 variant_map).

    ``tier`` gates whether the variant belongs to the basic or full model.
    """

    variant_id: str
    region_codes: tuple[str, ...]
    contexts: tuple[str, ...]
    education_level: str  # "school" | "university" | "unspecified"
    tier: str  # "basic" | "full"


@dataclass(frozen=True)
class Concept:
    """A language-neutral meaning with its mapped variants (C2).

    Versioned with a monotonically increasing ``vocabulary_version``; a deleted
    concept becomes a tombstone (``deleted=True``) so clients syncing ``since=``
    learn about removals.
    """

    concept_id: str
    gloss: str
    es_text: str
    es_forms: tuple[str, ...]
    variants: tuple[Variant, ...]
    vocabulary_version: int
    deleted: bool = False


@dataclass(frozen=True)
class CorrectionInput:
    """A submitted correction before persistence (validated by the service)."""

    schema_version: int
    predicted_variant_id: str
    proposed_variant_id: str | None
    new_variant_proposal: dict | None
    region: str
    context: str
    education_level: str
    observed_sequence: bytes | None  # decoded f16 landmark bytes, or None


@dataclass(frozen=True)
class CorrectionRecord:
    """A stored correction (C7). Contains NO uid — only a pseudonymous id.

    ``contributor_id`` = HMAC-SHA256(uid, pepper); it cannot be re-linked to an
    account without the pepper (Secret Manager).
    """

    correction_id: str
    contributor_id: str
    content_hash: str
    schema_version: int
    predicted_variant_id: str
    proposed_variant_id: str | None
    new_variant_proposal: dict | None
    region: str
    context: str
    education_level: str
    blob_object: str | None  # datasets bucket object path, or None
    status: str
    created_at: str
    reviewed_at: str | None = None
    review_reason: str | None = None
    retention_expires_at: str | None = None


@dataclass(frozen=True)
class VocabularyDelta:
    """Changes since a given vocabulary version."""

    vocabulary_version: int
    concepts: list[Concept] = field(default_factory=list)
