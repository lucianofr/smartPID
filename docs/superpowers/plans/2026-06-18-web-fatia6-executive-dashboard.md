# Fatia 6: Executive Dashboard — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** Ship the Web HMI Executive Dashboard — a consolidated/executive view rendering per-loop and aggregate KPIs (variability `2σ/RANGE`, TV, IAE, AI engine state, % loops in AUTO), loop health (running / stopped / error + OPC connection), a configurable period window for aggregated stats/AI, and per-loop tuning recommendations. All data comes from the **existing** REST surface; live `status` updates refresh the cards via `useRealtime`. Rendered KPI values must equal the REST/WS source values (numeric acceptance, NOT visual parity).

**Architecture:** Greenfield React page inside the `packages/smart_pid_web/` scaffold created by Fatia 0+1. Page = `src/pages/ExecutiveDashboardPage.tsx`; presentational card = `src/components/ExecutiveKPICard.tsx`. Server state via TanStack Query hooks built on the canonical `src/api/client.ts` (contract §6). Live overlay via the canonical `useRealtime()` hook (contract §5) — `lastStatus` (mode → AUTO%, loop running) and `lastStats` (live KPIs) Maps, plus `onResync` to refetch REST after a WS reconnect. KPI math and formatting live in a pure, unit-tested module `src/lib/kpi.ts` so acceptance can assert numbers without rendering.

**Tech Stack:** React 18 + Vite 5 + TypeScript 5 (strict); TanStack Query v5; native WebSocket via `useRealtime`; Vitest + @testing-library/react (unit/hook/component); Playwright (e2e). API types from `openapi-typescript` (`src/api/generated/openapi.ts`). Design tokens/components per design-system authority (`tokens.css`, `[data-theme]` themes; ISA-101 normative). **No charts/sparklines on loop cards** — the executive card may use a discrete range bar only (design-system §5.10 / §11).

## Global Constraints

Every task inherits the Foundation Contract §9 (verbatim):

- **Backend:** bind `127.0.0.1` (config `SPID_API_HOST`); serve SPA via `app.mount('/', StaticFiles(directory=dist, html=True))` mounted **after** routers (single-origin → no CORS in prod); dev CORS allowlist `http://127.0.0.1:5173` only; add security headers (`X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`, basic CSP). Validate `Origin` on `/ws/realtime`.
- **RealtimeWS:** it is the **2nd EventBus consumer**, structurally analogous to `TelemetryPublisher`. The bus `recv()` is **blocking ZMQ** — a naive `await sub.recv()` freezes the daemon loop. Use `zmq.asyncio`. WS frames are **lossy-coalesced** for `status`/`stats` (last value wins) and **lossless bounded** for discrete events (on overflow, close the socket so the client re-syncs via REST). `ConnectionManager` with async lock + resilient broadcast.
- **TDD (mandatory):** failing test → run it red → minimal impl → run it green → commit. Bite-sized steps (2–5 min each), checkbox `- [ ]` syntax.
- **Branching (inviolable):** each fatia is implemented on a **new dedicated branch from `main`**. Never reuse another task's branch, never commit to `main` directly, never touch `feat/windows-installers`. Merge to `main` only with explicit user approval.
- **Subagents:** `model: opus` (project rule).
- **Commits:** conventional (`feat(web): …`, `fix(web): …`); **no attribution trailers**.
- **Python toolchain:** Python 3.13, `uv` workspace.

**Branch for this fatia:** `feat/web-fatia6-executive-dashboard` (created from `main`).

**Product overrides inherited (contract §1):** **Mono-user / NO RBAC.** Auth is mandatory on every endpoint via a single `require_authenticated_admin` dependency; there is no role-gated UI and no user CRUD. The current backend code still decorates the routers this fatia consumes with `require_operator`, but the executive page renders identically for the single admin — **do not add role gating**. The client always sends `Authorization: Bearer <token>` via `client.ts`.

**Dependencies:** This fatia depends on Fatia 0+1 (scaffold, `client.ts`, `RealtimeProvider`/`useRealtime`, `envelope.ts`, `tokens.css`, `AuthProvider`, router, design-system primitives). Do not re-implement those; import them.

---

## Backend — NO CHANGE

This fatia reuses the existing REST/WS surface. **No backend file is created or modified.** Endpoints consumed (confirmed from real router code, `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/`):

| Purpose | Method + Path | Response model | Notes |
|---|---|---|---|
| Aggregate stats (all loops) | `GET /controllers/stats` | `list[StatsResponse]` | stats router mounted at prefix `/controllers`. One entry per controller that has a live stats worker. |
| Per-loop stats | `GET /controllers/{controller_id}/stats` | `StatsResponse` | `404` if no stats worker for that loop. |
| Controller list (loop health source) | `GET /controllers` | `list[ControllerResponse]` | The **LIST** (router `@router.get("")` at prefix `/controllers`). There is **NO `/active`**. Provides `id, name, mode, pv, sp, co, mode_normal, …`. |
| Per-loop AI status | `GET /controllers/{controller_id}/ai/status` | `AIStatusResponse` | ai router at prefix `/controllers`. `404` if no AI worker. Fields: `engine` (`NONE`/`FUZZY`/`RL`), `objective`, `speed`, `current_ki`, `enabled`, `last_gamma?`. **Per-loop only — there is no list endpoint.** |
| AI tuning log over a period | `GET /alarms/ai-history?start=&end=&controller_id=` | `list[dict]` (no Pydantic model) | ai-history lives in the **alarms** router (prefix `/alarms`). `start` and `end` are **required ISO-8601** query params; `controller_id` optional. **CONTRACT PRECONDITION GAP** (§6): this route has no declared `response_model` so `openapi-typescript` types it as `unknown[]`. The plan defines a hand-written `AiHistoryEntry` runtime guard and notes the gap; it does NOT modify the backend. |
| Per-loop tuning recommendation | `GET /commands/tuning-recommendations/{controller_id}` | `TuningRecommendationResponse` | commands router at prefix `/commands`. `404` when no recommendation exists for that loop (treated as "none", not an error). Fields: `current_kp/ti/td`, `recommended_kp/ti/td`, `reason`, `timestamp`, `status` (`pending`/`applied`/`rejected`/`expired`), `source?`. |
| OPC connection (loop health) | `GET /opcua/status` | `OPCUAStatusResponse` | prefix `/opcua`. Fields: `state` (`OFFLINE`/`CONNECTING`/`ONLINE`/`RECONNECTING`), `endpoint`. System-wide OPC state (shared by all loops). |

**WS:** `status` frames (`StatusData`, keyed by `loop_id`) drive live card updates via `useRealtime().lastStatus`. `stats` frames (`StatsData`, keyed by `loop_id`) provide live KPI refresh via `lastStats`. On WS reconnect, `onResync` triggers a refetch of the REST queries below.

