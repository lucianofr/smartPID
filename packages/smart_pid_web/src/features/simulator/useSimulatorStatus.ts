import { useEffect } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useRealtime } from '../../realtime/useRealtime';
import { getSimulatorStatus } from './api';

export function useSimulatorStatus() {
  const qc = useQueryClient();
  const rt = useRealtime();
  const query = useQuery({ queryKey: ['simulator', 'status'], queryFn: getSimulatorStatus });
  useEffect(
    () => rt.onResync(() => qc.invalidateQueries({ queryKey: ['simulator', 'status'] })),
    [rt, qc],
  );
  return { data: query.data, isLoading: query.isLoading, live: rt.lastStatus };
}
