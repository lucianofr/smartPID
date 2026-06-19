import { useQuery } from '@tanstack/react-query';
import { apiGet } from '../../api/client';

export interface TelemetryFrame {
  timestamp: string;
  pv: number;
  sp: number;
  co: number;
  mode: string;
  status: string;
}

export interface HistoryResponse {
  controller_id: number;
  frames: TelemetryFrame[];
  count: number;
}

export interface HistoryParams {
  controllerId: number;
  start?: string;
  end?: string;
  limit?: number;
}

function buildPath(p: HistoryParams): string {
  const qs = new URLSearchParams();
  if (p.start) qs.set('start', p.start);
  if (p.end) qs.set('end', p.end);
  if (p.limit != null) qs.set('limit', String(p.limit));
  const suffix = qs.toString();
  return suffix ? `/history/${p.controllerId}?${suffix}` : `/history/${p.controllerId}`;
}

export function useHistory(params: HistoryParams | null) {
  const query = useQuery({
    queryKey: ['history', params],
    queryFn: () => apiGet<HistoryResponse>(buildPath(params as HistoryParams)),
    enabled: params !== null,
  });
  return {
    frames: query.data?.frames ?? [],
    count: query.data?.count ?? 0,
    isLoading: query.isLoading && params !== null,
    refetch: () => void query.refetch(),
  };
}
