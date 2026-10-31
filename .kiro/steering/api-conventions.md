---
inclusion: fileMatch
fileMatchPattern: "apps/api/**/*.py"
---
# API conventions
- Every route declares: `response_model`, a dependency from `core.security.deps` (`require_auth`, `require_roles(...)`, or explicit `public`), and an error mapping to problem+json.
- Pydantic models use `extra="forbid"` and strict types. No raw `dict` in or out. No mass assignment: separate request, domain and response models.
- Ownership checks live in services and are applied on every object lookup by id.
- Money/entitlement/role logic only on the server. Never read tier or roles from request bodies.
- Idempotent creates require `Idempotency-Key` (store key + response hash with TTL).
- Admin and privileged actions write an audit event (hash-chained).
- Async I/O only; no blocking calls in request handlers.
- Pagination: cursor + limit (max 100). Bound every list and every body size.
