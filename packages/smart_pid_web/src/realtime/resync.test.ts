import { QueryClient } from '@tanstack/react-query';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../api/client';
import { queryKeys } from '../api/queryKeys';
import { createResyncRunner, RESYNC_HISTORY_LIMIT, type ResyncApi } from './resync';

function fakeApi(overrides: Partial<ResyncApi> = {}): ResyncApi {
  return {
    controllers: vi.fn().mockResolvedValue([{ id: 1 }, { id: 2 }]),
    activeAlarms: vi.fn().mockResolvedValue([{ id: 10, status: 'UNACKNOWLEDGED' }]),
    alarmHistory: vi.fn().mockResolvedValue([{ id: 9, status: 'CLEARED_UNACK' }]),
    aiStatus: vi
      .fn()
      .mockImplementation((id: number) => Promise.resolve({ controller_id: id, enabled: true })),
    opcuaStatus: vi.fn().mockResolvedValue({ state: 'ONLINE', endpoint: 'opc.tcp://x' }),
    simulatorStatus: vi
      .fn()
      .mockResolvedValue({ enabled: false, running: false, controllers: {} }),
    ...overrides,
  } as ResyncApi;
}

describe('createResyncRunner', () => {
  let qc: QueryClient;
  beforeEach(() => {
    qc = new QueryClient();
  });

  it('primes the full §7 set into the canonical query keys', async () => {
    const api = fakeApi();
    await createResyncRunner({ queryClient: qc, api })({ lastSeenAlarmTs: 1_718_743_200 });

    expect(qc.getQueryData(queryKeys.controllers)).toEqual([{ id: 1 }, { id: 2 }]);
    expect(qc.getQueryData(queryKeys.alarmsActive)).toEqual([
      { id: 10, status: 'UNACKNOWLEDGED' },
    ]);
    expect(qc.getQueryData(queryKeys.alarmsResyncHistory)).toEqual([
      { id: 9, status: 'CLEARED_UNACK' },
    ]);
    expect(qc.getQueryData(queryKeys.aiStatus(1))).toEqual({ controller_id: 1, enabled: true });
    expect(qc.getQueryData(queryKeys.aiStatus(2))).toEqual({ controller_id: 2, enabled: true });
    expect(qc.getQueryData(queryKeys.opcuaStatus)).toEqual({
      state: 'ONLINE',
      endpoint: 'opc.tcp://x',
    });
    expect(qc.getQueryData(queryKeys.simulatorStatus)).toEqual({
      enabled: false,
      running: false,
      controllers: {},
    });
  });

  it('requests alarm history since last_seen_ts with the high resync limit', async () => {
    const api = fakeApi();
    await createResyncRunner({ queryClient: qc, api })({ lastSeenAlarmTs: 1_718_743_200.5 });
    expect(api.alarmHistory).toHaveBeenCalledWith({
      start: new Date(1_718_743_200.5 * 1000).toISOString(),
      end: expect.any(String),
      limit: RESYNC_HISTORY_LIMIT,
    });
  });

  it('skips the history window when no alarm was ever seen this session', async () => {
    const api = fakeApi();
    await createResyncRunner({ queryClient: qc, api })({ lastSeenAlarmTs: null });
    expect(api.alarmHistory).not.toHaveBeenCalled();
    expect(qc.getQueryData(queryKeys.alarmsResyncHistory)).toBeUndefined();
  });

  it('fetches AI status for every controller id', async () => {
    const api = fakeApi();
    await createResyncRunner({ queryClient: qc, api })({ lastSeenAlarmTs: null });
    expect(api.aiStatus).toHaveBeenCalledTimes(2);
    expect(api.aiStatus).toHaveBeenCalledWith(1);
    expect(api.aiStatus).toHaveBeenCalledWith(2);
  });

  it('swallows the deterministic 403 on simulator status (user-role session)', async () => {
    const api = fakeApi({
      simulatorStatus: vi
        .fn()
        .mockRejectedValue(new ApiError(403, 'forbidden', 'sem permissão')),
    });
    await expect(
      createResyncRunner({ queryClient: qc, api })({ lastSeenAlarmTs: null }),
    ).resolves.toBeUndefined();
    expect(qc.getQueryData(queryKeys.simulatorStatus)).toBeUndefined();
  });

  it('rejects on any non-403 failure (provider retries via reconnect)', async () => {
    const api = fakeApi({
      opcuaStatus: vi.fn().mockRejectedValue(new ApiError(500, 'server', 'boom')),
    });
    await expect(
      createResyncRunner({ queryClient: qc, api })({ lastSeenAlarmTs: null }),
    ).rejects.toMatchObject({ status: 500 });
  });
});