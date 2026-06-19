import { describe, it, expect, vi, beforeEach } from 'vitest';
import * as client from '../../../api/client';
import {
  setPreset, injectDisturbance, clearDisturbance, setCo, setMode,
  setAutoSp, setAutoDisturbance, startSimulator, stopSimulator, getSimulatorStatus,
} from '../api';

vi.mock('../../../api/client');

beforeEach(() => vi.clearAllMocks());

describe('simulator api wrappers', () => {
  it('setPreset POSTs /simulator/preset with controller_id + preset', async () => {
    vi.mocked(client.apiPost).mockResolvedValue({ ok: true });
    await setPreset({ controller_id: 1, preset: 'FLOW' });
    expect(client.apiPost).toHaveBeenCalledWith('/simulator/preset', { controller_id: 1, preset: 'FLOW' });
  });
  it('injectDisturbance POSTs /simulator/disturbance', async () => {
    vi.mocked(client.apiPost).mockResolvedValue({ ok: true });
    await injectDisturbance({ controller_id: 1, type: 'step', amplitude: 10 });
    expect(client.apiPost).toHaveBeenCalledWith('/simulator/disturbance', { controller_id: 1, type: 'step', amplitude: 10 });
  });
  it('clearDisturbance DELETEs /simulator/disturbance/{id}', async () => {
    vi.mocked(client.apiDelete).mockResolvedValue({ ok: true });
    await clearDisturbance(1);
    expect(client.apiDelete).toHaveBeenCalledWith('/simulator/disturbance/1');
  });
  it('setCo POSTs /simulator/{id}/co with sp carrying CO%', async () => {
    vi.mocked(client.apiPost).mockResolvedValue({ ok: true });
    await setCo(1, 42);
    expect(client.apiPost).toHaveBeenCalledWith('/simulator/1/co', { controller_id: 1, sp: 42 });
  });
  it('setMode POSTs /simulator/{id}/pid/mode', async () => {
    vi.mocked(client.apiPost).mockResolvedValue({ ok: true });
    await setMode(1, 'AUTO');
    expect(client.apiPost).toHaveBeenCalledWith('/simulator/1/pid/mode', { controller_id: 1, mode: 'AUTO' });
  });
  it('setAutoSp PUTs /simulator/{id}/auto-sp', async () => {
    vi.mocked(client.apiPut).mockResolvedValue({});
    await setAutoSp(1, { enabled: true, sp_min_pct: 30, sp_max_pct: 70 });
    expect(client.apiPut).toHaveBeenCalledWith('/simulator/1/auto-sp', { enabled: true, sp_min_pct: 30, sp_max_pct: 70 });
  });
  it('setAutoDisturbance PUTs /simulator/{id}/auto-disturbance', async () => {
    vi.mocked(client.apiPut).mockResolvedValue({});
    await setAutoDisturbance(1, { enabled: true, max_amplitude_pct: 10 });
    expect(client.apiPut).toHaveBeenCalledWith('/simulator/1/auto-disturbance', { enabled: true, max_amplitude_pct: 10 });
  });
  it('start/stop/status hit the right paths', async () => {
    vi.mocked(client.apiPost).mockResolvedValue({ ok: true });
    vi.mocked(client.apiGet).mockResolvedValue({ enabled: true, running: false, controllers: {} });
    await startSimulator(); expect(client.apiPost).toHaveBeenCalledWith('/simulator/start', undefined);
    await stopSimulator();  expect(client.apiPost).toHaveBeenCalledWith('/simulator/stop', undefined);
    await getSimulatorStatus(); expect(client.apiGet).toHaveBeenCalledWith('/simulator/status');
  });
});
