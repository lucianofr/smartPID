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

describe('endpoints — exact backend routes (app.py create_app prefixes)', () => {
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

  it('alarmHistory sends BOTH start and end (alarms.py get_alarm_history) plus limit', async () => {
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
    // A Response body is single-use: hand each call its own.
    fetchMock.mockImplementation(
      () =>
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

  it('opcua writes hit the real verbs: PUT /endpoint, POST /connect|/disconnect', async () => {
    fetchMock.mockImplementation(
      () => new Response('{}', { status: 200, headers: { 'Content-Type': 'application/json' } }),
    );
    await endpoints.saveOpcuaEndpoint('opc.tcp://plc:4840');
    expect(calledPath()).toBe('/api/opcua/endpoint');
    expect((fetchMock.mock.calls[0][1] as RequestInit).method).toBe('PUT');
    expect((fetchMock.mock.calls[0][1] as RequestInit).body).toBe(
      JSON.stringify({ endpoint: 'opc.tcp://plc:4840' }),
    );

    fetchMock.mockClear();
    await endpoints.opcuaConnect();
    expect(calledPath()).toBe('/api/opcua/connect');
    // OPCUAConnectRequest is optional — no body means "reuse the stored endpoint".
    expect((fetchMock.mock.calls[0][1] as RequestInit).body).toBeUndefined();

    fetchMock.mockClear();
    await endpoints.opcuaDisconnect();
    expect(calledPath()).toBe('/api/opcua/disconnect');
  });

  it('percent-encodes node ids and search queries', async () => {
    fetchMock.mockImplementation(
      () => new Response('{}', { status: 200, headers: { 'Content-Type': 'application/json' } }),
    );
    await endpoints.opcuaBrowse('ns=2;s=FT-101');
    expect(calledPath()).toBe('/api/opcua/browse/ns%3D2%3Bs%3DFT-101');
    fetchMock.mockClear();
    await endpoints.opcuaSearch('MAIN.PV');
    expect(calledPath()).toBe('/api/opcua/search?q=MAIN.PV');
  });

  it('project routes match routers/project.py exactly', async () => {
    fetchMock.mockImplementation(
      () => new Response('{}', { status: 200, headers: { 'Content-Type': 'application/json' } }),
    );
    await endpoints.projectList();
    expect(calledPath()).toBe('/api/project/list');

    fetchMock.mockClear();
    await endpoints.createProject('unit-a');
    expect(calledPath()).toBe('/api/project/new');
    expect((fetchMock.mock.calls[0][1] as RequestInit).body).toBe(
      JSON.stringify({ name: 'unit-a' }),
    );

    fetchMock.mockClear();
    await endpoints.openProject('unit a');
    expect(calledPath()).toBe('/api/project/open');

    fetchMock.mockClear();
    fetchMock.mockResolvedValue(new Response(null, { status: 204 }));
    await endpoints.deleteProject('unit a/b');
    expect(calledPath()).toBe('/api/project/unit%20a%2Fb');
    expect((fetchMock.mock.calls[0][1] as RequestInit).method).toBe('DELETE');
  });

  it('import posts multipart with the file and optional name, no manual content-type', async () => {
    fetchMock.mockResolvedValue(
      new Response('{}', { status: 200, headers: { 'Content-Type': 'application/json' } }),
    );
    const file = new File(['x'], 'plant.spid');
    await endpoints.importProject(file, 'plant');
    expect(calledPath()).toBe('/api/project/import');
    const init = fetchMock.mock.calls[0][1] as RequestInit;
    expect(init.method).toBe('POST');
    expect(init.headers).not.toHaveProperty('Content-Type');
    const form = init.body as FormData;
    expect(form.get('file')).toBe(file);
    expect(form.get('name')).toBe('plant');
  });

  it('user management uses PATCH for updates and DELETE for deactivation', async () => {
    fetchMock.mockImplementation(
      () => new Response('{}', { status: 200, headers: { 'Content-Type': 'application/json' } }),
    );
    await endpoints.users();
    expect(calledPath()).toBe('/api/users');

    fetchMock.mockClear();
    await endpoints.createUser({ username: 'operador', password: 'p', role: 'user' });
    expect(calledPath()).toBe('/api/users');
    expect((fetchMock.mock.calls[0][1] as RequestInit).method).toBe('POST');

    fetchMock.mockClear();
    await endpoints.updateUser(9, { role: 'user' });
    expect(calledPath()).toBe('/api/users/9');
    expect((fetchMock.mock.calls[0][1] as RequestInit).method).toBe('PATCH');

    fetchMock.mockClear();
    await endpoints.deactivateUser(9);
    expect(calledPath()).toBe('/api/users/9');
    expect((fetchMock.mock.calls[0][1] as RequestInit).method).toBe('DELETE');
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
    expect(queryKeys.projects).toEqual(['projects', 'list']);
    expect(queryKeys.users).toEqual(['users']);
    expect(queryKeys.opcuaBrowse('i=85')).toEqual(['opcua', 'browse', 'i=85']);
    expect(queryKeys.opcuaSearch('FT')).toEqual(['opcua', 'search', 'FT']);
  });
});