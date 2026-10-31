# W08 — Call signaling, ICE credentials, speech-to-text and rooms
Spec name: `web-live-calls` · Phase: P3 · Repo: lsc-web · Depends on: P2 complete; lsc-mobile M10

ROLE: Senior backend/real-time engineer. Contracts C6 and C10 are binding.

## Objective
Provide the minimal server side for WebRTC calls and add a no-install web participant. Captions travel peer-to-peer; the server never sees call content.

## Deliver — backend (`modules/calls`)
- `POST /calls` (create call/room), `POST /calls/{id}/ws-ticket` (single-use, 60 s, bound to user/call), `WS /calls/{id}/signal` relaying `signal.offer/answer/ice` and `call.state`; authenticate with the ticket as the first message; enforce room membership and a participant cap; close idle sockets.
- `GET /calls/ice-servers`: time-limited credentials through an `IceServerProvider` Protocol (note: Google offers only public STUN; TURN must be self-hosted (coturn) or a managed provider; implement the provider-agnostic interface and a time-limited-HMAC credential generator for coturn).
- `WS /calls/{id}/stt`: streaming Google Speech-to-Text (`es-CO`) for the hearing participant's audio; forward `stt.partial/stt.final` text only; audio is never stored or logged; per-call duration and rate limits.
- Institutional rooms: persistent room links created by org admins; guests join with a short-lived ticket without an account.
- Human-interpreter assist role: joins as a visible participant; all other participants must receive a `call.state` event naming that a monitor is present (the app shows a persistent indicator).
- Call records contain only metadata (participants, org, start/end). Abuse reports and repeat-offender suspension through custom claims.
- Scale: stateless signaling with room state in Firestore; Pub/Sub for cross-instance fan-out and reconnect replay.

## Deliver — listener PWA
- Join-by-link page, camera/microphone permissions, WebRTC session with the app, live captions on the DataChannel (large text), speech input sent to the STT socket (fallback: typed text), consent dialog for recording, report button, persistent "interpreter present" indicator.

## Rules
- Tickets and ICE credentials are single-purpose, short-lived and never logged.
- No media or captions are routed through or stored on the server.

## Done when (verify by reading)
- Server components touch only signaling, credentials, STT text and metadata, exactly as C10 describes.

## Out of scope
Interpretation models (on device), tests, running anything.
