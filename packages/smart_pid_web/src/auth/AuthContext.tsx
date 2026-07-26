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
  const [token, setToken] = useState<string | null>(() => sessionStorage.getItem(STORAGE_KEY));
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
    sessionStorage.removeItem(STORAGE_KEY);
    tokenRef.current = null;
    setToken(null);
    setUser(null);
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    const res = await endpoints.login(username, password);
    sessionStorage.setItem(STORAGE_KEY, res.access_token);
    // The immediate /auth/me below must already carry the fresh token.
    tokenRef.current = res.access_token;
    setToken(res.access_token);
    const me = await endpoints.me();
    setUser(me);
  }, []);

  // Single api↔auth coupling point: token injection + §11 401/403 side effects.
  useEffect(() => {
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
  }, [logout, refreshUser, onPermissionDenied]);

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