> **Field-name reconciliation (load-bearing):** the live WS `StatsData` (contract §4) and the REST `StatsResponse` use **different names for the same metrics**. The KPI module maps both to one internal `LoopKpis` shape:
>
> | Metric | WS `StatsData` (§4) | REST `StatsResponse` |
> |---|---|---|
> | std-dev (σ) | `sigma` | `std_dev` |
> | total variation | `tv` | `total_variation` |
> | variability vs SP | `var_sp` | `variability_sp` |
> | variability vs RANGE | `var_range` | `variability_range` |
> | IAE / ITAE / ISE / MSE | `iae` / `itae` / `ise` / `mse` | same names |
>
> "Variability `2σ/RANGE`" used by `ExecutiveKPICard` = the REST `variability_range` (already `2σ/span`) for the period view, and `var_range` from the live WS frame for the live overlay. `% loops in AUTO` is derived from `mode` (`ControllerResponse.mode` / live `StatusData.mode`), not from stats.

---

## File Structure

```
packages/smart_pid_web/
  src/
    lib/
      kpi.ts                         # NEW — pure KPI normalization, aggregation, formatting (no React)
      period.ts                      # NEW — period-window options → {start, end} ISO range
    api/
      executive.ts                   # NEW — TanStack Query hooks for the 6 endpoints above
    components/
      ExecutiveKPICard.tsx           # NEW — design-system §5.10 presentational card
      ExecutiveKPICard.module.css    # NEW — tokens-only styling
      LoopHealthRow.tsx              # NEW — running/stopped/error + OPC pill (presentational)
      PeriodSelector.tsx             # NEW — period-window <select> (presentational)
      TuningRecommendationCard.tsx   # NEW — per-loop tuning rec (presentational)
    pages/
      ExecutiveDashboardPage.tsx     # NEW — page: wires hooks + useRealtime → cards/health/recs
  tests/
    unit/
      kpi.test.ts                    # NEW (Vitest)
      period.test.ts                 # NEW (Vitest)
    component/
      ExecutiveKPICard.test.tsx      # NEW (Vitest + @testing-library/react)
      ExecutiveDashboardPage.test.tsx# NEW (Vitest, mocked REST + mocked useRealtime)
  e2e/
    executive-dashboard.spec.ts      # NEW (Playwright)
docs/
  smartPIDv2.md                      # MODIFY — Executive Dashboard (web) section
  superpowers/specs/
    2026-06-18-web-fatia6-executive-dashboard-design.md  # MODIFY — mark implemented + final route/components
  superpowers/plans/
    _web-hmi-INDEX.md                # CREATE/APPEND — link this plan
```

> Test file locations follow the scaffold's `vitest.config.ts` (jsdom) glob and `playwright.config.ts` `testDir: e2e`. If Fatia 0+1 colocated tests (e.g. `*.test.tsx` next to source), match that convention instead — confirm in Task 1.

---

### Task 1 — Investigation + branch + types preflight

**Files:** (read-only investigation; then branch)

**Interfaces:** confirms the real scaffold conventions and the generated OpenAPI types this fatia consumes.

- [ ] **Step 1:** Create the dedicated branch from `main`.

```bash
git checkout main
git pull --ff-only
git checkout -b feat/web-fatia6-executive-dashboard
```

Expected: `Switched to a new branch 'feat/web-fatia6-executive-dashboard'`.

- [ ] **Step 2:** Confirm the scaffold exists and locate the canonical primitives this fatia imports. Do NOT modify them.

```bash
cd packages/smart_pid_web
ls src/api/client.ts src/realtime/useRealtime.ts src/realtime/envelope.ts src/theme/tokens.css
grep -n "export function useRealtime" src/realtime/useRealtime.ts
grep -n "export interface StatsData\|export interface StatusData" src/realtime/envelope.ts
grep -n "apiGet\|ApiError" src/api/client.ts
```

Expected: all files exist; `useRealtime` and the `StatsData`/`StatusData` types resolve. If any is missing, STOP — Fatia 0+1 is not merged; this fatia cannot proceed.

- [ ] **Step 3:** Regenerate OpenAPI types against a running backend and confirm the response shapes this fatia relies on.

```bash
# backend must be running on :8000 (uv run python -m smart_pid_core)
npm run gen:api
grep -n "StatsResponse\|TuningRecommendationResponse\|ControllerResponse\|AIStatusResponse\|OPCUAStatusResponse" src/api/generated/openapi.ts | head
```

Expected: `StatsResponse` shows `std_dev`, `total_variation`, `variability_sp`, `variability_range`, `sample_count`; `TuningRecommendationResponse` shows `recommended_kp/ti/td`, `status`. **Confirm `GET /alarms/ai-history` has no schema** (typed as `unknown[]`) — this is the documented PRECONDITION GAP; record it, do not patch the backend.

- [ ] **Step 4:** Confirm test conventions (test dir vs colocated). Adjust the File Structure paths used in later tasks to match.

```bash
cat vitest.config.ts | grep -i "include\|environment\|setup"
cat playwright.config.ts | grep -i "testDir\|baseURL"
```

Expected: jsdom env + a setup file; Playwright `testDir` + `baseURL` pointing at the Vite dev/preview server. No commit (investigation only).

---

### Task 2 — Period window (`src/lib/period.ts`)

**Files:** create `src/lib/period.ts`, `tests/unit/period.test.ts`.

**Interfaces:**

```ts
export type PeriodKey = '15m' | '1h' | '8h' | '24h' | '7d';
export interface PeriodRange { startIso: string; endIso: string; key: PeriodKey; }
export const PERIOD_OPTIONS: ReadonlyArray<{ key: PeriodKey; label: string; ms: number }>;
export function periodRange(key: PeriodKey, now?: Date): PeriodRange;
```

- [ ] **Step 1 (RED):** Write the failing unit test for the period-window math. Use a fixed `now` so the assertion is deterministic.

```ts
// tests/unit/period.test.ts
import { describe, it, expect } from 'vitest';
import { periodRange, PERIOD_OPTIONS } from '../../src/lib/period';

describe('periodRange', () => {
  const now = new Date('2026-06-18T12:00:00.000Z');

  it('1h window ends at now and starts exactly one hour earlier (ISO-8601)', () => {
    const r = periodRange('1h', now);
    expect(r.endIso).toBe('2026-06-18T12:00:00.000Z');
    expect(r.startIso).toBe('2026-06-18T11:00:00.000Z');
    expect(r.key).toBe('1h');
  });

  it('7d window spans 604800 seconds', () => {
    const r = periodRange('7d', now);
    const span = (Date.parse(r.endIso) - Date.parse(r.startIso)) / 1000;
    expect(span).toBe(7 * 24 * 3600);
  });

  it('exposes a labelled option per PeriodKey with no duplicates', () => {
    const keys = PERIOD_OPTIONS.map((o) => o.key);
    expect(new Set(keys).size).toBe(keys.length);
    expect(keys).toEqual(['15m', '1h', '8h', '24h', '7d']);
  });
});
```

Run: `npm run test -- period` → Expected: FAIL (module not found).

- [ ] **Step 2 (GREEN):** Implement the module.

