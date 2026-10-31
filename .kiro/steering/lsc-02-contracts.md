---
inclusion: always
---
# Contracts shared by lsc-training, lsc-mobile and lsc-web
Identical copy in all three repos. Never edit locally (working agreement rule 2).

## C1 Landmark schema (schema_version = 1)
Source of truth: `landmark_schema.json`, produced by lsc-training and shipped inside every package.
Frame vector, float32, blocks in this order:
- pose: 33 x (x,y,z)
- left_hand: 21 x (x,y,z). The signer's anatomical left hand. The image is NEVER mirrored.
- right_hand: 21 x (x,y,z)
- face_subset: N x (x,y,z). MediaPipe face-mesh indices come from `face_subset_indices` in the schema file (lips, eyebrows, eye contours, face oval). Never hardcode indices elsewhere.
- masks: 4 x {0,1} = presence of [pose, left_hand, right_hand, face]
F = 99 + 63 + 63 + 3N + 4. The schema file also holds block_order, sequence_length (default 32), pose_mirror_map, face_mirror_map.
Normalization (identical in every repo): origin = midpoint of pose landmarks 11 and 12; scale = distance between them; apply to x, y, z. If that distance < 1e-6 the frame is fully absent (all zeros, masks 0). An absent block is zeros with mask 0.
Mirroring (augmentation only): swap left/right blocks, apply mirror maps, negate x.
Sequence: one take = [T, F] float32 with T = sequence_length, resampled by linear interpolation over present blocks.
Extractors are pluggable (training: MediaPipe 0.10.9 `solutions.holistic`; mobile: MediaPipe Tasks). Cross-implementation drift is a known risk: never bake extractor-specific constants into a model.

## C2 Model package
`lsc-model-<semver>/` (zipped):
- Plain files: manifest.json, landmark_schema.json, labels.json, variant_map.json, grammar_rules.json, es_lexicon.json, motion_templates.json
- Encrypted files: backbone.tflite.enc, head.tflite.enc (only if head_mode = on_device), sequence.tflite.enc (P2, optional)
manifest.json (NO floats anywhere; ratios are integer basis points):
- package_version, profile ("basic"|"full"), schema_version, dataset_version, created_at (UTC ISO-8601), min_app_version, head_mode ("on_device"|"server")
- files: [{role: "backbone"|"head"|"sequence", name, sha256_plain, sha256_cipher, nonce_b64}]
- plain_files: [{name, sha256}]
- backbone: {input_shape: [1,T,F], embedding_dim}; head: {num_classes}; sequence (P2): {window, stride, blank_index, nmm_labels[]}
- segmentation: {smooth_ms, rest_speed_milli, rest_wrist_y_milli, min_rest_ms, min_take_ms, merge_gap_ms}
- encryption: {alg: "AES-256-GCM", key_id: "k-<package_version>"}
- metrics: {unseen_signer_acc_bp, ctr_acc_bp, dct_acc_bp, gate_passed}
- signature: {alg: "Ed25519", key_id, value_b64}
Canonical JSON for signing = manifest without `signature`, keys sorted, separators (",",":"), UTF-8.
Crypto: AES-256-GCM, random 96-bit nonce per file, tag appended to ciphertext, AAD = utf8("<package_version>|<role>"). One random 256-bit data key per package version, released only by the API (C6), never stored in the package.
Client rules: verify signature (public keys pinned by key_id) BEFORE downloading blobs; verify sha256_cipher after download; reject a package_version lower than the installed one (anti-downgrade; rollbacks ship as new higher versions); decrypt in memory only.
labels.json: [{class_index, variant_id, concept_id, gloss}]
variant_map.json: {concepts: [{concept_id, gloss, es_text, variants: [{variant_id, region_codes[], contexts[], education_level}]}]}

## C3 Grammar rules and tokens (grammar_rules.json, es_lexicon.json)
Token: {concept_id, variant_id, gloss, confidence (0..1), nmm[], start_ms, end_ms}. NMM values: brow_raise, brow_furrow, head_shake, head_nod, mouth_open, mouth_pursed.
grammar_rules.json: {rules_version, direction: "lsc_to_es"|"es_to_lsc", rules: [{id, priority, pattern: [Matcher], actions: [Action]}]}
- Matcher: {concept_id? | gloss? | any?, nmm_any?[], nmm_none?[], capture?, optional?}
- Action: {op:"emit", text (may contain {capture})} | {op:"reorder", order:[capture]} | {op:"mood", value:"question"|"negation"|"statement"} | {op:"drop", capture}
Engine = pure function (tokens, rules, variant_map) -> text. Highest priority first, non-overlapping matches, unmatched tokens fall back to variant_map es_text, final pass for capitalization and punctuation (¿ ?). No I/O.
es_lexicon.json: {entries: [{concept_id, es_forms[]}]}, longest-match first. Used for es_to_lsc.

## C4 Motion templates (motion_templates.json)
{template_version, fps: 30, variants: {<variant_id>: {frames, block_order: ["pose","left_hand","right_hand","face_subset"], data_f16_b64}}}. Data is normalized (C1 space), without masks, float16 little-endian, base64.

