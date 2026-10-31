---
inclusion: always
---
# lsc-web — Tech
## Backend (apps/api)
- Python 3.12, FastAPI, Pydantic v2 (+ pydantic-settings), Uvicorn. Pin exact versions.
- GCP clients: `google-cloud-firestore`, `google-cloud-storage`, `google-cloud-secret-manager`, `google-cloud-pubsub`, `google-cloud-speech` (P3), `google-api-python-client` (Play Developer + Play Integrity APIs), `firebase-admin` (ID token verification, FCM). `onnxruntime` (CPU) only for the optional server head. JWT: `PyJWT[crypto]`. Crypto: `cryptography`. Logging: `structlog`. IDs: `python-ulid`.
- Runs stateless on Cloud Run: no local disk state, config from environment, secrets from Secret Manager.
## Frontend (apps/admin, apps/listener, packages/*)
- pnpm workspaces, TypeScript (strict), React 18, Vite, React Router, TanStack Query, Zod, react-hook-form, Tailwind CSS. API types generated from OpenAPI with `openapi-typescript` into `packages/api-client`. Listener PWA via `vite-plugin-pwa`; E2E crypto via WebCrypto only (no custom crypto libs).
- Anything else requires a dependency proposal. Pin exact versions.