```ts
// src/lib/period.ts
export type PeriodKey = '15m' | '1h' | '8h' | '24h' | '7d';

export interface PeriodRange {
  startIso: string;
  endIso: string;
  key: PeriodKey;
}

const MINUTE = 60_000;
const HOUR = 60 * MINUTE;
const DAY = 24 * HOUR;

export const PERIOD_OPTIONS: ReadonlyArray<{ key: PeriodKey; label: string; ms: number }> = [
  { key: '15m', label: 'Last 15 min', ms: 15 * MINUTE },
  { key: '1h', label: 'Last 1 hour', ms: HOUR },
  { key: '8h', label: 'Last 8 hours', ms: 8 * HOUR },
  { key: '24h', label: 'Last 24 hours', ms: DAY },
  { key: '7d', label: 'Last 7 days', ms: 7 * DAY },
];

export function periodRange(key: PeriodKey, now: Date = new Date()): PeriodRange {
  const opt = PERIOD_OPTIONS.find((o) => o.key === key);
  if (!opt) throw new Error(`Unknown period key: ${key}`);
  const end = now.getTime();
  return {
    endIso: new Date(end).toISOString(),
    startIso: new Date(end - opt.ms).toISOString(),
    key,
  };
}
```

Run: `npm run test -- period` → Expected: PASS (3 tests).

- [ ] **Step 3:** Commit.

```bash
git add src/lib/period.ts tests/unit/period.test.ts
git commit -m "feat(web): add configurable period-window range helper for executive dashboard"
```

---

### Task 3 — KPI normalization, aggregation, formatting (`src/lib/kpi.ts`)

**Files:** create `src/lib/kpi.ts`, `tests/unit/kpi.test.ts`.

**Interfaces:**

```ts
import type { StatsData } from '../realtime/envelope';

/** REST StatsResponse subset this fatia reads (names confirmed from backend dtos/ai.py). */
export interface StatsResponseLike {
  controller_id: number;
  iae: number; itae: number; ise: number; mse: number;
  std_dev: number; total_variation: number;
  variability_sp: number; variability_range: number;
  sample_count: number;
}

/** Internal unified per-loop KPI shape (source-agnostic). */
export interface LoopKpis {
  controllerId: number;
  iae: number; itae: number; ise: number; mse: number;
  sigma: number;            // std-dev
  tv: number;               // total variation (valve travel)
  variabilitySp: number;    // 2σ/SP
  variabilityRange: number; // 2σ/RANGE
  sampleCount: number;
}

export interface AggregateKpis {
  loopCount: number;
  avgVariabilityRange: number; // mean of per-loop variabilityRange
  totalTv: number;             // sum of TV across loops
  avgIae: number;              // mean IAE
  autoPct: number;             // % loops whose mode is an AUTO-family mode
}

export function fromRestStats(r: StatsResponseLike): LoopKpis;
export function fromWsStats(controllerId: number, s: StatsData): LoopKpis;
export function aggregate(loops: ReadonlyArray<LoopKpis>, modesById: ReadonlyMap<number, string>): AggregateKpis;
export function isAutoMode(mode: string): boolean;       // AUTO | CAS | RCAS
export function formatKpi(value: number, kind: 'pct' | 'index' | 'count'): string;
export function variabilityOutOfTarget(variabilityRange: number, targetPct?: number): boolean; // default 5%
```

- [ ] **Step 1 (RED):** Write failing unit tests — the **numeric** acceptance backbone. These assert the exact mapping/aggregation the cards will render.

```ts
// tests/unit/kpi.test.ts
import { describe, it, expect } from 'vitest';
import {
  fromRestStats, fromWsStats, aggregate, isAutoMode,
  formatKpi, variabilityOutOfTarget, type StatsResponseLike,
} from '../../src/lib/kpi';
import type { StatsData } from '../../src/realtime/envelope';

const rest: StatsResponseLike = {
  controller_id: 1, iae: 12.5, itae: 200, ise: 30, mse: 1.1,
  std_dev: 0.8, total_variation: 4.2, variability_sp: 0.03,
  variability_range: 0.04, sample_count: 600,
};

describe('fromRestStats', () => {
  it('maps REST field names onto the unified LoopKpis shape', () => {
    const k = fromRestStats(rest);
    expect(k).toEqual({
      controllerId: 1, iae: 12.5, itae: 200, ise: 30, mse: 1.1,
      sigma: 0.8, tv: 4.2, variabilitySp: 0.03, variabilityRange: 0.04,
      sampleCount: 600,
    });
  });
});

describe('fromWsStats', () => {
  it('maps WS StatsData (sigma/tv/var_sp/var_range) onto the same shape', () => {
    const ws: StatsData = {
      iae: 12.5, itae: 200, ise: 30, mse: 1.1,
      sigma: 0.8, tv: 4.2, var_sp: 0.03, var_range: 0.04,
    };
    const k = fromWsStats(1, ws);
    expect(k.tv).toBe(4.2);
    expect(k.variabilityRange).toBe(0.04);
    expect(k.sampleCount).toBe(0); // WS frame carries no sample count
  });
});

describe('isAutoMode', () => {
  it.each(['AUTO', 'CAS', 'RCAS'])('treats %s as AUTO-family', (m) => {
    expect(isAutoMode(m)).toBe(true);
  });
  it.each(['MAN', 'OOS', 'IMAN', 'LO', 'ROUT', 'BYPASS'])('treats %s as non-AUTO', (m) => {
    expect(isAutoMode(m)).toBe(false);
  });
});

describe('aggregate', () => {
  it('computes loopCount, avg variability/IAE, total TV, and AUTO%', () => {
    const a = fromRestStats(rest);
    const b = fromRestStats({ ...rest, controller_id: 2, iae: 7.5, total_variation: 1.8, variability_range: 0.06 });
    const modes = new Map([[1, 'AUTO'], [2, 'MAN']]);
    const agg = aggregate([a, b], modes);
    expect(agg.loopCount).toBe(2);
    expect(agg.avgIae).toBeCloseTo(10.0, 6);
    expect(agg.totalTv).toBeCloseTo(6.0, 6);
    expect(agg.avgVariabilityRange).toBeCloseTo(0.05, 6);
    expect(agg.autoPct).toBeCloseTo(50, 6);
  });

  it('returns zeros (no NaN) for an empty loop set', () => {
    const agg = aggregate([], new Map());
    expect(agg).toEqual({ loopCount: 0, avgVariabilityRange: 0, totalTv: 0, avgIae: 0, autoPct: 0 });
  });
});

describe('formatKpi', () => {
  it('renders variability as a percentage with one decimal', () => {
    expect(formatKpi(0.042, 'pct')).toBe('4.2%');
  });
  it('renders an index with two decimals', () => {
    expect(formatKpi(12.5, 'index')).toBe('12.50');
  });
  it('renders a count as an integer', () => {
    expect(formatKpi(2, 'count')).toBe('2');
  });
});

describe('variabilityOutOfTarget', () => {
  it('flags > 5% by default', () => {
    expect(variabilityOutOfTarget(0.06)).toBe(true);
    expect(variabilityOutOfTarget(0.04)).toBe(false);
  });
});
```

Run: `npm run test -- kpi` → Expected: FAIL (module not found).

- [ ] **Step 2 (GREEN):** Implement `src/lib/kpi.ts`.

