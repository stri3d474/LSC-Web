# W03 — Play Billing, entitlements, verification codes and organizations
Spec name: `web-billing-entitlements` · Phase: P1 · Repo: lsc-web · Depends on: W02

ROLE: Senior backend engineer with payments experience. Contract C6 applies.

## Objective
Grant access only from server-verified facts: Google Play purchases, organization-issued verification codes, and institutional membership.

## Deliver
- `config/products.yaml`: product_id -> tier and features list (feature ids such as interpret_basic, interpret_full_vocab, avatar, messaging, calls).
- `infra/play.py`: Play Developer API client (subscriptions v2 get/acknowledge) behind a Protocol.
- `GET /billing/products`: products plus an `account_id` = HMAC-SHA256(uid, pepper from Secret Manager) the app attaches to purchases.
- `POST /billing/play/verify {product_id, purchase_token}`: verify with Play, require package name and that the purchase's obfuscated account id equals the caller's `account_id`, acknowledge if needed, store the purchase keyed by SHA-256 of the token (never the raw token), update entitlements. Idempotent. Pending purchases (cash methods) are stored as `pending` and grant nothing.
- `POST /internal/play/rtdn`: Pub/Sub push endpoint verifying the Google OIDC token (audience + service account). Treat the message only as a trigger: re-query Play for the current state, update entitlements for renewal, cancel, expiry, hold, grace period, pause, revoke and pending-resolved events. Idempotent by message id.
- `EntitlementsService` implementing `EntitlementsPort`: derive tier, features, state (active, pending, grace, expired), `expires_at` from purchases, community verification and organization membership. `GET /me/entitlements` returns `{tier, features[], state, expires_at, as_of}`.
- Organizations: `orgs`, `org_members`, seat limits. `POST /orgs/{org_id}/verification-codes` (institution_admin, ownership checked): generate single-use, expiring, high-entropy codes stored hashed. `POST /verification/redeem {code}`: grants role `verified_deaf` and tier `community`; store only the fact, issuing org and time. Rate-limited; audit every grant.

## Rules
- The client is never a source of truth for entitlements.
- Replaying a purchase token for another account must fail.

## Done when (verify by reading)
- Every entitlement change is traceable to a Play response, a redeemed code or a membership record, and is audited.

## Out of scope
Admin UI (W06), tests, running anything.
