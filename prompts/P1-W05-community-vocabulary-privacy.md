# W05 — Vocabulary, community corrections and data-subject rights
Spec name: `web-community-privacy` · Phase: P1 · Repo: lsc-web · Depends on: W02

ROLE: Senior backend engineer with privacy-engineering focus. Ley 1581 steering is binding.

## Objective
Maintain the vocabulary of Concepts and Variants, collect consented corrections as landmarks only, and implement access/export/deletion.

## Deliver
- `modules/community`:
  - Concepts and variants (fields per C2 variant_map plus `es_forms`, `tier: basic|full`, tags region_codes/contexts/education_level), versioned with a monotonically increasing `vocabulary_version`; tombstones on delete. `GET /vocabulary?since=` returns changes since a version. Admin/reviewer CRUD under `/admin/vocabulary`.
  - `POST /corrections`: auth required; verify the `landmark_contribution` consent (and guardian authorization for minors) before accepting landmarks; accept `{observed_sequence_f16_b64?, schema_version, predicted_variant_id, proposed_variant_id | new_variant_proposal, region, context, education_level}`; validate shape against the C1 schema (length = T x F x 2 bytes), size caps, per-user daily limits, content-hash dedupe. Store the blob in the `datasets` bucket under a pseudonymous contributor id = HMAC-SHA256(uid, pepper); store metadata WITHOUT uid.
  - Reviewer workflow `/admin/corrections`: list by status (pending, approved, rejected, merged), approve/reject with reason, bulk export of approved items as JSONL matching the training repo's importer schema, delivered via short-lived signed URL.
- `modules/privacy`:
  - `GET /me/data-export`: create an export job (`JobQueue` Protocol over Pub/Sub), assemble profile, consent history, session metadata, purchases summary into a zip in the `exports` bucket, return job status and a 24 h signed URL when ready.
  - `DELETE /me`: revoke sessions, delete the Firebase user, delete personal documents, delete pseudonymous contributions (default) unless the user chose to keep them, keep consent history pseudonymized as legal evidence, write an audit event. `config/retention.yaml` defines TTLs per collection and applies them through TTL fields.
- `docs/privacy/processors.md` listing every processor and data category.

## Rules
- The pseudonym pepper lives in Secret Manager; contributions can never be re-linked to an account without it.
- Deletion must be idempotent and resumable.

## Done when (verify by reading)
- No Firestore document in the corrections collection contains uid, email or device identifiers.

## Out of scope
Admin UI (W06), tests, running anything.
