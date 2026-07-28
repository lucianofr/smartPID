import type { AiTuningLogRow, OpcuaStatus, SystemStatusResponse } from '@/api/types';

/**
 * Executive data model (§13 phase 9) — the shapes the buyer-facing dashboard
 * shows AND the pure rules that derive them. No React, no formatting: numerals
 * are rendered by `@/lib/format` at the leaves.
 *
 * The rules below are PORTED from the deleted pre-rewrite `src/lib/kpi.ts`
 * (recovered at 38005e9^): the AUTO mode set, the 5 %-of-range variability
 * target and the loop-health classification are domain rules, not styling, so
 * they survive the rewrite unchanged.
 */

/**
 * A loop counts as automatic when the operator is not driving the output by
 * hand. CAS/RCAS are cascade slaves — still automatic from the plant's view.
 */
export const AUTO_MODES: Record<string, true> = { AUTO: true, CAS: true, RCAS: true };

/** Variability target: 2σ inside 5 % of the loop's engineering range. */
export const VARIABILITY_TARGET = 0.05;

/** Names the 5 %-of-range rule so call sites do not re-state the constant. */
export function variabilityOutOfTarget(
  ratio: number | null | undefined,
  target: number = VARIABILITY_TARGET,
): boolean {
  return ratio !== null && ratio !== undefined && Number.isFinite(ratio) && ratio > target;
}

export type LoopHealth = 'running' | 'stopped' | 'error';

/** pt-BR labels for the health row; `LoopHealth` stays the machine value. */
export const HEALTH_LABEL: Record<LoopHealth, string> = {
  running: 'Em operação',
  stopped: 'Parada',
  error: 'Falha',
};

/**
 * OOS/IMAN are the PID block's own fault states. A loop with no live frame and
 * no usable mode is stopped; everything else is running.
 */
export function healthOf(mode: string, hasLiveStatus: boolean): LoopHealth {
  if (mode === 'OOS' || mode === 'IMAN') return 'error';
  if (!hasLiveStatus && (mode === '' || mode === 'BYPASS')) return 'stopped';
  return 'running';
}

/**
 * The slice `aggregate` needs. A loop with no stats worker still counts for
 * AUTO and AI coverage, so every metric is optional: it drops out of its own
 * average instead of poisoning it with a zero.
 */
export interface AggregateInput {
  mode: string;
  /** AI optimization is enabled AND an engine is selected for this loop. */
  ai: boolean;
  iae?: number | null;
  /** variability_range — a RATIO (2σ/Range), never a percentage. */
  variabilityRange?: number | null;
  /** total_variation — how far the control signal travelled. */
  tv?: number | null;
}

export interface ExecutiveLoop extends AggregateInput {
  loopId: number;
  name: string;
  health: LoopHealth;
}

export interface AggregateKpis {
  loopCount: number;
  autoPercent: number;
  aiCoveragePercent: number;
  /** null when NO loop reported the metric — renders '—', never a fake 0. */
  averageIae: number | null;
  averageVariabilityRange: number | null;
  totalTv: number | null;
}

/** Every reported value of one metric; unreported loops are simply absent. */
function finiteValues(
  loops: readonly AggregateInput[],
  pick: (loop: AggregateInput) => number | null | undefined,
): number[] {
  const out: number[] = [];
  for (const loop of loops) {
    const v = pick(loop);
    if (v !== null && v !== undefined && Number.isFinite(v)) out.push(v);
  }
  return out;
}

/** Arithmetic mean, or null for an empty sample — '—' beats a fabricated 0. */
function mean(values: readonly number[]): number | null {
  if (values.length === 0) return null;
  let total = 0;
  for (const v of values) total += v;
  return total / values.length;
}

/** Plant-wide roll-up. Percentages are over the WHOLE roster; averages are
 *  over the loops that actually reported the metric. */
