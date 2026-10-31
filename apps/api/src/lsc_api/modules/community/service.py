"""Community service: vocabulary and consented, landmarks-only corrections.

SECURITY(PRIV-01..03): corrections require a current ``landmark_contribution``
consent (plus guardian authorization for minors); the landmark blob is stored
under a pseudonymous contributor id in the ``datasets`` bucket; the metadata
document carries no uid. Size caps, per-user daily limits and content-hash
dedupe bound abuse.
"""

from __future__ import annotations

import hashlib

from lsc_api.core.clock import Clock, iso_utc
from lsc_api.core.errors import (
    AuthorizationError,
    ConflictError,
    RateLimitedError,
    ValidationError,
)
from lsc_api.core.ids import new_id
from lsc_api.core.security.pseudonym import PEPPER_SECRET_NAME, contributor_id
from lsc_api.infra.secrets import SecretStore
from lsc_api.infra.storage import BlobStore
from lsc_api.modules.audit.service import AuditService
from lsc_api.modules.community.domain import (
    CORRECTION_PENDING,
    Concept,
    CorrectionInput,
    CorrectionRecord,
    VocabularyDelta,
)
from lsc_api.modules.community.repository import CommunityRepository
from lsc_api.modules.consent.domain import AgeBand, guardian_required
from lsc_api.modules.consent.service import ConsentService

_CONTRIBUTION_PURPOSE = "landmark_contribution"
_MAX_CORRECTIONS_PER_DAY = 50