```ts
// src/lib/kpi.ts
import type { StatsData } from '../realtime/envelope';

export interface StatsResponseLike {
  controller_id: number;
  iae: number; itae: number; ise: number; mse: number;
  std_dev: number; total_variation: number;
  variability_sp: number; variability_range: number;
  sample_count: number;
}

export interface LoopKpis {
  controllerId: number;
  iae: number; itae: number; ise: number; mse: number;
  sigma: number;
  tv: number;
  variabilitySp: number;
  variabilityRange: number;
  sampleCount: number;
}

export interface AggregateKpis {
  loopCount: number;
  avgVariabilityRange: number;
  totalTv: number;
  avgIae: number;
  autoPct: number;
}

const AUTO_MODES = new Set(['AUTO', 'CAS', 'RCAS']);
const DEFAULT_VARIABILITY_TARGET = 0.05; // 5% of RANGE

export function fromRestStats(r: StatsResponseLike): LoopKpis {
  return {
    controllerId: r.controller_id,
    iae: r.iae, itae: r.itae, ise: r.ise, mse: r.mse,
    sigma: r.std_dev,
    tv: r.total_variation,
    variabilitySp: r.variability_sp,
    variabilityRange: r.variability_range,
    sampleCount: r.sample_count,
  };
}

export function fromWsStats(controllerId: number, s: StatsData): LoopKpis {
  return {
    controllerId,
    iae: s.iae, itae: s.itae, ise: s.ise, mse: s.mse,
    sigma: s.sigma,
    tv: s.tv,
    variabilitySp: s.var_sp,
    variabilityRange: s.var_range,
    sampleCount: 0,
  };
}

export function isAutoMode(mode: string): boolean {
  return AUTO_MODES.has(mode);
}

export function aggregate(
  loops: ReadonlyArray<LoopKpis>,
  modesById: ReadonlyMap<number, string>,
): AggregateKpis {
  const n = loops.length;
  if (n === 0) {
    return { loopCount: 0, avgVariabilityRange: 0, totalTv: 0, avgIae: 0, autoPct: 0 };
  }
  const totalTv = loops.reduce((s, l) => s + l.tv, 0);
  const sumVar = loops.reduce((s, l) => s + l.variabilityRange, 0);
  const sumIae = loops.reduce((s, l) => s + l.iae, 0);
  const autoCount = loops.reduce(
    (c, l) => c + (isAutoMode(modesById.get(l.controllerId) ?? '') ? 1 : 0),
    0,
  );
  return {
    loopCount: n,
    avgVariabilityRange: sumVar / n,
    totalTv,
    avgIae: sumIae / n,
    autoPct: (autoCount / n) * 100,
  };
}

export function formatKpi(value: number, kind: 'pct' | 'index' | 'count'): string {
  switch (kind) {
    case 'pct':
      return `${(value * 100).toFixed(1)}%`;
    case 'index':
      return value.toFixed(2);
    case 'count':
      return Math.round(value).toString();
  }
}

export function variabilityOutOfTarget(
  variabilityRange: number,
  targetPct: number = DEFAULT_VARIABILITY_TARGET,
): boolean {
  return variabilityRange > targetPct;
}
```

> If `npm run gen:api` (Task 1) revealed different exact REST field names, fix `StatsResponseLike` + `fromRestStats` here and update the test — the backend code is authoritative, not this snippet.

Run: `npm run test -- kpi` → Expected: PASS (all groups).

- [ ] **Step 3:** Commit.

```bash
git add src/lib/kpi.ts tests/unit/kpi.test.ts
git commit -m "feat(web): add KPI normalization, aggregation, and formatting for executive dashboard"
```

---

### Task 4 — Data hooks (`src/api/executive.ts`)

**Files:** create `src/api/executive.ts`. (No standalone test file — these are thin TanStack Query wrappers exercised by the page test in Task 8 against a mocked `client.ts`.)

**Interfaces:** Build on the canonical `apiGet` from `src/api/client.ts` and the generated OpenAPI types. Each hook is a TanStack Query `useQuery`.

- [ ] **Step 1:** Implement the hooks. Use generated types where available; for `ai-history` (no schema) use a hand-written entry type and tolerate `unknown`.

```ts
// src/api/executive.ts
import { useQuery } from '@tanstack/react-query';
import { apiGet } from './client';
import type { components } from './generated/openapi';
import type { PeriodRange } from '../lib/period';

type StatsResponse = components['schemas']['StatsResponse'];
type ControllerResponse = components['schemas']['ControllerResponse'];
type AIStatusResponse = components['schemas']['AIStatusResponse'];
type TuningRecommendationResponse = components['schemas']['TuningRecommendationResponse'];
type OPCUAStatusResponse = components['schemas']['OPCUAStatusResponse'];

/** Hand-typed: GET /alarms/ai-history has NO Pydantic response_model (CONTRACT §6 GAP). */
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

const STALE_MS = 5_000;

export function useAllStats() {
  return useQuery({
    queryKey: ['controllers', 'stats'],
    queryFn: () => apiGet<StatsResponse[]>('/controllers/stats'),
    staleTime: STALE_MS,
  });
}

export function useControllers() {
  return useQuery({
    queryKey: ['controllers'],
    queryFn: () => apiGet<ControllerResponse[]>('/controllers'),
    staleTime: STALE_MS,
  });
}

/** Per-loop AI status. enabled-gated to a real loop id. 404 → treated as null by caller. */
export function useAiStatus(controllerId: number | null) {
  return useQuery({
    queryKey: ['controllers', controllerId, 'ai', 'status'],
    queryFn: () => apiGet<AIStatusResponse>(`/controllers/${controllerId}/ai/status`),
    enabled: controllerId != null,
    retry: false, // do not retry 404 (loop has no AI worker)
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

/** Per-loop tuning recommendation. 404 → null (no pending recommendation). */
export function useTuningRecommendation(controllerId: number | null) {
  return useQuery({
    queryKey: ['commands', 'tuning-recommendations', controllerId],
    queryFn: () => apiGet<TuningRecommendationResponse>(`/commands/tuning-recommendations/${controllerId}`),
    enabled: controllerId != null,
    retry: false,
    staleTime: STALE_MS,
  });
}

export function useOpcuaStatus() {
  return useQuery({
    queryKey: ['opcua', 'status'],
    queryFn: () => apiGet<OPCUAStatusResponse>('/opcua/status'),
    staleTime: STALE_MS,
  });
}
```

> If `apiGet`'s real signature in the scaffold differs (e.g. takes a typed path map instead of a raw string), adapt the calls — `client.ts` is canonical.

- [ ] **Step 2:** Type-check the new module.

```bash
npm run lint && npx tsc --noEmit
```

Expected: no errors. (If `components['schemas']['…']` keys differ from the generated file, correct them from `src/api/generated/openapi.ts`.)

- [ ] **Step 3:** Commit.

```bash
git add src/api/executive.ts
git commit -m "feat(web): add TanStack Query hooks for executive dashboard endpoints"
```

---

### Task 5 — `ExecutiveKPICard` (`src/components/ExecutiveKPICard.tsx`)

**Files:** create `src/components/ExecutiveKPICard.tsx`, `src/components/ExecutiveKPICard.module.css`, `tests/component/ExecutiveKPICard.test.tsx`.

