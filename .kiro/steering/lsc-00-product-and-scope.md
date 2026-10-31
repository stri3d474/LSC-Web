---
inclusion: always
---
# LSC Interpreter — Product and Working Agreement

## Product
Android-first app (Flutter) that interprets Colombian Sign Language (LSC) into Spanish text and Spanish text into LSC (animated avatar). Users are Deaf Colombians. Paying customers are hearing institutions (hospitals, schools, government offices). One developer: strong in Python, new to Flutter and TFLite.

Hard principle: interpretation runs on-device. No external LLM or third-party AI API anywhere in the interpretation path. The backend exists only for accounts, billing/entitlements, model distribution, community corrections, messaging (P2) and call signaling (P3).

## Repositories (separate; they meet only through lsc-02-contracts.md)
- lsc-training: Python/PyTorch pipeline. Videos -> landmarks -> trained model -> signed, encrypted model package.
- lsc-mobile: Flutter Android app (Kotlin native module for camera + MediaPipe).
- lsc-web: FastAPI backend + React admin panel + React listener PWA.

## Phases (implement ONLY the phase named by the active spec)
- P1 local interpretation (isolated signs -> grammar -> Spanish text; text -> avatar)
- P2 asynchronous messaging Deaf <-> hearing
- P3 live video calls
Later-phase hooks are interfaces only. Never stub them with fake logic.

## Tiers (computed server-side only)
free · community (verified Deaf users, free) · professional (hearing individuals, paid) · institutional (custom).

## Working agreement (always follow)
1. SCOPE IS DEVELOPMENT ONLY. Write source code, config schemas and docs. Do NOT write tests, CI/CD files, Dockerfiles, IaC or deployment/run scripts. Do NOT run, build, install or launch anything unless the user explicitly asks.
2. CONTRACTS ARE LAW. Never change a name, field, path, format or number defined in lsc-02-contracts.md. If a task needs a change, stop and output a "CONTRACT CHANGE PROPOSAL" (what, why, impacted repos) instead of coding around it.
3. DEPENDENCIES: use only those listed in tech.md, at exact pinned versions. If another is needed, propose it with a reason; never add silently.
4. ONE TASK AT A TIME: do exactly what the active spec asks. Put discoveries outside scope in a final "Follow-ups" list.
5. NO FAKE COMPLETENESS: no placeholder logic, no sample data inside production code paths. If blocked, state precisely what is missing.
6. NEVER hardcode secrets, keys, URLs or project ids. Read them from typed configuration.
7. LANGUAGE: code, identifiers, comments and docs in English. User-facing app/web text in Spanish (es-CO) through localization files.
8. Security-relevant code carries a `SECURITY(<control-id>)` comment and an entry in docs/security/controls-matrix.md.
9. Prefer small single-purpose modules, explicit types, and docstrings stating inputs, outputs and failure modes.