class CommunityService:
    """Vocabulary distribution and community corrections."""

    def __init__(
        self,
        repository: CommunityRepository,
        consent: ConsentService,
        blobs: BlobStore,
        secrets: SecretStore,
        audit: AuditService,
        clock: Clock,
        *,
        datasets_bucket: str,
        expected_frame_vector_size: int,
        sequence_length: int,
        schema_version: int,
    ) -> None:
        self._repo = repository
        self._consent = consent
        self._blobs = blobs
        self._secrets = secrets
        self._audit = audit
        self._clock = clock
        self._bucket = datasets_bucket
        self._f = expected_frame_vector_size
        self._t = sequence_length
        self._schema_version = schema_version

    # --- Vocabulary. ---
    async def vocabulary_since(self, since: int) -> VocabularyDelta:
        """Return concept changes (incl. tombstones) after version ``since``."""

        concepts = await self._repo.changes_since(since)
        current = await self._repo.current_vocabulary_version()
        return VocabularyDelta(vocabulary_version=current, concepts=concepts)

    async def upsert_concept(
        self, *, actor_uid: str, concept: Concept
    ) -> Concept:
        """Create or update a concept, stamping a new vocabulary version."""

        version = await self._repo.next_vocabulary_version()
        stamped = Concept(
            concept_id=concept.concept_id,
            gloss=concept.gloss,
            es_text=concept.es_text,
            es_forms=concept.es_forms,
            variants=concept.variants,
            vocabulary_version=version,
            deleted=False,
        )
        await self._repo.upsert_concept(stamped)
        await self._audit.record(
            actor=actor_uid, action="vocabulary.upsert", target=concept.concept_id
        )
        return stamped

    async def delete_concept(self, *, actor_uid: str, concept_id: str) -> None:
        """Tombstone a concept so syncing clients learn of the removal."""

        existing = await self._repo.get_concept(concept_id)
        if existing is None:
            raise ValidationError("unknown concept")
        version = await self._repo.next_vocabulary_version()
        await self._repo.upsert_concept(
            Concept(
                concept_id=existing.concept_id,
                gloss=existing.gloss,
                es_text=existing.es_text,
                es_forms=existing.es_forms,
                variants=existing.variants,
                vocabulary_version=version,
                deleted=True,
            )
        )
        await self._audit.record(
            actor=actor_uid, action="vocabulary.delete", target=concept_id
        )

    # --- Corrections. ---
    async def submit_correction(
        self, *, uid: str, age_band: AgeBand, data: CorrectionInput
    ) -> CorrectionRecord:
        """Validate consent and shape, then store a landmarks-only correction.

        Steps: require a current granted ``landmark_contribution`` consent (and a
        guardian authorization record for minors); validate the schema version
        and, if a landmark blob is present, its exact byte length (T*F*2);
        enforce the per-user daily limit; dedupe by content hash; store the blob
        under the pseudonymous contributor id in the datasets bucket; persist
        metadata WITHOUT uid.
        Failure modes: ``AuthorizationError`` (no/again-needed consent),
        ``ValidationError`` (bad schema/shape), ``RateLimitedError`` (daily cap),
        ``ConflictError`` (duplicate content).
        """

        await self._require_contribution_consent(uid, age_band)

        if data.schema_version != self._schema_version:
            raise ValidationError("unsupported landmark schema version")
        if data.proposed_variant_id is None and data.new_variant_proposal is None:
            raise ValidationError("a proposed variant or new-variant proposal is required")

        blob = data.observed_sequence
        if blob is not None:
            expected = self._t * self._f * 2  # f16 = 2 bytes
            if len(blob) != expected:
                raise ValidationError(
                    f"landmark blob must be exactly {expected} bytes (T*F*2)"
                )

        pepper = await self._secrets.access(PEPPER_SECRET_NAME)
        cid = contributor_id(uid, pepper)

        content_hash = _content_hash(data, blob)
        if await self._repo.content_hash_exists(content_hash):
            raise ConflictError("duplicate correction")

        now = self._clock.now()
        day = iso_utc(now)[:10]
        if await self._repo.count_today(cid, day) >= _MAX_CORRECTIONS_PER_DAY:
            raise RateLimitedError("daily correction limit reached")

        blob_object: str | None = None
        if blob is not None:
            blob_object = f"contributions/{cid}/{content_hash}.f16"
            await self._blobs.put_bytes(self._bucket, blob_object, blob)

        record = CorrectionRecord(
            correction_id=new_id(),
            contributor_id=cid,
            content_hash=content_hash,
            schema_version=data.schema_version,
            predicted_variant_id=data.predicted_variant_id,
            proposed_variant_id=data.proposed_variant_id,
            new_variant_proposal=data.new_variant_proposal,
            region=data.region,
            context=data.context,
            education_level=data.education_level,
            blob_object=blob_object,
            status=CORRECTION_PENDING,
            created_at=iso_utc(now),
        )
        await self._repo.create_correction(record, day)
        # Audit by pseudonymous contributor id, never uid.
        await self._audit.record(
            actor=cid, action="correction.submit", target=record.correction_id
        )
        return record

    async def _require_contribution_consent(
        self, uid: str, age_band: AgeBand
    ) -> None:
        """Raise unless a current granted contribution consent exists (and a
        guardian record for minors)."""

        purposes = {p.key: p for p in self._consent.purposes()}
        purpose = purposes.get(_CONTRIBUTION_PURPOSE)
        if purpose is None:
            raise AuthorizationError("contribution consent is not configured")

        records = {r.purpose: r for r in await self._consent.current(uid)}
        current = records.get(_CONTRIBUTION_PURPOSE)
        if current is None or not current.granted or current.version != purpose.version:
            raise AuthorizationError("landmark contribution consent required")
        if guardian_required(purpose, age_band) and current.guardian_authorization is None:
            raise AuthorizationError("guardian authorization required to contribute")


def _content_hash(data: CorrectionInput, blob: bytes | None) -> str:
    """Stable content hash for dedupe, over the salient fields and the blob."""

    hasher = hashlib.sha256()
    hasher.update(data.predicted_variant_id.encode("utf-8"))
    hasher.update((data.proposed_variant_id or "").encode("utf-8"))
    hasher.update(data.region.encode("utf-8"))
    hasher.update(data.context.encode("utf-8"))
    hasher.update(data.education_level.encode("utf-8"))
    if blob is not None:
        hasher.update(blob)
    return hasher.hexdigest()
