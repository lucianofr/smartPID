# Phase 3 — Realtime Layer + Pure Modules Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the rewritten client's realtime layer (`RealtimeProvider`, `useRealtime`, normative §7 resync) and all pure logic modules (`envelope`, `windowBuffer`, `alarmMachine`, `scale`/`format` extensions), plus the typed `apiClient` and the `auth/` surface (`AuthContext`, `useCan`, `RouteGuard`) — fully unit-tested, with **no pages, no routes, no App.tsx changes** (E2E stays dark per spec §13).

**Architecture:** Pure modules first (no React, no DOM — spec §7), then the typed REST client over the phase-2 generated OpenAPI types, then the auth context, then the WebSocket provider that consumes all of it. One socket per session; REST is the source of truth; on reconnect or `seq` gap the §7 resync set runs before live render resumes (spec §8). Types mirror the backend wire **field-for-field** with the producing backend line cited next to every interface.

**Tech Stack:** React 18.3 (provider/hooks only), TypeScript 5.5 `strict`, Vitest 2 + jsdom + Testing Library, TanStack Query v5 (`QueryClient` cache priming), openapi-typescript 7 generated types (committed by phase 2). No new npm dependencies.

## Global Constraints

- All commands run from the worktree root `smartPID/.worktrees/web-frontend-rewrite/`; frontend commands run with `packages/smart_pid_web` as cwd (shown explicitly per step).
- React pinned at **18** (spec §7); no React/DOM imports allowed inside `src/lib/*` (pure modules, spec §7 "Layered so that logic is testable without a DOM").
- Spec-pinned module names (NEVER deviate): `envelope`, `windowBuffer`, `alarmMachine`, `scale`, `format` in `packages/smart_pid_web/src/lib/`; `RealtimeProvider`, `useRealtime(loopId, type)` in `src/realtime/`; `AuthContext`, `RouteGuard`, `useCan(action)` in `src/auth/`; api client in `src/api/`.
- Roles are lowercase `'admin' | 'user'` (spec §9, phase-0 migration). Legacy uppercase never reaches this client: legacy JWTs are rejected 401 by phase 0.
- Absent/invalid numeric renders as `'—'` (em dash U+2014) — same glyph phase 2's `formatNumber` pins.
- Session token storage key: `sessionStorage['smart-pid-token']` — kept verbatim (retained E2E specs seed it).
- REST base path is `/api` (single constant in `src/api/client.ts`); Vite dev proxy strips it (`packages/smart_pid_web/vite.config.ts:22-29`). WS endpoint is `/ws/realtime` (proxied at `/ws`, `vite.config.ts:28`).
- WS close code `4401` = auth failure (`realtime.py:27`) → force re-login, never reconnect (spec §11). Any other close (including a future server overflow close) → reconnect with backoff; every reconnect resyncs, which is what §11 requires for "WS overflow close". (Note: backend `ConnectionBuffer` — `realtime.py:168-191` — is currently **not wired** into the endpoint; no dedicated overflow close code exists today.)
- Commits: conventional style matching repo history (`feat(web): ...`, `test(web): ...`), one commit per task.
- Test commands: `npm run test -- <file>` (vitest run), `npm run typecheck` (`tsc -b`), `npm run lint` (`eslint .`) — all with cwd `packages/smart_pid_web`. Vitest config: jsdom, `globals: true`, setup `src/test/setup.ts` (exists from phase 2), include `src/**/*.test.{ts,tsx}`.
- Import style: use the `@/` alias for cross-directory imports (configured in `tsconfig.json:19-21`, `vite.config.ts:14-18`, `vitest.config.ts:8-12`); same-directory imports stay relative. (Code below uses relative `../` between sibling top-level dirs — both resolve; keep whichever the phase-2 scaffold standardised, but be consistent per file.)
- Do NOT touch `src/App.tsx`, `src/pages/`, `src/main.tsx`, `src/features/` — mounting the providers is phase 4's job. Do NOT touch `src/lib/uplotTheme.ts` (phase 2 owns it).

## Interfaces consumed (pinned by phases 0 and 2 — do not re-derive)

**From phase 0 (backend, `docs/superpowers/plans/2026-07-26-phase00-two-role-rbac.md`):**

- `GET /auth/me` — gated `require_user`, `response_model=UserClaims` → `{"user_id": number, "username": string, "role": "admin" | "user"}`. The client **never decodes the JWT**; role comes from this endpoint.
- `POST /auth/login` — `TokenResponse` **unchanged**: `{"access_token": string, "token_type": "bearer"}` (no role field).
- Resync-set route classification: `GET /controllers`, `GET /controllers/{id}`, `GET /alarms/active`, `GET /alarms/history`, `GET /opcua/status`, `GET /controllers/{id}/ai/status` → `require_user`. `GET /simulator/status` → **admin-only**: a `user`-role resync must treat its deterministic 403 as skip, not error.
- Error body shape for 4xx: `{"detail": string}` (`error_handlers.py:22-34`); FastAPI 422 uses `{"detail": [{loc, msg, type}, ...]}`.

**From phase 2 (frontend scaffold, quoted verbatim from its Interfaces-exported section):**

- Generated OpenAPI types committed at `packages/smart_pid_web/src/api/generated/openapi.ts` (openapi-typescript 7 standard output: `export interface paths {...}`, `export interface components {...}`, `export interface operations {...}`). Import as `import type { components } from '@/api/generated/openapi'`. Regenerated by `npm run gen:api` (hermetic dump chain); CI drift gate `npm run gen:api:check`.
- `src/lib/scale.ts` (base, phase 2):
  - `export interface Scale { euMin: number; euMax: number; unit: string }`
  - `export function valueToFraction(value: number, scale: Scale): number` — clamped 0..1, returns 0 when span <= 0
  - `export function ticks(scale: Scale, count?: number): number[]` — evenly spaced tick values euMin→euMax inclusive, count defaults 5, minimum 2 (not consumed by phase 3; listed for completeness)
- `src/lib/format.ts` (base, phase 2):
  - `export function formatNumber(value: number | null | undefined, decimals: number): string` — `value.toFixed(decimals)`; returns `'—'` for null/undefined/NaN; does NOT append units
- `vitest.config.ts` + `src/test/setup.ts` exist (jsdom stubs for canvas/ResizeObserver/matchMedia).
- `src/api/queryClient.ts` may exist from scaffold; this plan does not depend on it (the resync runner takes a `QueryClient` argument).

## Backend wire evidence (every mirrored field cites its producer)

All paths relative to `packages/smart_pid_core/src/smart_pid_core/` unless noted.

| Client type | Backend source |
|---|---|
| Envelope `{type, loop_id, seq, ts, data}` | `adapters/inbound/api/ws/realtime.py:109` |
| Type taxonomy `status/action/ai/alarm/system/stats` (+ `has_loop_id`) | `realtime.py:82-89` (`_TOPIC_MAP`); `EVENT.SYSTEM` → `loop_id: null` (`realtime.py:99,104-108`) |
| `seq` monotonic per-bridge counter | `realtime.py:127,154` |
| `ts` epoch seconds `time.time()` | `realtime.py:156` |
| Handshake `{"type":"auth","token"}` → `{"type":"auth_ok"}`, close 4401 | `realtime.py:208-225`, `realtime.py:27` |
| `FFSignal {value, severity, limit_bits, sub_status}` | `application/workers/pid_worker.py:88-95` (`_serialize_ff_signal`), defaults `monitor_worker.py:25-28` |
| `StatusData` (execute) | `pid_worker.py:438-455` |
| `StatusData` (monitor: `error`, `saturated`, float `timestamp`, nullable kp/ti/td) | `monitor_worker.py:109-138` |
| `ActionData` | `pid_worker.py:421-430` |
| `AiData` | `ai_worker.py:295-305` |
| `AlarmEventData`, transitions `TRIGGERED`/`CLEARED` | `alarm_worker.py:169-179`; `domain/services/alarm_engine.py:207,240` |
| `SystemEventData` | `system_event_worker.py:31-39` |
| `StatsData` (17 keys, no controller_id on the wire) | `stats_worker.py:86-108`; field list matches `smart_pid_domain/dtos/ai.py:14-35` minus `controller_id` |
| Alarm REST rows + `status` CASE | `adapters/outbound/alarm_repo.py:114-135` (active), `:191-215` (history) |
| `GET /alarms/history` requires `start` AND `end` (ISO, `fromisoformat`), `limit` default 100 | `adapters/inbound/api/routers/alarms.py:34-54` |
| Router prefixes (`/auth`, `/controllers`, `/alarms`, `/opcua`, `/simulator`, ai under `/controllers`) | `adapters/inbound/api/app.py:161-174` |

---

### Task 1: Envelope types + parse/validate (`src/lib/envelope.ts`)

**Files:**
- Create: `packages/smart_pid_web/src/lib/envelope.ts`
- Test: `packages/smart_pid_web/src/lib/envelope.test.ts`

**Interfaces:**
- Consumes: nothing (pure module, first task).
- Produces: `RealtimeType`, `REALTIME_TYPES`, `RealtimeEnvelope<T>`, `FFSignal`, `StatusData`, `ActionData`, `AiData`, `AlarmTransition`, `AlarmEventData`, `SystemEventData`, `StatsData`, `AnyEnvelope`, `isAuthOk(v): boolean`, `validateEnvelope(v): v is AnyEnvelope`, `parseEnvelope(raw): AnyEnvelope | null`, `statusTimestampToEpoch(ts): number | null`. Tasks 2, 13, 14 import these exact names.

- [ ] **Step 1: Write the failing test**

Create `packages/smart_pid_web/src/lib/envelope.test.ts`:

```ts
import { describe, expect, it } from 'vitest';
import {
  isAuthOk,
  parseEnvelope,
  statusTimestampToEpoch,
  validateEnvelope,
} from './envelope';

const statusEnvelope = {
  type: 'status',
  loop_id: 12,
  seq: 7,
  ts: 1718743200.5,
  data: { pv: { value: 150.2 } },
};

describe('validateEnvelope', () => {
  it('accepts a well-formed status envelope', () => {
    expect(validateEnvelope(statusEnvelope)).toBe(true);
  });

  it('accepts loop_id null (EVENT.SYSTEM has no loop)', () => {
    expect(
      validateEnvelope({ type: 'system', loop_id: null, seq: 1, ts: 0, data: {} }),
    ).toBe(true);
  });

  it('rejects the auth_ok handshake frame (not an envelope)', () => {
    expect(validateEnvelope({ type: 'auth_ok' })).toBe(false);
  });

  it('rejects unknown types', () => {
    expect(
      validateEnvelope({ type: 'telemetry', loop_id: 1, seq: 1, ts: 0, data: {} }),
    ).toBe(false);
  });

  it('rejects missing seq / non-numeric ts / absent data', () => {
    expect(validateEnvelope({ type: 'status', loop_id: 1, ts: 0, data: {} })).toBe(false);
    expect(
      validateEnvelope({ type: 'status', loop_id: 1, seq: 1, ts: 'x', data: {} }),
    ).toBe(false);
    expect(validateEnvelope({ type: 'status', loop_id: 1, seq: 1, ts: 0 })).toBe(false);
  });

  it('rejects primitives and null', () => {
    expect(validateEnvelope(null)).toBe(false);
    expect(validateEnvelope('status')).toBe(false);
  });
});

describe('parseEnvelope', () => {
  it('parses valid JSON envelopes', () => {
    const env = parseEnvelope(JSON.stringify(statusEnvelope));
    expect(env).not.toBeNull();
    expect(env?.type).toBe('status');
    expect(env?.loop_id).toBe(12);
    expect(env?.seq).toBe(7);
  });

  it('returns null for invalid JSON and for non-envelopes', () => {
    expect(parseEnvelope('{oops')).toBeNull();
    expect(parseEnvelope(JSON.stringify({ type: 'auth_ok' }))).toBeNull();
  });
});

describe('isAuthOk', () => {
  it('recognises the handshake ack frame', () => {
    expect(isAuthOk({ type: 'auth_ok' })).toBe(true);
    expect(isAuthOk(statusEnvelope)).toBe(false);
    expect(isAuthOk(null)).toBe(false);
  });
});

describe('statusTimestampToEpoch', () => {
  it('passes through finite epoch-second numbers (monitor mode)', () => {
    expect(statusTimestampToEpoch(1718743200.5)).toBe(1718743200.5);
  });

  it('parses ISO-8601 strings to epoch seconds (execute mode)', () => {
    expect(statusTimestampToEpoch('2024-06-18T20:40:00.000Z')).toBe(1718743200);
  });

  it('returns null for garbage', () => {
    expect(statusTimestampToEpoch('not-a-date')).toBeNull();
    expect(statusTimestampToEpoch(Number.NaN)).toBeNull();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run (cwd `packages/smart_pid_web`): `npm run test -- src/lib/envelope.test.ts`
Expected: FAIL — `Failed to resolve import "./envelope" from "src/lib/envelope.test.ts"` (module does not exist yet).

- [ ] **Step 3: Write the implementation**

Create `packages/smart_pid_web/src/lib/envelope.ts`:

```ts
/**
 * WS envelope — pure module, no React, no DOM (spec §7).
 *
 * Mirrors the backend bridge field-for-field:
 *   realtime.py:109    envelope shape {type, loop_id, seq, ts, data}
 *   realtime.py:82-89  topic → type taxonomy (has_loop_id per prefix)
 *   realtime.py:154    seq: monotonic per-bridge counter (shared by all sockets)
 *   realtime.py:156    ts: server time.time() → epoch SECONDS
 */

export type RealtimeType = 'status' | 'action' | 'ai' | 'alarm' | 'system' | 'stats';

export const REALTIME_TYPES: readonly RealtimeType[] = [
  'status',
  'action',
  'ai',
  'alarm',
  'system',
  'stats',
];

export interface RealtimeEnvelope<T = unknown> {
  type: RealtimeType;
  /** Parsed from the numeric topic suffix; null for EVENT.SYSTEM (realtime.py:99). */
  loop_id: number | null;
  /** Per-bridge monotonic counter (realtime.py:154); restarts when the daemon restarts. */
  seq: number;
  /** Epoch seconds, server-stamped (realtime.py:156). */
  ts: number;
  data: T;
}

/** Fieldbus signal dict — pid_worker.py:88-95 (_serialize_ff_signal). */
export interface FFSignal {
  value: number;
  severity: string;
  limit_bits: string;
  sub_status: string;
}

/**
 * STATUS.{id} — two producers, one shape plus two monitor-only fields:
 *   execute: pid_worker.py:438-455 (timestamp ISO-8601 string; kp/ti/td always numbers)
 *   monitor: monitor_worker.py:109-138 (timestamp may be float epoch seconds via
 *            time.time() fallback; adds error + saturated; kp/ti/td via .get() → null)
 */
export interface StatusData {
  controller_id: number;
  pv: FFSignal;
  sp: FFSignal;
  co: FFSignal;
  bkcal_in: FFSignal;
  bkcal_out: FFSignal;
  mode: string;
  kp: number | null;
  ti: number | null;
  td: number | null;
  integral_val: number;
  timestamp: string | number;
  /** monitor mode only: pv - sp (monitor_worker.py:116,132). */
  error?: number;
  /** monitor mode only: CO limit_bits HIGH_LIMITED/LOW_LIMITED (monitor_worker.py:118-121,133). */
  saturated?: boolean;
}

/** ACTION.CTRL.{id} — pid_worker.py:421-430. */
export interface ActionData {
  controller_id: number;
  co: FFSignal;
  bkcal_out: FFSignal;
  integral_val: number;
  delta_cv: number;
  timestamp: string;
}

/** ACTION.AI.{id} — ai_worker.py:295-305. */
export interface AiData {
  controller_id: number;
  gamma: number;
  new_ki: number;
  engine: string;
  objective: string;
  integral_type: string;
  execution_mode: string;
  reasoning: string;
  timestamp: string;
}

/** Wire transition values — alarm_engine.py:207,240. */
export type AlarmTransition = 'TRIGGERED' | 'CLEARED';

/** EVENT.ALARM.{id} — alarm_worker.py:169-179. Carries NO row id: alarms are keyed
 *  client-side by (controller_id, alarm_type); REST remains the source of row state. */
export interface AlarmEventData {
  controller_id: number;
  controller_name: string;
  controller_description: string;
  alarm_type: string;
  priority: string;
  transition: AlarmTransition;
  value: number;
  limit: number;
  timestamp: string;
}

/** EVENT.SYSTEM — system_event_worker.py:31-39. */
export interface SystemEventData {
  source: string;
  severity: string;
  message: string;
  timestamp: string;
}

/** STATS.{id} — stats_worker.py:86-108. The wire payload has NO controller_id
 *  (loop identity travels in envelope.loop_id); the REST StatsResponse does. */
export interface StatsData {
  iae: number;
  itae: number;
  ise: number;
  mse: number;
  std_dev: number;
  total_variation: number;
  variability_sp: number;
  variability_range: number;
  mean_abs_error: number;
  pk_pk_error: number;
  reversals: number;
  zero_crossings: number;
  recent_pk_pk_error: number;
  recent_reversals: number;
  tv_per_sample: number;
  osc: number;
  sample_count: number;
}

export type AnyEnvelope =
  | (RealtimeEnvelope<StatusData> & { type: 'status' })
  | (RealtimeEnvelope<ActionData> & { type: 'action' })
  | (RealtimeEnvelope<AiData> & { type: 'ai' })
  | (RealtimeEnvelope<AlarmEventData> & { type: 'alarm' })
  | (RealtimeEnvelope<SystemEventData> & { type: 'system' })
  | (RealtimeEnvelope<StatsData> & { type: 'stats' });

