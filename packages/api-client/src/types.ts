// Typed request/response models mirroring the backend contracts (C5/C6).
//
// These are maintained to match the FastAPI Pydantic schemas. When the backend
// is running, `pnpm --filter @lsc/api-client generate` regenerates a
// `schema.ts` from its OpenAPI document; these hand-written types are the
// stable surface the admin app imports in the meantime.

export type Tier = 'free' | 'community' | 'professional' | 'institutional';
export type Role =
  | 'user'
  | 'verified_deaf'
  | 'professional'
  | 'institution_member'
  | 'institution_admin'
  | 'reviewer'
  | 'admin';

export interface TokenResponse {
  access_token: string;
  token_type: 'Bearer';
  expires_in: number;
  sid: string;
  refresh_token?: string | null;
}

export interface Me {
  uid: string;
  age_band: string;
  roles: Role[];
  status: string;
  created_at: string;
}

export interface Entitlement {
  tier: Tier;
  features: string[];
  state: string;
  expires_at: string | null;
  as_of: string;
}

// --- Models ---
export interface ModelPackage {
  package_version: string;
  profile: 'basic' | 'full';
  schema_version: number;
  min_app_version: string;
  head_mode: 'on_device' | 'server';
  status: 'draft' | 'active' | 'inactive';
  channel: 'stable' | 'beta' | null;
  rollout_bp: number;
  created_at: string;
  activated_at: string | null;
}

export interface ActivateModelBody {
  channel: 'stable' | 'beta';
  rollout_bp: number;
  min_app_version?: string | null;
}

// --- Vocabulary ---
export interface Variant {
  variant_id: string;
  region_codes: string[];
  contexts: string[];
  education_level: 'school' | 'university' | 'unspecified';
  tier: 'basic' | 'full';
}

export interface Concept {
  concept_id: string;
  gloss: string;
  es_text: string;
  es_forms: string[];
  variants: Variant[];
  vocabulary_version: number;
  deleted: boolean;
}

export interface VocabularyResponse {
  vocabulary_version: number;
  concepts: Concept[];
}

// --- Corrections ---
export type CorrectionStatus = 'pending' | 'approved' | 'rejected' | 'merged';

export interface Correction {
  correction_id: string;
  status: CorrectionStatus;
  predicted_variant_id: string;
  proposed_variant_id: string | null;
  region: string;
  context: string;
  education_level: string;
  created_at: string;
}

export interface ReviewDecisionBody {
  approve: boolean;
  reason?: string | null;
}

// --- Audit ---
export interface AuditEntry {
  entry_id: string;
  actor: string;
  action: string;
  target: string | null;
  metadata: Record<string, unknown>;
  at: string;
  prev_hash: string;
  entry_hash: string;
}

// --- Orgs ---
export interface IssueCodeResponse {
  code: string;
}
