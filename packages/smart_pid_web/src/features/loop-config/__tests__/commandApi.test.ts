import { describe, it, expect, vi, beforeEach } from 'vitest';

const apiPost = vi.fn(async () => ({ ok: true, controller_id: 1, detail: 'x' }));
const apiGet = vi.fn(async () => ({}));
const apiPut = vi.fn(async () => ({}));
vi.mock('../../../api/client', () => ({ apiPost, apiGet, apiPut, apiDelete: vi.fn() }));

beforeEach(() => {
  apiPost.mockClear();
  apiGet.mockClear();
  apiPut.mockClear();
});

describe('commandApi body/path shapes', () => {
  it('setSetpoint posts {controller_id,value}', async () => {
    const { setSetpoint } = await import('../commandApi');
    await setSetpoint(7, 55.5);
    expect(apiPost).toHaveBeenCalledWith('/commands/setpoint', { controller_id: 7, value: 55.5 });
  });
  it('setMode posts {controller_id,mode}', async () => {
    const { setMode } = await import('../commandApi');
    await setMode(7, 'AUTO');
    expect(apiPost).toHaveBeenCalledWith('/commands/mode', { controller_id: 7, mode: 'AUTO' });
  });
  it('setOptimization posts {controller_id,enabled} (GAP-2b)', async () => {
    const { setOptimization } = await import('../commandApi');
    await setOptimization(7, true);
    expect(apiPost).toHaveBeenCalledWith('/commands/optimization', { controller_id: 7, enabled: true });
  });
  it('writeTuning posts {controller_id,kp,ti,td} (GAP-2a)', async () => {
    const { writeTuning } = await import('../commandApi');
    await writeTuning(7, 1.2, 10, 0.5);
    expect(apiPost).toHaveBeenCalledWith('/commands/tuning', { controller_id: 7, kp: 1.2, ti: 10, td: 0.5 });
  });
  it('applyTuning posts to path with no meaningful body', async () => {
    const { applyTuning } = await import('../commandApi');
    await applyTuning(7);
    expect(apiPost).toHaveBeenCalledWith('/commands/apply-tuning/7', {});
  });
});
