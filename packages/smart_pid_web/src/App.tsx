import { QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { queryClient } from './api/queryClient';
import { AuthProvider, useAuth } from './auth/AuthContext';
import { LoginPage } from './auth/LoginPage';
import { RequireAuth } from './auth/RequireAuth';
import { RealtimeProvider } from './realtime/RealtimeProvider';
import { ThemeProvider } from './theme/ThemeProvider';
import { DashboardPage } from './pages/DashboardPage';
import { ExecutiveDashboardPage } from './pages/ExecutiveDashboardPage';
import { MultiTrendPage } from './pages/MultiTrendPage';
import { SimulatorPage } from './pages/SimulatorPage';
import { AppShell } from './components/shell/AppShell';
import { AlarmPanel } from './features/alarms/AlarmPanel';
import './theme/tokens.css';
import './theme/themes.css';

function Shell() {
  const { token } = useAuth();
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
              <ExecutiveDashboardPage />
            </RequireAuth>
          }
        />
        <Route
          path="/multitrend"
          element={
            <RequireAuth>
              <MultiTrendPage />
            </RequireAuth>
          }
        />
        <Route
          path="/simulator"
          element={
            <RequireAuth>
              <SimulatorPage />
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
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
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
