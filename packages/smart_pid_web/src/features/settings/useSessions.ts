import { useQuery, type UseQueryResult } from '@tanstack/react-query';
import type { ApiError } from '@/api/client';
import { endpoints } from '@/api/endpoints';
import { queryKeys } from '@/api/queryKeys';
import type { AccessLogRow, ActiveSessionRow } from '@/api/types';

/**
 * The two admin-only session reads behind the settings security panel
 * (routers/auth.py — `require_admin` on both).
 *
 * Both poll: an active-session list that only refreshes on mount is a claim
 * about the past. The poll is also what keeps the reader's OWN session from
 * ageing out of the list while they watch it, which is correct — the browser
 * really is open.
 */

const POLL_MS = 10_000;

/** Backend caps this at 500 (`Query(50, ge=1, le=500)`). */
export const ACCESS_LOG_LIMIT = 50;

export function useActiveSessions(enabled = true): UseQueryResult<ActiveSessionRow[], ApiError> {
  return useQuery<ActiveSessionRow[], ApiError>({
    queryKey: queryKeys.authSessions,
    enabled,
    queryFn: () => endpoints.activeSessions(),
    refetchInterval: POLL_MS,
  });
}

export function useAccessLog(enabled = true): UseQueryResult<AccessLogRow[], ApiError> {
  return useQuery<AccessLogRow[], ApiError>({
    queryKey: queryKeys.accessLog(ACCESS_LOG_LIMIT),
    enabled,
    queryFn: () => endpoints.accessLog(ACCESS_LOG_LIMIT),
    refetchInterval: POLL_MS,
  });
}
