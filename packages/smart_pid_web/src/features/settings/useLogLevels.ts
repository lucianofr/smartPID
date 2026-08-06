import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationResult,
  type UseQueryResult,
} from '@tanstack/react-query';
import type { ApiError } from '@/api/client';
import { endpoints } from '@/api/endpoints';
import type { LogLevelName, LogLevelsResponse } from '@/api/types';
import { toast } from '@/components/Toast';

/**
 * Admin-controlled daemon log levels (`GET`/`PUT /system/log-levels`). The
 * selection is a set, not a threshold — the mutation body is the exact list
 * the operator checked, never a derived "and above" range.
 */
export const logLevelsQueryKey = ['system', 'log-levels'] as const;

function useLogLevelsQuery(): UseQueryResult<LogLevelsResponse, ApiError> {
  return useQuery<LogLevelsResponse, ApiError>({
    queryKey: logLevelsQueryKey,
    queryFn: () => endpoints.getLogLevels(),
  });
}

function useSetLogLevels(): UseMutationResult<void, ApiError, LogLevelName[]> {
  const queryClient = useQueryClient();
  return useMutation<void, ApiError, LogLevelName[]>({
    mutationFn: (levels) => endpoints.setLogLevels(levels),
    onSuccess: () => {
      toast({ title: 'Níveis de log aplicados' });
      void queryClient.invalidateQueries({ queryKey: logLevelsQueryKey });
    },
    onError: () => {
      toast({ title: 'Falha ao aplicar níveis de log', tone: 'crit' });
    },
  });
}

export interface UseLogLevelsResult {
  data: LogLevelsResponse | undefined;
  isLoading: boolean;
  isError: boolean;
  save: (levels: LogLevelName[]) => void;
  isSaving: boolean;
}

export function useLogLevels(): UseLogLevelsResult {
  const query = useLogLevelsQuery();
  const mutation = useSetLogLevels();
  return {
    data: query.data,
    isLoading: query.isLoading,
    isError: query.isError,
    save: (levels) => mutation.mutate(levels),
    isSaving: mutation.isPending,
  };
}
