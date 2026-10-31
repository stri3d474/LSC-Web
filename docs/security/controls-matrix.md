# Controls matrix — lsc-web

Maps each `SECURITY(<id>)` code marker to the OWASP ASVS L2 / API Top 10
requirement it addresses and the files that implement it. Extended as modules
land; W01 establishes the cross-cutting controls.

| ID | Requirement (ASVS L2 / API Top 10) | Control | File(s) |
|----|------------------------------------|---------|---------|
| CFG-01  | ASVS V14.1 (config) | No secret defaults; missing config fails at startup | `apps/api/src/lsc_api/config.py` |
| AUTH-01 | ASVS V4.1; API1/API5 (BOLA/BFLA) | Deny by default; every route declares an auth dependency | `apps/api/src/lsc_api/core/security/deps.py`, `apps/api/src/lsc_api/main.py` |
| AUTH-02 | ASVS V3 (session/JWT) | ES256 access JWT (15 min), claims per C5, rotating keyring | `apps/api/src/lsc_api/core/security/keyring.py`, `apps/api/src/lsc_api/core/security/tokens.py` |
| AUTH-03 | ASVS V3.3 (session termination) | Refresh families: hashed at rest, single-use rotation, reuse revokes family, per-user cap | `apps/api/src/lsc_api/modules/identity/service.py`, `apps/api/src/lsc_api/modules/identity/repository.py` |
| AUTH-04 | API5 (BFLA) | Roles/tier resolved server-side only; never read from the client | `apps/api/src/lsc_api/modules/identity/service.py` |
| AUTH-05 | ASVS V3.4 (cookie-based session), CSRF | Web refresh cookie HttpOnly/Secure/SameSite=Strict scoped to /v1/auth + Origin check | `apps/api/src/lsc_api/modules/identity/router.py` |
| AUDIT-01 | ASVS V7.2 (log integrity) | Append-only, hash-chained audit entries | `apps/api/src/lsc_api/modules/audit/domain.py`, `apps/api/src/lsc_api/modules/audit/repository.py` |
| BILL-01 | API Top 10 (business logic), ASVS V1.11 | Subscription state always from a fresh Play query, never client/RTDN body | `apps/api/src/lsc_api/modules/billing/service.py`, `apps/api/src/lsc_api/infra/play.py` |
| BILL-02 | ASVS V8.1 (sensitive data) | Purchases keyed by SHA-256 of the token; raw token never stored | `apps/api/src/lsc_api/modules/billing/repository.py` |
| BILL-03 | API1 (BOLA) | HMAC account id binds a purchase to its account; replay for another account rejected | `apps/api/src/lsc_api/core/security/accountid.py`, `apps/api/src/lsc_api/modules/billing/service.py` |
| ENT-01 | API5 (BFLA) | Tier/features/state derived only from verified facts | `apps/api/src/lsc_api/modules/billing/entitlements.py` |
| RTDN-01 | API2 (broken auth) | Pub/Sub push verifies Google OIDC token (audience + service account) | `apps/api/src/lsc_api/infra/oidc.py`, `apps/api/src/lsc_api/modules/billing/router.py` |
| VERIFY-01 | ASVS V2.1 (verification), API4 | Single-use, expiring, high-entropy codes stored hashed; redemption audited + rate-limited | `apps/api/src/lsc_api/modules/billing/orgs_repository.py`, `apps/api/src/lsc_api/modules/billing/verification_service.py` |
| SEC-01  | ASVS V6.4 (secret management) | Secrets only from Secret Manager, fetched by name | `apps/api/src/lsc_api/infra/secrets.py` |
| LOG-01  | ASVS V7.1 (logging), V8 (data protection) | Structured logs with PII/secret redaction; access log without bodies | `apps/api/src/lsc_api/core/logging.py`, `apps/api/src/lsc_api/core/middleware.py` |
| ERR-01  | ASVS V7.4 (error handling) | problem+json with stable codes, no internals | `apps/api/src/lsc_api/core/errors.py` |
| HDR-01  | ASVS V14.4 (HTTP headers) | Security headers on every response (HSTS in prod) | `apps/api/src/lsc_api/core/middleware.py` |
| SIZE-01 | API4 (resource consumption) | Request body size limit | `apps/api/src/lsc_api/core/middleware.py` |
| URL-01  | ASVS V8.3; API Top 10 | Signed URLs <=10 min, single object, least privilege | `apps/api/src/lsc_api/infra/storage.py` |
| RATE-01 | API4 (rate limiting) | App-level token bucket on sensitive endpoints | `apps/api/src/lsc_api/core/ratelimit.py` |
| FS-01   | ASVS V12.3 (path traversal) | (training repo) safe path resolution | see lsc-training |
