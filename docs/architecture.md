# lsc-web — Architecture

## Role
FastAPI backend (Cloud Run) plus a React admin panel and a React listener PWA.
It handles accounts, billing/entitlements, model distribution, community
corrections, messaging (P2) and call signaling (P3). It is **never** part of the
interpretation path — interpretation runs on-device.

This document covers the W01 foundation.

## Modular monolith
One API service today; feature modules sit behind strict boundaries so
interpretation/signaling can later be split into separate services without
changing contracts.

```
apps/api/src/lsc_api/
  main.py            app factory: CORS, middleware, error handling, routers
  config.py          typed settings (no secret defaults; fail closed)
  core/
    clock.py ids.py logging.py errors.py middleware.py ratelimit.py
    security/        principal, deps (require_auth/roles/mfa/public)
  infra/             DocumentStore · BlobStore · SecretStore · EventPublisher
                     (each a Protocol; concrete GCP adapters injected later)
  modules/           identity · consent · billing · models · community ·
                     privacy · admin · audit · (messaging P2) · (calls P3)
```

## Layering
```
router  ->  service  ->  repository  ->  infra
```
- Routers hold no business rules; each declares `response_model` and exactly one
  auth dependency (`require_auth`, `require_roles(...)`, `require_mfa`, or
  `public`).
- Modules never import another module's repository; they call its service
  interface.
- External services are reached only through `infra` Protocols so they can be
  swapped.

## Request flow
1. `RequestContextMiddleware` assigns an `X-Request-Id` and logs a PII-free
   access line.
2. `SecurityHeadersMiddleware` sets security headers (HSTS in prod).
3. `BodySizeLimitMiddleware` rejects oversized bodies with problem+json.
4. `CORSMiddleware` enforces the exact origin allow-list (no wildcard).
5. The route's auth dependency runs (deny by default).
6. Errors become RFC 9457 problem+json with a stable `code` and no internals.

## Endpoints present (W01–W02)
- `GET /healthz`, `GET /readyz` — public probes, no sensitive data.
- `GET /.well-known/jwks.json` — public; serves the active ES256 public keys
  from the keyring (empty when the container is not wired).
- Identity (W02): `POST /v1/auth/session`, `POST /v1/auth/refresh`,
  `POST /v1/auth/logout`, `GET /v1/me`.
- Consent (W02): `GET /v1/consents/purposes` (public), `GET /v1/consents`,
  `PUT /v1/consents/{purpose}`.
- Billing/entitlements (W03): `GET /v1/billing/products`,
  `POST /v1/billing/play/verify`, `GET /v1/me/entitlements`,
  `POST /v1/internal/play/rtdn` (Pub/Sub OIDC), `POST /v1/verification/redeem`,
  `POST /v1/orgs/{org_id}/verification-codes`.

## Billing and entitlements (W03)
- `EntitlementsService` implements the identity `EntitlementsPort`: it derives
  tier, features and state only from server-verified facts (Play purchases,
  community verification, org membership). The strongest active source wins.
- Play verification requires the purchase's obfuscated account id to equal the
  caller's HMAC account id (`HMAC-SHA256(uid, pepper)`), so a token replayed for
  another account is rejected. Tokens are stored only as SHA-256. Pending (cash)
  purchases grant nothing.
- RTDN is a trigger only: the handler verifies the Google OIDC token, then
  re-queries Play for authoritative state.
- Verification codes are single-use, expiring, high-entropy and stored hashed;
  redeeming grants `verified_deaf` + `community`, audited.

## Composition
`composition.build_container` assembles the service `Container` from concrete
infra adapters (DocumentStore, SecretStore, FirebaseVerifier) and attaches it to
`app.state`. Routers reach services only through the `core/deps_providers`
FastAPI dependencies. Type-only imports between `container`, `deps_providers`
and the module routers are kept under `TYPE_CHECKING` to avoid import cycles.

## Identity and sessions (W02)
- `POST /auth/session` verifies a Firebase ID token (revocation-checked),
  requires a verified email for the email provider (anonymous allowed), upserts
  a minimal `users/{uid}` (no email/name), resolves roles (user record +
  `org_members`) and tier (`EntitlementsPort`, default `free` until W03) on the
  server, and issues a 15-minute ES256 access token plus an opaque refresh
  token. Web clients get the refresh token as a scoped HttpOnly cookie; mobile
  gets it in the body.
- Refresh families (`sessions/{sid}`): the token is stored only as SHA-256,
  rotates on every use, and reuse of a consumed token revokes the whole family.
  A per-user session cap bounds active families.
- `require_mfa` demands the `mfa` claim (set from the Firebase second factor)
  for admin/reviewer actions.

## Consent (W02)
Versioned, revocable purposes from `config/consent_purposes.yaml`. `PUT` appends
an immutable record; minors (age band read server-side) need a guardian
authorization for every purpose except terms/privacy/core. History is retained
as pseudonymized legal proof.

## Security and privacy posture (W01)
- No secret defaults: missing configuration fails at startup (SECURITY(CFG-01)).
- Deny by default: every route declares an explicit auth dependency
  (SECURITY(AUTH-01)); verification body lands in W02 and currently fails closed.
- Secrets only from Secret Manager via `SecretStore` (SECURITY(SEC-01)).
- Logs carry no PII, tokens, landmarks or bodies (SECURITY(LOG-01)).
- Signed URLs capped at 10 minutes, single object (SECURITY(URL-01)).
- Config holds names/ids only, never secret values or PII.

## Frontend
`apps/admin` (staff SPA) and `apps/listener` (PWA) are pnpm workspaces sharing
`tsconfig.base.json` and consuming `packages/api-client` generated from the
OpenAPI schema. Their application code is added by later specs; W01 provides only
the workspace scaffolding.
