import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../../api/client', () => ({
  apiGet: vi.fn(),
  apiPut: vi.fn(),
  apiPost: vi.fn(),
  ApiError: class ApiError extends Error {},
}));

import { apiGet, apiPut, apiPost } from '../../api/client';
import { opcuaApi } from './opcuaApi';

beforeEach(() => {
  vi.mocked(apiGet).mockReset();
  vi.mocked(apiPut).mockReset();
  vi.mocked(apiPost).mockReset();
});

describe('opcuaApi', () => {
  it('getStatus calls GET /opcua/status', async () => {
    vi.mocked(apiGet).mockResolvedValue({ state: 'ONLINE', endpoint: 'opc.tcp://x:4840' });
    const r = await opcuaApi.getStatus();
    expect(apiGet).toHaveBeenCalledWith('/opcua/status');
    expect(r.state).toBe('ONLINE');
  });

  it('saveEndpoint PUTs the endpoint body', async () => {
    vi.mocked(apiPut).mockResolvedValue({ state: 'OFFLINE', endpoint: 'opc.tcp://y:4840' });
    await opcuaApi.saveEndpoint('opc.tcp://y:4840');
    expect(apiPut).toHaveBeenCalledWith('/opcua/endpoint', { endpoint: 'opc.tcp://y:4840' });
  });

  it('connect POSTs an optional endpoint', async () => {
    vi.mocked(apiPost).mockResolvedValue({ state: 'ONLINE', endpoint: 'opc.tcp://z:4840' });
    await opcuaApi.connect('opc.tcp://z:4840');
    expect(apiPost).toHaveBeenCalledWith('/opcua/connect', { endpoint: 'opc.tcp://z:4840' });
    await opcuaApi.disconnect();
    expect(apiPost).toHaveBeenCalledWith('/opcua/disconnect');
  });

  it('browse URL-encodes the node id into the path', async () => {
    vi.mocked(apiGet).mockResolvedValue({ parent_node_id: 'ns=2;s=Demo', children: [] });
    await opcuaApi.browse('ns=2;s=Demo');
    expect(apiGet).toHaveBeenCalledWith(`/opcua/browse/${encodeURIComponent('ns=2;s=Demo')}`);
  });

  it('search passes q as a query param', async () => {
    vi.mocked(apiGet).mockResolvedValue({ query: 'flow', results: [] });
    await opcuaApi.search('flow');
    expect(apiGet).toHaveBeenCalledWith(`/opcua/search?q=${encodeURIComponent('flow')}`);
  });
});
