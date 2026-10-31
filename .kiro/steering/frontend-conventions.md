---
inclusion: fileMatch
fileMatchPattern: ["apps/admin/**/*.ts", "apps/admin/**/*.tsx", "apps/listener/**/*.ts", "apps/listener/**/*.tsx", "packages/**/*.ts", "packages/**/*.tsx"]
---
# Frontend conventions
- Strict TypeScript, no `any`. Data fetching only through the generated API client + TanStack Query. Forms validated with Zod on top of server validation.
- Never use `dangerouslySetInnerHTML`, `eval`, or inline scripts/styles (the CSP forbids them). Render all server text as text.
- Tokens: access token in memory only; never `localStorage`/`sessionStorage`. Refresh happens through the HttpOnly cookie.
- All UI strings in a typed Spanish (es-CO) dictionary. Accessible components (labels, focus order, contrast, keyboard use).
- No third-party scripts, fonts or analytics loaded from external origins.
