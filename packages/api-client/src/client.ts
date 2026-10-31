import { ApiError, type Problem } from './problem';
import type {
  ActivateModelBody,
  AuditEntry,
  Concept,
  Correction,
  CorrectionStatus,
  Entitlement,
  IssueCodeResponse,
  Me,
  ModelPackage,
  ReviewDecisionBody,
  TokenResponse,
  VocabularyResponse,
} from './types';

// Access token is held in memory only (never localStorage). The refresh token
// is an HttpOnly cookie the browser sends automatically to /v1/auth; the client
// never reads it.
export interface TokenHolder {
  get(): string | null;
  set(token: string | null): void;
}

export class ApiClient {
  private readonly baseUrl: string;
  private readonly tokens: TokenHolder;

  constructor(baseUrl: string, tokens: TokenHolder) {
    this.baseUrl = baseUrl.replace(/\/$/, '');
    this.tokens = tokens;
  }

  private async request<T>(
    method: string,
    path: string,
    options: { body?: unknown; auth?: boolean } = {},
  ): Promise<T> {
    const headers: Record<string, string> = { Accept: 'application/json' };
    if (options.body !== undefined) headers['Content-Type'] = 'application/json';
    if (options.auth !== false) {
      const token = this.tokens.get();
      if (token) headers['Authorization'] = `Bearer ${token}`;
    }

    const init: RequestInit = {
      method,
      headers,
      credentials: 'include', // send the HttpOnly refresh cookie to /v1/auth
    };
    if (options.body !== undefined) init.body = JSON.stringify(options.body);
    const res = await fetch(`${this.baseUrl}${path}`, init);

    if (res.status === 204) return undefined as T;
    if (!res.ok) {
      let problem: Problem | null = null;
      try {
        problem = (await res.json()) as Problem;
      } catch {
        problem = null;
      }
      throw new ApiError(res.status, problem?.code ?? 'unknown', problem);
    }
    const contentType = res.headers.get('Content-Type') ?? '';
    if (contentType.includes('application/json')) return (await res.json()) as T;
    return (await res.text()) as unknown as T;
  }

  // --- Auth ---
  createSession(firebaseIdToken: string, device: {
    install_id: string;
    app_version: string;
    platform: string;
  }): Promise<TokenResponse> {
    return this.request<TokenResponse>('POST', '/v1/auth/session', {
      auth: false,
      body: {
        firebase_id_token: firebaseIdToken,
        client_type: 'web',
        device: { ...device, risk_signals: {} },
      },
    });
  }

  refresh(sid: string): Promise<TokenResponse> {
    return this.request<TokenResponse>('POST', '/v1/auth/refresh', {
      auth: false,
      body: { sid },
    });
  }

  logout(): Promise<void> {
    return this.request<void>('POST', '/v1/auth/logout');
  }

  me(): Promise<Me> {
    return this.request<Me>('GET', '/v1/me');
  }

  myEntitlements(): Promise<Entitlement> {
    return this.request<Entitlement>('GET', '/v1/me/entitlements');
  }

  // --- Models ---
  listModels(): Promise<{ packages: ModelPackage[] }> {
    return this.request('GET', '/v1/admin/models');
  }

  activateModel(version: string, body: ActivateModelBody): Promise<ModelPackage> {
    return this.request('POST', `/v1/admin/models/${encodeURIComponent(version)}/activate`, {
      body,
    });
  }

  deactivateModel(version: string): Promise<ModelPackage> {
    return this.request('POST', `/v1/admin/models/${encodeURIComponent(version)}/deactivate`);
  }

  // Upload uses multipart; handled by a dedicated method (not JSON).
  async uploadModel(packageZip: File, dataKeyB64: string): Promise<ModelPackage> {
    const form = new FormData();
    form.append('package', packageZip);
    form.append('data_key_b64', dataKeyB64);
    const token = this.tokens.get();
    const res = await fetch(`${this.baseUrl}/v1/admin/models`, {
      method: 'POST',
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      credentials: 'include',
      body: form,
    });
    if (!res.ok) {
      let problem: Problem | null = null;
      try {
        problem = (await res.json()) as Problem;
      } catch {
        problem = null;
      }
      throw new ApiError(res.status, problem?.code ?? 'unknown', problem);
    }
    return (await res.json()) as ModelPackage;
  }

  // --- Vocabulary ---
  vocabulary(since = 0): Promise<VocabularyResponse> {
    return this.request('GET', `/v1/vocabulary?since=${since}`);
  }

  upsertConcept(conceptId: string, concept: Omit<Concept, 'vocabulary_version' | 'deleted'>): Promise<Concept> {
    return this.request('PUT', `/v1/admin/vocabulary/${encodeURIComponent(conceptId)}`, {
      body: concept,
    });
  }

  deleteConcept(conceptId: string): Promise<void> {
    return this.request('DELETE', `/v1/admin/vocabulary/${encodeURIComponent(conceptId)}`);
  }

  // --- Corrections ---
  listCorrections(status: CorrectionStatus): Promise<{ corrections: Correction[] }> {
    return this.request('GET', `/v1/admin/corrections?status=${status}`);
  }

  reviewCorrection(correctionId: string, body: ReviewDecisionBody): Promise<void> {
    return this.request('POST', `/v1/admin/corrections/${encodeURIComponent(correctionId)}/review`, {
      body,
    });
  }

  exportCorrections(): Promise<{ url: string }> {
    return this.request('POST', '/v1/admin/corrections/export');
  }

  // --- Orgs ---
  issueVerificationCode(orgId: string): Promise<IssueCodeResponse> {
    return this.request('POST', `/v1/orgs/${encodeURIComponent(orgId)}/verification-codes`);
  }

  // --- Audit ---
  listAudit(params: { actor?: string; action?: string } = {}): Promise<{ entries: AuditEntry[] }> {
    const q = new URLSearchParams();
    if (params.actor) q.set('actor', params.actor);
    if (params.action) q.set('action', params.action);
    const suffix = q.toString() ? `?${q.toString()}` : '';
    return this.request('GET', `/v1/admin/audit${suffix}`);
  }
}
