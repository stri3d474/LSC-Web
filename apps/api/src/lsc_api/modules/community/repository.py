"""Community persistence: concepts/variants (versioned) and corrections.

SECURITY(PRIV-02): no document in the ``corrections`` collection contains a uid,
email or device identifier — only a pseudonymous ``contributor_id`` and the
correction metadata.
"""

from __future__ import annotations

from typing import Any

from lsc_api.modules.community.domain import (
    Concept,
    CorrectionRecord,
    Variant,
)

_CONCEPTS = "concepts"
_VOCAB_META = "vocabulary_meta"  # holds the monotonic vocabulary_version
_VOCAB_DOC = "current"
_CORRECTIONS = "corrections"
_CONTENT_INDEX = "correction_content_index"  # content_hash -> correction_id


class CommunityRepository:
    """Reads and writes concepts/variants and corrections."""

    def __init__(self, store: Any) -> None:
        self._store = store

    # --- Vocabulary version counter. ---
    async def next_vocabulary_version(self) -> int:
        """Atomically increment and return the vocabulary version."""

        def _bump(current: dict[str, Any] | None) -> tuple[dict[str, Any], int]:
            version = 0 if current is None else int(current["version"])
            version += 1
            return {"version": version}, version

        return await self._store.transact_update(_VOCAB_META, _VOCAB_DOC, _bump)

    async def current_vocabulary_version(self) -> int:
        doc = await self._store.get(_VOCAB_META, _VOCAB_DOC)
        return 0 if doc is None else int(doc["version"])

    # --- Concepts. ---
    async def upsert_concept(self, concept: Concept) -> None:
        await self._store.set(_CONCEPTS, concept.concept_id, _concept_doc(concept))

    async def get_concept(self, concept_id: str) -> Concept | None:
        doc = await self._store.get(_CONCEPTS, concept_id)
        return _to_concept(concept_id, doc) if doc else None

    async def changes_since(self, since: int) -> list[Concept]:
        """Return concepts (including tombstones) with version > ``since``."""

        rows, _ = await self._store.query(
            _CONCEPTS, where=[("vocabulary_version", ">", since)], limit=100
        )
        return [_to_concept(r["concept_id"], r) for r in rows]

    # --- Corrections. ---
    async def content_hash_exists(self, content_hash: str) -> bool:
        return await self._store.get(_CONTENT_INDEX, content_hash) is not None

    async def count_today(self, contributor_id: str, day: str) -> int:
        """Count a contributor's corrections created on ``day`` (YYYY-MM-DD)."""

        rows, _ = await self._store.query(
            _CORRECTIONS,
            where=[("contributor_id", "==", contributor_id), ("day", "==", day)],
            limit=100,
        )
        return len(rows)

    async def create_correction(self, record: CorrectionRecord, day: str) -> None:
        """Persist a correction and its content-hash dedupe index entry."""

        await self._store.create(
            _CORRECTIONS,
            record.correction_id,
            _correction_doc(record, day),
        )
        await self._store.set(
            _CONTENT_INDEX, record.content_hash, {"correction_id": record.correction_id}
        )

    async def list_corrections(self, status: str) -> list[CorrectionRecord]:
        rows, _ = await self._store.query(
            _CORRECTIONS, where=[("status", "==", status)], limit=100
        )
        return [_to_correction(r["correction_id"], r) for r in rows]

    async def get_correction(self, correction_id: str) -> CorrectionRecord | None:
        doc = await self._store.get(_CORRECTIONS, correction_id)
        return _to_correction(correction_id, doc) if doc else None

    async def set_correction_status(
        self, correction_id: str, *, status: str, reason: str | None, reviewed_at: str
    ) -> None:
        def _apply(current: dict[str, Any] | None) -> tuple[dict[str, Any], None]:
            from lsc_api.core.errors import NotFoundError

            if current is None:
                raise NotFoundError("correction not found")
            updated = dict(current)
            updated["status"] = status
            updated["review_reason"] = reason
            updated["reviewed_at"] = reviewed_at
            return updated, None

        await self._store.transact_update(_CORRECTIONS, correction_id, _apply)


# --- mapping helpers ---
def _concept_doc(c: Concept) -> dict[str, Any]:
    return {
        "concept_id": c.concept_id,
        "gloss": c.gloss,
        "es_text": c.es_text,
        "es_forms": list(c.es_forms),
        "variants": [
            {
                "variant_id": v.variant_id,
                "region_codes": list(v.region_codes),
                "contexts": list(v.contexts),
                "education_level": v.education_level,
                "tier": v.tier,
            }
            for v in c.variants
        ],
        "vocabulary_version": c.vocabulary_version,
        "deleted": c.deleted,
    }


def _to_concept(concept_id: str, doc: dict[str, Any]) -> Concept:
    return Concept(
        concept_id=concept_id,
        gloss=str(doc.get("gloss", "")),
        es_text=str(doc.get("es_text", "")),
        es_forms=tuple(doc.get("es_forms", [])),
        variants=tuple(
            Variant(
                variant_id=str(v["variant_id"]),
                region_codes=tuple(v.get("region_codes", [])),
                contexts=tuple(v.get("contexts", [])),
                education_level=str(v.get("education_level", "unspecified")),
                tier=str(v.get("tier", "basic")),
            )
            for v in doc.get("variants", [])
        ),
        vocabulary_version=int(doc.get("vocabulary_version", 0)),
        deleted=bool(doc.get("deleted", False)),
    )


def _correction_doc(r: CorrectionRecord, day: str) -> dict[str, Any]:
    # NOTE: deliberately no uid/email/device fields (SECURITY(PRIV-02)).
    return {
        "correction_id": r.correction_id,
        "contributor_id": r.contributor_id,
        "content_hash": r.content_hash,
        "schema_version": r.schema_version,
        "predicted_variant_id": r.predicted_variant_id,
        "proposed_variant_id": r.proposed_variant_id,
        "new_variant_proposal": r.new_variant_proposal,
        "region": r.region,
        "context": r.context,
        "education_level": r.education_level,
        "blob_object": r.blob_object,
        "status": r.status,
        "created_at": r.created_at,
        "day": day,
        "reviewed_at": r.reviewed_at,
        "review_reason": r.review_reason,
        "retention_expires_at": r.retention_expires_at,
    }


def _to_correction(correction_id: str, doc: dict[str, Any]) -> CorrectionRecord:
    return CorrectionRecord(
        correction_id=correction_id,
        contributor_id=str(doc["contributor_id"]),
        content_hash=str(doc["content_hash"]),
        schema_version=int(doc["schema_version"]),
        predicted_variant_id=str(doc["predicted_variant_id"]),
        proposed_variant_id=(
            str(doc["proposed_variant_id"]) if doc.get("proposed_variant_id") else None
        ),
        new_variant_proposal=doc.get("new_variant_proposal"),
        region=str(doc["region"]),
        context=str(doc["context"]),
        education_level=str(doc["education_level"]),
        blob_object=(str(doc["blob_object"]) if doc.get("blob_object") else None),
        status=str(doc["status"]),
        created_at=str(doc.get("created_at", "")),
        reviewed_at=(str(doc["reviewed_at"]) if doc.get("reviewed_at") else None),
        review_reason=(str(doc["review_reason"]) if doc.get("review_reason") else None),
        retention_expires_at=(
            str(doc["retention_expires_at"]) if doc.get("retention_expires_at") else None
        ),
    )
