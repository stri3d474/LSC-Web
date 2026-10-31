# Data processors and data categories (Ley 1581)

Engineering reference, not legal advice. The authoritative processor agreements
and the database registration before the SIC are the lawyer's responsibility;
this file lists the processors the system uses and the data categories each one
touches, so the privacy notice and records of processing can be kept accurate.

Residency: all GCP resources are provisioned in the configured region
(`LSC_GCP_REGION`); document that region in the privacy policy.

| Processor | Role | Data category | Notes |
|-----------|------|---------------|-------|
| Google Cloud Firestore | Document store | Account metadata (uid, age band, roles, status), entitlements, purchases (token hashes), consent history, correction metadata (pseudonymous), audit log | No raw video; no email/name; corrections carry no uid |
| Google Cloud Storage — `models` | Object store | Encrypted model blobs, manifests | No personal data |
| Google Cloud Storage — `datasets` | Object store | Contributed landmark sequences under a pseudonymous contributor id | Never video; consented only |
| Google Cloud Storage — `exports` | Object store | Per-user data-subject export zips | Short-lived (<= 24 h), signed URLs |
| Google Secret Manager | Secret store | JWT signing keys, model data keys, pseudonymization pepper, Play/Firebase credentials | Secrets never in Firestore or logs |
| Google Cloud Pub/Sub | Messaging | Job triggers and RTDN notifications | Ids only, no PII |
| Firebase Authentication | Identity provider | Firebase uid, sign-in provider, second-factor status | Email/name not copied into our store |
| Firebase Cloud Messaging (P2) | Push | Message ids only | No message content in notifications |
| Google Play Developer API | Billing | Purchase tokens, subscription state | Tokens stored only as SHA-256 |
| Play Integrity API | Attestation | Device/app integrity verdicts | Coarse booleans; no device identifiers stored |
| Google Speech-to-Text (P3) | Transcription | Call audio (not retained), transcript text | Audio never stored |

## Data categories and handling
- Biometric landmarks: stored only as contributed, consented, pseudonymous
  sequences in `datasets`; raw video never leaves the device and is never
  stored.
- Deaf/hard-of-hearing status: stored only as the fact of community
  verification plus the issuing organization; never medical documents.
- Account data: minimized (uid, age band, roles, status). No email or name.
- Logs and analytics: no PII, tokens, landmarks or message content.

## Data-subject rights (habeas data)
- Access/export: `GET /me/data-export` assembles profile, consent history,
  session metadata and a purchases summary; delivered via a 24 h signed URL.
- Deletion: `DELETE /me` is idempotent and resumable; it removes sessions, the
  Firebase user, personal documents and (by default) pseudonymous
  contributions, while retaining consent history pseudonymized as legal proof.
- Rectification and consent revocation: through the vocabulary/profile and
  consent endpoints (W02).
- Retention: `config/retention.yaml` sets per-collection TTLs.
