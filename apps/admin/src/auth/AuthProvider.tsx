import { ApiClient, type Me, type Role } from '@lsc/api-client';
import type { ReactNode } from 'react';
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { loadConfig } from '../config';
import { createFirebase } from './firebase';
import { createTokenHolder } from './tokenHolder';

interface AuthState {
  me: Me | null;
  sid: string | null;
  status: 'loading' | 'signed_out' | 'signed_in' | 'mfa_required';
}

interface AuthContextValue extends AuthState {
  api: ApiClient;
  signIn: () => Promise<void>;
  signOut: () => Promise<void>;
  hasRole: (...roles: Role[]) => boolean;
}

const AuthContext = createContext<AuthContextValue | null>(null);

// Idle timeout: 15 minutes with no user interaction forces a sign-out.
const IDLE_MS = 15 * 60 * 1000;
// Access tokens last 15 min; refresh a minute early.
const REFRESH_MS = 14 * 60 * 1000;

export function AuthProvider({ children }: { children: ReactNode }) {
  const config = useMemo(() => loadConfig(), []);
  const tokens = useMemo(() => createTokenHolder(), []);
  const api = useMemo(() => new ApiClient(config.apiBaseUrl, tokens), [config.apiBaseUrl, tokens]);
  const firebase = useMemo(() => createFirebase(config), [config]);

  const [state, setState] = useState<AuthState>({ me: null, sid: null, status: 'loading' });
  const sidRef = useRef<string | null>(null);
  const idleTimer = useRef<number | undefined>(undefined);
  const refreshTimer = useRef<number | undefined>(undefined);

  const signOut = useCallback(async () => {
    try {
      await api.logout();
    } catch {
      // ignore network errors on logout
    }
    tokens.set(null);
    sidRef.current = null;
    window.clearTimeout(idleTimer.current);
    window.clearTimeout(refreshTimer.current);
    setState({ me: null, sid: null, status: 'signed_out' });
  }, [api, tokens]);

  const scheduleRefresh = useCallback(() => {
    window.clearTimeout(refreshTimer.current);
    refreshTimer.current = window.setTimeout(async () => {
      const sid = sidRef.current;
      if (!sid) return;
      try {
        const res = await api.refresh(sid);
        tokens.set(res.access_token);
        scheduleRefresh();
      } catch {
        await signOut();
      }
    }, REFRESH_MS);
  }, [api, tokens, signOut]);

  const resetIdle = useCallback(() => {
    window.clearTimeout(idleTimer.current);
    idleTimer.current = window.setTimeout(() => {
      void signOut();
    }, IDLE_MS);
  }, [signOut]);

  const signIn = useCallback(async () => {
    const user = await firebase.signIn();
    if (!firebase.hasSecondFactor(user)) {
      setState((s) => ({ ...s, status: 'mfa_required' }));
      return;
    }
    const idToken = await user.getIdToken();
    const session = await api.createSession(idToken, {
      install_id: `admin-web-${user.uid}`,
      app_version: 'admin-1',
      platform: 'web',
    });
    tokens.set(session.access_token);
    sidRef.current = session.sid;
    const me = await api.me();
    setState({ me, sid: session.sid, status: 'signed_in' });
    scheduleRefresh();
    resetIdle();
  }, [api, firebase, tokens, scheduleRefresh, resetIdle]);

  // On first load there is no in-memory token; the user must sign in.
  useEffect(() => {
    setState((s) => (s.status === 'loading' ? { ...s, status: 'signed_out' } : s));
  }, []);

  // Track activity to reset the idle timer only while signed in.
  useEffect(() => {
    if (state.status !== 'signed_in') return;
    const handler = () => resetIdle();
    const events = ['pointerdown', 'keydown', 'visibilitychange'];
    events.forEach((e) => window.addEventListener(e, handler));
    return () => events.forEach((e) => window.removeEventListener(e, handler));
  }, [state.status, resetIdle]);

  const hasRole = useCallback(
    (...roles: Role[]) => {
      const mine = state.me?.roles ?? [];
      return roles.some((r) => mine.includes(r));
    },
    [state.me],
  );

  const value: AuthContextValue = { ...state, api, signIn, signOut, hasRole };
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