/** First server frame after a successful handshake (realtime.py:225). Not an envelope. */
export function isAuthOk(v: unknown): boolean {
  return typeof v === 'object' && v !== null && (v as { type?: unknown }).type === 'auth_ok';
}

/** Structural guard for the envelope shell. Payloads are typed, not runtime-checked:
 *  the producers above are the contract, and unknown extra keys must pass through. */
export function validateEnvelope(v: unknown): v is AnyEnvelope {
  if (typeof v !== 'object' || v === null) return false;
  const e = v as Record<string, unknown>;
  return (
    typeof e.type === 'string' &&
    (REALTIME_TYPES as readonly string[]).includes(e.type) &&
    (e.loop_id === null || typeof e.loop_id === 'number') &&
    typeof e.seq === 'number' &&
    typeof e.ts === 'number' &&
    'data' in e
  );
}

export function parseEnvelope(raw: string): AnyEnvelope | null {
  let v: unknown;
  try {
    v = JSON.parse(raw);
  } catch {
    return null;
  }
  return validateEnvelope(v) ? v : null;
}

/**
 * StatusData.timestamp normaliser: ISO-8601 string (execute mode) or float epoch
 * seconds (monitor mode) → epoch seconds; null when unparseable. Callers decide
 * the fallback (the window buffer rejects non-monotonic time anyway).
 */
