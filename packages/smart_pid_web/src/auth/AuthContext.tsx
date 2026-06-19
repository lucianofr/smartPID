import { createContext, useContext, useMemo, useState, type ReactNode } from 'react';
import { apiPost, setTokenGetter } from '../api/client';

const STORAGE_KEY = 'smart-pid-token';

interface LoginResponse {
  access_token: string;
  token_type: string;
}
interface AuthCtx {
  token: string | null;
  isAuthenticated: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
}
const Ctx = createContext<AuthCtx | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(() => sessionStorage.getItem(STORAGE_KEY));
  setTokenGetter(() => token);

  const login = async (username: string, password: string) => {
    const res = await apiPost<LoginResponse>('/auth/login', { username, password });
    sessionStorage.setItem(STORAGE_KEY, res.access_token);
    setToken(res.access_token);
  };
  const logout = () => {
    sessionStorage.removeItem(STORAGE_KEY);
    setToken(null);
  };
  const value = useMemo<AuthCtx>(
    () => ({ token, isAuthenticated: token !== null, login, logout }),
    [token],
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAuth(): AuthCtx {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