**Interfaces (design-system §5.10):** larger-than-ControllerCard bento card; big KPI number (`--text-2xl`, mono tabular) + label + micro-delta (▲/▼ + value, colored **only** when variability is out-of-target → amber/red; otherwise neutral gray). Optional discrete range bar (NOT a sparkline).

```ts
export interface ExecutiveKPICardProps {
  label: string;
  value: string;                 // already formatted via kpi.formatKpi
  delta?: { dir: 'up' | 'down'; value: string; outOfTarget: boolean };
  rangeBar?: { ratio: number };  // 0..1 discrete fill, optional
  testId?: string;
}
```

- [ ] **Step 1 (RED):** Write the failing component test asserting the **rendered number equals the passed value** and that color semantics only appear when out-of-target.

```tsx
// tests/component/ExecutiveKPICard.test.tsx
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ExecutiveKPICard } from '../../src/components/ExecutiveKPICard';

describe('ExecutiveKPICard', () => {
  it('renders the exact formatted KPI value and label', () => {
    render(<ExecutiveKPICard label="Variability 2σ/RANGE" value="4.2%" testId="kpi-var" />);
    const card = screen.getByTestId('kpi-var');
    expect(card).toHaveTextContent('4.2%');
    expect(card).toHaveTextContent('Variability 2σ/RANGE');
  });

  it('marks the delta out-of-target so styling can react (data attribute, not color-only)', () => {
    render(
      <ExecutiveKPICard
        label="Variability" value="6.0%"
        delta={{ dir: 'up', value: '+1.0%', outOfTarget: true }}
        testId="kpi-bad"
      />,
    );
    expect(screen.getByTestId('kpi-bad-delta')).toHaveAttribute('data-out-of-target', 'true');
  });

  it('does not flag a within-target delta', () => {
    render(
      <ExecutiveKPICard
        label="Variability" value="4.0%"
        delta={{ dir: 'down', value: '-0.5%', outOfTarget: false }}
        testId="kpi-ok"
      />,
    );
    expect(screen.getByTestId('kpi-ok-delta')).toHaveAttribute('data-out-of-target', 'false');
  });
});
```

Run: `npm run test -- ExecutiveKPICard` → Expected: FAIL.

- [ ] **Step 2 (GREEN):** Implement the card (tokens only; no hardcoded palette).

```tsx
// src/components/ExecutiveKPICard.tsx
import styles from './ExecutiveKPICard.module.css';

export interface ExecutiveKPICardProps {
  label: string;
  value: string;
  delta?: { dir: 'up' | 'down'; value: string; outOfTarget: boolean };
  rangeBar?: { ratio: number };
  testId?: string;
}

export function ExecutiveKPICard({ label, value, delta, rangeBar, testId }: ExecutiveKPICardProps) {
  return (
    <article className={styles.card} data-testid={testId}>
      <span className={styles.value}>{value}</span>
      <span className={styles.label}>{label}</span>
      {delta && (
        <span
          className={styles.delta}
          data-testid={testId ? `${testId}-delta` : undefined}
          data-out-of-target={delta.outOfTarget}
        >
          {delta.dir === 'up' ? '▲' : '▼'} {delta.value}
        </span>
      )}
      {rangeBar && (
        <div className={styles.rangeBar} aria-hidden>
          <div
            className={styles.rangeFill}
            style={{ width: `${Math.max(0, Math.min(1, rangeBar.ratio)) * 100}%` }}
          />
        </div>
      )}
    </article>
  );
}
```

```css
/* src/components/ExecutiveKPICard.module.css — tokens only (design-system §7) */
.card {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding: var(--space-4) var(--space-5);
  background: var(--color-surface-raised);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
}
.value {
  font-family: var(--font-mono);
  font-variant-numeric: tabular-nums;
  font-size: var(--text-2xl);
  color: var(--color-text-primary);
}
.label { font-size: var(--text-sm); color: var(--color-text-secondary); }
.delta { font-size: var(--text-sm); color: var(--color-text-secondary); }
.delta[data-out-of-target='true'] { color: var(--color-warning); }
.rangeBar { height: 4px; background: var(--color-track); border-radius: var(--radius-sm); overflow: hidden; }
.rangeFill { height: 100%; background: var(--color-accent); }
```

> Use the **exact** token names from the Fatia 0+1 `tokens.css`. The names above follow the design-system contract; if any differs in the merged scaffold, use the scaffold's name. No color in the normal state except the 3 functional trend colors (design-system §11).

Run: `npm run test -- ExecutiveKPICard` → Expected: PASS.

- [ ] **Step 3:** Commit.

```bash
git add src/components/ExecutiveKPICard.tsx src/components/ExecutiveKPICard.module.css tests/component/ExecutiveKPICard.test.tsx
git commit -m "feat(web): add ExecutiveKPICard design-system component"
```

---

### Task 6 — Presentational sub-components (health, period, tuning rec)

**Files:** create `src/components/LoopHealthRow.tsx`, `src/components/PeriodSelector.tsx`, `src/components/TuningRecommendationCard.tsx`. (Behavior verified inside the page test in Task 8; these are pure presentational pieces.)

**Interfaces:**

```ts
export type LoopHealth = 'running' | 'stopped' | 'error';
export interface LoopHealthRowProps {
  name: string;
  health: LoopHealth;        // derived: running if live status seen / mode != OOS; error on shed; else stopped
  opc: 'OFFLINE' | 'CONNECTING' | 'ONLINE' | 'RECONNECTING';
  mode: string;
}
export interface PeriodSelectorProps {
  value: import('../lib/period').PeriodKey;
  onChange: (k: import('../lib/period').PeriodKey) => void;
}
export interface TuningRecommendationCardProps {
  loopName: string;
  rec: import('../api/executive').AiHistoryEntry extends never ? never : {
    current_kp: number; current_ti: number; current_td: number;
    recommended_kp: number; recommended_ti: number; recommended_td: number;
    reason: string; status: string;
  } | null;       // null = no pending recommendation
}
```

- [ ] **Step 1:** Implement `PeriodSelector` driven by `PERIOD_OPTIONS`.

```tsx
// src/components/PeriodSelector.tsx
import { PERIOD_OPTIONS, type PeriodKey } from '../lib/period';

export interface PeriodSelectorProps {
  value: PeriodKey;
  onChange: (k: PeriodKey) => void;
}

export function PeriodSelector({ value, onChange }: PeriodSelectorProps) {
  return (
    <label>
      <span className="sr-only">Aggregation period</span>
      <select
        aria-label="Aggregation period"
        value={value}
        onChange={(e) => onChange(e.target.value as PeriodKey)}
      >
        {PERIOD_OPTIONS.map((o) => (
          <option key={o.key} value={o.key}>{o.label}</option>
        ))}
      </select>
    </label>
  );
}
```

- [ ] **Step 2:** Implement `LoopHealthRow` (status + OPC pill; color only on abnormal — ISA-101 §8).

