import { apiGet, apiPost, apiPut, apiDelete } from '../../api/client';
import type {
  SimulatorStatusResponse, SimulatorPresetRequest, SimulatorParametersRequest,
  SimulatorDisturbanceRequest, AutoSPRequest, AutoDisturbanceRequest,
  CommandResponse, ControllerSimStatus, TwinMode,
} from './types';

export const startSimulator = () => apiPost<CommandResponse>('/simulator/start', undefined);
export const stopSimulator = () => apiPost<CommandResponse>('/simulator/stop', undefined);
export const getSimulatorStatus = () => apiGet<SimulatorStatusResponse>('/simulator/status');

export const setPreset = (b: SimulatorPresetRequest) =>
  apiPost<CommandResponse>('/simulator/preset', b);
export const setParameters = (b: SimulatorParametersRequest) =>
  apiPut<CommandResponse>('/simulator/parameters', b);

export const injectDisturbance = (b: SimulatorDisturbanceRequest) =>
  apiPost<CommandResponse>('/simulator/disturbance', b);
export const clearDisturbance = (controllerId: number) =>
  apiDelete<CommandResponse>(`/simulator/disturbance/${controllerId}`);

export const setCo = (controllerId: number, co: number) =>
  apiPost<CommandResponse>(`/simulator/${controllerId}/co`, { controller_id: controllerId, sp: co });
export const setMode = (controllerId: number, mode: TwinMode) =>
  apiPost<CommandResponse>(`/simulator/${controllerId}/pid/mode`, { controller_id: controllerId, mode });

export const setAutoSp = (controllerId: number, b: AutoSPRequest) =>
  apiPut<ControllerSimStatus>(`/simulator/${controllerId}/auto-sp`, b);
export const setAutoDisturbance = (controllerId: number, b: AutoDisturbanceRequest) =>
  apiPut<ControllerSimStatus>(`/simulator/${controllerId}/auto-disturbance`, b);
