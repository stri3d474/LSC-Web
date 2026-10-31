---
inclusion: always
---
# lsc-web — Security (ASVS L2 + API Top 10)
- Secrets only in Secret Manager; JWT signing keys are versioned secrets (`jwt-signing-<kid>`) loaded into a `KeyRing` (active + previous for verification). Rotation = add a new version; old tokens expire in 15 min.
- Verify Firebase ID tokens with revocation checking. Admin/reviewer roles require MFA: the session endpoint checks the Firebase second-factor claim and sets `mfa:true`; privileged routes demand it.
- Refresh tokens: hashed at rest, rotating, reuse detection revokes the family. Web refresh cookie: HttpOnly, Secure, SameSite=Strict, Path=/v1/auth; the refresh endpoint also checks the `Origin` header.
- Pub/Sub push (Play RTDN) endpoints verify the Google-signed OIDC token (audience + service account). Notification content is never trusted; always re-query the Play API.
- Security headers on every response (HSTS, `X-Content-Type-Options`, `Referrer-Policy`, `Permissions-Policy`, frame protection); strict CORS allow-list; request body limits; docs/OpenAPI UI disabled in prod.
- Signed URLs: short expiry (<= 10 min), single object, least privilege. Buckets private, uniform access.
- Model data keys never in Firestore or logs; key releases are rate-limited and audited.
- Audit log is append-only and hash-chained (each entry includes the previous hash).
- Rate limits: Cloud Armor at the edge plus an app-level limiter on auth, key release, corrections and link endpoints.
- Error handling returns problem+json with stable codes and no internals.
