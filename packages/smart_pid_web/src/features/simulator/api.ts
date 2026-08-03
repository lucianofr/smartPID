import { api } from '@/api/client';
import { endpoints } from '@/api/endpoints';
import type { CommandResponse, SimulatorStatus } from '@/api/types';
import type {
  AutoDisturbanceRequest,
  AutoSPRequest,
  ControllerSimStatus,
  SimulatorDisturbanceRequest,
  SimulatorLoopCreateRequest,
  SimulatorParametersRequest,
  SimulatorPIDParamsRequest,
  SimulatorPresetRequest,
  TwinMode,
} from './types';

/**
 * Typed wrapper over the real `/simulator/*` routes (routers/simulator.py).
 *
 * Two split lines matter here:
 *  - RBAC: everything except `sp` / `mode` / `co` is admin-only, and GET
 *    `/simulator/status` is admin-only too (pinned by the backend RBAC contract
 *    test). `useSimulatorStatus` never calls it without `simulator.configure`.
 *  - Paths: `status` delegates to `endpoints.simulatorStatus` so the §7 resync
 *    set and this feature cannot drift onto two different URLs.
 */
export const simulatorApi = {
  status: (): Promise<SimulatorStatus> => endpoints.simulatorStatus(),

  start: () => api.post<CommandResponse>('/simulator/start'),
  stop: () => api.post<CommandResponse>('/simulator/stop'),

  preset: (body: SimulatorPresetRequest) => api.post<CommandResponse>('/simulator/preset', body),
  parameters: (body: SimulatorParametersRequest) =>
    api.put<CommandResponse>('/simulator/parameters', body),
  setPidParams: (controllerId: number, body: Omit<SimulatorPIDParamsRequest, 'controller_id'>) =>
    api.post<CommandResponse>(`/simulator/${controllerId}/pid/params`, {
      controller_id: controllerId,
      ...body,
    } satisfies SimulatorPIDParamsRequest),

  injectDisturbance: (body: SimulatorDisturbanceRequest) =>
    api.post<CommandResponse>('/simulator/disturbance', body),
  clearDisturbance: (controllerId: number) =>
    api.delete<CommandResponse>(`/simulator/disturbance/${controllerId}`),

  // ---- operator surface: `loop.operate`, available to the `user` role ----

  setSp: (controllerId: number, sp: number) =>
    api.post<CommandResponse>(`/simulator/${controllerId}/pid/sp`, {
      controller_id: controllerId,
      sp,
    }),
  /** `/co` reuses SimulatorPIDSPRequest: the CO percentage rides in `sp`. */
  setCo: (controllerId: number, co: number) =>
    api.post<CommandResponse>(`/simulator/${controllerId}/co`, {
      controller_id: controllerId,
      sp: co,
    }),
  setMode: (controllerId: number, mode: TwinMode) =>
    api.post<CommandResponse>(`/simulator/${controllerId}/pid/mode`, {
      controller_id: controllerId,
      mode,
    }),

  // ---- automation: admin-only, and both PUTs answer with the new status ----

  setAutoSp: (controllerId: number, body: AutoSPRequest) =>
    api.put<ControllerSimStatus>(`/simulator/${controllerId}/auto-sp`, body),
  setAutoDisturbance: (controllerId: number, body: AutoDisturbanceRequest) =>
    api.put<ControllerSimStatus>(`/simulator/${controllerId}/auto-disturbance`, body),

  // ---- loop lifecycle: admin-only, independent of controller CRUD ----

  /** `controller_id: null` lets the server allocate the next free loop id. */
  createLoop: (body: SimulatorLoopCreateRequest) =>
    api.post<ControllerSimStatus>('/simulator/loops', body),
  deleteLoop: (controllerId: number) => api.delete<void>(`/simulator/loops/${controllerId}`),
};
