import type { TokenHolder } from '@lsc/api-client';

// In-memory token holder: the access token lives only in a closure variable,
// never in localStorage/sessionStorage (frontend conventions). It is lost on
// reload, which is fine because the HttpOnly refresh cookie re-establishes it.
export function createTokenHolder(): TokenHolder {
  let token: string | null = null;
  return {
    get: () => token,
    set: (value) => {
      token = value;
    },
  };
}
