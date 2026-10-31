---
inclusion: always
---
# Privacy by design — Ley 1581 de 2012 (Colombia)
Engineering guidance, not legal advice. Legal texts (privacy policy, authorization wording, database registration, processor agreements) belong to a lawyer; code only implements the mechanisms.

- Sensitive data: video of a person's face/hands is biometric; Deaf/hard-of-hearing status is health-related. Treat both as sensitive: explicit, informed, optional authorization; never a condition for core interpretation.
- Purpose limitation: each purpose has its own versioned, revocable consent (C8), logged with timestamp and text version.
- Minors: under-18 users need guardian authorization for every purpose beyond core interpretation. Onboarding collects an age band. No contributions, messages or call recordings without a guardian record.
- Minimization: store landmarks, never video. Raw user video never leaves the device and is never stored. Contributed landmarks live under a pseudonymous contributor id kept separate from the account.
- Data-subject rights (habeas data): API and UI for access/export, rectification, deletion and consent revocation. Deletion cascades to sessions, messages and pseudonymous contributions; consent history is kept only as pseudonymized legal proof.
- Retention: every collection has a configured retention period implemented with TTL fields.
- Verification of Deaf status stores only the fact and the issuing organization, never medical documents.
- Recorded interpreters (training repo): signed authorization before any use of their videos; videos are sensitive and access is limited to the project.
- Processors and regions are configuration. Every processor (GCP, Firebase, Google Play, FCM, Speech-to-Text in P3) is listed in docs/privacy/processors.md.
- Logs and analytics contain no PII. Aggregate analytics only with consent.
