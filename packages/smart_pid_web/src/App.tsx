import { Suspense, useCallback, useMemo, useState, type ReactNode } from 'react';
import { QueryClient, QueryClientProvider, useQueryClient } from '@tanstack/react-query';
import { BrowserRouter, Navigate, Outlet, Route, Routes } from 'react-router-dom';
import { AppShell } from '@/app/AppShell';
import { appRoutes } from '@/app/routes';
import { AuthProvider, useAuth } from '@/auth/AuthContext';
import { RouteGuard } from '@/auth/RouteGuard';
import { LoadingState } from '@/components/MissingState';
import { Toaster, toast } from '@/components/Toast';
import { TooltipProvider } from '@/components/Tooltip';
import { LoginPage } from '@/pages/LoginPage';
import { RealtimeProvider } from '@/realtime/RealtimeProvider';
import { createResyncRunner } from '@/realtime/resync';
import { ThemeProvider } from '@/theme/ThemeProvider';

/**
 * Composition root. Provider order is load-bearing: the realtime socket needs
 * the auth token and the query client (§7 resync primes canonical keys), and a
 * 4401 close must be able to force the login route — so it sits inside both.
 */

/**
 * Secondary routes are code-split (see `app/routes.tsx`), so the shell needs
 * one Suspense boundary. It sits INSIDE `AppShell` — the top bar and the
 * palette must stay on screen while a route chunk arrives.
 */
function ProtectedLayout() {
  return (
    <RouteGuard>
      <AppShell>
        <Suspense fallback={<LoadingState label="Carregando página…" bars={3} />}>
          <Outlet />
        </Suspense>
      </AppShell>
    </RouteGuard>
  );
}

function RealtimeSession({ children }: { children: ReactNode }) {
  const { token, logout } = useAuth();
  const queryClient = useQueryClient();
  const resync = useMemo(() => createResyncRunner({ queryClient }), [queryClient]);
  return (
    <RealtimeProvider token={token} resync={resync} onAuthExpired={logout}>
      {children}
    </RealtimeProvider>
  );
}

export function App() {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } },
      }),
  );
  const onPermissionDenied = useCallback(() => {
    toast({
      title: 'Sem permissão',
      description: 'Sua conta não tem acesso a esta ação.',
      tone: 'warn',
    });
  }, []);

  return (
    <TooltipProvider delayDuration={300}>
      <ThemeProvider>
      <QueryClientProvider client={queryClient}>
        <AuthProvider onPermissionDenied={onPermissionDenied}>
          <BrowserRouter>
            <RealtimeSession>
              <Routes>
                <Route path="/login" element={<LoginPage />} />
                <Route element={<ProtectedLayout />}>
                  {appRoutes.map(({ path, element: Element, adminOnly }) => (
                    <Route
                      key={path}
                      path={path}
                      element={
                        adminOnly === true ? (
                          <RouteGuard adminOnly>
                            <Element />
                          </RouteGuard>
                        ) : (
                          <Element />
                        )
                      }
                    />
                  ))}
                  {/* Unknown path under a session lands on the dashboard; without
                      one it inherits ProtectedLayout's guard → /login. */}
                  <Route path="*" element={<Navigate to="/" replace />} />
                </Route>
              </Routes>
            </RealtimeSession>
            <Toaster />
          </BrowserRouter>
        </AuthProvider>
      </QueryClientProvider>
    </ThemeProvider>
    </TooltipProvider>
  );
}
