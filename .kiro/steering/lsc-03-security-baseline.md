---
inclusion: always
---
# Security baseline (all repos)
Targets: OWASP MASVS v2 L2 (mobile) · OWASP ASVS L2 (web/API) · OWASP API Security Top 10 (2023). Assume a gray-box penetration test: testers get architecture docs, test accounts and builds. Keep the attack surface small and the evidence easy to find.

## Rules
- Crypto: AES-256-GCM (random 96-bit nonce, never reused per key), Ed25519 (signatures), ES256 (JWT), SHA-256, HKDF-SHA256, X25519. Vetted libraries only. No custom crypto, no ECB, no MD5/SHA-1.
- Secrets: never in code, repo, logs, app binary or client config. Server secrets only from Secret Manager. Local secrets come from env-referenced files outside the repo.
- Authorization: deny by default. Every endpoint declares its auth and role. Object ownership is checked server-side on every access (prevents IDOR/BOLA). Never trust client-supplied role, tier, entitlement, price or user id.
- Input: validate at the boundary with strict schemas (reject unknown fields), size limits and allow-lists. Parameterize queries. Never build paths or URLs from raw input (path traversal, SSRF).
- Output: generic error messages with stable codes; no stack traces or internal ids. Security events (auth failure, refresh reuse, key release, admin action) are logged without PII, tokens, landmarks or message content.
- Transport: TLS only, no cleartext anywhere. Mobile pins the backend certificate.
- Dependencies: exact pins, minimal set, no abandoned packages. Each addition is justified in docs/adr/.
- Fail closed: if a signature, hash, integrity, consent or entitlement check fails, stop. Never degrade silently into insecure behavior.
- No backdoors: no debug endpoints, hardcoded accounts or weakened modes in production configuration.
- Honest limits: assume a determined attacker on a rooted device can extract the model. The goal is to raise the cost, keep keys out of the package, and keep legal licensing as the backstop.

## Pentest-readiness conventions
- Each repo maintains docs/security/: threat-model.md, attack-surface.md, controls-matrix.md, data-flow.md, assumptions-and-accepted-risks.md, self-review.md.
- Mark security-relevant code `SECURITY(<id>)` (e.g. SECURITY(AUTH-03)) and map every id in controls-matrix.md to MASVS/ASVS requirements and file paths.
