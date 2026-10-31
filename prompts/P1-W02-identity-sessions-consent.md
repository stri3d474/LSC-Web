# W02 — Identity, sessions, roles and consent registry
Spec name: `web-identity-consent` · Phase: P1 · Repo: lsc-web · Depends on: W01

ROLE: Senior backend engineer specializing in authentication. Contracts C5, C6, C8 apply.

## Objective
Exchange Firebase identities for the app's own short-lived sessions, enforce roles and MFA, and keep a legally useful consent history.

## Deliver
- `modules/identity`:
  - `POST /auth/session`: verify the Firebase ID token with revocation check; require verified email for the email provider; anonymous allowed (role `user`, tier `free`). Upsert `users/{uid}` with minimal data (uid, age_band, roles, status, created_at); do not store email or name. For `client_type=web` set the refresh cookie; for `mobile` return it in the body. Record `risk_signals` on the session.
  - `KeyRing` loading ES256 private keys from Secret Manager (`jwt-signing-<kid>`), signing with the newest, verifying with all active; `GET /.well-known/jwks.json`.
  - Refresh families in `sessions/{sid}`: random 256-bit token stored as SHA-256, rotation on every use, reuse detection revokes the family, device `install_id` hashed, per-user session cap, `POST /auth/logout`, revoke-all.
  - Roles from `users` + `org_members`; tier from an `EntitlementsPort` (Protocol; default returns `free` until W03). `mfa` claim set from the Firebase second-factor info; `require_mfa` demands it for admin/reviewer.
  - `GET /me` (non-sensitive profile), `POST /me/devices/keys` interface reserved for P2 (do not implement now).
- `modules/consent`: `GET /consents/purposes` (public; each purpose with current version and Spanish text from `config/consent_purposes.yaml`), `GET /consents`, `PUT /consents/{purpose}` appending an immutable record (purpose, version, granted, at, guardian_authorization {name, relationship, confirmed_at} required for under-18 users on all purposes except terms/privacy/core).
- `modules/audit`: `AuditService.record(actor, action, target, metadata)` writing hash-chained entries (prev_hash + entry hash).
- Rate limits on `/auth/session` and `/auth/refresh` per IP and per install.

## Rules
- Every denial path returns generic problem+json; log the specific reason server-side only.
- Never put roles or tier in anything the client can choose.

## Done when (verify by reading)
- A refresh token can be used exactly once; reuse revokes the family.
- All JWT claims match C5.

## Out of scope
Billing, models, admin UI, tests, running anything.
