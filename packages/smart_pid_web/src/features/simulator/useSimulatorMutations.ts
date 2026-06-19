import { useMutation, useQueryClient } from '@tanstack/react-query';
import {
  startSimulator, stopSimulator, setPreset, setParameters,
  injectDisturbance, clearDisturbance, setCo, setMode, setAutoSp, setAutoDisturbance,
} from './api';
import type {
  ProcessPresetName, DisturbanceType, TwinMode, AutoSPRequest, AutoDisturbanceRequest,
} from './types';
import type { Dynamics } from './DynamicsSliders';

export function useSimulatorMutations(controllerId: number) {
  const qc = useQueryClient();
  const invalidate = () => qc.invalidateQueries({ queryKey: ['simulator', 'status'] });
  const opts = { onSuccess: invalidate };

  return {
    start: useMutation({ mutationFn: () => startSimulator(), ...opts }),
    stop: useMutation({ mutationFn: () => stopSimulator(), ...opts }),
    preset: useMutation({
      mutationFn: (p: ProcessPresetName) => setPreset({ controller_id: controllerId, preset: p }), ...opts }),
    params: useMutation({
      mutationFn: (d: Dynamics) =>
        setParameters({ controller_id: controllerId, gain: d.gain, tau1: d.tau1, tau2: d.tau2, dead_time: d.dead_time }),
      ...opts }),
    inject: useMutation({
      mutationFn: (v: { type: DisturbanceType; amplitude: number }) =>
        injectDisturbance({ controller_id: controllerId, type: v.type, amplitude: v.amplitude }), ...opts }),
    clear: useMutation({ mutationFn: () => clearDisturbance(controllerId), ...opts }),
    co: useMutation({ mutationFn: (co: number) => setCo(controllerId, co), ...opts }),
    mode: useMutation({ mutationFn: (m: TwinMode) => setMode(controllerId, m), ...opts }),
    autoSp: useMutation({ mutationFn: (b: AutoSPRequest) => setAutoSp(controllerId, b), ...opts }),
    autoDist: useMutation({ mutationFn: (b: AutoDisturbanceRequest) => setAutoDisturbance(controllerId, b), ...opts }),
  };
}
