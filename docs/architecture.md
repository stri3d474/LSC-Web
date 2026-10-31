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

## Endpoints present in W01
- `GET /healthz`, `GET /readyz` — public probes, no sensitive data.
- `GET /.well-known/jwks.json` — public; empty key set until W02 wires the
  keyring.
- `GET /v1/me/ping` — placeholder proving the `require_auth` wiring; replaced by
  the real identity router in W02.

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