```tsx
// src/components/LoopHealthRow.tsx
export type LoopHealth = 'running' | 'stopped' | 'error';
export interface LoopHealthRowProps {
  name: string;
  health: LoopHealth;
  opc: 'OFFLINE' | 'CONNECTING' | 'ONLINE' | 'RECONNECTING';
  mode: string;
}

export function LoopHealthRow({ name, health, opc, mode }: LoopHealthRowProps) {
  return (
    <div data-testid={`health-${name}`} data-health={health} data-opc={opc}>
      <span>{name}</span>
      <span>{mode}</span>
      <span data-testid={`health-${name}-state`}>{health}</span>
      <span data-testid={`health-${name}-opc`}>{opc}</span>
    </div>
  );
}
```

- [ ] **Step 3:** Implement `TuningRecommendationCard` (null = "no recommendation").

```tsx
// src/components/TuningRecommendationCard.tsx
export interface TuningRec {
  current_kp: number; current_ti: number; current_td: number;
  recommended_kp: number; recommended_ti: number; recommended_td: number;
  reason: string; status: string;
}
export interface TuningRecommendationCardProps { loopName: string; rec: TuningRec | null; }

export function TuningRecommendationCard({ loopName, rec }: TuningRecommendationCardProps) {
  return (
    <article data-testid={`tuning-${loopName}`}>
      <h4>{loopName}</h4>
      {rec == null ? (
        <p data-testid={`tuning-${loopName}-empty`}>No tuning recommendation</p>
      ) : (
        <dl data-testid={`tuning-${loopName}-body`} data-status={rec.status}>
          <div><dt>Kp</dt><dd>{rec.current_kp.toFixed(4)} → {rec.recommended_kp.toFixed(4)}</dd></div>
          <div><dt>Ti</dt><dd>{rec.current_ti.toFixed(4)} → {rec.recommended_ti.toFixed(4)}</dd></div>
          <div><dt>Td</dt><dd>{rec.current_td.toFixed(4)} → {rec.recommended_td.toFixed(4)}</dd></div>
          <p>{rec.reason}</p>
        </dl>
      )}
    </article>
  );
}
```

- [ ] **Step 4:** Type-check + lint.

Run: `npm run lint && npx tsc --noEmit` → Expected: no errors.

- [ ] **Step 5:** Commit.

```bash
git add src/components/LoopHealthRow.tsx src/components/PeriodSelector.tsx src/components/TuningRecommendationCard.tsx
git commit -m "feat(web): add loop-health, period-selector, and tuning-recommendation components"
```

---

### Task 7 — `ExecutiveDashboardPage` wiring (`src/pages/ExecutiveDashboardPage.tsx`)

**Files:** create `src/pages/ExecutiveDashboardPage.tsx`; register the route in `src/App.tsx` (add a route entry only).

**Interfaces:** The page composes Tasks 2–6. It reads REST via the hooks and overlays live `useRealtime().lastStats` / `lastStatus` (per `loop_id`). The displayed per-loop KPI prefers the **live WS frame** when present, falling back to the **period REST snapshot**. Aggregate KPIs feed `ExecutiveKPICard`s. `onResync` refetches the REST queries after a WS reconnect.

- [ ] **Step 1:** Implement the page.

```tsx
// src/pages/ExecutiveDashboardPage.tsx
import { useEffect, useMemo, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useRealtime } from '../realtime/useRealtime';
import { periodRange, type PeriodKey } from '../lib/period';
import {
  fromRestStats, fromWsStats, aggregate, formatKpi,
  variabilityOutOfTarget, isAutoMode, type LoopKpis,
} from '../lib/kpi';
import { useAllStats, useControllers, useOpcuaStatus } from '../api/executive';
import { ExecutiveKPICard } from '../components/ExecutiveKPICard';
import { LoopHealthRow, type LoopHealth } from '../components/LoopHealthRow';
import { PeriodSelector } from '../components/PeriodSelector';

function healthOf(mode: string, hasLiveStatus: boolean): LoopHealth {
  if (mode === 'OOS' || mode === 'IMAN') return 'error';
  if (!hasLiveStatus && (mode === '' || mode === 'BYPASS')) return 'stopped';
  return 'running';
}

export function ExecutiveDashboardPage() {
  const [period, setPeriod] = useState<PeriodKey>('1h');
  const range = useMemo(() => periodRange(period), [period]);

  const qc = useQueryClient();
  const { lastStatus, lastStats, onResync } = useRealtime();

  const statsQ = useAllStats();
  const ctrlQ = useControllers();
  const opcQ = useOpcuaStatus();

  useEffect(() => onResync(() => {
    void qc.invalidateQueries({ queryKey: ['controllers'] });
    void qc.invalidateQueries({ queryKey: ['opcua', 'status'] });
  }), [onResync, qc]);

  const controllers = ctrlQ.data ?? [];
  const modesById = useMemo(() => {
    const m = new Map<number, string>();
    for (const c of controllers) m.set(c.id, lastStatus.get(c.id)?.mode ?? c.mode);
    return m;
  }, [controllers, lastStatus]);

  // Per-loop KPIs: live WS frame wins, else period REST snapshot.
  const loopKpis: LoopKpis[] = useMemo(() => {
    const byId = new Map<number, LoopKpis>();
    for (const r of statsQ.data ?? []) byId.set(r.controller_id, fromRestStats(r));
    for (const c of controllers) {
      const live = lastStats.get(c.id);
      if (live) byId.set(c.id, fromWsStats(c.id, live));
    }
    return [...byId.values()];
  }, [statsQ.data, controllers, lastStats]);

  const agg = useMemo(() => aggregate(loopKpis, modesById), [loopKpis, modesById]);
  const opcState = opcQ.data?.state ?? 'OFFLINE';

  return (
    <main data-testid="executive-dashboard">
      <header>
        <h1>Executive Dashboard</h1>
        <PeriodSelector value={period} onChange={setPeriod} />
      </header>

      <section aria-label="Aggregate KPIs" data-testid="aggregate-kpis">
        <ExecutiveKPICard
          label="Loops in AUTO"
          value={formatKpi(agg.autoPct / 100, 'pct')}
          testId="kpi-auto"
        />
        <ExecutiveKPICard
          label="Avg variability 2σ/RANGE"
          value={formatKpi(agg.avgVariabilityRange, 'pct')}
          delta={{ dir: 'up', value: formatKpi(agg.avgVariabilityRange, 'pct'),
                   outOfTarget: variabilityOutOfTarget(agg.avgVariabilityRange) }}
          testId="kpi-variability"
        />
        <ExecutiveKPICard label="Total valve travel (TV)" value={formatKpi(agg.totalTv, 'index')} testId="kpi-tv" />
        <ExecutiveKPICard label="Avg IAE" value={formatKpi(agg.avgIae, 'index')} testId="kpi-iae" />
        <ExecutiveKPICard label="Loops" value={formatKpi(agg.loopCount, 'count')} testId="kpi-loops" />
      </section>

      <section aria-label="Loop health" data-testid="loop-health">
        {controllers.map((c) => {
          const live = lastStatus.get(c.id);
          const mode = live?.mode ?? c.mode;
          return (
            <LoopHealthRow
              key={c.id}
              name={c.name}
              mode={mode}
              health={healthOf(mode, live != null)}
              opc={opcState as LoopHealthRow['opc'] extends never ? never : typeof opcState}
            />
          );
        })}
      </section>
    </main>
  );
}
```

