import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import { setAuthHooks } from '../api/client';
import { endpoints } from '../api/endpoints';
import type { MeResponse } from '../api/types';

/** Kept verbatim — retained E2E specs seed this key. */
const STORAGE_KEY = 'smart-pid-token';

/**
 * The JWT lives in localStorage, not sessionStorage: sessionStorage is
 * per-tab, so every new tab forced operators to re-authenticate even though
 * the token was still valid for hours. localStorage is shared across tabs of
 * the same origin. The one-time migration adopts tokens issued before this
 * change so the fix itself does not force one more re-login.
 */
function readStoredToken(): string | null {
  const persisted = localStorage.getItem(STORAGE_KEY);
  if (persisted !== null) return persisted;
  const legacy = sessionStorage.getItem(STORAGE_KEY);
  if (legacy === null) return null;
  localStorage.setItem(STORAGE_KEY, legacy);
  sessionStorage.removeItem(STORAGE_KEY);
  return legacy;
}

export type AuthUser = MeResponse;

export interface AuthContextValue {
  token: string | null;
  /** null until GET /auth/me resolves — deny-by-default for role checks. */
  user: AuthUser | null;
  isAuthenticated: boolean;
  login(username: string, password: string): Promise<void>;
  logout(): void;
  /** §11: refetched on any 403 (role may have changed mid-session). */
  refreshUser(): Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export interface AuthProviderProps {
  children?: ReactNode;
  /** Phase 4 wires this to the pt-BR toast "sem permissão" (§11). */
  onPermissionDenied?: () => void;
}

export function AuthProvider({ children, onPermissionDenied }: AuthProviderProps) {
  const [token, setToken] = useState<string | null>(readStoredToken);
  const [user, setUser] = useState<AuthUser | null>(null);
  const tokenRef = useRef<string | null>(token);
  tokenRef.current = token;

  const refreshUser = useCallback(async () => {
    if (tokenRef.current === null) {
      setUser(null);
      return;
    }
    const me = await endpoints.me();
    setUser(me);
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem(STORAGE_KEY);
    sessionStorage.removeItem(STORAGE_KEY); // legacy sessions issued before the move
    tokenRef.current = null;
    setToken(null);
    setUser(null);
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    const res = await endpoints.login(username, password);
    localStorage.setItem(STORAGE_KEY, res.access_token);
    // The immediate /auth/me below must already carry the fresh token.
    tokenRef.current = res.access_token;
    setToken(res.access_token);
    const me = await endpoints.me();
    setUser(me);
  }, []);

  // Single api↔auth coupling point: token injection + §11 401/403 side effects.
  //
  // Wired synchronously in the render body, NOT a `useEffect`. `AuthProvider`
  // wraps the whole tree (App.tsx), including every route/query component
  // that fires its own request on mount. React commits effects bottom-up —
  // a descendant's mount effect runs BEFORE this component's own effects —
  // so on a cold load/reload a child's very first fetch could race ahead of
  // an effect-based registration and see the pre-wired `getToken: () => null`
  // default from api/client.ts, draw a real (but spurious) 401 for a session
  // that IS valid, and then this component's real `onUnauthorized: () => logout()`
  // — wired moments later by the time that response lands — incorrectly wipes
  // it. Registering here, during render, guarantees the hooks are live before
  // React even begins mounting any descendant.
  setAuthHooks({
    getToken: () => tokenRef.current,
    onUnauthorized: () => logout(),
    onForbidden: () => {
      onPermissionDenied?.();
      void refreshUser().catch(() => {
        /* refresh failure surfaces via the failing call itself */
      });
    },
  });

  // Session restore: storage has a token but this mount has no user yet.
  useEffect(() => {
    if (token !== null && user === null) {
      void refreshUser().catch(() => {
        /* a 401 here already triggered logout via onUnauthorized */
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- rehydrate per token change only
  }, [token]);

  const value = useMemo<AuthContextValue>(
    () => ({ token, user, isAuthenticated: token !== null, login, logout, refreshUser }),
    [token, user, login, logout, refreshUser],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}