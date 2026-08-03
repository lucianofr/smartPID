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
import type { AiHistoryResponse, AiStatus } from '@/api/types';
import {
  getAiStatus,
  getTuningRecommendation,
  sendAiAction,
  type AiAction,
  type TuningRecommendation,
} from './commandApi';

/** Pending recommendation for one loop; not part of the §7 resync set. */
export const tuningRecommendationKey = (controllerId: number) =>
  ['tuning', 'recommendation', controllerId] as const;

/**
 * Optimizer state. `queryKeys.aiStatus` is the key the §7 resync primes, so the
 * panel shows the resynced status without a second fetch.
 */
export function useAiStatus(
  controllerId: number,
  enabled = true,
): UseQueryResult<AiStatus, ApiError> {
  return useQuery<AiStatus, ApiError>({
    queryKey: queryKeys.aiStatus(controllerId),
    queryFn: () => getAiStatus(controllerId),
    enabled,
    // 404 = the loop has no AI worker. A settled state, not a transient failure.
    retry: false,
  });
}

/**
 * The loop's persisted tuning log, used to SEED the panel's live LOG.AI list.
 *
 * ACTION.AI fires once per AI period — minutes apart — so a live-only log reads
 * `Sem eventos de IA.` for most of the time an operator has the loop open, and
 * loses every line on navigation. Keyed by `controllerId`, so switching loops
 * swaps the log instead of blending two loops' decisions.
 */
export function useAiHistory(
  controllerId: number,
  enabled = true,
): UseQueryResult<AiHistoryResponse, ApiError> {
  return useQuery<AiHistoryResponse, ApiError>({
    queryKey: queryKeys.aiHistory(controllerId),
    queryFn: () => endpoints.aiHistory(controllerId),
    enabled,
    // 404 = the loop has no AI worker, same settled state as useAiStatus.
    retry: false,
  });
}

export function useTuningRecommendation(
  controllerId: number,
  enabled = true,
): UseQueryResult<TuningRecommendation, ApiError> {
  return useQuery<TuningRecommendation, ApiError>({
    queryKey: tuningRecommendationKey(controllerId),
    queryFn: () => getTuningRecommendation(controllerId),
    enabled,
    // 404 = nothing pending. Same reasoning as above.
    retry: false,
  });
}

export function useAiAction(): UseMutationResult<
  Record<string, unknown>,
  ApiError,
  { id: number; action: AiAction }
> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, action }: { id: number; action: AiAction }) => sendAiAction(id, action),
    onSuccess: (_data, { id }) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.aiStatus(id) });
    },
  });
}
