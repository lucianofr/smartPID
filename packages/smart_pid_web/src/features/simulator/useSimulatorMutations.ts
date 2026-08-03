import { useMutation, useQueryClient, type UseMutationResult } from '@tanstack/react-query';
import { queryKeys } from '@/api/queryKeys';
import type { CommandResponse } from '@/api/types';
import { simulatorApi } from './api';
import {
  SIM_LOOP_PV_DEFAULTS,
  type AutoDisturbanceRequest,
  type AutoSPRequest,
  type ControllerSimStatus,
  type DisturbanceType,
  type Dynamics,
  type ProcessPresetName,
  type SimulatorPIDParamsRequest,
  type TwinMode,
} from './types';

export interface DisturbanceInput {
  type: DisturbanceType;
  amplitude: number;
}

export interface SimulatorMutations {
  start: UseMutationResult<CommandResponse, Error, void>;
  stop: UseMutationResult<CommandResponse, Error, void>;
  preset: UseMutationResult<CommandResponse, Error, ProcessPresetName>;
  parameters: UseMutationResult<CommandResponse, Error, Dynamics>;
  pidParams: UseMutationResult<
    CommandResponse,
    Error,
    Omit<SimulatorPIDParamsRequest, 'controller_id'>
  >;
  inject: UseMutationResult<CommandResponse, Error, DisturbanceInput>;
  clear: UseMutationResult<CommandResponse, Error, void>;
  sp: UseMutationResult<CommandResponse, Error, number>;
  co: UseMutationResult<CommandResponse, Error, number>;
  mode: UseMutationResult<CommandResponse, Error, TwinMode>;
  autoSp: UseMutationResult<ControllerSimStatus, Error, AutoSPRequest>;
  autoDisturbance: UseMutationResult<ControllerSimStatus, Error, AutoDisturbanceRequest>;
  /** Loop lifecycle, admin-only and independent of controller CRUD. */
  createLoop: UseMutationResult<ControllerSimStatus, Error, void>;
  deleteLoop: UseMutationResult<void, Error, void>;
}

/**
 * Every twin write, each one invalidating the shared status snapshot.
 *
 * The simulator has no write-echo on the WebSocket — `/simulator/status` is the
 * only place a preset, a dynamics change or a disturbance becomes visible — so
 * the invalidation IS the feedback loop. Returning the invalidation promise
 * keeps the mutation pending until the refetch lands, so nothing renders the
 * pre-write snapshot as if the command had already taken.
 */
export function useSimulatorMutations(controllerId: number): SimulatorMutations {
  const queryClient = useQueryClient();
  const onSuccess = () => queryClient.invalidateQueries({ queryKey: queryKeys.simulatorStatus });

  return {
    start: useMutation({ mutationFn: () => simulatorApi.start(), onSuccess }),
    stop: useMutation({ mutationFn: () => simulatorApi.stop(), onSuccess }),
    preset: useMutation({
      mutationFn: (preset: ProcessPresetName) =>
        simulatorApi.preset({ controller_id: controllerId, preset }),
      onSuccess,
    }),
    parameters: useMutation({
      mutationFn: (d: Dynamics) =>
        simulatorApi.parameters({
          controller_id: controllerId,
          gain: d.gain,
          tau1: d.tau1,
          tau2: d.tau2,
          dead_time: d.dead_time,
        }),
      onSuccess,
    }),
    pidParams: useMutation({
      mutationFn: (p: Omit<SimulatorPIDParamsRequest, 'controller_id'>) =>
        simulatorApi.setPidParams(controllerId, p),
      onSuccess,
    }),
    inject: useMutation({
      mutationFn: (d: DisturbanceInput) =>
        simulatorApi.injectDisturbance({
          controller_id: controllerId,
          type: d.type,
          amplitude: d.amplitude,
        }),
      onSuccess,
    }),
    clear: useMutation({ mutationFn: () => simulatorApi.clearDisturbance(controllerId), onSuccess }),
    sp: useMutation({ mutationFn: (v: number) => simulatorApi.setSp(controllerId, v), onSuccess }),
    co: useMutation({ mutationFn: (v: number) => simulatorApi.setCo(controllerId, v), onSuccess }),
    mode: useMutation({
      mutationFn: (m: TwinMode) => simulatorApi.setMode(controllerId, m),
      onSuccess,
    }),
    autoSp: useMutation({
      mutationFn: (b: AutoSPRequest) => simulatorApi.setAutoSp(controllerId, b),
      onSuccess,
    }),
    autoDisturbance: useMutation({
      mutationFn: (b: AutoDisturbanceRequest) => simulatorApi.setAutoDisturbance(controllerId, b),
      onSuccess,
    }),
    createLoop: useMutation({
      mutationFn: () => simulatorApi.createLoop({ controller_id: null, ...SIM_LOOP_PV_DEFAULTS }),
      onSuccess,
    }),
    deleteLoop: useMutation({
      mutationFn: () => simulatorApi.deleteLoop(controllerId),
      onSuccess,
    }),
  };
}
