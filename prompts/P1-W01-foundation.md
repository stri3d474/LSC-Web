# W01 — Monorepo and API foundation
Spec name: `web-foundation` · Phase: P1 · Repo: lsc-web · Depends on: none

ROLE: Senior Python backend engineer. Steering and contracts are binding.

## Objective
Create the backend skeleton and cross-cutting infrastructure all modules will use.

## Deliver
- `apps/api` package per structure.md: `config.py` (pydantic-settings: environment, project id, region, bucket names, allowed origins, JWT issuer/audience, token lifetimes, integrity enforcement mode `enforce|log_only`, feature flag `SERVER_HEAD_ENABLED`), no defaults for secrets.
- App factory in `main.py` mounting versioned routers under `/v1`, JWKS at `/.well-known/jwks.json`, `/healthz` and `/readyz` (no sensitive data). OpenAPI/docs disabled in prod.
- `core/middleware.py`: request id, security headers, body size limit, strict CORS allow-list, access log without PII.
- `core/errors.py`: domain exception hierarchy mapped to RFC 9457 problem+json with stable codes.
- `core/logging.py` (structlog with redaction), `core/ids.py` (ULID), `core/clock.py` (injectable).
- `core/ratelimit.py`: `RateLimiter` Protocol + Firestore-backed token-bucket implementation used for per-account and per-install limits (edge limits are handled by Cloud Armor).
- `infra/` adapters behind Protocols: `DocumentStore` (Firestore with transactions), `BlobStore` (GCS with V4 signed URLs), `SecretStore` (Secret Manager), `EventPublisher` (Pub/Sub). Concrete GCP classes plus in-memory fakes are NOT needed (no tests).
- `core/security/deps.py`: `require_auth`, `require_roles`, `require_mfa`, `public` dependencies (implemented fully in W02; define signatures and failure behavior now).
- pnpm workspace files (`pnpm-workspace.yaml`, root `package.json`, shared `tsconfig.base.json`) and empty-by-design app folders only where config files exist.
- `docs/architecture.md`: modules, layering and request flow.

## Rules
- No business logic in routers. Every external service behind a Protocol.
- No secret defaults; missing config fails at startup with a clear error.

## Done when (verify by reading)
- Every route placeholder in the factory has an explicit auth dependency.
- Layer imports follow structure.md.

## Out of scope
Feature modules, frontend code, tests, deployment, running anything.
