import { useQuery } from '@tanstack/react-query';
import { apiGet } from './client';
import type { StatsResponseLike } from '../lib/kpi';
import type { PeriodRange } from '../lib/period';
import {
  getAiStatus,
  getTuningRecommendation,
  type AiStatus,
  type TuningRecommendation,
} from '../features/loop-config/commandApi';

// Data hooks for the executive dashboard. Thin TanStack Query wrappers over the
// canonical apiGet from client.ts. AI-status, tuning-recommendation, and opcua-status
// reuse the queryFns/types and queryKeys established by earlier fatias so this page
// shares the same query cache (no fragmentation).

const STALE_MS = 5_000;

/** Minimal ControllerResponse subset the executive dashboard reads (full DTO has 30+ fields). */
export interface ControllerSummary {
  id: number;
  name: string;
  mode: string;
  pv: number;
  sp: number;
  co: number;
}

/** OPC-UA status. Matches GET /opcua/status (dtos/opcua.py OPCUAStatusResponse). */
export interface OpcuaStatus {
  state: string;
  endpoint: string | null;
}

/** Hand-typed: GET /alarms/ai-history has NO Pydantic response_model (returns list[dict]). */
export interface AiHistoryEntry {
  id: number;
  controller_id: number;
  timestamp: string;
  engine: string;
  ki_before: number | null;
  ki_after: number | null;
  objective: string | null;
  metric: number | null;
  approved: boolean;
}

export function useAllStats() {
  return useQuery({
    queryKey: ['controllers', 'stats'],
    queryFn: () => apiGet<StatsResponseLike[]>('/controllers/stats'),
    staleTime: STALE_MS,
  });
}

export function useControllers() {
  return useQuery({
    queryKey: ['controllers'],
    queryFn: () => apiGet<ControllerSummary[]>('/controllers'),
    staleTime: STALE_MS,
  });
}

/**
 * Per-loop AI status. enabled-gated to a real loop id. 404 (loop has no AI worker) is an
 * expected state, not transient -> retry:false; the caller treats the error as null.
 * Reuses the ['ai','status',id] queryKey + getAiStatus queryFn from loop-config (shared cache).
 */
export function useAiStatus(controllerId: number | null) {
  return useQuery<AiStatus>({
    queryKey: ['ai', 'status', controllerId],
    queryFn: () => getAiStatus(controllerId as number),
    enabled: controllerId != null,
    retry: false,
    staleTime: STALE_MS,
  });
}

/**
 * Per-loop tuning recommendation. 404 (no pending recommendation) -> retry:false; caller
 * treats the error as null. Reuses the ['tuning','rec',id] queryKey + getTuningRecommendation
 * queryFn from loop-config (shared cache).
 */
export function useTuningRecommendation(controllerId: number | null) {
  return useQuery<TuningRecommendation>({
    queryKey: ['tuning', 'rec', controllerId],
    queryFn: () => getTuningRecommendation(controllerId as number),
    enabled: controllerId != null,
    retry: false,
    staleTime: STALE_MS,
  });
}

/** AI tuning log over the selected period (alarms router). */
export function useAiHistory(range: PeriodRange, controllerId?: number) {
  const params = new URLSearchParams({ start: range.startIso, end: range.endIso });
  if (controllerId != null) params.set('controller_id', String(controllerId));
  return useQuery({
    queryKey: ['alarms', 'ai-history', range.startIso, range.endIso, controllerId ?? 'all'],
    queryFn: () => apiGet<AiHistoryEntry[]>(`/alarms/ai-history?${params.toString()}`),
    staleTime: STALE_MS,
  });
}

/** OPC-UA connection status. Reuses the ['opcua-status'] queryKey used by the page shells. */
export function useOpcuaStatus() {
  return useQuery({
    queryKey: ['opcua-status'],
    queryFn: () => apiGet<OpcuaStatus>('/opcua/status'),
    staleTime: STALE_MS,
  });
}
