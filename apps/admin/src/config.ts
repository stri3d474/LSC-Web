// Admin app configuration from Vite env (VITE_*). No secrets: Firebase web
// config values are public identifiers, not secrets.
export interface AdminConfig {
  apiBaseUrl: string;
  firebase: {
    apiKey: string;
    authDomain: string;
    projectId: string;
    appId: string;
  };
}

function required(name: string, value: string | undefined): string {
  if (!value) throw new Error(`missing required env var ${name}`);
  return value;
}

export function loadConfig(): AdminConfig {
  const env = import.meta.env;
  return {
    apiBaseUrl: required('VITE_API_BASE_URL', env.VITE_API_BASE_URL),
    firebase: {
      apiKey: required('VITE_FIREBASE_API_KEY', env.VITE_FIREBASE_API_KEY),
      authDomain: required('VITE_FIREBASE_AUTH_DOMAIN', env.VITE_FIREBASE_AUTH_DOMAIN),
      projectId: required('VITE_FIREBASE_PROJECT_ID', env.VITE_FIREBASE_PROJECT_ID),
      appId: required('VITE_FIREBASE_APP_ID', env.VITE_FIREBASE_APP_ID),
    },
  };
}
