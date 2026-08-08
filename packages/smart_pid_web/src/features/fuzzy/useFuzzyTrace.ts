import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import type { ApiError } from '@/api/client';
import { endpoints } from '@/api/endpoints';
import { queryKeys } from '@/api/queryKeys';
import type { FuzzyTraceResponse } from '@/api/types';
import { STATS_POLL_MS } from '@/features/multitrend/useStats';
import type { FuzzyInput, FuzzyOutput, FuzzyRule } from './types';

/**
 * View-model for one loop's fuzzy inference trace (§ fuzzy screen). Maps the
 * wire DTO's snake_case fields to the camelCase shapes `MembershipFunctionPlot`
 * and `FuzzyRuleTable` take as plain props — those components never import
 * `@/api/*` themselves (features/fuzzy/types.ts), so this hook owns that
 * boundary, same split as `toStatsRow` in multitrend/useStats.ts.
 */
export interface FuzzyTraceView {
  controllerId: number;
  objective: string;
  timestamp: number;
  inputs: FuzzyInput[];
  rules: FuzzyRule[];
  outputs: FuzzyOutput[];
  deltaTi: number;
}

export function toFuzzyView(dto: FuzzyTraceResponse): FuzzyTraceView {
  return {
    controllerId: dto.controller_id,
    objective: dto.objective,
    timestamp: dto.timestamp,
    deltaTi: dto.delta_ti,
    inputs: dto.inputs.map((input) => ({
      name: input.name,
      value: input.value,
      domainMin: input.domain_min,
      domainMax: input.domain_max,
      functions: input.functions.map((fn) => ({
        label: fn.label,
        kind: fn.kind,
        params: fn.params,
        degree: fn.degree,
      })),
    })),
    rules: dto.rules.map((rule) => ({
      index: rule.index,
      conditions: rule.conditions,
      output: rule.output,
      strength: rule.strength,
      fired: rule.fired,
    })),
    outputs: dto.outputs.map((output) => ({
      label: output.label,
      center: output.center,
      strength: output.strength,
    })),
  };
}

export interface UseFuzzyTraceResult {
  view: FuzzyTraceView | undefined;
  isPending: boolean;
  /** A genuine transport/server failure. Never true for the expected 404 (see `notRun`). */
  isError: boolean;
  /** 404 — no fuzzy inference recorded yet for this loop. A settled state, not a failure. */
  notRun: boolean;
  refetch(): void;
}

/**
 * One loop's fuzzy inference trace, polled at the same cadence as the stats
 * roster (`STATS_POLL_MS`) so the highlighted rule and membership degrees
 * track the AI as it cycles. `controllerId === null` means no FUZZY loop is
 * selected yet — the query stays disabled rather than firing against an
 * invalid id (same nullable-key shape as `useExport`'s `jobId` / `useHistory`'s
 * `range`).
 */
export function useFuzzyTrace(controllerId: number | null): UseFuzzyTraceResult {
  const query = useQuery<FuzzyTraceResponse, ApiError>({
    queryKey: queryKeys.fuzzyTrace(controllerId ?? -1),
    queryFn: () => {
      if (controllerId === null) throw new Error('fuzzy trace query ran without a loop');
      return endpoints.fuzzyTrace(controllerId);
    },
    enabled: controllerId !== null,
    refetchInterval: STATS_POLL_MS,
    // 404 = no inference recorded yet for this loop — the expected steady
    // state right after a FUZZY loop is picked, not a transient failure. The
    // App-wide default (retry: 1) must not be spent retrying it.
    retry: false,
  });

  const notRun = query.isError && query.error?.kind === 'not-found';
  const view = useMemo(
    () => (query.data === undefined ? undefined : toFuzzyView(query.data)),
    [query.data],
  );

  return {
    view,
    isPending: query.isPending,
    isError: query.isError && !notRun,
    notRun,
    refetch: () => void query.refetch(),
  };
}
