import { useMutation, useQueryClient, type UseMutationResult } from '@tanstack/react-query';
import type { ApiError } from '@/api/client';
import { queryKeys } from '@/api/queryKeys';
import type { ControllerMode, ControllerResponse } from '@/api/types';
import {
  createController,
  deleteController,
  setMode,
  setOptimization,
  setOutput,
  setSetpoint,
  updateController,
  writeTuning,
  type CommandResponse,
} from './commandApi';

/**
 * Typed loop mutations. Every success invalidates the canonical §7 keys so the
 * roster and the AI status the resync primed cannot drift from a write.
 *
 * Error routing is deliberately absent here: `apiClient` already dispatches 401
 * and 403 to the auth hooks (logout / "sem permissão" toast + `/auth/me`
 * refetch, §11). 409 and 422 stay on the mutation as `error` so the caller can
 * render them beside a form that keeps its inputs.
 */
function useInvalidateLoop(): (controllerId: number) => void {
  const queryClient = useQueryClient();
  return (controllerId: number) => {
    void queryClient.invalidateQueries({ queryKey: queryKeys.controllers });
    void queryClient.invalidateQueries({ queryKey: queryKeys.aiStatus(controllerId) });
  };
}

export interface LoopValueVars {
  id: number;
  value: number;
}

export function useSetpointMutation(): UseMutationResult<CommandResponse, ApiError, LoopValueVars> {
  const invalidate = useInvalidateLoop();
  return useMutation({
    mutationFn: ({ id, value }: LoopValueVars) => setSetpoint(id, value),
    onSuccess: (_data, { id }) => invalidate(id),
  });
}

export function useModeMutation(): UseMutationResult<
  CommandResponse,
  ApiError,
  { id: number; mode: ControllerMode }
> {
  const invalidate = useInvalidateLoop();
  return useMutation({
    mutationFn: ({ id, mode }: { id: number; mode: ControllerMode }) => setMode(id, mode),
    onSuccess: (_data, { id }) => invalidate(id),
  });
}

export function useOutputMutation(): UseMutationResult<CommandResponse, ApiError, LoopValueVars> {
  const invalidate = useInvalidateLoop();
  return useMutation({
    mutationFn: ({ id, value }: LoopValueVars) => setOutput(id, value),
    onSuccess: (_data, { id }) => invalidate(id),
  });
}

export function useOptimizationMutation(): UseMutationResult<
  CommandResponse,
  ApiError,
  { id: number; enabled: boolean }
> {
  const invalidate = useInvalidateLoop();
  return useMutation({
    mutationFn: ({ id, enabled }: { id: number; enabled: boolean }) => setOptimization(id, enabled),
    onSuccess: (_data, { id }) => invalidate(id),
  });
}

export function useWriteTuningMutation(): UseMutationResult<
  CommandResponse,
  ApiError,
  { id: number; kp: number; ti: number; td: number }
> {
  const invalidate = useInvalidateLoop();
  return useMutation({
    mutationFn: ({ id, kp, ti, td }: { id: number; kp: number; ti: number; td: number }) =>
      writeTuning(id, kp, ti, td),
    onSuccess: (_data, { id }) => invalidate(id),
  });
}

export function useUpdateControllerMutation(): UseMutationResult<
  ControllerResponse,
  ApiError,
  { id: number; patch: Record<string, unknown> }
> {
  const invalidate = useInvalidateLoop();
  return useMutation({
    mutationFn: ({ id, patch }: { id: number; patch: Record<string, unknown> }) =>
      updateController(id, patch),
    onSuccess: (_data, { id }) => invalidate(id),
  });
}

export function useCreateControllerMutation(): UseMutationResult<
  ControllerResponse,
  ApiError,
  Record<string, unknown>
> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: Record<string, unknown>) => createController(body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.controllers });
    },
  });
}

export function useDeleteControllerMutation(): UseMutationResult<
  Record<string, unknown>,
  ApiError,
  number
> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => deleteController(id),
    onSuccess: (_data, id) => {
      queryClient.removeQueries({ queryKey: queryKeys.aiStatus(id) });
      void queryClient.invalidateQueries({ queryKey: queryKeys.controllers });
    },
  });
}
