# ADR 0002 — Raw-byte responses for model manifest and data key

- Status: accepted
- Date: 2026-10-31

## Context
The API conventions require every route to declare a `response_model`. Two W04
routes cannot: `GET /v1/models/latest` must return the package's `manifest.json`
**bytes exactly as stored** so the client verifies the original Ed25519
signature (any re-serialization through a Pydantic model would change the bytes
and break signature verification, C2); `POST /v1/models/{v}/key` returns the raw
data key.

## Decision
These two routes return a Starlette `Response` with explicit `media_type` and
`Cache-Control: no-store` instead of a `response_model`. The manifest route
serves `application/json` bytes verbatim; the key route serves the
base64-encoded key as `application/octet-stream`.

## Consequences
- Signature verification on the client stays correct because the manifest bytes
  are never reshaped by the server.
- These responses are excluded from the generated OpenAPI body schema by design;
  they are documented here and in `docs/architecture.md`.
- Both responses set `no-store`; the key is never logged or cached (SECURITY).
