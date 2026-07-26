import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { endpoints } from './endpoints';
import { queryKeys } from './queryKeys';
import { setAuthHooks } from './client';

const fetchMock = vi.fn();
beforeEach(() => {
  fetchMock.mockReset();
  fetchMock.mockResolvedValue(
    new Response('[]', { status: 200, headers: { 'Content-Type': 'application/json' } }),
  );
  vi.stubGlobal('fetch', fetchMock);
  setAuthHooks({ getToken: () => null });
});
afterEach(() => vi.unstubAllGlobals());

const calledPath = () => fetchMock.mock.calls[0][0] as string;

describe('endpoints — exact backend routes (app.py:161-174 prefixes)', () => {
  it('login posts credentials to /api/auth/login', async () => {
    await endpoints.login('admin', 'secret');
    expect(calledPath()).toBe('/api/auth/login');
    const init = fetchMock.mock.calls[0][1] as RequestInit;
    expect(init.body).toBe(JSON.stringify({ username: 'admin', password: 'secret' }));
  });

  it('me hits /api/auth/me', async () => {
    await endpoints.me();
    expect(calledPath()).toBe('/api/auth/me');
  });

  it('controllers hits /api/controllers', async () => {
    await endpoints.controllers();
    expect(calledPath()).toBe('/api/controllers');
  });

  it('activeAlarms hits /api/alarms/active', async () => {
    await endpoints.activeAlarms();
    expect(calledPath()).toBe('/api/alarms/active');
  });

  it('alarmHistory sends BOTH start and end (alarms.py:38-39) plus limit', async () => {
    await endpoints.alarmHistory({
      start: '2026-07-26T10:00:00.000Z',
      end: '2026-07-26T11:00:00.000Z',
      limit: 1000,
    });
    expect(calledPath()).toBe(
      '/api/alarms/history?start=2026-07-26T10%3A00%3A00.000Z&end=2026-07-26T11%3A00%3A00.000Z&limit=1000',
    );
  });

  it('aiStatus hits /api/controllers/{id}/ai/status (ai router mounted under /controllers)', async () => {
    await endpoints.aiStatus(7);
    expect(calledPath()).toBe('/api/controllers/7/ai/status');
  });

  it('opcuaStatus and simulatorStatus hit their routers', async () => {
    await endpoints.opcuaStatus();
    expect(calledPath()).toBe('/api/opcua/status');
    fetchMock.mockClear();
    fetchMock.mockResolvedValue(
      new Response('{}', { status: 200, headers: { 'Content-Type': 'application/json' } }),
    );
    await endpoints.simulatorStatus();
    expect(calledPath()).toBe('/api/simulator/status');
  });

  it('ackAllAlarms posts to /api/alarms/ack-all', async () => {
    fetchMock.mockResolvedValue(
      new Response('{}', { status: 200, headers: { 'Content-Type': 'application/json' } }),
    );
    await endpoints.ackAllAlarms();
    expect(calledPath()).toBe('/api/alarms/ack-all');
    expect((fetchMock.mock.calls[0][1] as RequestInit).method).toBe('POST');
  });

  it('operator commands post the controller_id in the body, not the path', async () => {
    fetchMock.mockResolvedValue(
      new Response('{}', { status: 200, headers: { 'Content-Type': 'application/json' } }),
    );
    await endpoints.setMode(4, 'MAN');
    expect(calledPath()).toBe('/api/commands/mode');
    expect((fetchMock.mock.calls[0][1] as RequestInit).body).toBe(
      JSON.stringify({ controller_id: 4, mode: 'MAN' }),
    );

    fetchMock.mockClear();
    await endpoints.setSetpoint(4, 55.5);
    expect(calledPath()).toBe('/api/commands/setpoint');
    expect((fetchMock.mock.calls[0][1] as RequestInit).body).toBe(
      JSON.stringify({ controller_id: 4, value: 55.5 }),
    );

    fetchMock.mockClear();
    await endpoints.setOutput(4, 12);
    expect(calledPath()).toBe('/api/commands/output');

    fetchMock.mockClear();
    await endpoints.applyTuning(4);
    expect(calledPath()).toBe('/api/commands/apply-tuning/4');
  });
});

describe('queryKeys — canonical, stable identities', () => {
  it('exposes the §7 resync keys', () => {
    expect(queryKeys.controllers).toEqual(['controllers']);
    expect(queryKeys.alarmsActive).toEqual(['alarms', 'active']);
    expect(queryKeys.alarmsResyncHistory).toEqual(['alarms', 'resync-history']);
    expect(queryKeys.aiStatus(3)).toEqual(['ai', 'status', 3]);
    expect(queryKeys.opcuaStatus).toEqual(['opcua', 'status']);
    expect(queryKeys.simulatorStatus).toEqual(['simulator', 'status']);
  });
});