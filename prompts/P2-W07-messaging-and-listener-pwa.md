# W07 — Messaging service and listener PWA
Spec name: `web-messaging-listener` · Phase: P2 · Repo: lsc-web · Depends on: P1 complete; lsc-mobile M09

ROLE: Senior full-stack engineer with end-to-end-encryption experience. Contracts C6, C8 and C11 are binding.

## Objective
Add secure asynchronous messaging and let hearing people join without an account through an installable web app.

## Deliver — backend (`modules/messaging`)
- Device keys: `POST /me/devices/keys` (public key registration, rotation, revocation).
- Conversations, participants, wrapped keys per device, messages (ciphertext, nonce, key epoch, `client_msg_id`, kind), read receipts, membership checks on every call, cursor pagination, idempotency. The server never receives plaintext, conversation keys or link secrets.
- Contacts: request, accept, decline, block, report; messaging only between accepted contacts or through a link.
- Listener links (`/listener-links`, `/listener/{link_id}/...`): link id is 128-bit random, stored hashed; expiry (default 24 h), participant cap, revocation; link-scoped tokens carry only that conversation; strict rate limits; abuse report endpoint.
- FCM via firebase-admin with data-only payloads `{type, message_id}`.
- Institutional broadcast: org admins post announcements to users who opted in to that institution (consent-gated); delivered as messages.
- Retention TTLs from `config/retention.yaml`.

## Deliver — listener PWA (apps/listener)
- Opens `/c/<link_id>#<secret>`: reads the fragment, derives the wrapping key with HKDF via WebCrypto, fetches the wrapped conversation key, decrypts messages in the browser, encrypts outgoing text. Keys live in memory only.
- Chat UI in Spanish: text input, incoming transcripts with confidence/alternatives shown clearly, link expiry notice, report/leave buttons.
- Installable PWA (manifest + service worker caching only the static shell, never messages or keys).

## Rules
- Do not log or persist anything derived from message content.
- Link secrets are never sent to the server or placed in any URL sent over the network (fragment only).

## Done when (verify by reading)
- The data the server stores for a message is limited to ciphertext and routing metadata.

## Out of scope
Calls (W08), tests, running anything.
