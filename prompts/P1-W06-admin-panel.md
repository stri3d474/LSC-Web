# W06 — Admin panel (React)
Spec name: `web-admin-panel` · Phase: P1 · Repo: lsc-web · Depends on: W02–W05

ROLE: Senior React/TypeScript engineer with security awareness. Frontend conventions and C5/C6 are binding.

## Objective
Give authorized staff a secure web panel to run models, vocabulary, corrections, organizations and audits.

## Deliver (apps/admin, packages/api-client, packages/ui)
- API client generated from the OpenAPI document; `packages/ui` with shared accessible components (table, form fields, dialog, status badge).
- Auth: Firebase web sign-in with mandatory second factor, then `POST /auth/session` with `client_type: "web"`. Access token in memory only, silent refresh through the HttpOnly cookie, 15-minute idle logout, role-guarded routes (admin, reviewer, institution_admin see only what they may).
- Screens:
  1. Models: upload package + data key, validation result view, metrics from the manifest, activate/deactivate with channel and rollout, history.
  2. Vocabulary: concepts and variants editor with region/context/education tags and Spanish word forms; version indicator.
  3. Corrections queue: filters; a `SkeletonPlayer` component that animates the submitted `[T,F]` landmark sequence on a canvas (C1 layout) so reviewers can judge it; approve/reject/merge; export approved JSONL.
  4. Organizations: orgs, members, seat limits, verification-code batches (shown once, copy/download).
  5. Audit log: filter by actor/action/date, verify the hash chain client-side with a clear OK/BROKEN indicator.
  6. Aggregate metrics (counts only).
- Spanish (es-CO) typed dictionary; keyboard accessible; consistent error display from problem+json.

## Rules
- No `localStorage` tokens, no inline scripts/styles, no external origins. Render server text as text only.
- Destructive actions require confirmation and reason where the API requires it.

## Done when (verify by reading)
- Every route and API call is behind the role guard the backend also enforces.
- The app builds a strict-CSP-compatible bundle (no inline code).

## Out of scope
Listener PWA (W07), hosting configuration, tests, running anything.
