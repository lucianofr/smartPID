import { useEffect } from 'react';
import {
  useQuery, useMutation, useQueryClient,
  type UseQueryResult, type UseMutationResult,
} from '@tanstack/react-query';
import { apiGet, apiPost, type ApiError } from '../../api/client';
import { useRealtime } from '../../realtime/useRealtime';
import type { ActiveAlarm } from './types';

export const alarmsKeys = {
  active: ['alarms', 'active'] as const,
};

export function useActiveAlarms(): UseQueryResult<ActiveAlarm[], ApiError> {
  return useQuery<ActiveAlarm[], ApiError>({
    queryKey: alarmsKeys.active,
    queryFn: () => apiGet<ActiveAlarm[]>('/alarms/active'),
  });
}

export function useAckAlarm(): UseMutationResult<void, ApiError, number> {
  const qc = useQueryClient();
  return useMutation<void, ApiError, number>({
    mutationFn: async (alarmId: number) => {
      await apiPost(`/alarms/${alarmId}/ack`);
    },
    // Backend is the source of truth — revalidate, never optimistic-mutate state.
    onSettled: () => { void qc.invalidateQueries({ queryKey: alarmsKeys.active }); },
  });
}

export function useAckAllAlarms(): UseMutationResult<void, ApiError, void> {
  const qc = useQueryClient();
  return useMutation<void, ApiError, void>({
    mutationFn: async () => {
      await apiPost('/alarms/ack-all');
    },
    onSettled: () => { void qc.invalidateQueries({ queryKey: alarmsKeys.active }); },
  });
}

/**
 * The WS `alarm` envelope is a trigger only (its payload carries `transition`,
 * not a row id/status — see GAP-3b). On any alarm event, refetch the
 * authoritative active list. `EVENT.SYSTEM` events (config/ack echoes) do the same.
 */
export function useAlarmRealtimeSync(): void {
  const qc = useQueryClient();
  const { subscribe, onResync } = useRealtime();
  useEffect(() => {
    const invalidate = (): void => {
      void qc.invalidateQueries({ queryKey: alarmsKeys.active });
    };
    const unsubAlarm = subscribe('alarm', invalidate);
    const unsubResync = onResync(invalidate);
    return () => { unsubAlarm(); unsubResync(); };
  }, [qc, subscribe, onResync]);
}