export function aggregate(loops: readonly AggregateInput[]): AggregateKpis {
  const n = loops.length;
  if (n === 0) {
    return {
      loopCount: 0,
      autoPercent: 0,
      aiCoveragePercent: 0,
      averageIae: null,
      averageVariabilityRange: null,
      totalTv: null,
    };
  }

  let autoCount = 0;
  let aiCount = 0;
  for (const loop of loops) {
    if (AUTO_MODES[loop.mode] === true) autoCount += 1;
    if (loop.ai) aiCount += 1;
  }
  const tv = finiteValues(loops, (l) => l.tv);

  return {
    loopCount: n,
    autoPercent: (autoCount / n) * 100,
    aiCoveragePercent: (aiCount / n) * 100,
    averageIae: mean(finiteValues(loops, (l) => l.iae)),
    averageVariabilityRange: mean(finiteValues(loops, (l) => l.variabilityRange)),
    totalTv: tv.length === 0 ? null : tv.reduce((s, v) => s + v, 0),
  };
}

/** Unscored loops sort last without producing NaN in the comparator. */
const UNSCORED = -Number.MAX_VALUE;
function rankScore(value: number | null | undefined): number {
  return value !== null && value !== undefined && Number.isFinite(value) ? value : UNSCORED;
}

export const BAD_ACTOR_LIMIT = 5;

/**
 * The worst offenders, descending by IAE then by variability — the two indices
 * a buyer can act on. Loops with neither index scored are omitted: an unscored
 * loop is not a good actor, it is an unknown one.
 */
export function rankBadActors(
  loops: readonly ExecutiveLoop[],
  limit: number = BAD_ACTOR_LIMIT,
): ExecutiveLoop[] {
  return loops
    .filter((l) => rankScore(l.iae) !== UNSCORED || rankScore(l.variabilityRange) !== UNSCORED)
    .sort(
      (a, b) =>
        rankScore(b.iae) - rankScore(a.iae) ||
        rankScore(b.variabilityRange) - rankScore(a.variabilityRange) ||
        a.loopId - b.loopId,
    )
    .slice(0, limit);
}

export interface AiRoi {
  /** Loops with a first AND a last scored tuning inside the window. */
  loopsCompared: number;
  tuningEvents: number;
  /** Mean objective metric at the FIRST scored tuning of the window. */
  metricBefore: number;
  /** …and at the LAST. */
  metricAfter: number;
  /** (before − after) / before, a RATIO. Negative means the AI made it worse. */
  improvement: number;
}

/**
 * Before/after comparison over the AI tuning log.
 *
 * The log is the only before/after evidence the backend keeps: each row carries
 * the objective metric measured at that tuning. So "before" is the metric at a
 * loop's FIRST scored tuning in the window and "after" is the metric at its
 * LAST, averaged over every loop that has both.
 *
 * Returns null — never a zeroed shape — when the window cannot support the
 * comparison: fewer than two scored tunings on every loop, or a zero baseline
 * that no ratio can be taken against. The panel renders a MissingState then.
 */
export function aiRoi(events: readonly AiTuningLogRow[]): AiRoi | null {
  const scoredByLoop = new Map<number, { ts: number; metric: number }[]>();
  for (const e of events) {
    if (e.metric === null || !Number.isFinite(e.metric)) continue;
    const point = { ts: Date.parse(e.timestamp), metric: e.metric };
    const bucket = scoredByLoop.get(e.controller_id);
    if (bucket) bucket.push(point);
    else scoredByLoop.set(e.controller_id, [point]);
  }

  const before: number[] = [];
  const after: number[] = [];
  for (const bucket of scoredByLoop.values()) {
    if (bucket.length < 2) continue;
    bucket.sort((a, b) => a.ts - b.ts);
    before.push(bucket[0].metric);
    after.push(bucket[bucket.length - 1].metric);
  }

  const metricBefore = mean(before);
  const metricAfter = mean(after);
  if (metricBefore === null || metricAfter === null || metricBefore === 0) return null;

  return {
    loopsCompared: before.length,
    tuningEvents: events.length,
    metricBefore,
    metricAfter,
    improvement: (metricBefore - metricAfter) / metricBefore,
  };
}

/**
 * What the health panel displays.
 *
 * `GET /system/status` (routers/system.py) reports `status`, `uptime_s`,
 * `active_controllers`, `bus_active` and `api_version`. It reports NO CPU or
 * memory today, and `EVENT.SYSTEM` carries none either (system_event_worker.py
 * emits source/severity/message/timestamp), so those two stay optional and
 * render '—' until a deployment publishes them. Nothing here is synthesised.
 */
export interface BackendHealthState extends Partial<SystemStatusResponse> {
  cpu_percent?: number | null;
  memory_percent?: number | null;
}

export type OpcState = OpcuaStatus['state'];
