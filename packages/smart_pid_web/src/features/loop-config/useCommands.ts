import { useMutation, useQueryClient, type UseMutationResult } from '@tanstack/react-query';
import type { ApiError } from '../../api/client';
import {
  setSetpoint,
  setMode,
  setOutput,
  setOptimization,
  writeTuning,
  updateController,
  type CommandResponse,
} from './commandApi';
import type { ControllerMode } from './types';

function useInvalidateLoop(): (id: number) => void {
  const queryClient = useQueryClient();
  return (id: number) => {
    void queryClient.invalidateQueries({ queryKey: ['controllers'] });
    void queryClient.invalidateQueries({ queryKey: ['ai', 'status', id] });
  };
}

export function useSetpointMutation(): UseMutationResult<
  CommandResponse,
  ApiError,
  { id: number; value: number }
> {
  const invalidate = useInvalidateLoop();
  return useMutation({
    mutationFn: ({ id, value }) => setSetpoint(id, value),
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
    mutationFn: ({ id, mode }) => setMode(id, mode),
    onSuccess: (_data, { id }) => invalidate(id),
  });
}

export function useOutputMutation(): UseMutationResult<
  CommandResponse,
  ApiError,
  { id: number; value: number }
> {
  const invalidate = useInvalidateLoop();
  return useMutation({
    mutationFn: ({ id, value }) => setOutput(id, value),
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
    mutationFn: ({ id, enabled }) => setOptimization(id, enabled),
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
    mutationFn: ({ id, kp, ti, td }) => writeTuning(id, kp, ti, td),
    onSuccess: (_data, { id }) => invalidate(id),
  });
}

export function useUpdateControllerMutation(): UseMutationResult<
  unknown,
  ApiError,
  { id: number; patch: Record<string, unknown> }
> {
  const invalidate = useInvalidateLoop();
  return useMutation({
    mutationFn: ({ id, patch }) => updateController(id, patch),
    onSuccess: (_data, { id }) => invalidate(id),
  });
}