export function statusTimestampToEpoch(ts: string | number): number | null {
  if (typeof ts === 'number') return Number.isFinite(ts) ? ts : null;
  const ms = Date.parse(ts);
  return Number.isNaN(ms) ? null : ms / 1000;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run (cwd `packages/smart_pid_web`): `npm run test -- src/lib/envelope.test.ts`
Expected: PASS — 1 test file, 12 tests.

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_web/src/lib/envelope.ts packages/smart_pid_web/src/lib/envelope.test.ts
git commit -m "feat(web): add realtime envelope types mirroring the WS bridge"
```

---

### Task 2: Seq-gap tracker + `last_seen_ts` per topic class (`envelope.ts`, second cycle)

**Files:**
- Modify: `packages/smart_pid_web/src/lib/envelope.ts` (append)
- Test: `packages/smart_pid_web/src/lib/envelope.test.ts` (append)

**Interfaces:**
- Consumes: `RealtimeEnvelope`, `RealtimeType` (Task 1).
- Produces: `SeqObservation { gap: boolean; expected: number | null; received: number }`, `SeqTracker { observe(env): SeqObservation; lastSeenTs(type): number | null; reset(): void }`, `createSeqTracker(): SeqTracker`. Task 13 uses `observe`/`reset`; Task 12's resync context is fed from `lastSeenTs('alarm')`.

- [ ] **Step 1: Write the failing test**

Append to `packages/smart_pid_web/src/lib/envelope.test.ts` (add `createSeqTracker` to the existing import from `./envelope`):

```ts
describe('createSeqTracker', () => {
  const env = (seq: number, type: 'status' | 'alarm' = 'status', ts = seq * 10) =>
    ({ type, loop_id: 1, seq, ts, data: {} }) as const;

  it('reports no gap on the first observation', () => {
    const t = createSeqTracker();
    expect(t.observe(env(41))).toEqual({ gap: false, expected: null, received: 41 });
  });

  it('reports no gap for consecutive seq', () => {
    const t = createSeqTracker();
    t.observe(env(1));
    expect(t.observe(env(2)).gap).toBe(false);
  });

  it('reports a gap when seq jumps forward', () => {
    const t = createSeqTracker();
    t.observe(env(1));
    expect(t.observe(env(3))).toEqual({ gap: true, expected: 2, received: 3 });
  });

  it('reports a gap when seq regresses (daemon restart resets the bridge counter)', () => {
    const t = createSeqTracker();
    t.observe(env(100));
    expect(t.observe(env(1)).gap).toBe(true);
  });

  it('tracks last_seen_ts per topic class', () => {
    const t = createSeqTracker();
    t.observe(env(1, 'status', 10));
    t.observe(env(2, 'alarm', 20));
    t.observe(env(3, 'status', 30));
    expect(t.lastSeenTs('status')).toBe(30);
    expect(t.lastSeenTs('alarm')).toBe(20);
    expect(t.lastSeenTs('ai')).toBeNull();
  });

  it('reset() clears the seq baseline but KEEPS last_seen_ts (resync needs it)', () => {
    const t = createSeqTracker();
    t.observe(env(5, 'alarm', 55));
    t.reset();
    expect(t.lastSeenTs('alarm')).toBe(55);
    expect(t.observe(env(999)).gap).toBe(false); // fresh baseline after reconnect
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run (cwd `packages/smart_pid_web`): `npm run test -- src/lib/envelope.test.ts`
Expected: FAIL — `createSeqTracker` is not exported by `./envelope`.

- [ ] **Step 3: Write the implementation**

Append to `packages/smart_pid_web/src/lib/envelope.ts`:

```ts
export interface SeqObservation {
  gap: boolean;
  expected: number | null;
  received: number;
}

export interface SeqTracker {
  /** Feed every validated envelope. gap=true ⇒ messages were lost (jump OR daemon-restart regression). */
  observe(env: Pick<RealtimeEnvelope, 'type' | 'seq' | 'ts'>): SeqObservation;
  /** Server ts of the last envelope seen per topic class — feeds the §7 resync
   *  "alarm history since last_seen_ts" window. */
  lastSeenTs(type: RealtimeType): number | null;
  /** Call on every (re)connect: the seq baseline is meaningless across
   *  connections (frames were missed), but last_seen_ts survives — the resync
   *  window must span the disconnect. */
  reset(): void;
}

export function createSeqTracker(): SeqTracker {
  let lastSeq: number | null = null;
  const lastTs = new Map<RealtimeType, number>();
  return {
    observe(env) {
      const expected = lastSeq === null ? null : lastSeq + 1;
      const gap = lastSeq !== null && env.seq !== lastSeq + 1;
      lastSeq = env.seq;
      lastTs.set(env.type, env.ts);
      return { gap, expected, received: env.seq };
    },
    lastSeenTs(type) {
      return lastTs.get(type) ?? null;
    },
    reset() {
      lastSeq = null;
    },
  };
}
```

- [ ] **Step 4: Run test to verify it passes**

Run (cwd `packages/smart_pid_web`): `npm run test -- src/lib/envelope.test.ts`
Expected: PASS — 18 tests.

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_web/src/lib/envelope.ts packages/smart_pid_web/src/lib/envelope.test.ts
git commit -m "feat(web): add seq-gap tracker with per-type last-seen timestamps"
```

---

### Task 3: Bounded sliding window with pen-tip head (`src/lib/windowBuffer.ts`)

**Files:**
- Create: `packages/smart_pid_web/src/lib/windowBuffer.ts`
- Test: `packages/smart_pid_web/src/lib/windowBuffer.test.ts`

**Interfaces:**
- Consumes: nothing (pure module).
- Produces: `WindowBufferConfig { maxSeconds: number; maxPoints: number }`, `WindowSample { t: number; values: readonly number[] }`, `WindowView { data: number[][]; decimated: boolean }`, `WindowBuffer { push(t, values): boolean; latest(): WindowSample | null; view(pxWidth): WindowView; length(): number; clear(): void }`, `createWindowBuffer(seriesCount: number, cfg: WindowBufferConfig): WindowBuffer`. Phase 4's Trend feeds `view().data` to uPlot and draws the pen tip from `latest()` (spec §6.7: the decimation policy **must expose the undecimated head** or the pen visibly jumps at high rates).

- [ ] **Step 1: Write the failing test**

Create `packages/smart_pid_web/src/lib/windowBuffer.test.ts`:

```ts
import { describe, expect, it } from 'vitest';
import { createWindowBuffer } from './windowBuffer';

const WIDE = { maxSeconds: Number.POSITIVE_INFINITY, maxPoints: Number.POSITIVE_INFINITY };

describe('createWindowBuffer', () => {
  it('stores pushed samples and reports length', () => {
    const b = createWindowBuffer(3, WIDE);
    expect(b.push(1, [10, 20, 30])).toBe(true);
    expect(b.push(2, [11, 21, 31])).toBe(true);
    expect(b.length()).toBe(2);
    expect(b.view(100).data).toEqual([
      [1, 2],
      [10, 11],
      [20, 21],
      [30, 31],
    ]);
  });

  it('rejects non-monotonic and non-finite timestamps (uPlot x must ascend)', () => {
    const b = createWindowBuffer(1, WIDE);
    b.push(5, [1]);
    expect(b.push(5, [2])).toBe(false);
    expect(b.push(4, [3])).toBe(false);
    expect(b.push(Number.NaN, [4])).toBe(false);
    expect(b.length()).toBe(1);
  });

  it('throws on wrong series arity', () => {
    const b = createWindowBuffer(2, WIDE);
    expect(() => b.push(1, [1])).toThrow(RangeError);
  });

  it('trims by time window, dropping from the left', () => {
    const b = createWindowBuffer(1, { maxSeconds: 10, maxPoints: Number.POSITIVE_INFINITY });
    b.push(0, [0]);
    b.push(5, [5]);
    b.push(20, [20]); // cutoff = 20 - 10 = 10 → drops t=0 and t=5
    expect(b.view(100).data[0]).toEqual([20]);
  });

  it('enforces the hard point cap after the time window', () => {
    const b = createWindowBuffer(1, { maxSeconds: Number.POSITIVE_INFINITY, maxPoints: 3 });
    for (let t = 1; t <= 5; t += 1) b.push(t, [t]);
    expect(b.view(100).data[0]).toEqual([3, 4, 5]);
  });

  it('latest() returns the undecimated newest sample — the §6.7 pen tip', () => {
    const b = createWindowBuffer(1, WIDE);
    // 400 samples into 100 px: min/max decimation keeps bucket extremes only.
    for (let i = 0; i < 400; i += 1) b.push(i, [Math.sin(i / 7) * 100]);
    // Final sample is mid-range: a min/max pick would typically drop it.
    b.push(400, [0.123]);
    const view = b.view(100);
    expect(view.decimated).toBe(true);
    expect(b.latest()).toEqual({ t: 400, values: [0.123] });
  });

  it('decimation preserves bucket extremes (transients survive)', () => {
    const b = createWindowBuffer(1, WIDE);
    for (let i = 0; i < 1000; i += 1) b.push(i, [i === 500 ? 9999 : 0]);
    const view = b.view(50);
    expect(view.decimated).toBe(true);
    expect(view.data[0].length).toBeLessThanOrEqual(100); // ≤ 2 per pixel column
    expect(view.data[1]).toContain(9999); // the spike survives
    const xs = view.data[0];
    for (let i = 1; i < xs.length; i += 1) expect(xs[i]).toBeGreaterThanOrEqual(xs[i - 1]);
  });

  it('view() below the pixel threshold is a verbatim, defensive copy', () => {
    const b = createWindowBuffer(1, WIDE);
    b.push(1, [10]);
    const view = b.view(100);
    expect(view.decimated).toBe(false);
    view.data[0].push(999); // mutating the view must not corrupt the buffer
    expect(b.view(100).data[0]).toEqual([1]);
  });

  it('clear() empties the buffer', () => {
    const b = createWindowBuffer(2, WIDE);
    b.push(1, [1, 2]);
    b.clear();
    expect(b.length()).toBe(0);
    expect(b.latest()).toBeNull();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run (cwd `packages/smart_pid_web`): `npm run test -- src/lib/windowBuffer.test.ts`
Expected: FAIL — `Failed to resolve import "./windowBuffer"`.

- [ ] **Step 3: Write the implementation**

Create `packages/smart_pid_web/src/lib/windowBuffer.ts`:

```ts
/**
 * Bounded sliding window with explicit min/max decimation — pure module (spec §7).
 *
 * Replaces the deleted client's ad-hoc pair (immutable append with ring cap in
 * features/simulator/twinTrend.ts + min/max column decimation in
 * features/multitrend/decimate.ts) with one buffer that ALSO exposes the
 * undecimated newest sample: the Recorder pen tip marks valToPos() of the TRUE
 * latest sample, not the tail of the decimated series (spec §6.7).
 */

export interface WindowBufferConfig {
  /** Time window in seconds; Infinity disables the time bound. */
  maxSeconds: number;
  /** Hard point cap applied after the time window; Infinity disables it. */
  maxPoints: number;
}

export interface WindowSample {
  t: number;
  values: readonly number[];
}

export interface WindowView {
  /** uPlot AlignedData shape: data[0] = ascending t, then one row per series. */
  data: number[][];
  decimated: boolean;
}

export interface WindowBuffer {
  /** Returns false (and drops the sample) for non-finite or non-increasing t. */
  push(t: number, values: readonly number[]): boolean;
  /** Undecimated head — the §6.7 pen tip. */
  latest(): WindowSample | null;
  /** Window contents; min/max-per-pixel-column decimated when length > pxWidth. */
  view(pxWidth: number): WindowView;
  length(): number;
  clear(): void;
}

export function createWindowBuffer(
  seriesCount: number,
  cfg: WindowBufferConfig,
): WindowBuffer {
  if (!Number.isInteger(seriesCount) || seriesCount < 1) {
    throw new RangeError(`seriesCount must be a positive integer, got ${seriesCount}`);
  }
  let ts: number[] = [];
  let rows: number[][] = Array.from({ length: seriesCount }, () => []);

  const trim = (): void => {
    const n = ts.length;
    if (n === 0) return;
    let start = 0;
    if (Number.isFinite(cfg.maxSeconds)) {
      const cutoff = ts[n - 1] - cfg.maxSeconds;
      while (start < n && ts[start] < cutoff) start += 1;
    }
    if (Number.isFinite(cfg.maxPoints) && n - start > cfg.maxPoints) {
      start = n - cfg.maxPoints;
    }
    if (start > 0) {
      ts = ts.slice(start);
      rows = rows.map((r) => r.slice(start));
    }
  };

  return {
    push(t, values) {
      if (values.length !== seriesCount) {
        throw new RangeError(
          `expected ${seriesCount} series values, got ${values.length}`,
        );
      }
      if (!Number.isFinite(t)) return false;
      const last = ts[ts.length - 1];
      if (last !== undefined && t <= last) return false;
      ts.push(t);
      for (let i = 0; i < seriesCount; i += 1) rows[i].push(values[i]);
      trim();
      return true;
    },

    latest() {
      const n = ts.length;
      if (n === 0) return null;
      return { t: ts[n - 1], values: rows.map((r) => r[n - 1]) };
    },

    view(pxWidth) {
      const n = ts.length;
      if (pxWidth <= 0 || n <= pxWidth) {
        return { data: [ts.slice(), ...rows.map((r) => r.slice())], decimated: false };
      }
      // Min/max per pixel column: each bucket contributes its min-sample and its
      // max-sample so transients and peaks survive (critical for control trends).
      const outX: number[] = [];
      const outRows: number[][] = rows.map(() => []);
      const perBucket = n / pxWidth;
      for (let b = 0; b < pxWidth; b += 1) {
        const lo = Math.floor(b * perBucket);
        const hi = Math.min(n, Math.floor((b + 1) * perBucket));
        if (hi <= lo) continue;
        for (let pass = 0; pass < 2; pass += 1) {
          let xi = lo;
          outRows.forEach((out, r) => {
            const row = rows[r];
            let bestIdx = lo;
            let best = row[lo];
            for (let i = lo + 1; i < hi; i += 1) {
              const v = row[i];
              if ((pass === 0 && v < best) || (pass === 1 && v > best)) {
                best = v;
                bestIdx = i;
              }
            }
            out.push(best);
            if (r === 0) xi = bestIdx;
          });
          outX.push(ts[xi]);
        }
      }
      // Re-sort by x so min/max columns stay monotonic for uPlot.
      const order = outX.map((_, i) => i).sort((a, c) => outX[a] - outX[c]);
      return {
        data: [
          order.map((i) => outX[i]),
          ...outRows.map((row) => order.map((i) => row[i])),
        ],
        decimated: true,
      };
    },

    length() {
      return ts.length;
    },

    clear() {
      ts = [];
      rows = rows.map(() => []);
    },
  };
}
```

- [ ] **Step 4: Run test to verify it passes**

Run (cwd `packages/smart_pid_web`): `npm run test -- src/lib/windowBuffer.test.ts`
Expected: PASS — 9 tests.

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_web/src/lib/windowBuffer.ts packages/smart_pid_web/src/lib/windowBuffer.test.ts
git commit -m "feat(web): add bounded window buffer exposing the undecimated pen tip"
```

---

### Task 4: Four-state alarm machine (`src/lib/alarmMachine.ts`)

**Files:**
- Create: `packages/smart_pid_web/src/lib/alarmMachine.ts`
- Test: `packages/smart_pid_web/src/lib/alarmMachine.test.ts`

**Interfaces:**
- Consumes: nothing at runtime; the event kinds reuse the `AlarmTransition` wire values (Task 1).
- Produces: `AlarmPointState`, `AlarmMachineEvent`, `transition(state, event): AlarmPointState`, `fromActiveRow(row): AlarmPointState`, `isUnacked(state): boolean`, `isActive(state): boolean`. Phase 6 (alarms feature) keys machines by `(controller_id, alarm_type)` and drives them from `alarm` envelopes + ack mutations.

**The normative state table** (backend truth: `alarm_engine.py:207,240` emits `TRIGGERED` only on the inactive→active edge and `CLEARED` on the active→inactive edge; `alarm_repo.py:129-132` derives row status from `reconhecido`/`cleared_at`; rows leave the active set when cleared ∧ acked):

| state \ event      | `TRIGGERED`        | `CLEARED`       | `ACK`          |
|--------------------|--------------------|-----------------|----------------|
| `NORMAL`           | `UNACKNOWLEDGED`   | `NORMAL`        | `NORMAL`       |
| `UNACKNOWLEDGED`   | `UNACKNOWLEDGED`   | `CLEARED_UNACK` | `ACKNOWLEDGED` |
| `ACKNOWLEDGED`     | `UNACKNOWLEDGED` ¹ | `NORMAL`        | `ACKNOWLEDGED` |
| `CLEARED_UNACK`    | `UNACKNOWLEDGED` ² | `CLEARED_UNACK` | `NORMAL`       |

¹ The engine cannot emit this without an intervening `CLEARED` we may have missed (gap healing): a new occurrence always requires a new acknowledgement.
² A re-trigger while cleared-unacked is a NEW alarm instance; it supersedes the stale cleared one and stays unacked.

- [ ] **Step 1: Write the failing test**

Create `packages/smart_pid_web/src/lib/alarmMachine.test.ts`:

```ts
import { describe, expect, it } from 'vitest';
import {
  fromActiveRow,
  isActive,
  isUnacked,
  transition,
  type AlarmPointState,
} from './alarmMachine';

describe('transition — full 12-cell table', () => {
  const cases: Array<[AlarmPointState, 'TRIGGERED' | 'CLEARED' | 'ACK', AlarmPointState]> = [
    ['NORMAL', 'TRIGGERED', 'UNACKNOWLEDGED'],
    ['NORMAL', 'CLEARED', 'NORMAL'],
    ['NORMAL', 'ACK', 'NORMAL'],
    ['UNACKNOWLEDGED', 'TRIGGERED', 'UNACKNOWLEDGED'],
    ['UNACKNOWLEDGED', 'CLEARED', 'CLEARED_UNACK'],
    ['UNACKNOWLEDGED', 'ACK', 'ACKNOWLEDGED'],
    ['ACKNOWLEDGED', 'TRIGGERED', 'UNACKNOWLEDGED'],
    ['ACKNOWLEDGED', 'CLEARED', 'NORMAL'],
    ['ACKNOWLEDGED', 'ACK', 'ACKNOWLEDGED'],
    ['CLEARED_UNACK', 'TRIGGERED', 'UNACKNOWLEDGED'],
    ['CLEARED_UNACK', 'CLEARED', 'CLEARED_UNACK'],
    ['CLEARED_UNACK', 'ACK', 'NORMAL'],
  ];
  it.each(cases)('%s + %s -> %s', (from, kind, to) => {
    expect(transition(from, { kind })).toBe(to);
  });
});

describe('fromActiveRow — mirrors alarm_repo.py:129-132 CASE', () => {
  it('acknowledged & cleared → NORMAL (row leaves the active set)', () => {
    expect(fromActiveRow({ acknowledged: 1, cleared_at: '2026-07-26T00:00:00Z' })).toBe('NORMAL');
  });
  it('acknowledged & not cleared → ACKNOWLEDGED', () => {
    expect(fromActiveRow({ acknowledged: 1, cleared_at: null })).toBe('ACKNOWLEDGED');
  });
  it('unacknowledged & cleared → CLEARED_UNACK', () => {
    expect(fromActiveRow({ acknowledged: 0, cleared_at: '2026-07-26T00:00:00Z' })).toBe('CLEARED_UNACK');
  });
  it('unacknowledged & not cleared → UNACKNOWLEDGED', () => {
    expect(fromActiveRow({ acknowledged: 0, cleared_at: null })).toBe('UNACKNOWLEDGED');
  });
});

describe('predicates', () => {
  it('isUnacked: UNACKNOWLEDGED and CLEARED_UNACK only', () => {
    expect(isUnacked('UNACKNOWLEDGED')).toBe(true);
    expect(isUnacked('CLEARED_UNACK')).toBe(true);
    expect(isUnacked('ACKNOWLEDGED')).toBe(false);
    expect(isUnacked('NORMAL')).toBe(false);
  });
  it('isActive: UNACKNOWLEDGED and ACKNOWLEDGED only', () => {
    expect(isActive('UNACKNOWLEDGED')).toBe(true);
    expect(isActive('ACKNOWLEDGED')).toBe(true);
    expect(isActive('CLEARED_UNACK')).toBe(false);
    expect(isActive('NORMAL')).toBe(false);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run (cwd `packages/smart_pid_web`): `npm run test -- src/lib/alarmMachine.test.ts`
Expected: FAIL — `Failed to resolve import "./alarmMachine"`.

- [ ] **Step 3: Write the implementation**

Create `packages/smart_pid_web/src/lib/alarmMachine.ts`:

```ts
/**
 * Four-state alarm ack/clear machine — pure module (spec §7).
 *
 * Wire events: EVENT.ALARM.{id} carries transition TRIGGERED | CLEARED
 * (alarm_worker.py:175, alarm_engine.py:207,240). ACK is a client action
 * (POST /alarms/{id}/ack). Row-state derivation mirrors the backend CASE in
 * alarm_repo.py:129-132; cleared∧acked rows leave the active set entirely.
 */

export type AlarmPointState =
  | 'NORMAL'
  | 'UNACKNOWLEDGED'
  | 'ACKNOWLEDGED'
  | 'CLEARED_UNACK';

export type AlarmMachineEvent = { kind: 'TRIGGERED' } | { kind: 'CLEARED' } | { kind: 'ACK' };

const TABLE: Record<AlarmPointState, Record<AlarmMachineEvent['kind'], AlarmPointState>> = {
  NORMAL: { TRIGGERED: 'UNACKNOWLEDGED', CLEARED: 'NORMAL', ACK: 'NORMAL' },
  UNACKNOWLEDGED: { TRIGGERED: 'UNACKNOWLEDGED', CLEARED: 'CLEARED_UNACK', ACK: 'ACKNOWLEDGED' },
  // A TRIGGERED on an acked-active point implies a missed CLEARED (gap healing):
  // a new occurrence always demands a new acknowledgement.
  ACKNOWLEDGED: { TRIGGERED: 'UNACKNOWLEDGED', CLEARED: 'NORMAL', ACK: 'ACKNOWLEDGED' },
  // A re-trigger while cleared-unacked is a NEW instance; it stays unacked.
  CLEARED_UNACK: { TRIGGERED: 'UNACKNOWLEDGED', CLEARED: 'CLEARED_UNACK', ACK: 'NORMAL' },
};

export function transition(state: AlarmPointState, event: AlarmMachineEvent): AlarmPointState {
  return TABLE[state][event.kind];
}

/** Derive machine state from a REST row (GET /alarms/active|history). */
export function fromActiveRow(row: {
  acknowledged: 0 | 1;
  cleared_at: string | null;
}): AlarmPointState {
  if (row.acknowledged === 1) return row.cleared_at !== null ? 'NORMAL' : 'ACKNOWLEDGED';
  return row.cleared_at !== null ? 'CLEARED_UNACK' : 'UNACKNOWLEDGED';
}

/** Unacked drives the non-color channel (weight + icon + blink, spec §6.4). */
export function isUnacked(state: AlarmPointState): boolean {
  return state === 'UNACKNOWLEDGED' || state === 'CLEARED_UNACK';
}

/** Active = the condition is still present. */
export function isActive(state: AlarmPointState): boolean {
  return state === 'UNACKNOWLEDGED' || state === 'ACKNOWLEDGED';
}
```

- [ ] **Step 4: Run test to verify it passes**

Run (cwd `packages/smart_pid_web`): `npm run test -- src/lib/alarmMachine.test.ts`
Expected: PASS — 18 tests (12 table + 4 row + 2 predicate).

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_web/src/lib/alarmMachine.ts packages/smart_pid_web/src/lib/alarmMachine.test.ts
git commit -m "feat(web): add four-state alarm ack/clear machine"
```

---

### Task 5: Scale extensions (`src/lib/scale.ts`)

**Files:**
- Modify: `packages/smart_pid_web/src/lib/scale.ts` (append two functions; the phase-2 base stays untouched)
- Modify: `packages/smart_pid_web/src/lib/scale.test.ts` (append)

**Interfaces:**
- Consumes (phase 2 base, quoted verbatim): `export interface Scale { euMin: number; euMax: number; unit: string }`; `export function valueToFraction(value: number, scale: Scale): number` — clamped 0..1, returns 0 when span <= 0. (`ticks(scale, count?)` lives in the same file but is not consumed by phase 3.)
- Produces: `valueToPercent(value: number, scale: Scale): number`, `clampToScale(value: number, scale: Scale): number`. Phase 4's Faceplate/AnalogBar use these for `aria-valuenow` and pen positioning.

- [ ] **Step 1: Write the failing test**

Append to `packages/smart_pid_web/src/lib/scale.test.ts` (extend the existing import from `./scale` with `clampToScale, valueToPercent`):

```ts
describe('valueToPercent (phase-3 extension)', () => {
  const scale = { euMin: 0, euMax: 200, unit: '°C' };
  it('maps the scale span onto 0..100', () => {
    expect(valueToPercent(0, scale)).toBe(0);
    expect(valueToPercent(100, scale)).toBe(50);
    expect(valueToPercent(200, scale)).toBe(100);
  });
  it('clamps out-of-range values (inherits valueToFraction clamping)', () => {
    expect(valueToPercent(-50, scale)).toBe(0);
    expect(valueToPercent(999, scale)).toBe(100);
  });
  it('degenerate span → 0 (matches valueToFraction)', () => {
    expect(valueToPercent(5, { euMin: 10, euMax: 10, unit: '' })).toBe(0);
  });
});

describe('clampToScale (phase-3 extension)', () => {
  const scale = { euMin: -10, euMax: 10, unit: 'bar' };
  it('passes in-range values through', () => {
    expect(clampToScale(3.5, scale)).toBe(3.5);
  });
  it('clamps to the engineering-unit bounds', () => {
    expect(clampToScale(-99, scale)).toBe(-10);
    expect(clampToScale(99, scale)).toBe(10);
  });
  it('degenerate span → euMin', () => {
    expect(clampToScale(7, { euMin: 4, euMax: 4, unit: '' })).toBe(4);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run (cwd `packages/smart_pid_web`): `npm run test -- src/lib/scale.test.ts`
Expected: FAIL — `valueToPercent` / `clampToScale` are not exported (the phase-2 base tests still pass).

- [ ] **Step 3: Write the implementation**

Append to `packages/smart_pid_web/src/lib/scale.ts` (do not modify the phase-2 base functions):

```ts
/** Percent position on the scale span, clamped 0..100 (phase-3 extension). */
export function valueToPercent(value: number, scale: Scale): number {
  return valueToFraction(value, scale) * 100;
}

/** Clamp a raw EU value into [euMin, euMax]; degenerate span collapses to euMin. */
export function clampToScale(value: number, scale: Scale): number {
  if (scale.euMax <= scale.euMin) return scale.euMin;
  return Math.min(Math.max(value, scale.euMin), scale.euMax);
}
```

- [ ] **Step 4: Run test to verify it passes**

Run (cwd `packages/smart_pid_web`): `npm run test -- src/lib/scale.test.ts`
Expected: PASS — phase-2 base tests plus 6 new tests.

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_web/src/lib/scale.ts packages/smart_pid_web/src/lib/scale.test.ts
git commit -m "feat(web): extend scale with percent and clamping helpers"
```

---

### Task 6: Format consolidation (`src/lib/format.ts`)

**Files:**
- Modify: `packages/smart_pid_web/src/lib/format.ts` (append three functions; the phase-2 `formatNumber` stays untouched)
- Modify: `packages/smart_pid_web/src/lib/format.test.ts` (append)

**Interfaces:**
- Consumes (phase 2 base, quoted verbatim): `export function formatNumber(value: number | null | undefined, decimals: number): string` — `value.toFixed(decimals)`, `'—'` for null/undefined/NaN, no units.
- Produces: `formatWithUnit(value, unit, decimals): string`, `formatPercent(ratio, decimals?): string`, `formatTimestamp(ts): string`. This makes `src/lib/format.ts` the **single** formatting module (spec §7: "today's `format` is duplicated in `lib/` and `multitrend/`"). The old `multitrend/format.ts` `formatMetric`/`formatVariabilityPct` semantics ('—' for non-finite; ratio → percent) are absorbed here; that file died with the phase-2 cutover and phase 7 MUST import from `@/lib/format` instead of recreating it.

- [ ] **Step 1: Write the failing test**

Append to `packages/smart_pid_web/src/lib/format.test.ts` (extend the existing import from `./format` with `formatPercent, formatTimestamp, formatWithUnit`):

```ts
describe('formatWithUnit (phase-3 consolidation)', () => {
  it('appends the unit after a space', () => {
    expect(formatWithUnit(150.25, '°C', 1)).toBe('150.3 °C');
  });
  it('omits the unit for absent values', () => {
    expect(formatWithUnit(null, '°C', 1)).toBe('—');
    expect(formatWithUnit(undefined, 'bar', 2)).toBe('—');
    expect(formatWithUnit(Number.NaN, 'bar', 2)).toBe('—');
  });
  it('non-finite values render as absent (absorbs multitrend formatMetric policy)', () => {
    expect(formatWithUnit(Number.POSITIVE_INFINITY, '%', 1)).toBe('—');
  });
  it('empty unit yields the bare number', () => {
    expect(formatWithUnit(42, '', 0)).toBe('42');
  });
});

describe('formatPercent (absorbs multitrend formatVariabilityPct)', () => {
  it('renders a ratio as percent with one decimal by default', () => {
    expect(formatPercent(0.1234)).toBe('12.3%');
  });
  it('honours the decimals parameter', () => {
    expect(formatPercent(0.5, 0)).toBe('50%');
  });
  it('absent and non-finite ratios render as absent', () => {
    expect(formatPercent(null)).toBe('—');
    expect(formatPercent(undefined)).toBe('—');
    expect(formatPercent(Number.NaN)).toBe('—');
    expect(formatPercent(Number.POSITIVE_INFINITY)).toBe('—');
  });
});

describe('formatTimestamp', () => {
  const pad = (n: number) => String(n).padStart(2, '0');
  const hms = (d: Date) => `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;

  it('formats epoch seconds (envelope ts / monitor timestamps) as local HH:MM:SS', () => {
    const epoch = 1718743200.5;
    expect(formatTimestamp(epoch)).toBe(hms(new Date(epoch * 1000)));
  });
  it('formats ISO-8601 strings (worker timestamps) as local HH:MM:SS', () => {
    const iso = '2024-06-18T20:40:05.000Z';
    expect(formatTimestamp(iso)).toBe(hms(new Date(iso)));
  });
  it('invalid input renders as absent', () => {
    expect(formatTimestamp('not-a-date')).toBe('—');
    expect(formatTimestamp(null)).toBe('—');
    expect(formatTimestamp(undefined)).toBe('—');
    expect(formatTimestamp(Number.NaN)).toBe('—');
  });
});
```

(The expected values are computed from the same local `Date` the implementation uses, so the tests are timezone-independent while still pinning the epoch-vs-ISO parsing paths, the 2-digit padding and the invalid→'—' policy.)

- [ ] **Step 2: Run test to verify it fails**

Run (cwd `packages/smart_pid_web`): `npm run test -- src/lib/format.test.ts`
Expected: FAIL — `formatWithUnit` / `formatPercent` / `formatTimestamp` are not exported.

- [ ] **Step 3: Write the implementation**

Append to `packages/smart_pid_web/src/lib/format.ts`:

```ts
/**
 * Phase-3 consolidation: this file is the SINGLE numeric formatting module
 * (spec §7 kills the old lib/ vs multitrend/ duplication). Policy: every
 * absent OR non-finite value renders as '—' (em dash), matching formatNumber.
 */

/** "150.3 °C" — formatNumber plus a unit suffix; absent values stay bare '—'. */
export function formatWithUnit(
  value: number | null | undefined,
  unit: string,
  decimals: number,
): string {
  if (value !== null && value !== undefined && !Number.isFinite(value)) return '—';
  const num = formatNumber(value, decimals);
  if (num === '—' || unit === '') return num;
  return `${num} ${unit}`;
}

/** Ratio → percent string: 0.1234 → "12.3%" (absorbs multitrend formatVariabilityPct). */
export function formatPercent(ratio: number | null | undefined, decimals = 1): string {
  if (ratio === null || ratio === undefined || !Number.isFinite(ratio)) return '—';
  return `${(ratio * 100).toFixed(decimals)}%`;
}

/**
 * Local wall-clock HH:MM:SS for wire timestamps: accepts epoch SECONDS
 * (envelope.ts, monitor-mode status) or ISO-8601 strings (worker payloads).
 */
export function formatTimestamp(ts: string | number | null | undefined): string {
  if (ts === null || ts === undefined) return '—';
  const ms =
    typeof ts === 'number' ? (Number.isFinite(ts) ? ts * 1000 : Number.NaN) : Date.parse(ts);
  if (Number.isNaN(ms)) return '—';
  const d = new Date(ms);
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run (cwd `packages/smart_pid_web`): `npm run test -- src/lib/format.test.ts`
Expected: PASS — phase-2 base tests plus 10 new tests.

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_web/src/lib/format.ts packages/smart_pid_web/src/lib/format.test.ts
git commit -m "feat(web): consolidate tabular formatting with unit, percent and timestamp helpers"
```

---

### Task 7: Typed API client core with §11 error taxonomy (`src/api/client.ts`)

**Files:**
- Create: `packages/smart_pid_web/src/api/client.ts`
- Test: `packages/smart_pid_web/src/api/client.test.ts`

**Interfaces:**
- Consumes: global `fetch` only.
- Produces: `ApiErrorKind`, `ValidationIssue`, `classifyStatus(status): ApiErrorKind`, `class ApiError extends Error { status; kind; detail; fields }`, `AuthHooks { getToken(): string | null; onUnauthorized?(e): void; onForbidden?(e): void }`, `setAuthHooks(hooks): void`, `api = { get, post, put, delete, download, upload }`. Tasks 8, 9 and 12 import `api`, `ApiError`, `setAuthHooks`.

Error taxonomy is spec §11 verbatim: 401 `unauthorized` (clear session → login), 403 `forbidden` (new in this work: toast + refetch me), 404 `not-found`, 409 `conflict`, 422 `validation` (field-level), 502 `opcua-down` (loop-level banner), other 5xx `server`, transport failure `network` (status 0).

- [ ] **Step 1: Write the failing test**

Create `packages/smart_pid_web/src/api/client.test.ts`:

```ts
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { api, ApiError, classifyStatus, setAuthHooks } from './client';

const fetchMock = vi.fn();

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal('fetch', fetchMock);
  setAuthHooks({ getToken: () => null });
});
afterEach(() => vi.unstubAllGlobals());

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });

describe('classifyStatus', () => {
  it('maps the §11 table', () => {
    expect(classifyStatus(401)).toBe('unauthorized');
    expect(classifyStatus(403)).toBe('forbidden');
    expect(classifyStatus(404)).toBe('not-found');
    expect(classifyStatus(409)).toBe('conflict');
    expect(classifyStatus(422)).toBe('validation');
    expect(classifyStatus(502)).toBe('opcua-down');
    expect(classifyStatus(500)).toBe('server');
    expect(classifyStatus(503)).toBe('server');
  });
});

describe('api core', () => {
  it('GETs JSON from /api and returns the parsed body', async () => {
    fetchMock.mockResolvedValueOnce(json({ ok: 1 }));
    await expect(api.get('/controllers')).resolves.toEqual({ ok: 1 });
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/controllers',
      expect.objectContaining({ method: 'GET' }),
    );
  });

  it('injects the Bearer token from the auth hooks', async () => {
    setAuthHooks({ getToken: () => 'tok-123' });
    fetchMock.mockResolvedValueOnce(json({}));
    await api.get('/auth/me');
    const init = fetchMock.mock.calls[0][1] as RequestInit;
    expect((init.headers as Record<string, string>).Authorization).toBe('Bearer tok-123');
  });

  it('sends JSON bodies with Content-Type and returns undefined on 204', async () => {
    fetchMock.mockResolvedValueOnce(new Response(null, { status: 204 }));
    await expect(api.post('/alarms/7/ack', { note: 'x' })).resolves.toBeUndefined();
    const init = fetchMock.mock.calls[0][1] as RequestInit;
    expect(init.body).toBe(JSON.stringify({ note: 'x' }));
    expect((init.headers as Record<string, string>)['Content-Type']).toBe('application/json');
  });

  it('throws a typed ApiError with the backend detail string', async () => {
    fetchMock.mockResolvedValueOnce(json({ detail: 'Controller 9 not found' }, 404));
    const err = await api.get('/controllers/9').catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err).toMatchObject({ status: 404, kind: 'not-found', detail: 'Controller 9 not found' });
  });

  it('parses FastAPI 422 field issues', async () => {
    fetchMock.mockResolvedValueOnce(
      json(
        { detail: [{ loc: ['body', 'sp'], msg: 'value is not a valid float', type: 'float_parsing' }] },
        422,
      ),
    );
    const err = (await api.put('/commands/setpoint', { sp: 'x' }).catch((e: unknown) => e)) as ApiError;
    expect(err.kind).toBe('validation');
    expect(err.fields).toEqual([
      { loc: ['body', 'sp'], msg: 'value is not a valid float', type: 'float_parsing' },
    ]);
    expect(err.detail).toBe('value is not a valid float');
  });

  it('fires onUnauthorized for 401 and onForbidden for 403', async () => {
    const onUnauthorized = vi.fn();
    const onForbidden = vi.fn();
    setAuthHooks({ getToken: () => 't', onUnauthorized, onForbidden });
    fetchMock.mockResolvedValueOnce(json({ detail: 'expired' }, 401));
    await api.get('/auth/me').catch(() => {});
    expect(onUnauthorized).toHaveBeenCalledTimes(1);
    fetchMock.mockResolvedValueOnce(json({ detail: 'sem permissão' }, 403));
    await api.post('/controllers', {}).catch(() => {});
    expect(onForbidden).toHaveBeenCalledTimes(1);
  });

  it('maps transport failure to kind network, status 0', async () => {
    fetchMock.mockRejectedValueOnce(new TypeError('Failed to fetch'));
    const err = (await api.get('/controllers').catch((e: unknown) => e)) as ApiError;
    expect(err).toMatchObject({ status: 0, kind: 'network' });
  });

  it('download returns a Blob and carries auth', async () => {
    setAuthHooks({ getToken: () => 'tok' });
    fetchMock.mockResolvedValueOnce(new Response(new Blob(['csv']), { status: 200 }));
    const blob = await api.download('/export/1/download');
    expect(blob).toBeInstanceOf(Blob);
    const init = fetchMock.mock.calls[0][1] as RequestInit;
    expect((init.headers as Record<string, string>).Authorization).toBe('Bearer tok');
  });

  it('upload posts FormData without a manual Content-Type (browser sets the boundary)', async () => {
    fetchMock.mockResolvedValueOnce(json({ imported: true }));
    const form = new FormData();
    await api.upload('/project/import', form);
    const init = fetchMock.mock.calls[0][1] as RequestInit;
    expect(init.body).toBe(form);
    expect((init.headers as Record<string, string>)['Content-Type']).toBeUndefined();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run (cwd `packages/smart_pid_web`): `npm run test -- src/api/client.test.ts`
Expected: FAIL — `Failed to resolve import "./client"`.

- [ ] **Step 3: Write the implementation**

Create `packages/smart_pid_web/src/api/client.ts`:

```ts
/**
 * Transport-only REST client. Single base URL, single auth-injection point,
 * §11 error taxonomy. Endpoint definitions live in ./endpoints.ts; generated
 * OpenAPI types in ./generated/openapi.ts (phase-2 hermetic codegen).
 */

export type ApiErrorKind =
  | 'unauthorized' // 401 → clear session, redirect to login (§11)
  | 'forbidden' // 403 → toast "sem permissão", refetch me/capabilities (§11)
  | 'not-found' // 404 → remove stale entity, MissingState (§11)
  | 'conflict' // 409 → show reason, preserve form state (§11)
  | 'validation' // 422 → field-level messages (§11)
  | 'opcua-down' // 502 → loop-level banner, writes disabled (§11)
  | 'server' // other 5xx → generic failure with retry (§11)
  | 'network'; // transport failure → offline banner (§11)

export interface ValidationIssue {
  loc: (string | number)[];
  msg: string;
  type: string;
}

export function classifyStatus(status: number): ApiErrorKind {
  if (status === 401) return 'unauthorized';
  if (status === 403) return 'forbidden';
  if (status === 404) return 'not-found';
  if (status === 409) return 'conflict';
  if (status === 422) return 'validation';
  if (status === 502) return 'opcua-down';
  return 'server';
}

export class ApiError extends Error {
  readonly status: number;
  readonly kind: ApiErrorKind;
  readonly detail: string;
  readonly fields: ValidationIssue[];

  constructor(status: number, kind: ApiErrorKind, detail: string, fields: ValidationIssue[] = []) {
    super(detail);
    this.name = 'ApiError';
    this.status = status;
    this.kind = kind;
    this.detail = detail;
    this.fields = fields;
  }
}

export interface AuthHooks {
  getToken(): string | null;
  onUnauthorized?(error: ApiError): void;
  onForbidden?(error: ApiError): void;
}

let hooks: AuthHooks = { getToken: () => null };

/** AuthProvider registers itself here — the ONLY coupling between api and auth. */
export function setAuthHooks(next: AuthHooks): void {
  hooks = next;
}

const BASE = '/api';

function isValidationIssue(v: unknown): v is ValidationIssue {
  if (typeof v !== 'object' || v === null) return false;
  const i = v as Record<string, unknown>;
  return Array.isArray(i.loc) && typeof i.msg === 'string' && typeof i.type === 'string';
}

async function toApiError(res: Response): Promise<ApiError> {
  const kind = classifyStatus(res.status);
  let detail = res.statusText;
  let fields: ValidationIssue[] = [];
  try {
    const body: unknown = await res.json();
    const d = (body as { detail?: unknown }).detail;
    if (typeof d === 'string') {
      detail = d; // error_handlers.py:22-34 shape
    } else if (Array.isArray(d)) {
      fields = d.filter(isValidationIssue); // FastAPI 422 shape
      detail = fields.map((f) => f.msg).join('; ') || detail;
    }
  } catch {
    /* non-JSON error body */
  }
  return new ApiError(res.status, kind, detail, fields);
}

function dispatchAuthSideEffects(err: ApiError): void {
  if (err.kind === 'unauthorized') hooks.onUnauthorized?.(err);
  if (err.kind === 'forbidden') hooks.onForbidden?.(err);
}

function authHeaders(): Record<string, string> {
  const token = hooks.getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function run(path: string, init: RequestInit): Promise<Response> {
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, init);
  } catch {
    throw new ApiError(0, 'network', 'network failure');
  }
  if (!res.ok) {
    const err = await toApiError(res);
    dispatchAuthSideEffects(err);
    throw err;
  }
  return res;
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = { ...authHeaders() };
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  const res = await run(path, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const api = {
  get: <T>(path: string) => request<T>('GET', path),
  post: <T>(path: string, body?: unknown) => request<T>('POST', path, body),
  put: <T>(path: string, body?: unknown) => request<T>('PUT', path, body),
  delete: <T>(path: string) => request<T>('DELETE', path),

  /** Authenticated binary GET (Bearer travels in a header; <a href> would lose it). */
  async download(path: string): Promise<Blob> {
    const res = await run(path, { method: 'GET', headers: authHeaders() });
    return res.blob();
  },

  /** Authenticated multipart POST — no manual Content-Type (browser sets the boundary). */
  async upload<T>(path: string, form: FormData): Promise<T> {
    const res = await run(path, { method: 'POST', headers: authHeaders(), body: form });
    if (res.status === 204) return undefined as T;
    return (await res.json()) as T;
  },
};
```

- [ ] **Step 4: Run test to verify it passes**

Run (cwd `packages/smart_pid_web`): `npm run test -- src/api/client.test.ts`
Expected: PASS — 10 tests.

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_web/src/api/client.ts packages/smart_pid_web/src/api/client.test.ts
git commit -m "feat(web): typed api client with §11 error taxonomy and auth hooks"
```

---

### Task 8: Wire types, typed endpoints and canonical query keys (`src/api/{types,endpoints,queryKeys}.ts`)

**Files:**
- Create: `packages/smart_pid_web/src/api/types.ts`
- Create: `packages/smart_pid_web/src/api/endpoints.ts`
- Create: `packages/smart_pid_web/src/api/queryKeys.ts`
- Test: `packages/smart_pid_web/src/api/endpoints.test.ts`

**Interfaces:**
- Consumes: `api` (Task 7); phase-2 generated `components` from `./generated/openapi`.
- Produces:
  - `types.ts`: `Role`, `MeResponse`, `TokenResponse`, `ControllerResponse`, `AiStatus`, `OpcuaStatus`, `SimulatorStatus` (aliases over `components['schemas'][...]`), `AlarmRowStatus`, `AlarmRow` (hand-typed — the backend returns bare `list[dict]`, `routers/alarms.py:30,43`).
  - `endpoints.ts`: `endpoints.login(username, password)`, `.me()`, `.controllers()`, `.activeAlarms()`, `.alarmHistory({start, end, limit?, offset?})`, `.aiStatus(controllerId)`, `.opcuaStatus()`, `.simulatorStatus()`; plus `AlarmHistoryParams`.
  - `queryKeys.ts`: `queryKeys.controllers`, `.alarmsActive`, `.alarmsResyncHistory`, `.aiStatus(id)`, `.opcuaStatus`, `.simulatorStatus` — **canonical cache keys**: later phases' hooks MUST use these exact keys so the resync runner primes their caches.

- [ ] **Step 1: Write the failing test**

Create `packages/smart_pid_web/src/api/endpoints.test.ts`:

```ts
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { endpoints } from './endpoints';
import { queryKeys } from './queryKeys';
import { setAuthHooks } from './client';

const fetchMock = vi.fn();
beforeEach(() => {
  fetchMock.mockReset();
  fetchMock.mockResolvedValue(
    new Response('[]', { status: 200, headers: { 'Content-Type': 'application/json' } }),
  );
  vi.stubGlobal('fetch', fetchMock);
  setAuthHooks({ getToken: () => null });
});
afterEach(() => vi.unstubAllGlobals());

const calledPath = () => fetchMock.mock.calls[0][0] as string;

describe('endpoints — exact backend routes (app.py:161-174 prefixes)', () => {
  it('login posts credentials to /api/auth/login', async () => {
    await endpoints.login('admin', 'secret');
    expect(calledPath()).toBe('/api/auth/login');
    const init = fetchMock.mock.calls[0][1] as RequestInit;
    expect(init.body).toBe(JSON.stringify({ username: 'admin', password: 'secret' }));
  });

  it('me hits /api/auth/me', async () => {
    await endpoints.me();
    expect(calledPath()).toBe('/api/auth/me');
  });

  it('controllers hits /api/controllers', async () => {
    await endpoints.controllers();
    expect(calledPath()).toBe('/api/controllers');
  });

  it('activeAlarms hits /api/alarms/active', async () => {
    await endpoints.activeAlarms();
    expect(calledPath()).toBe('/api/alarms/active');
  });

  it('alarmHistory sends BOTH start and end (alarms.py:38-39) plus limit', async () => {
    await endpoints.alarmHistory({
      start: '2026-07-26T10:00:00.000Z',
      end: '2026-07-26T11:00:00.000Z',
      limit: 1000,
    });
    expect(calledPath()).toBe(
      '/api/alarms/history?start=2026-07-26T10%3A00%3A00.000Z&end=2026-07-26T11%3A00%3A00.000Z&limit=1000',
    );
  });

  it('aiStatus hits /api/controllers/{id}/ai/status (ai router mounted under /controllers)', async () => {
    await endpoints.aiStatus(7);
    expect(calledPath()).toBe('/api/controllers/7/ai/status');
  });

  it('opcuaStatus and simulatorStatus hit their routers', async () => {
    await endpoints.opcuaStatus();
    expect(calledPath()).toBe('/api/opcua/status');
    fetchMock.mockClear();
    fetchMock.mockResolvedValue(
      new Response('{}', { status: 200, headers: { 'Content-Type': 'application/json' } }),
    );
    await endpoints.simulatorStatus();
    expect(calledPath()).toBe('/api/simulator/status');
  });
});

describe('queryKeys — canonical, stable identities', () => {
  it('exposes the §7 resync keys', () => {
    expect(queryKeys.controllers).toEqual(['controllers']);
    expect(queryKeys.alarmsActive).toEqual(['alarms', 'active']);
    expect(queryKeys.alarmsResyncHistory).toEqual(['alarms', 'resync-history']);
    expect(queryKeys.aiStatus(3)).toEqual(['ai', 'status', 3]);
    expect(queryKeys.opcuaStatus).toEqual(['opcua', 'status']);
    expect(queryKeys.simulatorStatus).toEqual(['simulator', 'status']);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run (cwd `packages/smart_pid_web`): `npm run test -- src/api/endpoints.test.ts`
Expected: FAIL — `Failed to resolve import "./endpoints"`.

- [ ] **Step 3: Write the implementation**

Create `packages/smart_pid_web/src/api/types.ts`:

```ts
import type { components } from './generated/openapi';

/** Lowercase roles — spec §9, phase-0 enum migration. */
export type Role = 'admin' | 'user';

/** GET /auth/me response (phase 0: response_model=UserClaims, require_user). */
export type MeResponse = components['schemas']['UserClaims'];

/** POST /auth/login response — unchanged by phase 0: {access_token, token_type}. */
export type TokenResponse = components['schemas']['TokenResponse'];

export type ControllerResponse = components['schemas']['ControllerResponse'];
export type AiStatus = components['schemas']['AIStatusResponse'];
export type OpcuaStatus = components['schemas']['OPCUAStatusResponse'];
export type SimulatorStatus = components['schemas']['SimulatorStatusResponse'];

/** Row status CASE — alarm_repo.py:129-132 / 209-212. */
export type AlarmRowStatus = 'UNACKNOWLEDGED' | 'ACKNOWLEDGED' | 'CLEARED_UNACK';

/**
 * GET /alarms/active and GET /alarms/history return bare `list[dict]`
 * (routers/alarms.py:30,43) — the OpenAPI dump carries no schema for them.
 * Hand-mirrored from the SELECT in alarm_repo.py:114-135 (the LEFT JOIN makes
 * controller_name nullable).
 */
export interface AlarmRow {
  id: number;
  controller_id: number;
  controller_name: string | null;
  alarm_type: string;
  priority: string;
  value: number;
  limit: number;
  timestamp: string;
  cleared_at: string | null;
  acknowledged: 0 | 1;
  ack_by_user: string | null;
  ack_at: string | null;
  status: AlarmRowStatus;
}
```

Create `packages/smart_pid_web/src/api/endpoints.ts`:

```ts
import { api } from './client';
import type {
  AiStatus,
  AlarmRow,
  ControllerResponse,
  MeResponse,
  OpcuaStatus,
  SimulatorStatus,
  TokenResponse,
} from './types';

export interface AlarmHistoryParams {
  /** ISO-8601 — backend parses with datetime.fromisoformat (alarms.py:46). */
  start: string;
  /** ISO-8601 — REQUIRED by the backend alongside start (alarms.py:38-39). */
  end: string;
  /** Backend default is 100 (alarms.py:41) — resync passes an explicit high cap. */
  limit?: number;
  offset?: number;
}

export const endpoints = {
  login: (username: string, password: string) =>
    api.post<TokenResponse>('/auth/login', { username, password }),

  me: () => api.get<MeResponse>('/auth/me'),

  controllers: () => api.get<ControllerResponse[]>('/controllers'),

  activeAlarms: () => api.get<AlarmRow[]>('/alarms/active'),

  alarmHistory: (params: AlarmHistoryParams) => {
    const q = new URLSearchParams({ start: params.start, end: params.end });
    if (params.limit !== undefined) q.set('limit', String(params.limit));
    if (params.offset !== undefined) q.set('offset', String(params.offset));
    return api.get<AlarmRow[]>(`/alarms/history?${q.toString()}`);
  },

  aiStatus: (controllerId: number) =>
    api.get<AiStatus>(`/controllers/${controllerId}/ai/status`),

  opcuaStatus: () => api.get<OpcuaStatus>('/opcua/status'),

  simulatorStatus: () => api.get<SimulatorStatus>('/simulator/status'),
};
```

Create `packages/smart_pid_web/src/api/queryKeys.ts`:

```ts
/**
 * Canonical TanStack Query keys. The §7 resync runner primes these entries via
 * setQueryData; feature hooks in phases 4-10 MUST reuse the same keys or the
 * resync becomes invisible to them.
 */
export const queryKeys = {
  controllers: ['controllers'] as const,
  alarmsActive: ['alarms', 'active'] as const,
  /** Gap-window history rows fetched by resync (alarms since last_seen_ts). */
  alarmsResyncHistory: ['alarms', 'resync-history'] as const,
  aiStatus: (controllerId: number) => ['ai', 'status', controllerId] as const,
  opcuaStatus: ['opcua', 'status'] as const,
  simulatorStatus: ['simulator', 'status'] as const,
};
```

- [ ] **Step 4: Run test to verify it passes**

Run (cwd `packages/smart_pid_web`): `npm run test -- src/api/endpoints.test.ts`
Expected: PASS — 8 tests.

- [ ] **Step 5: Typecheck the generated-type wiring**

Run (cwd `packages/smart_pid_web`): `npm run typecheck`
Expected: exit 0. If `components['schemas']['UserClaims']` (or any alias) is missing, the committed codegen predates phase 0's schema — run `npm run gen:api` once against the phase-0 backend and re-check (`npm run gen:api:check` keeps it honest in CI thereafter).

- [ ] **Step 6: Commit**

```bash
git add packages/smart_pid_web/src/api/types.ts packages/smart_pid_web/src/api/endpoints.ts packages/smart_pid_web/src/api/queryKeys.ts packages/smart_pid_web/src/api/endpoints.test.ts
git commit -m "feat(web): typed endpoints, wire types and canonical query keys"
```

---

### Task 9: AuthContext with `/auth/me` role hydration (`src/auth/AuthContext.tsx`)

**Files:**
- Create: `packages/smart_pid_web/src/auth/AuthContext.tsx`
- Test: `packages/smart_pid_web/src/auth/AuthContext.test.tsx`

**Interfaces:**
- Consumes: `endpoints.login`, `endpoints.me` (Task 8); `setAuthHooks` (Task 7); `MeResponse` (Task 8).
- Produces: `AuthUser` (= `MeResponse`), `AuthContextValue { token; user; isAuthenticated; login(username, password): Promise<void>; logout(): void; refreshUser(): Promise<void> }`, `AuthProviderProps { children?; onPermissionDenied?() }`, `AuthProvider(props)`, `useAuth(): AuthContextValue`. Phase 4 mounts `AuthProvider` at the root and wires `onPermissionDenied` to the pt-BR toast `"sem permissão"` (§11).

Behavior contract (spec §11 + phase-0 pins): token persists in `sessionStorage['smart-pid-token']`; role comes ONLY from `GET /auth/me` (never JWT decoding); any 401 anywhere clears the session; any 403 anywhere refetches `me` (role may have changed mid-session) and invokes `onPermissionDenied`.

- [ ] **Step 1: Write the failing test**

Create `packages/smart_pid_web/src/auth/AuthContext.test.tsx`:

```tsx
import { act, renderHook, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { createElement, type ReactNode } from 'react';
import { AuthProvider, useAuth } from './AuthContext';
import { api } from '../api/client';

const fetchMock = vi.fn();
const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });

beforeEach(() => {
  sessionStorage.clear();
  fetchMock.mockReset();
  vi.stubGlobal('fetch', fetchMock);
});
afterEach(() => vi.unstubAllGlobals());

const wrapper = ({ children }: { children: ReactNode }) =>
  createElement(AuthProvider, null, children);

describe('AuthProvider', () => {
  it('login stores the token and hydrates user from /auth/me', async () => {
    fetchMock
      .mockResolvedValueOnce(json({ access_token: 't1', token_type: 'bearer' }))
      .mockResolvedValueOnce(json({ user_id: 1, username: 'admin', role: 'admin' }));
    const { result } = renderHook(() => useAuth(), { wrapper });

    await act(() => result.current.login('admin', 'admin'));

    expect(sessionStorage.getItem('smart-pid-token')).toBe('t1');
    expect(result.current.isAuthenticated).toBe(true);
    expect(result.current.user).toEqual({ user_id: 1, username: 'admin', role: 'admin' });
    // the /auth/me request carried the fresh token
    const meInit = fetchMock.mock.calls[1][1] as RequestInit;
    expect((meInit.headers as Record<string, string>).Authorization).toBe('Bearer t1');
  });

  it('restores a stored session by refetching /auth/me on mount', async () => {
    sessionStorage.setItem('smart-pid-token', 't-stored');
    fetchMock.mockResolvedValueOnce(json({ user_id: 2, username: 'op', role: 'user' }));
    const { result } = renderHook(() => useAuth(), { wrapper });
    await waitFor(() => expect(result.current.user?.role).toBe('user'));
    expect(result.current.token).toBe('t-stored');
  });

  it('logout clears token, user and storage', async () => {
    sessionStorage.setItem('smart-pid-token', 't-stored');
    fetchMock.mockResolvedValueOnce(json({ user_id: 2, username: 'op', role: 'user' }));
    const { result } = renderHook(() => useAuth(), { wrapper });
    await waitFor(() => expect(result.current.user).not.toBeNull());

    act(() => result.current.logout());

    expect(result.current.token).toBeNull();
    expect(result.current.user).toBeNull();
    expect(sessionStorage.getItem('smart-pid-token')).toBeNull();
  });

  it('a 401 from ANY api call clears the session (§11)', async () => {
    sessionStorage.setItem('smart-pid-token', 't-stored');
    fetchMock.mockResolvedValueOnce(json({ user_id: 2, username: 'op', role: 'user' }));
    const { result } = renderHook(() => useAuth(), { wrapper });
    await waitFor(() => expect(result.current.user).not.toBeNull());

    fetchMock.mockResolvedValueOnce(json({ detail: 'expired' }, 401));
    await act(async () => {
      await api.get('/controllers').catch(() => {});
    });

    await waitFor(() => expect(result.current.isAuthenticated).toBe(false));
    expect(sessionStorage.getItem('smart-pid-token')).toBeNull();
  });

  it('a 403 refetches /auth/me and notifies onPermissionDenied (§11)', async () => {
    sessionStorage.setItem('smart-pid-token', 't-stored');
    const onPermissionDenied = vi.fn();
    fetchMock.mockResolvedValueOnce(json({ user_id: 2, username: 'op', role: 'admin' }));
    const { result } = renderHook(() => useAuth(), {
      wrapper: ({ children }: { children: ReactNode }) =>
        createElement(AuthProvider, { onPermissionDenied }, children),
    });
    await waitFor(() => expect(result.current.user?.role).toBe('admin'));

    // role was downgraded server-side; the next call 403s, me now reports 'user'
    fetchMock
      .mockResolvedValueOnce(json({ detail: 'sem permissão' }, 403))
      .mockResolvedValueOnce(json({ user_id: 2, username: 'op', role: 'user' }));
    await act(async () => {
      await api.post('/controllers', {}).catch(() => {});
    });

    await waitFor(() => expect(result.current.user?.role).toBe('user'));
    expect(onPermissionDenied).toHaveBeenCalledTimes(1);
  });

  it('useAuth outside the provider throws', () => {
    expect(() => renderHook(() => useAuth())).toThrow(
      'useAuth must be used within AuthProvider',
    );
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run (cwd `packages/smart_pid_web`): `npm run test -- src/auth/AuthContext.test.tsx`
Expected: FAIL — `Failed to resolve import "./AuthContext"`.

- [ ] **Step 3: Write the implementation**

Create `packages/smart_pid_web/src/auth/AuthContext.tsx`:

```tsx
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import { setAuthHooks } from '../api/client';
import { endpoints } from '../api/endpoints';
import type { MeResponse } from '../api/types';

/** Kept verbatim — retained E2E specs seed this key. */
const STORAGE_KEY = 'smart-pid-token';

export type AuthUser = MeResponse;

export interface AuthContextValue {
  token: string | null;
  /** null until GET /auth/me resolves — deny-by-default for role checks. */
  user: AuthUser | null;
  isAuthenticated: boolean;
  login(username: string, password: string): Promise<void>;
  logout(): void;
  /** §11: refetched on any 403 (role may have changed mid-session). */
  refreshUser(): Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export interface AuthProviderProps {
  children?: ReactNode;
  /** Phase 4 wires this to the pt-BR toast "sem permissão" (§11). */
  onPermissionDenied?: () => void;
}

export function AuthProvider({ children, onPermissionDenied }: AuthProviderProps) {
  const [token, setToken] = useState<string | null>(() => sessionStorage.getItem(STORAGE_KEY));
  const [user, setUser] = useState<AuthUser | null>(null);
  const tokenRef = useRef<string | null>(token);
  tokenRef.current = token;

  const refreshUser = useCallback(async () => {
    if (tokenRef.current === null) {
      setUser(null);
      return;
    }
    const me = await endpoints.me();
    setUser(me);
  }, []);

  const logout = useCallback(() => {
    sessionStorage.removeItem(STORAGE_KEY);
    tokenRef.current = null;
    setToken(null);
    setUser(null);
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    const res = await endpoints.login(username, password);
    sessionStorage.setItem(STORAGE_KEY, res.access_token);
    // The immediate /auth/me below must already carry the fresh token.
    tokenRef.current = res.access_token;
    setToken(res.access_token);
    const me = await endpoints.me();
    setUser(me);
  }, []);

  // Single api↔auth coupling point: token injection + §11 401/403 side effects.
  useEffect(() => {
    setAuthHooks({
      getToken: () => tokenRef.current,
      onUnauthorized: () => logout(),
      onForbidden: () => {
        onPermissionDenied?.();
        void refreshUser().catch(() => {
          /* refresh failure surfaces via the failing call itself */
        });
      },
    });
  }, [logout, refreshUser, onPermissionDenied]);

  // Session restore: storage has a token but this mount has no user yet.
  useEffect(() => {
    if (token !== null && user === null) {
      void refreshUser().catch(() => {
        /* a 401 here already triggered logout via onUnauthorized */
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- rehydrate per token change only
  }, [token]);

  const value = useMemo<AuthContextValue>(
    () => ({ token, user, isAuthenticated: token !== null, login, logout, refreshUser }),
    [token, user, login, logout, refreshUser],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run (cwd `packages/smart_pid_web`): `npm run test -- src/auth/AuthContext.test.tsx`
Expected: PASS — 6 tests.

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_web/src/auth/AuthContext.tsx packages/smart_pid_web/src/auth/AuthContext.test.tsx
git commit -m "feat(web): auth context with /auth/me role hydration and 401/403 side effects"
```

---

### Task 10: Capability map + `useCan(action)` (`src/auth/useCan.ts`)

**Files:**
- Create: `packages/smart_pid_web/src/auth/useCan.ts`
- Test: `packages/smart_pid_web/src/auth/useCan.test.tsx`

**Interfaces:**
- Consumes: `useAuth` (Task 9), `Role` (Task 8).
- Produces: `CAPABILITY_ACTIONS`, `CapabilityAction`, `can(role, action): boolean`, `useCan(action): boolean`. Phases 4-10 gate every admin-only control with `useCan` (presentation only — the backend enforces).

**The capability-action list (pinned, derived 1:1 from the spec §9 table):**

| Action | §9 table row | `admin` | `user` |
|---|---|---|---|
| `view` | View dashboards, trends, alarms, stats | yes | yes |
| `alarms.ack` | Acknowledge alarms | yes | yes |
| `loop.operate` | Set SP, mode, manual CO | yes | yes |
| `export.data` | Export data (create + download) | yes | yes |
| `tuning.edit` | Edit PID / fuzzy / RL parameters, apply tuning | yes | no |
| `ai.control` | Start, pause, stop AI workers; optimization toggle | yes | no |
| `controllers.manage` | Create, edit, delete controllers | yes | no |
| `alarms.configure` | Configure alarm limits | yes | no |
| `opcua.configure` | OPC-UA connection and tag mapping | yes | no |
| `projects.manage` | `.spid` project management | yes | no |
| `users.manage` | Manage users | yes | no |
| `settings.manage` | Change application settings | yes | no |

- [ ] **Step 1: Write the failing test**

Create `packages/smart_pid_web/src/auth/useCan.test.tsx`:

```tsx
import { renderHook, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { createElement, type ReactNode } from 'react';
import { AuthProvider } from './AuthContext';
import { CAPABILITY_ACTIONS, can, useCan, type CapabilityAction } from './useCan';

describe('can — pure capability matrix', () => {
  const userAllowed: CapabilityAction[] = ['view', 'alarms.ack', 'loop.operate', 'export.data'];

  it('admin can do everything', () => {
    for (const action of CAPABILITY_ACTIONS) expect(can('admin', action)).toBe(true);
  });

  it('user gets exactly the four operate/observe capabilities', () => {
    for (const action of CAPABILITY_ACTIONS) {
      expect(can('user', action)).toBe(userAllowed.includes(action));
    }
  });

  it('unknown role (me not yet resolved) denies everything', () => {
    for (const action of CAPABILITY_ACTIONS) expect(can(null, action)).toBe(false);
  });

  it('the pinned action list matches spec §9 exactly', () => {
    expect(CAPABILITY_ACTIONS).toEqual([
      'view',
      'alarms.ack',
      'loop.operate',
      'export.data',
      'tuning.edit',
      'ai.control',
      'controllers.manage',
      'alarms.configure',
      'opcua.configure',
      'projects.manage',
      'users.manage',
      'settings.manage',
    ]);
  });
});

describe('useCan — hook over AuthContext', () => {
  const fetchMock = vi.fn();
  beforeEach(() => {
    sessionStorage.clear();
    fetchMock.mockReset();
    vi.stubGlobal('fetch', fetchMock);
  });
  afterEach(() => vi.unstubAllGlobals());

  it('reflects the hydrated role', async () => {
    sessionStorage.setItem('smart-pid-token', 't');
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ user_id: 2, username: 'op', role: 'user' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    );
    const wrapper = ({ children }: { children: ReactNode }) =>
      createElement(AuthProvider, null, children);
    const { result } = renderHook(
      () => ({ view: useCan('view'), users: useCan('users.manage') }),
      { wrapper },
    );
    await waitFor(() => expect(result.current.view).toBe(true));
    expect(result.current.users).toBe(false);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run (cwd `packages/smart_pid_web`): `npm run test -- src/auth/useCan.test.tsx`
Expected: FAIL — `Failed to resolve import "./useCan"`.

- [ ] **Step 3: Write the implementation**

Create `packages/smart_pid_web/src/auth/useCan.ts`:

```ts
import type { Role } from '../api/types';
import { useAuth } from './AuthContext';

/**
 * Capability actions — 1:1 with the spec §9 permission table (12 rows).
 * Frontend gating is PRESENTATION ONLY: the backend enforces on every route
 * (require_user / require_admin, phase 0).
 */
export const CAPABILITY_ACTIONS = [
  'view', // View dashboards, trends, alarms, stats
  'alarms.ack', // Acknowledge alarms
  'loop.operate', // Set SP, mode, manual CO
  'export.data', // Export data (create + download)
  'tuning.edit', // Edit PID / fuzzy / RL parameters, apply tuning
  'ai.control', // Start, pause, stop AI workers; optimization toggle
  'controllers.manage', // Create, edit, delete controllers
  'alarms.configure', // Configure alarm limits
  'opcua.configure', // OPC-UA connection and tag mapping
  'projects.manage', // .spid project management
  'users.manage', // Manage users
  'settings.manage', // Change application settings
] as const;

export type CapabilityAction = (typeof CAPABILITY_ACTIONS)[number];

const USER_ACTIONS: ReadonlySet<CapabilityAction> = new Set<CapabilityAction>([
  'view',
  'alarms.ack',
  'loop.operate',
  'export.data',
]);

/** Deny-by-default: null/undefined role (me not resolved) can do nothing. */
export function can(role: Role | null | undefined, action: CapabilityAction): boolean {
  if (role === 'admin') return true;
  if (role === 'user') return USER_ACTIONS.has(action);
  return false;
}

export function useCan(action: CapabilityAction): boolean {
  const { user } = useAuth();
  return can(user?.role ?? null, action);
}
```

- [ ] **Step 4: Run test to verify it passes**

Run (cwd `packages/smart_pid_web`): `npm run test -- src/auth/useCan.test.tsx`
Expected: PASS — 5 tests.

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_web/src/auth/useCan.ts packages/smart_pid_web/src/auth/useCan.test.tsx
git commit -m "feat(web): §9 capability map and useCan hook"
```

---

### Task 11: RouteGuard with admin-only variant (`src/auth/RouteGuard.tsx`)

**Files:**
- Create: `packages/smart_pid_web/src/auth/RouteGuard.tsx`
- Test: `packages/smart_pid_web/src/auth/RouteGuard.test.tsx`

**Interfaces:**
- Consumes: `useAuth` (Task 9); `react-router-dom` (`Navigate`, `useLocation` — dependency already present, ^6.26).
- Produces: `RouteGuardProps { children: ReactNode; adminOnly?: boolean }`, `RouteGuard(props)`. Phase 4 wraps every authenticated route; phase 10 uses `adminOnly` for the users-management route.

Behavior: unauthenticated → `<Navigate to="/login" replace state={{ from: location }} />`. `adminOnly` with role still unknown (`user === null`, `/auth/me` in flight) → render `null` (no flash of forbidden content, no premature bounce). `adminOnly` with role `user` → `<Navigate to="/" replace />`.

- [ ] **Step 1: Write the failing test**

Create `packages/smart_pid_web/src/auth/RouteGuard.test.tsx`:

```tsx
import { render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { ReactNode } from 'react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { AuthProvider } from './AuthContext';
import { RouteGuard } from './RouteGuard';

const fetchMock = vi.fn();
const meResponse = (role: 'admin' | 'user') =>
  new Response(JSON.stringify({ user_id: 1, username: 'u', role }), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  });

beforeEach(() => {
  sessionStorage.clear();
  fetchMock.mockReset();
  vi.stubGlobal('fetch', fetchMock);
});
afterEach(() => vi.unstubAllGlobals());

function app(guarded: ReactNode) {
  return render(
    <AuthProvider>
      <MemoryRouter initialEntries={['/protegido']}>
        <Routes>
          <Route path="/login" element={<div>tela de login</div>} />
          <Route path="/" element={<div>dashboard</div>} />
          <Route path="/protegido" element={guarded} />
        </Routes>
      </MemoryRouter>
    </AuthProvider>,
  );
}

describe('RouteGuard', () => {
  it('redirects unauthenticated visitors to /login', () => {
    app(
      <RouteGuard>
        <div>conteúdo protegido</div>
      </RouteGuard>,
    );
    expect(screen.getByText('tela de login')).toBeInTheDocument();
  });

  it('renders children for an authenticated session', async () => {
    sessionStorage.setItem('smart-pid-token', 't');
    fetchMock.mockResolvedValueOnce(meResponse('user'));
    app(
      <RouteGuard>
        <div>conteúdo protegido</div>
      </RouteGuard>,
    );
    expect(await screen.findByText('conteúdo protegido')).toBeInTheDocument();
  });

  it('adminOnly renders nothing while the role is unknown, then admits admin', async () => {
    sessionStorage.setItem('smart-pid-token', 't');
    let release!: (r: Response) => void;
    fetchMock.mockReturnValueOnce(new Promise<Response>((r) => { release = r; }));
    app(
      <RouteGuard adminOnly>
        <div>painel admin</div>
      </RouteGuard>,
    );
    expect(screen.queryByText('painel admin')).not.toBeInTheDocument();
    expect(screen.queryByText('dashboard')).not.toBeInTheDocument();
    release(meResponse('admin'));
    expect(await screen.findByText('painel admin')).toBeInTheDocument();
  });

  it('adminOnly redirects a user-role session to /', async () => {
    sessionStorage.setItem('smart-pid-token', 't');
    fetchMock.mockResolvedValueOnce(meResponse('user'));
    app(
      <RouteGuard adminOnly>
        <div>painel admin</div>
      </RouteGuard>,
    );
    await waitFor(() => expect(screen.getByText('dashboard')).toBeInTheDocument());
    expect(screen.queryByText('painel admin')).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run (cwd `packages/smart_pid_web`): `npm run test -- src/auth/RouteGuard.test.tsx`
Expected: FAIL — `Failed to resolve import "./RouteGuard"`.

- [ ] **Step 3: Write the implementation**

Create `packages/smart_pid_web/src/auth/RouteGuard.tsx`:

```tsx
import type { ReactNode } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from './AuthContext';

export interface RouteGuardProps {
  children: ReactNode;
  /** Admin-only route variant (phase 10: users management). */
  adminOnly?: boolean;
}

export function RouteGuard({ children, adminOnly = false }: RouteGuardProps) {
  const { isAuthenticated, user } = useAuth();
  const location = useLocation();

  if (!isAuthenticated) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }
  if (adminOnly) {
    // Role unknown while GET /auth/me is in flight: render nothing rather than
    // flashing forbidden content or bouncing an admin to the dashboard.
    if (user === null) return null;
    if (user.role !== 'admin') return <Navigate to="/" replace />;
  }
  return <>{children}</>;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run (cwd `packages/smart_pid_web`): `npm run test -- src/auth/RouteGuard.test.tsx`
Expected: PASS — 4 tests.

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_web/src/auth/RouteGuard.tsx packages/smart_pid_web/src/auth/RouteGuard.test.tsx
git commit -m "feat(web): RouteGuard with admin-only variant"
```

---

### Task 12: Normative §7 resync runner (`src/realtime/resync.ts`)

**Files:**
- Create: `packages/smart_pid_web/src/realtime/resync.ts`
- Test: `packages/smart_pid_web/src/realtime/resync.test.ts`

**Interfaces:**
- Consumes: `endpoints` + `AlarmHistoryParams` (Task 8, default `ResyncApi`), `queryKeys` (Task 8), `ApiError` (Task 7), `QueryClient` (`@tanstack/react-query`).
- Produces: `ResyncContext { lastSeenAlarmTs: number | null }`, `ResyncRunner = (ctx: ResyncContext) => Promise<void>`, `ResyncApi` (six-method subset), `RESYNC_HISTORY_LIMIT = 1000`, `createResyncRunner({ queryClient, api? }): ResyncRunner`. Task 13's provider invokes the runner; phase 4 constructs it in App with the real `QueryClient`.

**The normative resync set (spec §7, verbatim):** controllers · active alarms · **alarm history since `last_seen_ts`** (active-only misses alarms that fired *and cleared* during the gap, breaking the cleared-unacknowledged promise) · AI status · OPC-UA status · simulator status — sequenced **before live render resumes**.

Pinned execution rules:
1. Controllers fetch first (AI statuses fan out over the returned ids); every result primes its canonical query key via `setQueryData`.
2. History uses `GET /alarms/history?start=<ISO>&end=<ISO>&limit=1000` — the backend REQUIRES `end` alongside `start` (`alarms.py:38-39`) and its `limit` defaults to 100 (`alarms.py:41`), too small for a long gap. `start` = `lastSeenAlarmTs` (epoch seconds → ISO). When `lastSeenAlarmTs` is `null` (no alarm envelope ever seen this session) the history call is skipped: there is no in-session baseline to reconcile and the active set fully covers current state.
3. `GET /simulator/status` is admin-only (phase-0 route classification): an `ApiError` with kind `forbidden` is swallowed — a `user`-role session resyncs everything else.
4. Any other rejection aborts the resync; the provider reacts by closing the socket so the backoff cycle retries the whole handshake + resync.

- [ ] **Step 1: Write the failing test**

Create `packages/smart_pid_web/src/realtime/resync.test.ts`:

```ts
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
```

- [ ] **Step 2: Run test to verify it fails**

Run (cwd `packages/smart_pid_web`): `npm run test -- src/realtime/resync.test.ts`
Expected: FAIL — `Failed to resolve import "./resync"`.

- [ ] **Step 3: Write the implementation**

Create `packages/smart_pid_web/src/realtime/resync.ts`:

```ts
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
```

Note: `controllers.map((c) => ...)` relies on `ControllerResponse` exposing `id: number` (backend `dtos/controllers.py:203-206`, `id` is the first field). If the generated alias ever loses `id`, `npm run typecheck` fails here — that is the drift gate doing its job, not a reason to loosen the type.

- [ ] **Step 4: Run test to verify it passes**

Run (cwd `packages/smart_pid_web`): `npm run test -- src/realtime/resync.test.ts`
Expected: PASS — 6 tests.

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_web/src/realtime/resync.ts packages/smart_pid_web/src/realtime/resync.test.ts
git commit -m "feat(web): normative §7 resync runner priming canonical query keys"
```

---

### Task 13: `RealtimeProvider` + `useRealtime(loopId, type)` — socket, auth, fan-out, close codes (`src/realtime/`)

**Files:**
- Create: `packages/smart_pid_web/src/realtime/RealtimeProvider.tsx`
- Create: `packages/smart_pid_web/src/realtime/useRealtime.ts`
- Test: `packages/smart_pid_web/src/realtime/useRealtime.test.tsx`

**Interfaces:**
- Consumes: `validateEnvelope`, `isAuthOk`, `createSeqTracker`, `AnyEnvelope`, `RealtimeEnvelope`, `RealtimeType` (Tasks 1-2); `ResyncRunner`, `ResyncContext` (Task 12).
- Produces: `ConnectionPhase = 'idle' | 'connecting' | 'resyncing' | 'live' | 'auth-failed'`, `RealtimeContextValue { phase; connected; live; subscribe(type, handler): () => void; lastSeenTs(type): number | null }`, `RealtimeContext`, `RealtimeProviderProps { token: string | null; resync: ResyncRunner; onAuthExpired(): void; children?: ReactNode }`, `RealtimeProvider(props)`, `UseRealtimeResult<T> { connected; live; last: RealtimeEnvelope<T> | null; subscribe(handler): () => void }`, `useRealtime<T>(loopId, type): UseRealtimeResult<T>`. Phase 4 mounts the provider inside `AuthProvider` (`token` from `useAuth()`, `resync` from `createResyncRunner`, `onAuthExpired` → `logout`).

Behavior pinned in this task (the full §8 resync sequencing implemented below is verified in depth by Task 14's integration suite; this task's tests cover handshake, fan-out and close codes):
- One `WebSocket` per provider mount to `` `${proto}://${location.host}/ws/realtime` `` (`wss` under https; `/ws` proxied — `vite.config.ts:28`).
- First frame after `onopen` is `{"type":"auth","token"}` (`realtime.py:208-216`); the server replies `{"type":"auth_ok"}` (`realtime.py:225`) — only then is the connection usable.
- Fan-out by envelope type; `useRealtime(loopId, type)` filters by `loop_id` (a `null` `loopId` receives every loop) and keeps the latest envelope in state.
- Close 4401 → phase `'auth-failed'`, call `onAuthExpired()`, NEVER reconnect (§11: token invalid → force re-login).
- Any other close → reconnect with exponential backoff 500 ms → ×2 → cap 10 s; backoff resets to 500 ms after a successful `auth_ok`.
- No token → phase `'idle'`, no socket.

- [ ] **Step 1: Write the failing test**

Create `packages/smart_pid_web/src/realtime/useRealtime.test.tsx` (the `MockWS` class reproduces the deleted client's fake-WS pattern — `vi.stubGlobal('WebSocket', ...)` with manual `_open`/`_emit`/`_close` triggers):

```tsx
import { act, renderHook, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { createElement, type ReactNode } from 'react';
import { RealtimeProvider } from './RealtimeProvider';
import { useRealtime } from './useRealtime';
import type { ResyncRunner } from './resync';

class MockWS {
  static instances: MockWS[] = [];
  onopen: (() => void) | null = null;
  onmessage: ((e: { data: string }) => void) | null = null;
  onclose: ((e: { code: number }) => void) | null = null;
  sent: string[] = [];
  readyState = 0;
  constructor(public url: string) {
    MockWS.instances.push(this);
  }
  send(d: string) {
    this.sent.push(d);
  }
  close() {
    this.readyState = 3;
    this.onclose?.({ code: 1000 });
  }
  _open() {
    this.readyState = 1;
    this.onopen?.();
    // Server handshake ack (realtime.py:225)
    this.onmessage?.({ data: JSON.stringify({ type: 'auth_ok' }) });
  }
  _emit(obj: unknown) {
    this.onmessage?.({ data: JSON.stringify(obj) });
  }
  _close(code: number) {
    this.readyState = 3;
    this.onclose?.({ code });
  }
}

let resyncCalls: Array<{ lastSeenAlarmTs: number | null }>;
const recordingResync: ResyncRunner = (ctx) => {
  resyncCalls.push(ctx);
  return Promise.resolve();
};

beforeEach(() => {
  MockWS.instances = [];
  resyncCalls = [];
  vi.stubGlobal('WebSocket', MockWS as unknown as typeof WebSocket);
});
afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

const onAuthExpired = vi.fn();

function wrapper({ children }: { children: ReactNode }) {
  return createElement(
    RealtimeProvider,
    { token: 'jwt-123', resync: recordingResync, onAuthExpired },
    children,
  );
}

const statusEnv = (loopId: number, seq: number, pv = 42) => ({
  type: 'status',
  loop_id: loopId,
  seq,
  ts: seq,
  data: { controller_id: loopId, pv: { value: pv } },
});

describe('RealtimeProvider handshake and fan-out', () => {
  it('opens /ws/realtime and sends the first-frame auth', () => {
    renderHook(() => useRealtime(null, 'status'), { wrapper });
    const ws = MockWS.instances[0];
    expect(ws.url).toContain('/ws/realtime');
    act(() => ws._open());
    expect(JSON.parse(ws.sent[0])).toEqual({ type: 'auth', token: 'jwt-123' });
  });

  it('creates no socket without a token (phase idle)', () => {
    renderHook(() => useRealtime(null, 'status'), {
      wrapper: ({ children }: { children: ReactNode }) =>
        createElement(
          RealtimeProvider,
          { token: null, resync: recordingResync, onAuthExpired },
          children,
        ),
    });
    expect(MockWS.instances).toHaveLength(0);
  });

  it('goes live after auth_ok WITHOUT resyncing on the first connection (§8: reconnect/gap only)', async () => {
    const { result } = renderHook(() => useRealtime(null, 'status'), { wrapper });
    act(() => MockWS.instances[0]._open());
    await waitFor(() => expect(result.current.live).toBe(true));
    expect(resyncCalls).toHaveLength(0);
  });

  it('delivers the latest envelope for the subscribed (loopId, type)', async () => {
    const { result } = renderHook(() => useRealtime(5, 'status'), { wrapper });
    act(() => MockWS.instances[0]._open());
    act(() => MockWS.instances[0]._emit(statusEnv(5, 1, 42)));
    await waitFor(() =>
      expect((result.current.last?.data as { pv: { value: number } }).pv.value).toBe(42),
    );
  });

  it('filters by loop_id — other loops never reach the hook', async () => {
    const { result } = renderHook(() => useRealtime(5, 'status'), { wrapper });
    act(() => MockWS.instances[0]._open());
    act(() => MockWS.instances[0]._emit(statusEnv(9, 1)));
    act(() => MockWS.instances[0]._emit(statusEnv(5, 2, 77)));
    await waitFor(() => expect(result.current.last?.loop_id).toBe(5));
    expect((result.current.last?.data as { pv: { value: number } }).pv.value).toBe(77);
  });

  it('loopId null receives every loop of that type', async () => {
    const seen: number[] = [];
    const { result } = renderHook(() => useRealtime(null, 'alarm'), { wrapper });
    act(() => MockWS.instances[0]._open());
    act(() => {
      result.current.subscribe((env) => seen.push(env.loop_id ?? -1));
    });
    act(() =>
      MockWS.instances[0]._emit({ type: 'alarm', loop_id: 1, seq: 1, ts: 1, data: { transition: 'TRIGGERED' } }),
    );
    act(() =>
      MockWS.instances[0]._emit({ type: 'alarm', loop_id: 2, seq: 2, ts: 2, data: { transition: 'CLEARED' } }),
    );
    await waitFor(() => expect(seen).toEqual([1, 2]));
  });

  it('ignores malformed frames without crashing', async () => {
    const { result } = renderHook(() => useRealtime(null, 'status'), { wrapper });
    const ws = MockWS.instances[0];
    act(() => ws._open());
    act(() => ws.onmessage?.({ data: '{not json' }));
    act(() => ws._emit({ type: 'bogus', whatever: 1 }));
    act(() => ws._emit(statusEnv(1, 1)));
    await waitFor(() => expect(result.current.last).not.toBeNull());
  });
});

describe('RealtimeProvider close-code policy', () => {
  it('close 4401 → onAuthExpired, phase auth-failed, NO reconnect', async () => {
    vi.useFakeTimers();
    const { result } = renderHook(() => useRealtime(null, 'status'), { wrapper });
    act(() => MockWS.instances[0]._open());
    act(() => MockWS.instances[0]._close(4401));
    expect(onAuthExpired).toHaveBeenCalledTimes(1);
    expect(result.current.connected).toBe(false);
    act(() => {
      vi.advanceTimersByTime(60_000);
    });
    expect(MockWS.instances).toHaveLength(1); // no new socket
  });

  it('other closes reconnect with doubling backoff capped at 10 s', () => {
    vi.useFakeTimers();
    renderHook(() => useRealtime(null, 'status'), { wrapper });
    act(() => MockWS.instances[0]._close(1006));
    act(() => {
      vi.advanceTimersByTime(500); // first retry after 500 ms
    });
    expect(MockWS.instances).toHaveLength(2);
    act(() => MockWS.instances[1]._close(1006));
    act(() => {
      vi.advanceTimersByTime(999);
    });
    expect(MockWS.instances).toHaveLength(2); // 1000 ms not yet elapsed
    act(() => {
      vi.advanceTimersByTime(1);
    });
    expect(MockWS.instances).toHaveLength(3); // doubled to 1000 ms
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run (cwd `packages/smart_pid_web`): `npm run test -- src/realtime/useRealtime.test.tsx`
Expected: FAIL — `Failed to resolve import "./RealtimeProvider"`.

- [ ] **Step 3: Write the implementation**

Create `packages/smart_pid_web/src/realtime/RealtimeProvider.tsx`:

```tsx
import {
  createContext,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import {
  createSeqTracker,
  isAuthOk,
  validateEnvelope,
  type AnyEnvelope,
  type RealtimeType,
} from '../lib/envelope';
import type { ResyncRunner } from './resync';

export type ConnectionPhase = 'idle' | 'connecting' | 'resyncing' | 'live' | 'auth-failed';

type Handler = (env: AnyEnvelope) => void;

export interface RealtimeContextValue {
  phase: ConnectionPhase;
  /** Socket authenticated (live or resyncing). */
  connected: boolean;
  /** Live render allowed — resync (§7) has completed. */
  live: boolean;
  subscribe(type: RealtimeType, handler: Handler): () => void;
  lastSeenTs(type: RealtimeType): number | null;
}

export const RealtimeContext = createContext<RealtimeContextValue | null>(null);

export interface RealtimeProviderProps {
  token: string | null;
  /** The §7 resync set — createResyncRunner(...) in App (phase 4); fakes in tests. */
  resync: ResyncRunner;
  /** WS close 4401 = token invalid → force re-login (§11). Wire to auth logout. */
  onAuthExpired(): void;
  children?: ReactNode;
}

const INITIAL_BACKOFF_MS = 500;
const MAX_BACKOFF_MS = 10_000;
/** Mirrors the backend per-connection lossless cap (realtime.py:28). */
const RESYNC_BUFFER_MAX = 256;

export function RealtimeProvider({ token, resync, onAuthExpired, children }: RealtimeProviderProps) {
  const [phase, setPhase] = useState<ConnectionPhase>('idle');
  const subs = useRef(new Map<RealtimeType, Set<Handler>>());
  const tracker = useRef(createSeqTracker());
  const wsRef = useRef<WebSocket | null>(null);
  const phaseRef = useRef<ConnectionPhase>('idle');
  const hadSession = useRef(false);
  const backoff = useRef(INITIAL_BACKOFF_MS);
  // Resync buffering — backend ConnectionBuffer policy (realtime.py:168-191):
  // status/stats coalesce per (type, loop_id); everything else queues lossless.
  const coalesced = useRef(new Map<string, AnyEnvelope>());
  const lossless = useRef<AnyEnvelope[]>([]);

  const setPhaseBoth = (p: ConnectionPhase): void => {
    phaseRef.current = p;
    setPhase(p);
  };

  const subscribe = useCallback((type: RealtimeType, handler: Handler) => {
    const set = subs.current.get(type) ?? new Set<Handler>();
    set.add(handler);
    subs.current.set(type, set);
    return () => {
      set.delete(handler);
    };
  }, []);

  const lastSeenTs = useCallback(
    (type: RealtimeType) => tracker.current.lastSeenTs(type),
    [],
  );

  useEffect(() => {
    if (!token) {
      setPhaseBoth('idle');
      return;
    }
    let cancelled = false;
    let reconnectTimer: ReturnType<typeof setTimeout> | undefined;

    const dispatch = (env: AnyEnvelope): void => {
      subs.current.get(env.type)?.forEach((h) => h(env));
    };

    const bufferDuringResync = (env: AnyEnvelope): void => {
      if (env.type === 'status' || env.type === 'stats') {
        coalesced.current.set(`${env.type}:${env.loop_id ?? 'null'}`, env);
      } else if (lossless.current.length < RESYNC_BUFFER_MAX) {
        lossless.current.push(env);
      }
      // Beyond the cap events drop — the resync that is already running
      // re-establishes truth from REST, mirroring the backend overflow policy.
    };

    const flushResyncBuffer = (): void => {
      const held = [...coalesced.current.values(), ...lossless.current];
      coalesced.current.clear();
      lossless.current = [];
      held.forEach(dispatch);
    };

    const runResync = (ws: WebSocket): void => {
      setPhaseBoth('resyncing');
      resync({ lastSeenAlarmTs: tracker.current.lastSeenTs('alarm') })
        .then(() => {
          if (cancelled || wsRef.current !== ws) return;
          flushResyncBuffer();
          setPhaseBoth('live');
        })
        .catch(() => {
          if (cancelled || wsRef.current !== ws) return;
          // Failed resync ⇒ state unknown: recycle the socket; backoff retries
          // the whole handshake + resync.
          ws.close();
        });
    };

    const connect = (): void => {
      setPhaseBoth('connecting');
      const proto = location.protocol === 'https:' ? 'wss' : 'ws';
      const ws = new WebSocket(`${proto}://${location.host}/ws/realtime`);
      wsRef.current = ws;
      tracker.current.reset(); // new connection = new seq baseline (last_seen_ts kept)

      ws.onopen = () => {
        ws.send(JSON.stringify({ type: 'auth', token })); // realtime.py:208-216
      };

      ws.onmessage = (e: { data: string }) => {
        let raw: unknown;
        try {
          raw = JSON.parse(e.data);
        } catch {
          return;
        }
        if (isAuthOk(raw)) {
          backoff.current = INITIAL_BACKOFF_MS;
          if (hadSession.current) {
            runResync(ws); // §8: resync on reconnect, before live render resumes
          } else {
            hadSession.current = true;
            setPhaseBoth('live');
          }
          return;
        }
        if (!validateEnvelope(raw)) return; // reuse the parse above — no second JSON.parse
        const env = raw;
        const obs = tracker.current.observe(env);
        if (phaseRef.current === 'resyncing') {
          bufferDuringResync(env);
          return;
        }
        if (obs.gap && phaseRef.current === 'live') {
          bufferDuringResync(env); // the envelope AFTER the gap is still valid
          runResync(ws); // §8: resync on detected seq gap
          return;
        }
        dispatch(env);
      };

      ws.onclose = (e: { code: number }) => {
        if (cancelled) return;
        if (e.code === 4401) {
          // Token invalid (realtime.py:27) → force re-login; never reconnect.
          setPhaseBoth('auth-failed');
          onAuthExpired();
          return;
        }
        // Includes any future server overflow close: reconnect → resync (§11).
        setPhaseBoth('connecting');
        reconnectTimer = setTimeout(connect, backoff.current);
        backoff.current = Math.min(backoff.current * 2, MAX_BACKOFF_MS);
      };
    };

    connect();
    return () => {
      cancelled = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      wsRef.current?.close();
      wsRef.current = null;
    };
  }, [token, resync, onAuthExpired]);

  const value = useMemo<RealtimeContextValue>(
    () => ({
      phase,
      connected: phase === 'live' || phase === 'resyncing',
      live: phase === 'live',
      subscribe,
      lastSeenTs,
    }),
    [phase, subscribe, lastSeenTs],
  );
  return <RealtimeContext.Provider value={value}>{children}</RealtimeContext.Provider>;
}
```

Create `packages/smart_pid_web/src/realtime/useRealtime.ts`:

```ts
import { useContext, useEffect, useMemo, useRef, useState } from 'react';
import type { RealtimeEnvelope, RealtimeType } from '../lib/envelope';
import { RealtimeContext } from './RealtimeProvider';

export interface UseRealtimeResult<T> {
  /** Socket authenticated (live or resyncing). */
  connected: boolean;
  /** Resync complete — safe to render live values (§8). */
  live: boolean;
  /** Latest envelope for (loopId, type); null before the first one. */
  last: RealtimeEnvelope<T> | null;
  /** Every-event callback subscription (alarm streams, §6.7 AI tick buffering). */
  subscribe(handler: (env: RealtimeEnvelope<T>) => void): () => void;
}

/**
 * Subscribe to one envelope type, optionally scoped to one loop
 * (loopId null = all loops). Spec §7 signature: useRealtime(loopId, type).
 */
export function useRealtime<T = unknown>(
  loopId: number | null,
  type: RealtimeType,
): UseRealtimeResult<T> {
  const ctx = useContext(RealtimeContext);
  if (!ctx) throw new Error('useRealtime must be used within RealtimeProvider');
  const { connected, live, subscribe } = ctx;

  const [last, setLast] = useState<RealtimeEnvelope<T> | null>(null);
  // Late external subscribers still see events that arrive between render and
  // their own subscribe() call via the shared per-hook relay below.
  const relays = useRef(new Set<(env: RealtimeEnvelope<T>) => void>());

  useEffect(() => {
    setLast(null); // scope changed — a stale loop's frame must not leak
    return subscribe(type, (env) => {
      if (loopId !== null && env.loop_id !== loopId) return;
      const typed = env as unknown as RealtimeEnvelope<T>;
      setLast(typed);
      relays.current.forEach((h) => h(typed));
    });
  }, [subscribe, type, loopId]);

  return useMemo(
    () => ({
      connected,
      live,
      last,
      subscribe(handler: (env: RealtimeEnvelope<T>) => void) {
        relays.current.add(handler);
        return () => {
          relays.current.delete(handler);
        };
      },
    }),
    [connected, live, last],
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run (cwd `packages/smart_pid_web`): `npm run test -- src/realtime/useRealtime.test.tsx`
Expected: PASS — 9 tests (7 handshake/fan-out + 2 close-code).

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_web/src/realtime/RealtimeProvider.tsx packages/smart_pid_web/src/realtime/useRealtime.ts packages/smart_pid_web/src/realtime/useRealtime.test.tsx
git commit -m "feat(web): RealtimeProvider with single-socket fan-out and useRealtime(loopId, type)"
```

---

### Task 14: Integration — §8 resync sequencing over a fake WebSocket + phase exit gate

**Files:**
- Modify: `packages/smart_pid_web/src/realtime/useRealtime.test.tsx` (append one describe block)

**Interfaces:**
- Consumes: everything from Tasks 1-13 (this is the capstone: `useRealtime` against a fake WebSocket per spec §12 "Integration" row; the `apiClient`-against-mocked-fetch integration half already lives in Tasks 7-9's suites).
- Produces: no new exports — behavioral proof of the §8 contract: "On reconnect or a detected `seq` gap, the §7 resync set runs before live render resumes."

These tests exercise behavior already implemented in Task 13. Expected: PASS on first run. **Any failure here is a Task-13 bug — fix `RealtimeProvider.tsx`, never weaken the test.**

- [ ] **Step 1: Write the integration tests**

Append to `packages/smart_pid_web/src/realtime/useRealtime.test.tsx`:

```tsx
describe('§8 resync sequencing (integration)', () => {
  function deferredRunner() {
    const calls: Array<{ lastSeenAlarmTs: number | null }> = [];
    let resolve!: () => void;
    let reject!: (e: unknown) => void;
    const runner: ResyncRunner = (ctx) => {
      calls.push(ctx);
      return new Promise<void>((res, rej) => {
        resolve = res;
        reject = rej;
      });
    };
    return {
      runner,
      calls,
      resolve: () => resolve(),
      reject: (e: unknown) => reject(e),
    };
  }

  function mount(runner: ResyncRunner) {
    return renderHook(
      () => ({
        status: useRealtime<{ pv: { value: number } }>(5, 'status'),
        alarms: useRealtime(null, 'alarm'),
      }),
      {
        wrapper: ({ children }: { children: ReactNode }) =>
          createElement(
            RealtimeProvider,
            { token: 'jwt-123', resync: runner, onAuthExpired },
            children,
          ),
      },
    );
  }

  it('reconnect resyncs with the alarm last_seen_ts and buffers envelopes until done', async () => {
    vi.useFakeTimers();
    const d = deferredRunner();
    const { result } = mount(d.runner);

    // First connection: live without resync (§8 covers reconnect/gap only).
    act(() => MockWS.instances[0]._open());
    expect(result.current.status.live).toBe(true);

    // An alarm envelope stamps last_seen_ts('alarm') = 111.
    act(() =>
      MockWS.instances[0]._emit({
        type: 'alarm',
        loop_id: 5,
        seq: 1,
        ts: 111,
        data: { transition: 'TRIGGERED' },
      }),
    );

    // Drop and reconnect.
    act(() => MockWS.instances[0]._close(1006));
    await act(async () => {
      await vi.advanceTimersByTimeAsync(500);
    });
    const ws1 = MockWS.instances[1];
    act(() => ws1._open());

    // Resync started with the pre-disconnect alarm timestamp; not live yet.
    expect(d.calls).toEqual([{ lastSeenAlarmTs: 111 }]);
    expect(result.current.status.connected).toBe(true);
    expect(result.current.status.live).toBe(false);

    // Envelopes during resync are held back: status coalesces (latest wins),
    // alarm events queue lossless — mirroring realtime.py:168-191.
    const alarmSeen: unknown[] = [];
    act(() => {
      result.current.alarms.subscribe((env) => alarmSeen.push(env.data));
    });
    act(() => ws1._emit(statusEnv(5, 2, 88)));
    act(() => ws1._emit(statusEnv(5, 3, 99)));
    act(() =>
      ws1._emit({ type: 'alarm', loop_id: 5, seq: 4, ts: 222, data: { transition: 'CLEARED' } }),
    );
    expect(result.current.status.last).toBeNull(); // nothing delivered yet
    expect(alarmSeen).toEqual([]);

    // Resync resolves → buffer flushes → live render resumes.
    await act(async () => {
      d.resolve();
      await Promise.resolve();
    });
    expect(result.current.status.live).toBe(true);
    expect(result.current.status.last?.data.pv.value).toBe(99); // coalesced: latest only
    expect(alarmSeen).toEqual([{ transition: 'CLEARED' }]); // lossless: delivered
  });

  it('a seq gap while live triggers resync WITHOUT reconnecting', async () => {
    const d = deferredRunner();
    const { result } = mount(d.runner);
    act(() => MockWS.instances[0]._open());
    act(() => MockWS.instances[0]._emit(statusEnv(5, 1, 10)));
    await waitFor(() => expect(result.current.status.last?.data.pv.value).toBe(10));

    // seq jumps 1 → 5: frames were lost.
    act(() => MockWS.instances[0]._emit(statusEnv(5, 5, 50)));
    expect(d.calls).toHaveLength(1);
    expect(result.current.status.live).toBe(false);
    expect(MockWS.instances).toHaveLength(1); // same socket, no reconnect

    await act(async () => {
      d.resolve();
      await Promise.resolve();
    });
    expect(result.current.status.live).toBe(true);
    // The post-gap envelope was buffered, not dropped.
    expect(result.current.status.last?.data.pv.value).toBe(50);
  });

  it('a failed resync recycles the socket and retries via backoff', async () => {
    vi.useFakeTimers();
    const d = deferredRunner();
    mount(d.runner);
    act(() => MockWS.instances[0]._open());
    act(() => MockWS.instances[0]._close(1006));
    await act(async () => {
      await vi.advanceTimersByTimeAsync(500);
    });
    act(() => MockWS.instances[1]._open()); // reconnect → resync starts
    expect(d.calls).toHaveLength(1);

    await act(async () => {
      d.reject(new Error('resync failed'));
      await Promise.resolve();
    });
    // Socket recycled; backoff schedules the next attempt (500 already doubled → 1000).
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });
    expect(MockWS.instances).toHaveLength(3);
  });
});
```

- [ ] **Step 2: Run the realtime suite**

Run (cwd `packages/smart_pid_web`): `npm run test -- src/realtime/useRealtime.test.tsx`
Expected: PASS — 12 tests. A failure means Task 13's provider violates §8: fix the provider, re-run, never adjust the assertions.

- [ ] **Step 3: Phase exit gate — full suite, types, lint**

Run (cwd `packages/smart_pid_web`): `npm run test`
Expected: exit 0 — every phase-2 and phase-3 test green (~110 new phase-3 tests across 12 test files: 10 new, `scale.test.ts` + `format.test.ts` extended).

Run (cwd `packages/smart_pid_web`): `npm run typecheck`
Expected: exit 0, no output.

Run (cwd `packages/smart_pid_web`): `npm run lint`
Expected: exit 0. The phase-2 token-only color guard does not fire (this phase ships zero styles); `react-hooks` rules must be clean in `RealtimeProvider.tsx`/`useRealtime.ts`/`AuthContext.tsx` except the single annotated `eslint-disable-next-line react-hooks/exhaustive-deps` in `AuthContext.tsx` (session-restore effect, intentional token-only dependency).

- [ ] **Step 4: Commit**

```bash
git add packages/smart_pid_web/src/realtime/useRealtime.test.tsx
git commit -m "test(web): §8 resync sequencing integration over a fake WebSocket"
```

---

## Self-review checklist (run after all tasks, per writing-plans)

1. **Spec coverage for phase 3 (§13 row 3: "realtime layer + pure modules, fully unit-tested"):**
   - §7 pure modules table → Tasks 1-6 (`envelope`, `windowBuffer`, `alarmMachine`, `scale`, `format`) — no React/DOM imports in `src/lib/`.
   - §7 realtime (`RealtimeProvider`, `useRealtime(loopId, type)`, resync set incl. alarm-history-since-`last_seen_ts`) → Tasks 12-14.
   - §7 data (`apiClient` typed from committed codegen) → Tasks 7-8.
   - §7 auth (`AuthContext`, `RouteGuard`, `useCan(action)`) → Tasks 9-11.
   - §8 data flow (resync before live render; writes REST-only — nothing in this layer writes over WS) → Tasks 13-14.
   - §9 capability table → Task 10 (12 actions, matrix test).
   - §11 error rows 401/403/404/409/422/5xx/502/network + WS 4401/overflow-close → Tasks 7, 9, 13.
   - §12 test rows "Unit: pure modules" + "Integration: useRealtime against a fake WebSocket; apiClient against a mocked API" → Tasks 1-6 / 14 + 7-9.
   - §6.7 pen-tip dependency (undecimated head) → Task 3 `latest()`.
   - Out of scope by §13 design: pages, routes, primitives, themes (phases 2 and 4+); E2E stays dark.
2. **Placeholder scan:** no TBD/TODO/"add validation"/"similar to Task N" — every code step carries complete code; every run step carries the exact command and expected outcome.
3. **Type consistency spot-checks:** `createSeqTracker().lastSeenTs('alarm')` (Task 2) feeds `ResyncContext.lastSeenAlarmTs` (Task 12) via the provider (Task 13); `endpoints.alarmHistory(AlarmHistoryParams)` (Task 8) matches the runner's call (Task 12); `ApiError.kind === 'forbidden'` (Task 7) is what Task 12 swallows; `RealtimeProviderProps.resync: ResyncRunner` names match Tasks 12/13/14; `AlarmRow.acknowledged: 0 | 1` + `cleared_at: string | null` (Task 8) satisfy `fromActiveRow` (Task 4).

## Interfaces exported (for later phases)

Everything later phases may import from phase-3 files, with exact signatures. File paths relative to `packages/smart_pid_web/`.

### `src/lib/envelope.ts`

```ts
export type RealtimeType = 'status' | 'action' | 'ai' | 'alarm' | 'system' | 'stats';
export const REALTIME_TYPES: readonly RealtimeType[];
export interface RealtimeEnvelope<T = unknown> {
  type: RealtimeType; loop_id: number | null; seq: number; ts: number; data: T;
}
export interface FFSignal { value: number; severity: string; limit_bits: string; sub_status: string }
export interface StatusData {
  controller_id: number; pv: FFSignal; sp: FFSignal; co: FFSignal;
  bkcal_in: FFSignal; bkcal_out: FFSignal; mode: string;
  kp: number | null; ti: number | null; td: number | null;
  integral_val: number; timestamp: string | number; error?: number; saturated?: boolean;
}
export interface ActionData {
  controller_id: number; co: FFSignal; bkcal_out: FFSignal;
  integral_val: number; delta_cv: number; timestamp: string;
}
export interface AiData {
  controller_id: number; gamma: number; new_ki: number; engine: string; objective: string;
  integral_type: string; execution_mode: string; reasoning: string; timestamp: string;
}
export type AlarmTransition = 'TRIGGERED' | 'CLEARED';
export interface AlarmEventData {
  controller_id: number; controller_name: string; controller_description: string;
  alarm_type: string; priority: string; transition: AlarmTransition;
  value: number; limit: number; timestamp: string;
}
export interface SystemEventData { source: string; severity: string; message: string; timestamp: string }
export interface StatsData {
  iae: number; itae: number; ise: number; mse: number; std_dev: number;
  total_variation: number; variability_sp: number; variability_range: number;
  mean_abs_error: number; pk_pk_error: number; reversals: number; zero_crossings: number;
  recent_pk_pk_error: number; recent_reversals: number; tv_per_sample: number;
  osc: number; sample_count: number;
}
export type AnyEnvelope =
  | (RealtimeEnvelope<StatusData> & { type: 'status' })
  | (RealtimeEnvelope<ActionData> & { type: 'action' })
  | (RealtimeEnvelope<AiData> & { type: 'ai' })
  | (RealtimeEnvelope<AlarmEventData> & { type: 'alarm' })
  | (RealtimeEnvelope<SystemEventData> & { type: 'system' })
  | (RealtimeEnvelope<StatsData> & { type: 'stats' });
export function isAuthOk(v: unknown): boolean;
export function validateEnvelope(v: unknown): v is AnyEnvelope;
export function parseEnvelope(raw: string): AnyEnvelope | null;
export function statusTimestampToEpoch(ts: string | number): number | null;
export interface SeqObservation { gap: boolean; expected: number | null; received: number }
export interface SeqTracker {
  observe(env: Pick<RealtimeEnvelope, 'type' | 'seq' | 'ts'>): SeqObservation;
  lastSeenTs(type: RealtimeType): number | null;
  reset(): void;
}
export function createSeqTracker(): SeqTracker;
```

### `src/lib/windowBuffer.ts`

```ts
export interface WindowBufferConfig { maxSeconds: number; maxPoints: number }
export interface WindowSample { t: number; values: readonly number[] }
export interface WindowView { data: number[][]; decimated: boolean }
export interface WindowBuffer {
  push(t: number, values: readonly number[]): boolean; // false = rejected (non-finite / non-increasing t)
  latest(): WindowSample | null;                        // undecimated head — §6.7 pen tip
  view(pxWidth: number): WindowView;                    // uPlot AlignedData; min/max decimated when length > pxWidth
  length(): number;
  clear(): void;
}
export function createWindowBuffer(seriesCount: number, cfg: WindowBufferConfig): WindowBuffer;
```

Phase-4 usage contract: Trend renders `view(plotWidthPx).data`; the pen-tip plugin marks `valToPos(latest().t, latest().values[i])` — never the decimated tail. AI-tick markers (§6.7) buffer `ai` envelopes separately and share the same time axis.

### `src/lib/alarmMachine.ts`

```ts
export type AlarmPointState = 'NORMAL' | 'UNACKNOWLEDGED' | 'ACKNOWLEDGED' | 'CLEARED_UNACK';
export type AlarmMachineEvent = { kind: 'TRIGGERED' } | { kind: 'CLEARED' } | { kind: 'ACK' };
export function transition(state: AlarmPointState, event: AlarmMachineEvent): AlarmPointState;
export function fromActiveRow(row: { acknowledged: 0 | 1; cleared_at: string | null }): AlarmPointState;
export function isUnacked(state: AlarmPointState): boolean; // UNACKNOWLEDGED | CLEARED_UNACK
export function isActive(state: AlarmPointState): boolean;  // UNACKNOWLEDGED | ACKNOWLEDGED
```

### `src/lib/scale.ts` (phase-3 additions; base owned by phase 2)

```ts
export function valueToPercent(value: number, scale: Scale): number; // 0..100, clamped
export function clampToScale(value: number, scale: Scale): number;   // [euMin, euMax]; degenerate → euMin
```

### `src/lib/format.ts` (phase-3 additions; base owned by phase 2)

```ts
export function formatWithUnit(value: number | null | undefined, unit: string, decimals: number): string; // "150.3 °C" | '—'
export function formatPercent(ratio: number | null | undefined, decimals?: number): string;               // 0.1234 → "12.3%" | '—' (default 1 decimal)
export function formatTimestamp(ts: string | number | null | undefined): string;                          // epoch s or ISO → local "HH:MM:SS" | '—'
```

### `src/api/client.ts`

```ts
export type ApiErrorKind =
  | 'unauthorized' | 'forbidden' | 'not-found' | 'conflict'
  | 'validation' | 'opcua-down' | 'server' | 'network';
export interface ValidationIssue { loc: (string | number)[]; msg: string; type: string }
export function classifyStatus(status: number): ApiErrorKind;
export class ApiError extends Error {
  readonly status: number;          // 0 for network failures
  readonly kind: ApiErrorKind;
  readonly detail: string;
  readonly fields: ValidationIssue[]; // populated for 422
  constructor(status: number, kind: ApiErrorKind, detail: string, fields?: ValidationIssue[]);
}
export interface AuthHooks {
  getToken(): string | null;
  onUnauthorized?(error: ApiError): void;
  onForbidden?(error: ApiError): void;
}
export function setAuthHooks(next: AuthHooks): void; // AuthProvider owns this registration
export const api: {
  get<T>(path: string): Promise<T>;
  post<T>(path: string, body?: unknown): Promise<T>;
  put<T>(path: string, body?: unknown): Promise<T>;
  delete<T>(path: string): Promise<T>;
  download(path: string): Promise<Blob>;
  upload<T>(path: string, form: FormData): Promise<T>;
};
```

All paths are backend-relative (e.g. `/controllers/3/ai/status`); the client prepends `/api`.

### `src/api/types.ts`

```ts
export type Role = 'admin' | 'user';
export type MeResponse = components['schemas']['UserClaims'];             // {user_id, username, role}
export type TokenResponse = components['schemas']['TokenResponse'];       // {access_token, token_type}
export type ControllerResponse = components['schemas']['ControllerResponse'];
export type AiStatus = components['schemas']['AIStatusResponse'];
export type OpcuaStatus = components['schemas']['OPCUAStatusResponse'];   // {state, endpoint}
export type SimulatorStatus = components['schemas']['SimulatorStatusResponse'];
export type AlarmRowStatus = 'UNACKNOWLEDGED' | 'ACKNOWLEDGED' | 'CLEARED_UNACK';
export interface AlarmRow {
  id: number; controller_id: number; controller_name: string | null;
  alarm_type: string; priority: string; value: number; limit: number;
  timestamp: string; cleared_at: string | null; acknowledged: 0 | 1;
  ack_by_user: string | null; ack_at: string | null; status: AlarmRowStatus;
}
```

### `src/api/endpoints.ts`

```ts
export interface AlarmHistoryParams { start: string; end: string; limit?: number; offset?: number }
export const endpoints: {
  login(username: string, password: string): Promise<TokenResponse>;   // POST /auth/login
  me(): Promise<MeResponse>;                                           // GET /auth/me (require_user)
  controllers(): Promise<ControllerResponse[]>;                        // GET /controllers
  activeAlarms(): Promise<AlarmRow[]>;                                 // GET /alarms/active
  alarmHistory(params: AlarmHistoryParams): Promise<AlarmRow[]>;       // GET /alarms/history?start&end[&limit&offset]
  aiStatus(controllerId: number): Promise<AiStatus>;                   // GET /controllers/{id}/ai/status
  opcuaStatus(): Promise<OpcuaStatus>;                                 // GET /opcua/status
  simulatorStatus(): Promise<SimulatorStatus>;                         // GET /simulator/status (admin-only!)
};
```

Later phases add their own endpoint functions here (same file, same `api.*` transport).

### `src/api/queryKeys.ts`

```ts
export const queryKeys: {
  controllers: readonly ['controllers'];
  alarmsActive: readonly ['alarms', 'active'];
  alarmsResyncHistory: readonly ['alarms', 'resync-history'];
  aiStatus(controllerId: number): readonly ['ai', 'status', number];
  opcuaStatus: readonly ['opcua', 'status'];
  simulatorStatus: readonly ['simulator', 'status'];
};
```

**Contract:** feature hooks (phases 4-10) MUST use these keys for these resources — the resync runner primes exactly these cache entries.

### `src/auth/AuthContext.tsx`

```ts
export type AuthUser = MeResponse; // {user_id: number; username: string; role: 'admin' | 'user'}
export interface AuthContextValue {
  token: string | null;
  user: AuthUser | null;            // null until /auth/me resolves
  isAuthenticated: boolean;         // token !== null
  login(username: string, password: string): Promise<void>; // POST /auth/login + GET /auth/me
  logout(): void;
  refreshUser(): Promise<void>;     // re-GET /auth/me
}
export interface AuthProviderProps { children?: ReactNode; onPermissionDenied?: () => void }
export function AuthProvider(props: AuthProviderProps): JSX.Element;
export function useAuth(): AuthContextValue;
```

Token storage: `sessionStorage['smart-pid-token']`. 401 anywhere → automatic `logout()`. 403 anywhere → `onPermissionDenied()` + `refreshUser()` (phase 4 supplies the "sem permissão" toast).

### `src/auth/useCan.ts`

```ts
export const CAPABILITY_ACTIONS: readonly [
  'view', 'alarms.ack', 'loop.operate', 'export.data',
  'tuning.edit', 'ai.control', 'controllers.manage', 'alarms.configure',
  'opcua.configure', 'projects.manage', 'users.manage', 'settings.manage',
];
export type CapabilityAction = (typeof CAPABILITY_ACTIONS)[number];
export function can(role: Role | null | undefined, action: CapabilityAction): boolean;
export function useCan(action: CapabilityAction): boolean; // deny-by-default while user === null
```

`user` role is allowed exactly: `view`, `alarms.ack`, `loop.operate`, `export.data`. `admin`: all 12.

**Planned additive extension:** phase 8 adds `simulator.configure` as an admin-only capability because simulator start/stop, presets, dynamics and disturbances are configuration operations while twin SP/mode/CO remain `loop.operate`. After phase 8, `CAPABILITY_ACTIONS` has 13 entries; the four `user` actions above remain unchanged.

### `src/auth/RouteGuard.tsx`

```ts
export interface RouteGuardProps { children: ReactNode; adminOnly?: boolean }
export function RouteGuard(props: RouteGuardProps): JSX.Element | null;
```

Unauthenticated → `<Navigate to="/login" replace state={{ from: location }} />`; `adminOnly` + role pending → `null`; `adminOnly` + `user` role → `<Navigate to="/" replace />`.

### `src/realtime/resync.ts`

```ts
export interface ResyncContext { lastSeenAlarmTs: number | null } // epoch seconds
export type ResyncRunner = (ctx: ResyncContext) => Promise<void>;
export interface ResyncApi {
  controllers(): Promise<ControllerResponse[]>;
  activeAlarms(): Promise<AlarmRow[]>;
  alarmHistory(params: AlarmHistoryParams): Promise<AlarmRow[]>;
  aiStatus(controllerId: number): Promise<AiStatus>;
  opcuaStatus(): Promise<OpcuaStatus>;
  simulatorStatus(): Promise<SimulatorStatus>;
}
export const RESYNC_HISTORY_LIMIT: 1000;
export function createResyncRunner(deps: { queryClient: QueryClient; api?: ResyncApi }): ResyncRunner;
```

Behavior: primes `queryKeys.{controllers, alarmsActive, alarmsResyncHistory, aiStatus(id)…, opcuaStatus, simulatorStatus}` via `setQueryData`; history window `[lastSeenAlarmTs → now]` with `limit=1000`, skipped when `lastSeenAlarmTs === null`; simulator-status 403 swallowed (user role); any other failure rejects.

### `src/realtime/RealtimeProvider.tsx` + `src/realtime/useRealtime.ts`

```ts
export type ConnectionPhase = 'idle' | 'connecting' | 'resyncing' | 'live' | 'auth-failed';
export interface RealtimeContextValue {
  phase: ConnectionPhase;
  connected: boolean;                                   // live || resyncing
  live: boolean;                                        // phase === 'live'
  subscribe(type: RealtimeType, handler: (env: AnyEnvelope) => void): () => void;
  lastSeenTs(type: RealtimeType): number | null;
}
export const RealtimeContext: Context<RealtimeContextValue | null>;
export interface RealtimeProviderProps {
  token: string | null;
  resync: ResyncRunner;
  onAuthExpired(): void;
  children?: ReactNode;
}
export function RealtimeProvider(props: RealtimeProviderProps): JSX.Element;

export interface UseRealtimeResult<T> {
  connected: boolean;
  live: boolean;
  last: RealtimeEnvelope<T> | null;
  subscribe(handler: (env: RealtimeEnvelope<T>) => void): () => void;
}
export function useRealtime<T = unknown>(loopId: number | null, type: RealtimeType): UseRealtimeResult<T>;
```

Resync behavior (normative for consumers): the §7 set runs on **reconnect** and on **seq gap** — never on first connect — and **before live render resumes**: `live` stays `false` while `resyncing`; envelopes received during resync are held (status/stats coalesced per loop, others queued lossless up to 256) and flushed on completion. WS close 4401 → `phase 'auth-failed'` + `onAuthExpired()` with no reconnect; every other close reconnects with 500 ms → ×2 → 10 s backoff. Phase-4 App wiring:

```tsx
<AuthProvider onPermissionDenied={/* toast "sem permissão" */}>
  {/* inside a component with useAuth(): */}
  <RealtimeProvider
    token={token}
    resync={createResyncRunner({ queryClient })}
    onAuthExpired={logout}
  >
    {/* routes */}
  </RealtimeProvider>
</AuthProvider>
```
