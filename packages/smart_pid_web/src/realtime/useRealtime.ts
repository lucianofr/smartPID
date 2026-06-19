import { useContext } from 'react';
import type { RealtimeEnvelope, RealtimeType, StatusData, StatsData } from './envelope';
import { RealtimeContext } from './RealtimeProvider';

export interface UseRealtime {
  connected: boolean;
  lastStatus: ReadonlyMap<number, StatusData>;
  lastStats: ReadonlyMap<number, StatsData>;
  subscribe<T = unknown>(
    type: RealtimeType,
    handler: (env: RealtimeEnvelope<T>) => void,
  ): () => void;
  onResync(cb: () => void): () => void;
}

export function useRealtime(): UseRealtime {
  const ctx = useContext(RealtimeContext);
  if (!ctx) throw new Error('useRealtime must be used within RealtimeProvider');
  return ctx as UseRealtime;
}
