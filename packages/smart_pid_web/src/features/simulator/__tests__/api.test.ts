import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError, setAuthHooks } from '@/api/client';
import { simulatorApi } from '../api';

/**
 * Path/verb/body contract for every simulator route. These are the calls that
 * fail SILENTLY when they drift (a wrong verb is a 405 swallowed by a mutation
 * handler), so the wire shape is asserted rather than the wrapper's return.
 */

const fetchMock = vi.fn();

function ok(json: unknown = { ok: true }): Response {
  return new Response(JSON.stringify(json), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  });
}

/** [path, init] of the single fetch this call made. */
function call(): { url: string; method: string; body: unknown } {
  expect(fetchMock).toHaveBeenCalledTimes(1);
  const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
  return {
    url,
    method: init.method as string,
    body: typeof init.body === 'string' ? JSON.parse(init.body) : undefined,
  };
}

beforeEach(() => {
  fetchMock.mockReset();
  // A Response body can only be read once — hand out a fresh one per call.
  fetchMock.mockImplementation(() => Promise.resolve(ok()));
  vi.stubGlobal('fetch', fetchMock);
  setAuthHooks({ getToken: () => 'jwt' });
});

afterEach(() => {
  vi.unstubAllGlobals();
  setAuthHooks({ getToken: () => null });
});

describe('simulatorApi wire contract', () => {
  it('reads status through the same path the §7 resync primes', async () => {
    fetchMock.mockImplementation(() =>
      Promise.resolve(ok({ enabled: true, running: false, controllers: {} })),
    );
    await simulatorApi.status();
    expect(call()).toMatchObject({ url: '/api/simulator/status', method: 'GET' });
  });

  it('starts and stops the twin with bodyless POSTs', async () => {
    await simulatorApi.start();
    expect(call()).toMatchObject({ url: '/api/simulator/start', method: 'POST', body: undefined });
    fetchMock.mockClear();
    await simulatorApi.stop();
    expect(call()).toMatchObject({ url: '/api/simulator/stop', method: 'POST' });
  });

  it('POSTs the preset with its controller_id', async () => {
    await simulatorApi.preset({ controller_id: 1, preset: 'TEMPERATURE' });
    expect(call()).toMatchObject({
      url: '/api/simulator/preset',
      method: 'POST',
      body: { controller_id: 1, preset: 'TEMPERATURE' },
    });
  });

  it('PUTs process parameters — a POST here is a 405', async () => {
    await simulatorApi.parameters({ controller_id: 1, gain: 1.2, tau1: 3, tau2: null, dead_time: 1 });
    expect(call()).toMatchObject({
      url: '/api/simulator/parameters',
      method: 'PUT',
      body: { controller_id: 1, gain: 1.2, tau1: 3, tau2: null, dead_time: 1 },
    });
  });

  it('injects with POST /disturbance and clears with DELETE /disturbance/{id}', async () => {
    await simulatorApi.injectDisturbance({ controller_id: 1, type: 'step', amplitude: 20 });
    expect(call()).toMatchObject({
      url: '/api/simulator/disturbance',
      method: 'POST',
      body: { controller_id: 1, type: 'step', amplitude: 20 },
    });
    fetchMock.mockClear();
    await simulatorApi.clearDisturbance(1);
    expect(call()).toMatchObject({ url: '/api/simulator/disturbance/1', method: 'DELETE' });
  });

  it('carries the CO percentage in the `sp` field — /co reuses SimulatorPIDSPRequest', async () => {
    await simulatorApi.setCo(1, 42);
    expect(call()).toMatchObject({
      url: '/api/simulator/1/co',
      method: 'POST',
      body: { controller_id: 1, sp: 42 },
    });
  });

  it('keeps the twin setpoint on its own /pid/sp route', async () => {
    await simulatorApi.setSp(1, 55);
    expect(call()).toMatchObject({
      url: '/api/simulator/1/pid/sp',
      method: 'POST',
      body: { controller_id: 1, sp: 55 },
    });
  });

  it('POSTs the twin mode as MAN/AUTO, not the wire int', async () => {
    await simulatorApi.setMode(1, 'AUTO');
    expect(call()).toMatchObject({
      url: '/api/simulator/1/pid/mode',
      method: 'POST',
      body: { controller_id: 1, mode: 'AUTO' },
    });
  });

  it('PUTs both automation toggles under the controller', async () => {
    await simulatorApi.setAutoSp(1, { enabled: true, sp_min_pct: 30, sp_max_pct: 70 });
    expect(call()).toMatchObject({
      url: '/api/simulator/1/auto-sp',
      method: 'PUT',
      body: { enabled: true, sp_min_pct: 30, sp_max_pct: 70 },
    });
    fetchMock.mockClear();
    await simulatorApi.setAutoDisturbance(1, { enabled: false, max_amplitude_pct: 10 });
    expect(call()).toMatchObject({
      url: '/api/simulator/1/auto-disturbance',
      method: 'PUT',
      body: { enabled: false, max_amplitude_pct: 10 },
    });
  });

  it('surfaces the admin-only 403 as a classified ApiError, never a bare throw', async () => {
    fetchMock.mockImplementation(() =>
      Promise.resolve(
        new Response(JSON.stringify({ detail: 'Admin role required' }), {
          status: 403,
          headers: { 'Content-Type': 'application/json' },
        }),
      ),
    );
    await expect(simulatorApi.status()).rejects.toMatchObject({
      name: 'ApiError',
      status: 403,
      kind: 'forbidden',
    });
    await expect(simulatorApi.status()).rejects.toBeInstanceOf(ApiError);
  });
});
