import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationResult,
  type UseQueryResult,
} from '@tanstack/react-query';
import type { ApiError } from '@/api/client';
import { endpoints } from '@/api/endpoints';
import { queryKeys } from '@/api/queryKeys';
import type { AlarmConfigResponse, AlarmThreshold } from './types';

/**
 * Per-loop alarm thresholds. Admin-only on the backend (require_admin), so the
 * query is `enabled`-gated by the caller's capability check — a user session
 * must not spend a request on a guaranteed 403.
 */

export function useAlarmConfig(
  controllerId: number,
  enabled = true,
): UseQueryResult<AlarmConfigResponse, ApiError> {
  return useQuery<AlarmConfigResponse, ApiError>({
    queryKey: queryKeys.alarmConfig(controllerId),
    enabled,
    queryFn: () => endpoints.alarmConfig(controllerId),
  });
}

export function useUpdateAlarmConfig(
  controllerId: number,
): UseMutationResult<AlarmConfigResponse, ApiError, AlarmThreshold[]> {
  const queryClient = useQueryClient();
  return useMutation<AlarmConfigResponse, ApiError, AlarmThreshold[]>({
    // PUT REPLACES the whole array (routers/controllers.py) — partial sends drop
    // every threshold the form did not include.
    mutationFn: (thresholds) => endpoints.updateAlarmConfig(controllerId, thresholds),
    onSuccess: (data) => {
      queryClient.setQueryData(queryKeys.alarmConfig(controllerId), data);
    },
  });
}