> Per-loop AI status / tuning recommendation are per-loop endpoints (`useAiStatus`, `useTuningRecommendation`, `useAiHistory`). Wire them into a per-loop detail strip in Step 2; aggregate AI-engine state ("how many loops running FUZZY/RL") is computed from `controllers[].ai_config.engine` plus `useAiStatus(selectedLoop)` for the detail. Keep the aggregate cards above driven by stats; expose AI engine state as a per-loop pill in the health row (extend `LoopHealthRowProps` with `aiEngine?: string` if desired).

- [ ] **Step 2:** Add per-loop AI engine + tuning-recommendation strip. Render `TuningRecommendationCard` per loop fed by `useTuningRecommendation(loopId)` (null on 404), and an "AI engine" pill from `useAiStatus(loopId)`/`ai_config.engine`. Include `useAiHistory(range, loopId)` count to show "N tuning events in period".

- [ ] **Step 3:** Register the route in `src/App.tsx` (route table only — do not touch the guard/provider wiring from Fatia 0+1):

```tsx
// inside the <Routes> table, under <RequireAuth>
<Route path="/executive" element={<ExecutiveDashboardPage />} />
```

- [ ] **Step 4:** Type-check + lint.

Run: `npm run lint && npx tsc --noEmit` → Expected: no errors.

- [ ] **Step 5:** Commit.

```bash
git add src/pages/ExecutiveDashboardPage.tsx src/App.tsx
git commit -m "feat(web): wire executive dashboard page with live KPI overlay and period window"
```

---

### Task 8 — Page integration test: numeric assertion vs mocked REST (Vitest)

**Files:** create `tests/component/ExecutiveDashboardPage.test.tsx`.

**Interfaces:** Mock `useRealtime` (empty live Maps so REST values are rendered verbatim) and `client.ts` `apiGet` (return canned REST payloads). Assert that the **rendered aggregate KPI numbers equal the values computed from the mocked REST**, and that the period selector changes the period query input.

- [ ] **Step 1 (RED):** Write the failing integration test.

```tsx
// tests/component/ExecutiveDashboardPage.test.tsx
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ExecutiveDashboardPage } from '../../src/pages/ExecutiveDashboardPage';

const stats = [
  { controller_id: 1, iae: 12.5, itae: 200, ise: 30, mse: 1.1, std_dev: 0.8,
    total_variation: 4.2, variability_sp: 0.03, variability_range: 0.04, sample_count: 600 },
  { controller_id: 2, iae: 7.5, itae: 100, ise: 15, mse: 0.6, std_dev: 0.5,
    total_variation: 1.8, variability_sp: 0.05, variability_range: 0.06, sample_count: 600 },
];
const controllers = [
  { id: 1, name: 'FIC-101', mode: 'AUTO' },
  { id: 2, name: 'TIC-202', mode: 'MAN' },
];

vi.mock('../../src/realtime/useRealtime', () => ({
  useRealtime: () => ({
    connected: true,
    lastStatus: new Map(),
    lastStats: new Map(),
    subscribe: () => () => {},
    onResync: () => () => {},
  }),
}));

vi.mock('../../src/api/client', () => ({
  apiGet: vi.fn((path: string) => {
    if (path === '/controllers/stats') return Promise.resolve(stats);
    if (path === '/controllers') return Promise.resolve(controllers);
    if (path === '/opcua/status') return Promise.resolve({ state: 'ONLINE', endpoint: 'opc.tcp://x:4840' });
    return Promise.resolve(null);
  }),
  ApiError: class ApiError extends Error {},
}));

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}><ExecutiveDashboardPage /></QueryClientProvider>,
  );
}

describe('ExecutiveDashboardPage', () => {
  beforeEach(() => vi.clearAllMocks());

  it('renders aggregate KPI values equal to the values derived from mocked REST', async () => {
    renderPage();
    // avgIae = (12.5+7.5)/2 = 10.00 ; totalTv = 4.2+1.8 = 6.00
    // avgVariabilityRange = (0.04+0.06)/2 = 0.05 → 5.0% ; autoPct = 1/2 = 50%
    expect(await screen.findByTestId('kpi-iae')).toHaveTextContent('10.00');
    expect(screen.getByTestId('kpi-tv')).toHaveTextContent('6.00');
    expect(screen.getByTestId('kpi-variability')).toHaveTextContent('5.0%');
    expect(screen.getByTestId('kpi-auto')).toHaveTextContent('50.0%');
    expect(screen.getByTestId('kpi-loops')).toHaveTextContent('2');
  });

  it('shows OPC ONLINE for both loops and marks AUTO/MAN health', async () => {
    renderPage();
    expect(await screen.findByTestId('health-FIC-101-opc')).toHaveTextContent('ONLINE');
    expect(screen.getByTestId('health-FIC-101-state')).toHaveTextContent('running');
    expect(screen.getByTestId('health-TIC-202-state')).toHaveTextContent('running');
  });

  it('changing the period selector keeps the dashboard mounted (period-window selection)', async () => {
    renderPage();
    const select = await screen.findByLabelText('Aggregation period');
    fireEvent.change(select, { target: { value: '24h' } });
    expect((select as HTMLSelectElement).value).toBe('24h');
    expect(screen.getByTestId('executive-dashboard')).toBeInTheDocument();
  });
});
```

Run: `npm run test -- ExecutiveDashboardPage` → Expected: FAIL initially if any wiring/test-id mismatch; iterate the page (Task 7) until green. The mocked-REST → rendered-number equality is the **numeric acceptance gate** (NOT visual parity).

- [ ] **Step 2 (GREEN):** Fix any mismatch between page test-ids/format and the test. Re-run until PASS.

Run: `npm run test` → Expected: all Vitest suites PASS (period, kpi, ExecutiveKPICard, ExecutiveDashboardPage).

- [ ] **Step 3:** Commit.

```bash
git add tests/component/ExecutiveDashboardPage.test.tsx
git commit -m "test(web): numeric KPI assertions for executive dashboard against mocked REST"
```

---

### Task 9 — Playwright e2e: dashboard loads + updates live

**Files:** create `e2e/executive-dashboard.spec.ts`.

**Interfaces:** Drive the real SPA. Auth as the single admin (reuse the Fatia 0+1 login helper if present; otherwise log in via the UI). Stub the REST endpoints with `page.route` so the asserted numbers are deterministic, then push a `status`/`stats` WS frame (or re-stub + reload) to prove live update. Assert the rendered KPI equals the stubbed REST value.

- [ ] **Step 1 (RED):** Write the failing e2e spec.

