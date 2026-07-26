import type { QueryClient } from '@tanstack/react-query';
import { ApiError } from '../api/client';
import { endpoints, type AlarmHistoryParams } from '../api/endpoints';
import { queryKeys } from '../api/queryKeys';
import type {
  AiStatus,
  AlarmRow,
  ControllerResponse,
  OpcuaStatus,
  SimulatorStatus,
} from '../api/types';

export interface ResyncContext {
  /** SeqTracker.lastSeenTs('alarm') — epoch seconds; null = no alarm seen yet. */
  lastSeenAlarmTs: number | null;
}

export type ResyncRunner = (ctx: ResyncContext) => Promise<void>;

/** The six §7 calls — injectable for tests; defaults to the real endpoints. */
export interface ResyncApi {
  controllers(): Promise<ControllerResponse[]>;
  activeAlarms(): Promise<AlarmRow[]>;
  alarmHistory(params: AlarmHistoryParams): Promise<AlarmRow[]>;
  aiStatus(controllerId: number): Promise<AiStatus>;
  opcuaStatus(): Promise<OpcuaStatus>;
  simulatorStatus(): Promise<SimulatorStatus>;
}

/** Backend limit default is 100 (alarms.py:41) — too small for a long gap. */
export const RESYNC_HISTORY_LIMIT = 1000;

export function createResyncRunner(deps: {
  queryClient: QueryClient;
  api?: ResyncApi;
}): ResyncRunner {
  const client: ResyncApi = deps.api ?? endpoints;
  const { queryClient } = deps;

  return async (ctx) => {
    // §7 normative set. Controllers first — AI statuses fan out over the ids.
    const controllers = await client.controllers();
    queryClient.setQueryData(queryKeys.controllers, controllers);

    const active = await client.activeAlarms();
    queryClient.setQueryData(queryKeys.alarmsActive, active);

    // Alarm history since last_seen_ts: active-only would miss alarms that
    // fired AND cleared during the gap (cleared-unacknowledged promise, §7).
    if (ctx.lastSeenAlarmTs !== null) {
      const history = await client.alarmHistory({
        start: new Date(ctx.lastSeenAlarmTs * 1000).toISOString(),
        end: new Date().toISOString(),
        limit: RESYNC_HISTORY_LIMIT,
      });
      queryClient.setQueryData(queryKeys.alarmsResyncHistory, history);
    }

    await Promise.all(
      controllers.map(async (c) => {
        const status = await client.aiStatus(c.id);
        queryClient.setQueryData(queryKeys.aiStatus(c.id), status);
      }),
    );

    const opcua = await client.opcuaStatus();
    queryClient.setQueryData(queryKeys.opcuaStatus, opcua);

    // Admin-only route (phase-0 classification): a user-role session gets a
    // deterministic 403 here — skip, never fail the whole resync.
    try {
      const simulator = await client.simulatorStatus();
      queryClient.setQueryData(queryKeys.simulatorStatus, simulator);
    } catch (e) {
      if (!(e instanceof ApiError) || e.kind !== 'forbidden') throw e;
    }
  };
}