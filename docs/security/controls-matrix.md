# Controls matrix — lsc-web

Maps each `SECURITY(<id>)` code marker to the OWASP ASVS L2 / API Top 10
requirement it addresses and the files that implement it. Extended as modules
land; W01 establishes the cross-cutting controls.

| ID | Requirement (ASVS L2 / API Top 10) | Control | File(s) |
|----|------------------------------------|---------|---------|
| CFG-01  | ASVS V14.1 (config) | No secret defaults; missing config fails at startup | `apps/api/src/lsc_api/config.py` |
| AUTH-01 | ASVS V4.1; API1/API5 (BOLA/BFLA) | Deny by default; every route declares an auth dependency | `apps/api/src/lsc_api/core/security/deps.py`, `apps/api/src/lsc_api/main.py` |
| SEC-01  | ASVS V6.4 (secret management) | Secrets only from Secret Manager, fetched by name | `apps/api/src/lsc_api/infra/secrets.py` |
| LOG-01  | ASVS V7.1 (logging), V8 (data protection) | Structured logs with PII/secret redaction; access log without bodies | `apps/api/src/lsc_api/core/logging.py`, `apps/api/src/lsc_api/core/middleware.py` |
| ERR-01  | ASVS V7.4 (error handling) | problem+json with stable codes, no internals | `apps/api/src/lsc_api/core/errors.py` |
| HDR-01  | ASVS V14.4 (HTTP headers) | Security headers on every response (HSTS in prod) | `apps/api/src/lsc_api/core/middleware.py` |
| SIZE-01 | API4 (resource consumption) | Request body size limit | `apps/api/src/lsc_api/core/middleware.py` |
| URL-01  | ASVS V8.3; API Top 10 | Signed URLs <=10 min, single object, least privilege | `apps/api/src/lsc_api/infra/storage.py` |
| RATE-01 | API4 (rate limiting) | App-level token bucket on sensitive endpoints | `apps/api/src/lsc_api/core/ratelimit.py` |
| FS-01   | ASVS V12.3 (path traversal) | (training repo) safe path resolution | see lsc-training |