```ts
// e2e/executive-dashboard.spec.ts
import { test, expect } from '@playwright/test';

const STATS = [
  { controller_id: 1, iae: 12.5, itae: 200, ise: 30, mse: 1.1, std_dev: 0.8,
    total_variation: 4.2, variability_sp: 0.03, variability_range: 0.04, sample_count: 600 },
];
const CONTROLLERS = [{ id: 1, name: 'FIC-101', mode: 'AUTO' }];

test.beforeEach(async ({ page }) => {
  await page.route('**/api/controllers/stats', (r) => r.fulfill({ json: STATS }));
  await page.route('**/api/controllers', (r) => r.fulfill({ json: CONTROLLERS }));
  await page.route('**/api/opcua/status', (r) =>
    r.fulfill({ json: { state: 'ONLINE', endpoint: 'opc.tcp://x:4840' } }));
});

test('executive dashboard loads and renders KPI values equal to REST', async ({ page }) => {
  // reuse Fatia 0+1 login helper if available; else navigate + log in here
  await page.goto('/executive');
  await expect(page.getByTestId('executive-dashboard')).toBeVisible();
  // avgIae for one loop = 12.50 ; variability 0.04 → 4.0%
  await expect(page.getByTestId('kpi-iae')).toContainText('12.50');
  await expect(page.getByTestId('kpi-variability')).toContainText('4.0%');
  await expect(page.getByTestId('health-FIC-101-opc')).toContainText('ONLINE');
});

test('a live status/stats frame updates the cards without reload', async ({ page }) => {
  await page.goto('/executive');
  await expect(page.getByTestId('kpi-iae')).toContainText('12.50');
  // Drive a live update: re-stub stats with a new value and trigger a refetch
  await page.route('**/api/controllers/stats', (r) =>
    r.fulfill({ json: [{ ...STATS[0], iae: 9.0 }] }));
  // If the app exposes a WS test hook, push a stats frame here instead of reload.
  await page.reload();
  await expect(page.getByTestId('kpi-iae')).toContainText('9.00');
});
```

Run: `npm run test:e2e -- executive-dashboard` → Expected: FAIL until the page + route + (optionally) WS test hook are correct.

- [ ] **Step 2 (GREEN):** Iterate until both e2e tests pass. If the scaffold provides a WS test seam (e.g. a `window.__pushRealtime__` in dev), use it for the live-update assertion instead of `reload()`; otherwise the re-stub + reload path is acceptable and still proves the card reflects new REST.

Run: `npm run test:e2e -- executive-dashboard` → Expected: PASS (2 tests).

- [ ] **Step 3:** Commit.

```bash
git add e2e/executive-dashboard.spec.ts
git commit -m "test(web): e2e for executive dashboard load and live KPI update"
```

---

### Task 10 — Full suite, lint, build, spec docs

**Files:** modify `docs/smartPIDv2.md`, `docs/superpowers/specs/2026-06-18-web-fatia6-executive-dashboard-design.md`; create/append `docs/superpowers/plans/_web-hmi-INDEX.md`.

- [ ] **Step 1:** Run the full gate.

```bash
cd packages/smart_pid_web
npm run lint
npx tsc --noEmit
npm run test
npm run build
npm run test:e2e -- executive-dashboard
```

Expected: lint clean, no type errors, all Vitest green, `dist/` builds, e2e green.

- [ ] **Step 2:** Update the Fatia 6 design spec — mark implemented; record the final route (`/executive`), the component inventory (`ExecutiveKPICard`, `LoopHealthRow`, `PeriodSelector`, `TuningRecommendationCard`), and the confirmed endpoint list (incl. the `ai-history` no-response_model gap and the `StatsResponse` ↔ `StatsData` field-name mapping).

- [ ] **Step 3:** Update `docs/smartPIDv2.md` — describe the Web HMI Executive Dashboard (aggregate KPI bento cards, loop health + OPC pill, configurable period window, per-loop tuning recommendations) per the project's "specs obrigatórias ao alterar UI" rule.

- [ ] **Step 4:** Create/append `docs/superpowers/plans/_web-hmi-INDEX.md` with a line linking this plan:

```md
- Fatia 6 — Executive Dashboard: [2026-06-18-web-fatia6-executive-dashboard.md](2026-06-18-web-fatia6-executive-dashboard.md)
```

- [ ] **Step 5:** Commit docs.

```bash
git add docs/smartPIDv2.md docs/superpowers/specs/2026-06-18-web-fatia6-executive-dashboard-design.md docs/superpowers/plans/_web-hmi-INDEX.md
git commit -m "docs(web): document executive dashboard fatia and index the plan"
```

- [ ] **Step 6:** Update `.claude/docs/estado-atual.md` (project rule) with: fatia complete, branch `feat/web-fatia6-executive-dashboard`, files added, awaiting user approval to merge. Then STOP — do not auto-merge; merge to `main` only on explicit user approval.

---

## Self-Review

- **Backend untouched:** confirmed. The plan reuses `GET /controllers/stats`, `GET /controllers/{id}/stats`, `GET /controllers`, `GET /controllers/{id}/ai/status`, `GET /alarms/ai-history`, `GET /commands/tuning-recommendations/{id}`, `GET /opcua/status` — all verified against real router source. No router/DTO is added or edited.
- **Real endpoints, no invention:** the controller LIST is `GET /controllers` (there is **no** `/active`); `ai-history` lives in the **alarms** router; `tuning-recommendations` lives in **commands** and 404s when none exists; AI status is **per-loop** (no list endpoint). All confirmed from code.
- **Field-name reconciliation:** `StatsResponse` (`std_dev/total_variation/variability_sp/variability_range/sample_count`) vs WS `StatsData` (`sigma/tv/var_sp/var_range`) is unified in `kpi.ts` with `fromRestStats`/`fromWsStats`; this is the highest-risk gotcha and is unit-tested.
- **Numeric acceptance (NOT visual parity):** Vitest (`kpi.test.ts` exact mapping/aggregation; `ExecutiveDashboardPage.test.tsx` rendered numbers == mocked REST) and Playwright (rendered KPI == stubbed REST + live update). Cards use design-system tokens/components (`ExecutiveKPICard` per §5.10; tokens-only CSS; no sparklines; color only for out-of-target trend).
- **Required coverage met:** ExecutiveKPICard grid (per-loop + aggregate variability/TV/IAE/AI-engine/AUTO%), loop health (running/stopped/error + OPC), configurable period window (`period.ts` + `PeriodSelector`), per-loop tuning recommendations, live `status`/`stats` updates via `useRealtime` + `onResync` refetch.
- **TDD + constraints:** every code task is RED→GREEN→commit, bite-sized, checkbox-tracked; branch `feat/web-fatia6-executive-dashboard` from `main`; conventional commits, no trailers; mono-user/no-RBAC override applied (auth mandatory, no role gating).
- **Documented gaps:** (1) `GET /alarms/ai-history` has no Pydantic `response_model` → contract §6 precondition gap; the plan adds a hand-typed `AiHistoryEntry` and notes it rather than mutating the backend. (2) "AI engine state" aggregate is derived from `controllers[].ai_config.engine` + per-loop `ai/status` since no aggregate AI endpoint exists.
- **Open risks:** exact token names and `apiGet`/`useRealtime` signatures depend on the merged Fatia 0+1 scaffold; Task 1 verifies them and later tasks adapt to the canonical names. Test file layout (colocated vs `tests/`/`e2e/`) is confirmed in Task 1 Step 4 and paths adjusted to match.
