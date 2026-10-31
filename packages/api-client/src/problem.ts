// RFC 9457 problem+json shape returned by the backend on every error.
export interface Problem {
  readonly type: string;
  readonly title: string;
  readonly status: number;
  readonly code: string;
  readonly instance: string | null;
}

// Thrown by the client when a request fails. Carries the stable `code` so the
// UI can branch on it and show a localized message (never the server text).
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly problem: Problem | null;

  constructor(status: number, code: string, problem: Problem | null) {
    super(`api error ${status} (${code})`);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.problem = problem;
  }
}
