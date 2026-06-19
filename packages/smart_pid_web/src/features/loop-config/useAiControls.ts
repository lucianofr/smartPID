import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationResult,
  type UseQueryResult,
} from '@tanstack/react-query';
import type { ApiError } from '../../api/client';
import {
  getAiStatus,
  getTuningRecommendation,
  sendAiAction,
  type AiAction,
  type AiStatus,
  type TuningRecommendation,
} from './commandApi';

export function useAiStatus(controllerId: number): UseQueryResult<AiStatus, ApiError> {
  // 404 = loop has no AI worker (expected state, not transient) -> do not retry.
  return useQuery<AiStatus, ApiError>({
    queryKey: ['ai', 'status', controllerId],
    queryFn: () => getAiStatus(controllerId),
    retry: false,
  });
}

export function useTuningRecommendation(
  controllerId: number,
): UseQueryResult<TuningRecommendation, ApiError> {
  // 404 = no pending recommendation (expected state, not transient) -> do not retry.
  return useQuery<TuningRecommendation, ApiError>({
    queryKey: ['tuning', 'rec', controllerId],
    queryFn: () => getTuningRecommendation(controllerId),
    retry: false,
  });
}

export function useAiAction(): UseMutationResult<
  unknown,
  ApiError,
  { id: number; action: AiAction }
> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, action }) => sendAiAction(id, action),
    onSuccess: (_data, { id }) => {
      void queryClient.invalidateQueries({ queryKey: ['ai', 'status', id] });
    },
  });
}
