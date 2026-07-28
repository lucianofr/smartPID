import type { ReactNode } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from './AuthContext';

export interface RouteGuardProps {
  children: ReactNode;
  /** Admin-only route variant (phase 10: users management). */
  adminOnly?: boolean;
}

export function RouteGuard({ children, adminOnly = false }: RouteGuardProps) {
  const { isAuthenticated, user } = useAuth();
  const location = useLocation();

  if (!isAuthenticated) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }
  if (adminOnly) {
    // Role unknown while GET /auth/me is in flight: render nothing rather than
    // flashing forbidden content or bouncing an admin to the dashboard.
    if (user === null) return null;
    if (user.role !== 'admin') return <Navigate to="/" replace />;
  }
  return <>{children}</>;
}