# W04 — Model registry, distribution and key release
Spec name: `web-model-registry` · Phase: P1 · Repo: lsc-web · Depends on: W02, W03

ROLE: Senior backend engineer with applied-cryptography and supply-chain focus. Contract C2 is binding.

## Objective
Store signed model packages, serve the right one to each client, and release the data key only to trusted, entitled installs.

## Deliver
- `POST /admin/models` (admin + MFA, multipart with size cap): receive the package zip and, as a separate field, the data key. Validate zip structure, manifest fields (C2), Ed25519 signature against `MANIFEST_VERIFY_KEYS` from configuration, every file hash, schema compatibility. Store blobs in the `models` bucket under `packages/<version>/`, keep the manifest bytes exactly as received, store the data key in Secret Manager as `model-key-<version>` (never Firestore), register `model_packages/{version}` as `draft`. Zip-slip and decompression-bomb protections required.
- Admin lifecycle: `activate` (channel stable|beta, rollout percentage, min_app_version), `deactivate`, list/get. Rollbacks are done by activating a previously re-issued higher version (the client rejects lower versions).
- `GET /models/latest?app_version&schema_version`: choose the eligible active package for the caller (profile from entitlements features, deterministic rollout bucket from uid), return the stored manifest bytes unchanged.
- `GET /models/{v}/download`: short-lived (<= 10 min) V4 signed URLs for each blob; auth required; entitlement for the package profile checked.
- `POST /models/{v}/key {integrity_token, nonce, install_id}`: verify the Play Integrity token via the Play Integrity API (nonce matches, package name, recognized app, licensed, device integrity verdict) according to `INTEGRITY_ENFORCEMENT`; rate-limit per user/install/version; audit each release; respond `Cache-Control: no-store` with the key.
- Optional `POST /models/{v}/head:infer` behind `SERVER_HEAD_ENABLED`: load `head.onnx` (CPU onnxruntime, session reused), accept a bounded base64 embedding, return top-k class probabilities; never log inputs.

## Rules
- The key route fails closed on any verification failure.
- Signed URLs and keys never appear in logs.

## Done when (verify by reading)
- Only the package's manifest signature (not server trust) establishes authenticity; the server re-verifies before activation.

## Out of scope
Producing packages (lsc-training), admin UI, tests, running anything.
