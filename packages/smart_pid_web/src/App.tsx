import { lazy, Suspense, useState } from 'react';
import { QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { queryClient } from './api/queryClient';
import { AuthProvider, useAuth } from './auth/AuthContext';
import { LoginPage } from './auth/LoginPage';
import { RequireAuth } from './auth/RequireAuth';
import { RealtimeProvider } from './realtime/RealtimeProvider';
import { ThemeProvider } from './theme/ThemeProvider';
import { DashboardPage } from './pages/DashboardPage';
import { SettingsPage } from './pages/SettingsPage';
import { ConnectionPage } from './pages/ConnectionPage';
import { AppShell } from './components/shell/AppShell';
import { AlarmPanel } from './features/alarms/AlarmPanel';
import { WelcomeDialog } from './features/projects/WelcomeDialog';
import './theme/tokens.css';
import './theme/themes.css';

// Heavy/rare surfaces are code-split so the dashboard entry stays within the
// app-page JS budget (see scripts/check-bundle.mjs, §12 perf budget).
const ExecutiveDashboardPage = lazy(() =>
  import('./pages/ExecutiveDashboardPage').then((m) => ({ default: m.ExecutiveDashboardPage })),
);
const MultiTrendPage = lazy(() =>
  import('./pages/MultiTrendPage').then((m) => ({ default: m.MultiTrendPage })),
);
const SimulatorPage = lazy(() =>
  import('./pages/SimulatorPage').then((m) => ({ default: m.SimulatorPage })),
);
const ProjectsPage = lazy(() =>
  import('./pages/ProjectsPage').then((m) => ({ default: m.ProjectsPage })),
);

function RouteFallback() {
  return <div role="status" aria-live="polite" className="p-8 text-muted-foreground" />;
}

function Shell() {
  const { token } = useAuth();
  const [welcomeSeen, setWelcomeSeen] = useState(
    () => sessionStorage.getItem('spid.welcome-seen') === '1',
  );
  const showWelcome = token != null && !welcomeSeen;
  const dismissWelcome = () => {
    sessionStorage.setItem('spid.welcome-seen', '1');
    setWelcomeSeen(true);
  };
  return (
    <RealtimeProvider token={token}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route
          path="/"
          element={
            <RequireAuth>
              <DashboardPage />
            </RequireAuth>
          }
        />
        <Route
          path="/executive"
          element={
            <RequireAuth>
              <Suspense fallback={<RouteFallback />}>
                <ExecutiveDashboardPage />
              </Suspense>
            </RequireAuth>
          }
        />
        <Route
          path="/multitrend"
          element={
            <RequireAuth>
              <Suspense fallback={<RouteFallback />}>
                <MultiTrendPage />
              </Suspense>
            </RequireAuth>
          }
        />
        <Route
          path="/simulator"
          element={
            <RequireAuth>
              <Suspense fallback={<RouteFallback />}>
                <SimulatorPage />
              </Suspense>
            </RequireAuth>
          }
        />
        <Route
          path="/alarms"
          element={
            <RequireAuth>
              <AppShell opcDown={false}>
                <AlarmPanel />
              </AppShell>
            </RequireAuth>
          }
        />
        <Route
          path="/settings"
          element={
            <RequireAuth>
              <SettingsPage />
            </RequireAuth>
          }
        />
        <Route
          path="/connection"
          element={
            <RequireAuth>
              <ConnectionPage />
            </RequireAuth>
          }
        />
        <Route
          path="/projects"
          element={
            <RequireAuth>
              <Suspense fallback={<RouteFallback />}>
                <ProjectsPage />
              </Suspense>
            </RequireAuth>
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
      {showWelcome && <WelcomeDialog open onDismiss={dismissWelcome} />}
    </RealtimeProvider>
  );
}

export function App() {
  return (
    <ThemeProvider>
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <BrowserRouter>
            <Shell />
          </BrowserRouter>
        </AuthProvider>
      </QueryClientProvider>
    </ThemeProvider>
  );
}
