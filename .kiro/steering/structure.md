---
inclusion: always
---
# lsc-web — Structure
```
lsc-web/
  apps/
    api/src/lsc_api/
      main.py (app factory) · config.py (typed settings)
      core/    security (jwt, keyring, deps, mfa) · errors (problem+json) · logging · ratelimit · middleware · ids · clock
      infra/   firestore · storage · secrets · pubsub · firebase · play · integrity · speech · ice   (each behind a Protocol)
      modules/ identity · consent · billing · models · community · privacy · admin · audit · (messaging P2) · (calls P3)
               each module: router.py · schemas.py · service.py · repository.py · domain.py
    admin/      React admin panel (staff only)
    listener/   React PWA for hearing users
  packages/     api-client (generated) · ui (shared components)
  config/       products.yaml · retention.yaml · consent_purposes.yaml
  docs/         architecture.md · adr/ · security/ · privacy/
```
Layering: router -> service -> repository -> infra. Routers hold no business rules. Modules never import another module's repository; they call its service interface. External services are injected through Protocols so they can be swapped.
Modular monolith first: one API service. Interpretation/signaling (P3) are separate modules behind the same boundaries so they can be split into services later without changing contracts.
All endpoints and payloads follow C5/C6 exactly. OpenAPI is the generated source for `packages/api-client`.
