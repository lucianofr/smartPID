import {
  useQuery, useMutation, useQueryClient,
  type UseQueryResult, type UseMutationResult,
} from '@tanstack/react-query';
import { apiGet, apiPut, type ApiError } from '../../api/client';
import type { AlarmConfigResponse, AlarmThreshold } from './types';

export const alarmConfigKey = (controllerId: number) =>
  ['alarms', 'config', controllerId] as const;

export function useAlarmConfig(controllerId: number): UseQueryResult<AlarmConfigResponse, ApiError> {
  return useQuery<AlarmConfigResponse, ApiError>({
    queryKey: alarmConfigKey(controllerId),
    queryFn: () => apiGet<AlarmConfigResponse>(`/controllers/${controllerId}/alarm-config`),
  });
}

export function useUpdateAlarmConfig(
  controllerId: number,
): UseMutationResult<AlarmConfigResponse, ApiError, AlarmThreshold[]> {
  const qc = useQueryClient();
  return useMutation<AlarmConfigResponse, ApiError, AlarmThreshold[]>({
    // Backend PUT replaces ALL thresholds — always send the full array.
    mutationFn: (thresholds) =>
      apiPut<AlarmConfigResponse>(`/controllers/${controllerId}/alarm-config`, { thresholds }),
    onSuccess: (data) => { qc.setQueryData(alarmConfigKey(controllerId), data); },
  });
}