## C5 API conventions, auth, roles
- Base /v1, JSON UTF-8 snake_case, ULID ids, UTC ISO-8601 times, cursor pagination (limit <= 100), `Idempotency-Key` header on creating POSTs. Errors: RFC 9457 problem+json with a stable `code`.
- Access token: JWT ES256, 15 min. Claims: iss, aud, sub, sid, iat, exp, kid, roles[], tier, mfa. JWKS at /.well-known/jwks.json. Multiple active kid values allowed (rotation).
- Refresh token: opaque 256-bit random, stored hashed, rotates on every use, reuse detection revokes the whole session family (sid). Mobile gets it in the JSON body; web clients get it as HttpOnly Secure SameSite=Strict cookie with Path=/v1/auth.
- Roles: user, verified_deaf, professional, institution_member, institution_admin, reviewer, admin. Tiers: free, community, professional, institutional. The client never sends roles or tier.

## C6 Endpoint catalog (under /v1, Bearer auth unless marked public)
- Auth: POST /auth/session (public; firebase_id_token, client_type "mobile"|"web", device{install_id, app_version, platform, risk_signals{rooted,emulator,debugger,hooked}}) · POST /auth/refresh · POST /auth/logout · GET /.well-known/jwks.json (root path, public)
- Me: GET /me · GET /me/entitlements ({tier, features[], state, expires_at, as_of}) · GET /me/data-export · DELETE /me · POST /me/devices/keys (P2)
- Consent: GET /consents/purposes (public) · GET /consents · PUT /consents/{purpose}
- Billing: GET /billing/products · POST /billing/play/verify · POST /internal/play/rtdn (Pub/Sub OIDC only)
- Verification: POST /verification/redeem · POST /orgs/{org_id}/verification-codes (institution_admin)
- Models: GET /models/latest?app_version&schema_version · GET /models/{v}/download · POST /models/{v}/key · POST /models/{v}/head:infer (head_mode=server only)
- Community: GET /vocabulary?since= · POST /corrections
- Admin (roles admin|reviewer, MFA required): /admin/models · /admin/vocabulary · /admin/corrections · /admin/orgs · /admin/audit
- P2: /conversations · /conversations/{id}/messages · /contacts · /listener-links · /listener/{link_id}/... (link-scoped)
- P3: POST /calls · POST /calls/{id}/ws-ticket · WS /calls/{id}/signal · GET /calls/ice-servers · WS /calls/{id}/stt

## C7 Data model (Firestore collections; Cloud Storage buckets)
users · sessions (refresh families) · consents (append-only) · entitlements · purchases · orgs · org_members · verification_codes · model_packages · concepts · variants · corrections · audit_log (hash-chained) · P2: conversations, messages (ciphertext only), contacts, listener_links, device_keys · P3: calls (metadata only).
Buckets: `models` (encrypted blobs), `datasets` (contributed landmarks under pseudonymous ids, never user video), `exports` (short-lived).
Secret Manager: JWT signing keys, model data keys (`model-key-<version>`), pseudonymization pepper, Play/Firebase service credentials.

## C8 Consent purposes (versioned, separate, revocable)
terms_of_service · privacy_policy · landmark_contribution · message_landmark_training (P2) · call_landmark_recording (P3) · aggregate_analytics.
Record: {purpose, version, granted, at, guardian_authorization?}. Users under 18 need guardian authorization for every purpose except core interpretation.

## C9 Mobile native channels
- EventChannel `lsc/landmarks`: Uint8List little-endian = int32 schema_version, int32 F, int64 timestamp_us, then F float32 (C1 layout, RAW, not yet normalized; masks set).
- MethodChannel `lsc/engine`: start({camera, target_fps, width, height}), stop().
- PlatformView `lsc/camera_preview`.
- MethodChannel `lsc/security`: getIntegrityToken(nonce), wrapKey(bytes), unwrapKey(bytes), deviceSignals(), setSecureScreen(bool). The Keystore wrapping key is AES-GCM, non-exportable (StrongBox when available), alias `lsc_wrap_v1`.

## C10 Realtime envelope (P3)
WebSocket frames: {v:1, type, seq, ts_ms, payload}. Types: ping, signal.offer, signal.answer, signal.ice, call.state, caption.partial, caption.final, avatar.glosses, stt.partial, stt.final. Captions between peers travel on a WebRTC DataChannel, not through the server. WS auth: single-use 60 s ticket from POST /calls/{id}/ws-ticket, sent as first message (never in the URL).

## C11 Messaging end-to-end encryption (P2)
- Each app install creates an X25519 keypair in Keystore-protected storage and registers the public key (POST /me/devices/keys).
- A conversation has one AES-256-GCM key, generated by its creator and wrapped per participant device using X25519 + HKDF-SHA256. The server stores only wrapped keys and ciphertext.
- Listener link (hearing user, no account): URL `https://<listener-host>/c/<link_id>#<secret>`. The 256-bit secret exists only in the URL fragment; HKDF(secret) wraps the conversation key for that link. The server never sees the secret.
