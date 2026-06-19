# Fatia 3: Alarms — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** Ship the web HMI alarm surface — a persistent `AlarmBar` in the canonical `AppShell` (counts by `AlarmPriority`, blink + ack-all), an `AlarmPanel` page (active list: severity, state, type, timestamp, sort/filter, virtualized to survive flood, deduped by `id`), individual + bulk acknowledge, and per-loop alarm-config (limits/severities) — all driven live by the WS `type:"alarm"` stream with the backend as the single source of truth.

**Architecture:** Consume the existing backend with **zero backend changes**. Alarm events already flow on the internal `EventBus` and reach the web client through the Fatia 0+1 RealtimeWS bridge as `RealtimeEnvelope<…>{ type: "alarm" }` (`EVENT.ALARM.*`, lossless/no-coalescing) plus `EVENT.SYSTEM`. The live `alarm` envelope is a **trigger only** (its wire payload carries `transition`, not a row id/state) — every consumer responds by invalidating TanStack Query `['alarms','active']`, which refetches `GET /alarms/active` (the authoritative rows with `id`/`status`/`priority`). Ack mutations (`POST /alarms/{alarm_id}/ack`, `POST /alarms/ack-all`) revalidate the same query. Per-loop thresholds use `GET`/`PUT /controllers/{controller_id}/alarm-config`. New code lives under `packages/smart_pid_web/src/`; `AlarmBar` mounts in the canonical `AppShell`; the panel registers as a route.

**Tech Stack:** React 18 + TypeScript (strict) + Vite, TanStack Query, `@tanstack/react-virtual` (virtualized list), Vitest + Testing Library (unit), Playwright (e2e). Backend (read-only, already shipped): FastAPI `routers/alarms` + `routers/controllers` alarm-config, Python 3.13.

**Spec:** `docs/superpowers/specs/2026-06-18-web-fatia3-alarms-design.md`
**UI authority:** `docs/superpowers/specs/2026-06-18-web-frontend-design-system-design.md` (§5.5 AlarmBar/AlarmPanel, §6.4 alarm motion, §8.2/§8.4 ISA-101 semantics, §10 Fatia 3).
**Contract:** `docs/superpowers/plans/_web-hmi-foundation-contract.md` (canonical names) · **Backend facts:** `docs/superpowers/plans/_web-hmi-backend-surface.md` (§13 alarm enums/DTOs).

---

## Global Constraints

*(Foundation contract §9 — verbatim; every task inherits these.)*

- **Backend:** bind `127.0.0.1` (config `SPID_API_HOST`); serve SPA via
  `app.mount('/', StaticFiles(directory=dist, html=True))` mounted **after** routers
  (single-origin → no CORS in prod); dev CORS allowlist `http://127.0.0.1:5173` only;
  add security headers (`X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`,
  `Referrer-Policy: strict-origin-when-cross-origin`, basic CSP). Validate `Origin` on `/ws/realtime`.
- **RealtimeWS:** it is the **2nd EventBus consumer**, structurally analogous to
  `TelemetryPublisher`. The bus `recv()` is **blocking ZMQ** — a naive `await sub.recv()`
  freezes the daemon loop. Use `zmq.asyncio` **or** a single shared consumer in
  `run_in_executor` (single-flight) that fans out to all clients. **Never** a recv-loop
  per client; **never** concurrent recv on the same socket. Coalesce last-value only for
  `status`/`stats`; `alarm`/`ai`/system are **lossless bounded** (on overflow, close the
  socket so the client re-syncs via REST). `ConnectionManager` with async lock + resilient broadcast.
- **TDD (mandatory):** failing test → run it red → minimal impl → run it green → commit.
  Bite-sized steps (2–5 min each), checkbox `- [ ]` syntax.
- **Branching (inviolable):** each fatia is implemented on a **new dedicated branch from
  `main`** (e.g. `feat/web-fatia01-foundation-dashboard`). Never reuse another task's branch,
  never commit to `main` directly, never touch `feat/windows-installers`. Merge to `main`
  only with explicit user approval.
- **Subagents:** `model: opus` (project rule).
- **Commits:** conventional (`feat(web): …`, `fix(web): …`); **no attribution trailers**.
- **Python toolchain:** Python 3.13, `uv`. Lint `uv run --with ruff ruff check .`
  (line-length 100). Types `uv run mypy packages/` (baseline ~540 errors — must not increase).
  Tests `uv run pytest`. uv fallback in Flatpak: `/home/luciano/.var/app/com.visualstudio.code/bin/uv`.
- **Frontend toolchain:** `npm` inside `packages/smart_pid_web/`. `npm run test` (Vitest),
  `npm run test:e2e` (Playwright), `npm run build` (Vite), `npm run gen:api`.
- **Known-environmental:** 3 pre-existing failures in
  `tests/.../test_opcua_endpoint.py::TestProjectServiceOPCUA` (Py3.14 `asyncio.get_event_loop()`)
  are NOT regressions — do not "fix" them inside a fatia.
- **UI specs upkeep:** any UI change updates `docs/smartPIDv2.md` + the relevant
  `docs/identidade_visual_*.md`; this design-system spec is the web UI authority.
- **GateGuard:** the first `Write` of each new file may be blocked by a PreToolUse hook —
  present the facts (no importers yet / no API or schema change / instructed to create) and
  retry the same Write, or the operator may `export ECC_GATEGUARD=off`.

**This fatia's branch (per the branching rule above):** `feat/web-fatia3-alarms` (new, from `main`).

### GAP-3a — alarm states resolved against the REAL enum

Foundation contract §8 (GAP-3a) names the state values in shorthand (`UNACK`/`ACK`/`CLEARED_UNACK`). The **real backend enum** (`packages/smart_pid_domain/.../enums.py`, verified) is:

```python
class AlarmState(StrEnum):
    """ISA-18.2 alarm states for ACK workflow."""
    UNACKNOWLEDGED = "UNACKNOWLEDGED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    CLEARED_UNACK = "CLEARED_UNACK"
```

`GET /alarms/active` and `GET /alarms/history` return rows whose `status` field is computed in SQL as exactly one of the three string literals `'ACKNOWLEDGED' | 'CLEARED_UNACK' | 'UNACKNOWLEDGED'`. The spec's "4-state machine (active / ack / cleared-unack / cleared+acked)" maps onto the **3** real values:

| Spec state | Real `status` | Meaning | In active list? |
|---|---|---|---|
| active | `UNACKNOWLEDGED` | condition present, not acked | yes |
| ack (acked-active) | `ACKNOWLEDGED` | acked while condition still present | yes |
| cleared-unack | `CLEARED_UNACK` | condition gone, not yet acked | yes |
| cleared + acked | *(none)* | left the active list (`get_active` filters `NOT (cleared_at IS NOT NULL AND reconhecido = 1)`) | **no — row removed** |

**Ack ≠ clear:** ack acknowledges; clear happens when the condition ceases (backend `AlarmWorker`). The plan uses these three real values; it does **not** invent a 4th state. `AlarmPriority` = `CRITICAL | WARNING | ADVISORY | LOG`; `AlarmType` = `HIHI | HI | LO | LOLO | DV_HI | DV_LO`.

### GAP-3b — WS `alarm` payload is a trigger, not a row (investigated)

The foundation contract's idealized `AlarmData` type is `{ alarm_id: string; severity: string; state: string }`, but the **real** `EVENT.ALARM.{controller_id}` wire payload published by `application/workers/alarm_worker.py` is:

```python
alarm_data = {
    "controller_id": ..., "controller_name": ..., "controller_description": ...,
    "alarm_type": str(t.alarm_type), "priority": str(t.priority),
    "transition": t.transition, "value": t.value, "limit": t.limit,
    "timestamp": t.timestamp.isoformat(),
}
```

It carries **no `id`, no `status`** — it carries `transition` (raised/cleared). Therefore the live `alarm` envelope is handled as a **trigger**: on receipt, invalidate `['alarms','active']` so the panel/bar refetch the authoritative `GET /alarms/active` rows (which DO carry `id` and `status`). This realizes the contract's `onResync`-style "backend is source of truth" rule and the spec's "UI revalida via REST após ack" risk mitigation. Task 1 begins with an explicit investigation step that re-confirms this payload shape from backend code before any UI is built.

### Single-admin override (contract §1)

Target system is **mono-user / NO RBAC**. The live backend still declares `require_operator` (ack, get alarm-config) and `require_supervisor` (put alarm-config), but per contract §1 these collapse to the single-admin model in the target system. The web client therefore performs **no role-based UI gating** for alarms: any authenticated admin may ack and edit alarm-config. Negative auth tests assert **401 when unauthenticated** (not 403-by-role).

---

## File Structure

New files created by this fatia (all under `packages/smart_pid_web/`):

```
src/
  features/
    alarms/
      types.ts                 # ActiveAlarm row type + AlarmConfig types (from generated OpenAPI), severity helpers
      severity.ts              # priority→rank, icon glyph (octagon/triangle/diamond), CSS class mapping (ISA-101 redundant coding)
      useAlarms.ts             # TanStack Query hooks: useActiveAlarms, useAckAlarm, useAckAllAlarms, + WS-trigger wiring
      useAlarmConfig.ts        # useAlarmConfig(controllerId), useUpdateAlarmConfig
      AlarmBar.tsx             # persistent shell footer (36px): counts by priority, blink, [ ACK ALL ]
      AlarmBar.css
      AlarmPanel.tsx           # virtualized dense table: Sev·Tag·Mensagem·Estado·Hora·Ack; sort/filter; ack-per-row + ack-all
      AlarmPanel.css
      AlarmConfigForm.tsx      # per-loop thresholds editor (6 alarm types: limit/priority/enabled)
      AlarmConfigForm.css
  features/alarms/__tests__/
      severity.test.ts
      useAlarms.test.tsx
      AlarmBar.test.tsx
      AlarmPanel.test.tsx
      AlarmConfigForm.test.tsx
tests-e2e/
  alarms.spec.ts               # Playwright: fire → appears → ack → state ACKNOWLEDGED (not removed); clear only after condition ceases
```

Touched existing canonical files:
- `src/components/shell/AppShell.tsx` — mount `<AlarmBar/>` in the footer slot.
- `src/App.tsx` — add the `/alarms` route → `<AlarmPanel/>`.
- `src/api/generated/openapi.ts` — regenerated via `npm run gen:api` (do not hand-edit) to pick up `AlarmConfigResponse`/`AlarmConfigUpdate`/`AlarmThreshold`.

**Backend:** NO change. `routers/alarms`, the `routers/controllers` alarm-config endpoints, the `AlarmState`/`AlarmPriority`/`AlarmType` enums, and the `EVENT.ALARM`/`EVENT.SYSTEM` topics already exist and already flow to the WS via Fatia 0+1. This fatia only consumes them.

---

### Task 0 — Investigate backend alarm surface & regenerate OpenAPI types

**Files:**
- Modify: `packages/smart_pid_web/src/api/generated/openapi.ts` (regenerated, not hand-edited)
- Reference only (read): `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/alarms.py`, `.../routers/controllers.py`, `packages/smart_pid_domain/src/smart_pid_domain/dtos/alarms.py`, `packages/smart_pid_domain/src/smart_pid_domain/enums.py`, `packages/smart_pid_core/src/smart_pid_core/application/workers/alarm_worker.py`, `.../adapters/outbound/alarm_repo.py`

**Interfaces (confirmed from backend, to be relied on by all later tasks):**
- `GET /alarms/active?controller_id&priority` → `200` `list[dict]`; each row keys: `id:int`, `controller_id:int`, `controller_name:str`, `alarm_type:str` (HIHI…), `priority:str` (CRITICAL…), `value:float`, `limit:float`, `timestamp:str(iso)`, `cleared_at:str|null`, `acknowledged:int(0/1)`, `ack_by_user:str|null`, `ack_at:str|null`, `status:str` (`UNACKNOWLEDGED|ACKNOWLEDGED|CLEARED_UNACK`). Auth: operator (→ single-admin).
- `POST /alarms/{alarm_id}/ack` → `200` `{ "status":"acknowledged", ...result }`. No body. Auth: operator (→ single-admin).
- `POST /alarms/ack-all` → `200` `{ "status":"acknowledged", "acknowledged_count":int, "controller_ids":int[] }`. Auth: operator (→ single-admin).
- `GET /controllers/{controller_id}/alarm-config` → `200` `AlarmConfigResponse { controller_id:int, thresholds: AlarmThreshold[] }`. Auth: operator (→ single-admin).
- `PUT /controllers/{controller_id}/alarm-config` body `AlarmConfigUpdate { thresholds: AlarmThreshold[] }` → `200` `AlarmConfigResponse`. Auth: supervisor (→ single-admin). Hot-reloads the running `AlarmWorker`.
- `AlarmThreshold { alarm_type:AlarmType, priority:AlarmPriority="WARNING", limit:float=0.0, enabled:bool=true, deadband:float=0.0, delay_on_s:float=0.0, delay_off_s:float=0.0 }`.
- WS envelope `RealtimeEnvelope<AlarmData>{ type:"alarm", loop_id, seq, ts, data }`; real `data` payload = `{ controller_id, controller_name, controller_description, alarm_type, priority, transition, value, limit, timestamp }` (no `id`/`status` → trigger only).

- [ ] **Step 0.1: Re-confirm the live alarm endpoints, the `status` literals, and the WS payload from backend source (no code yet)**

Read these and verify the facts in the Interfaces block above are still true on this branch:
```bash
sed -n '24,120p' packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/alarms.py
sed -n '518,600p' packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/controllers.py
sed -n '120,235p' packages/smart_pid_core/src/smart_pid_core/adapters/outbound/alarm_repo.py
sed -n '142,162p' packages/smart_pid_domain/src/smart_pid_domain/enums.py
sed -n '160,185p' packages/smart_pid_core/src/smart_pid_core/application/workers/alarm_worker.py
```
Expected: `get_active` SQL emits `CASE … 'ACKNOWLEDGED' … 'CLEARED_UNACK' … ELSE 'UNACKNOWLEDGED' END as status`; `alarm_worker` publishes the dict with `transition` and **no** `id`/`status`. If any fact differs, update this plan's Interfaces block and the GAP notes before continuing. **Do not invent endpoints** (`get_active`/`ack`/`ack-all`/`alarm-config` are the only alarm routes this fatia uses).

- [ ] **Step 0.2: Confirm `routers/controllers` alarm-config endpoints declare a `response_model`**

```bash
grep -n 'alarm-config' packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/controllers.py
```
Expected: both `@router.get(".../alarm-config", response_model=AlarmConfigResponse)` and `@router.put(".../alarm-config", response_model=AlarmConfigResponse)` are present, so OpenAPI will emit typed `AlarmConfigResponse`/`AlarmConfigUpdate`/`AlarmThreshold` schemas. (`/alarms/active`, `/ack`, `/ack-all` return bare `dict`/`list[dict]` and therefore have **no** typed schema — the web client types those rows by hand in Task 1. Note this gap; do **not** add a `response_model` to the backend in this fatia.)

- [ ] **Step 0.3: Regenerate OpenAPI types (backend must be running on :8000)**

```bash
cd packages/smart_pid_web && npm run gen:api
git diff --stat src/api/generated/openapi.ts
```
Expected: `src/api/generated/openapi.ts` updates; it now contains `AlarmConfigResponse`, `AlarmConfigUpdate`, and `AlarmThreshold` component schemas. Commit only if the generated file changed.

- [ ] **Step 0.4: Commit**

Run: `cd packages/smart_pid_web && npm run build`
Expected: build succeeds (generated file is valid TS).
Commit: `chore(web): regenerate OpenAPI types for fatia 3 alarm-config schemas`

---

### Task 1 — Alarm domain types + severity helpers (ISA-101 redundant coding)

**Files:**
- Create: `packages/smart_pid_web/src/features/alarms/types.ts`
- Create: `packages/smart_pid_web/src/features/alarms/severity.ts`
- Test: `packages/smart_pid_web/src/features/alarms/__tests__/severity.test.ts`

**Interfaces:**
```ts
// types.ts
export type AlarmType = 'HIHI' | 'HI' | 'LO' | 'LOLO' | 'DV_HI' | 'DV_LO';
export type AlarmPriority = 'CRITICAL' | 'WARNING' | 'ADVISORY' | 'LOG';
export type AlarmStatus = 'UNACKNOWLEDGED' | 'ACKNOWLEDGED' | 'CLEARED_UNACK';

/** One row from GET /alarms/active (bare dict — typed here by hand, see Task 0.2). */
export interface ActiveAlarm {
  id: number;
  controller_id: number;
  controller_name: string;
  alarm_type: AlarmType;
  priority: AlarmPriority;
  value: number;
  limit: number;
  timestamp: string;        // ISO UTC
  cleared_at: string | null;
  acknowledged: number;     // 0 | 1
  ack_by_user: string | null;
  ack_at: string | null;
  status: AlarmStatus;
}

import type { components } from '../../api/generated/openapi';
export type AlarmThreshold = components['schemas']['AlarmThreshold'];
export type AlarmConfigResponse = components['schemas']['AlarmConfigResponse'];
export type AlarmConfigUpdate = components['schemas']['AlarmConfigUpdate'];
```

- [ ] **Step 1.1: Write failing tests for severity helpers**

Create `packages/smart_pid_web/src/features/alarms/__tests__/severity.test.ts`:
```ts
import { describe, it, expect } from 'vitest';
import { priorityRank, severityIcon, severityClass, isUnacked } from '../severity';

describe('severity helpers', () => {
  it('ranks CRITICAL before WARNING before ADVISORY before LOG', () => {
    expect(priorityRank('CRITICAL')).toBeLessThan(priorityRank('WARNING'));
    expect(priorityRank('WARNING')).toBeLessThan(priorityRank('ADVISORY'));
    expect(priorityRank('ADVISORY')).toBeLessThan(priorityRank('LOG'));
  });

  it('maps each priority to a distinct geometric glyph (ISA-101: shape not just color)', () => {
    const glyphs = new Set([
      severityIcon('CRITICAL'),
      severityIcon('WARNING'),
      severityIcon('ADVISORY'),
    ]);
    expect(glyphs.size).toBe(3); // octagon / triangle / diamond
    expect(severityIcon('CRITICAL')).toBe('octagon');
    expect(severityIcon('WARNING')).toBe('triangle');
    expect(severityIcon('ADVISORY')).toBe('diamond');
  });

  it('maps priority to a stable CSS class token', () => {
    expect(severityClass('CRITICAL')).toBe('sev-critical');
    expect(severityClass('WARNING')).toBe('sev-warning');
    expect(severityClass('ADVISORY')).toBe('sev-advisory');
    expect(severityClass('LOG')).toBe('sev-log');
  });

  it('treats UNACKNOWLEDGED and CLEARED_UNACK as unacked (blink); ACKNOWLEDGED as stable', () => {
    expect(isUnacked('UNACKNOWLEDGED')).toBe(true);
    expect(isUnacked('CLEARED_UNACK')).toBe(true);
    expect(isUnacked('ACKNOWLEDGED')).toBe(false);
  });
});
```

- [ ] **Step 1.2: Run the test — confirm RED**

Run: `cd packages/smart_pid_web && npm run test -- severity`
Expected: FAIL — `Failed to resolve import "../severity"` (module does not exist yet).

- [ ] **Step 1.3: Implement `types.ts` and `severity.ts`**

Create `packages/smart_pid_web/src/features/alarms/types.ts` with the Interfaces block above (verbatim).

Create `packages/smart_pid_web/src/features/alarms/severity.ts`:
```ts
import type { AlarmPriority, AlarmStatus } from './types';

const RANK: Record<AlarmPriority, number> = {
  CRITICAL: 0,
  WARNING: 1,
  ADVISORY: 2,
  LOG: 3,
};

export type SeverityGlyph = 'octagon' | 'triangle' | 'diamond' | 'dot';

const GLYPH: Record<AlarmPriority, SeverityGlyph> = {
  CRITICAL: 'octagon',
  WARNING: 'triangle',
  ADVISORY: 'diamond',
  LOG: 'dot',
};

/** Lower number = higher severity (CRITICAL=0). Used for sort + counters. */
export function priorityRank(p: AlarmPriority): number {
  return RANK[p];
}

/** ISA-101 §8.2: severity is also a SHAPE, never color alone. */
export function severityIcon(p: AlarmPriority): SeverityGlyph {
  return GLYPH[p];
}

/** Stable CSS class token → resolves to --alarm-* / --alarm-*-bg in themes.css. */
export function severityClass(p: AlarmPriority): string {
  return `sev-${p.toLowerCase()}`;
}

/** Unacked rows blink (icon/counter opacity); ACKNOWLEDGED rows are stable (§6.4). */
export function isUnacked(status: AlarmStatus): boolean {
  return status === 'UNACKNOWLEDGED' || status === 'CLEARED_UNACK';
}
```

- [ ] **Step 1.4: Run the test — confirm GREEN**

Run: `cd packages/smart_pid_web && npm run test -- severity`
Expected: PASS (4 tests).

- [ ] **Step 1.5: Lint + typecheck**

Run: `cd packages/smart_pid_web && npm run lint && npm run build`
Expected: no lint errors; build succeeds.
Commit: `feat(web): add alarm domain types and ISA-101 severity helpers`

---

### Task 2 — Alarm data hooks (active query + ack mutations + WS trigger)

**Files:**
- Create: `packages/smart_pid_web/src/features/alarms/useAlarms.ts`
- Test: `packages/smart_pid_web/src/features/alarms/__tests__/useAlarms.test.tsx`

**Interfaces:**
```ts
export const alarmsKeys = {
  active: ['alarms', 'active'] as const,
};
export function useActiveAlarms(): UseQueryResult<ActiveAlarm[], ApiError>;
export function useAckAlarm(): UseMutationResult<void, ApiError, number>;       // arg = alarm id
export function useAckAllAlarms(): UseMutationResult<void, ApiError, void>;
export function useAlarmRealtimeSync(): void;                                   // subscribes WS 'alarm' → invalidate active
```

- [ ] **Step 2.1: Write failing tests for the hooks**

Create `packages/smart_pid_web/src/features/alarms/__tests__/useAlarms.test.tsx`:
```tsx
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import { useActiveAlarms, useAckAlarm, useAckAllAlarms, useAlarmRealtimeSync } from '../useAlarms';
import * as client from '../../../api/client';

vi.mock('../../../api/client');

const rows = [
  { id: 1, controller_id: 7, controller_name: 'FIC-101', alarm_type: 'HIHI',
    priority: 'CRITICAL', value: 99, limit: 90, timestamp: '2026-06-18T10:00:00Z',
    cleared_at: null, acknowledged: 0, ack_by_user: null, ack_at: null, status: 'UNACKNOWLEDGED' },
];

function wrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return { qc, Wrapper: ({ children }: { children: ReactNode }) =>
    <QueryClientProvider client={qc}>{children}</QueryClientProvider> };
}

const subscribers: Record<string, ((env: unknown) => void)[]> = {};
vi.mock('../../../realtime/useRealtime', () => ({
  useRealtime: () => ({
    connected: true,
    lastStatus: new Map(),
    lastStats: new Map(),
    subscribe: (type: string, handler: (env: unknown) => void) => {
      (subscribers[type] ??= []).push(handler);
      return () => { subscribers[type] = subscribers[type].filter((h) => h !== handler); };
    },
    onResync: () => () => {},
  }),
}));

beforeEach(() => {
  vi.clearAllMocks();
  for (const k of Object.keys(subscribers)) delete subscribers[k];
});

describe('useActiveAlarms', () => {
  it('fetches GET /alarms/active and returns rows', async () => {
    vi.spyOn(client, 'apiGet').mockResolvedValue(rows);
    const { Wrapper } = wrapper();
    const { result } = renderHook(() => useActiveAlarms(), { wrapper: Wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(client.apiGet).toHaveBeenCalledWith('/alarms/active');
    expect(result.current.data?.[0].status).toBe('UNACKNOWLEDGED');
  });
});

describe('useAckAlarm', () => {
  it('POSTs /alarms/{id}/ack and invalidates the active query', async () => {
    vi.spyOn(client, 'apiGet').mockResolvedValue(rows);
    vi.spyOn(client, 'apiPost').mockResolvedValue({ status: 'acknowledged' });
    const { qc, Wrapper } = wrapper();
    const spy = vi.spyOn(qc, 'invalidateQueries');
    const { result } = renderHook(() => useAckAlarm(), { wrapper: Wrapper });
    await act(async () => { await result.current.mutateAsync(1); });
    expect(client.apiPost).toHaveBeenCalledWith('/alarms/1/ack');
    expect(spy).toHaveBeenCalledWith({ queryKey: ['alarms', 'active'] });
  });
});

describe('useAckAllAlarms', () => {
  it('POSTs /alarms/ack-all and invalidates the active query', async () => {
    vi.spyOn(client, 'apiPost').mockResolvedValue({ status: 'acknowledged', acknowledged_count: 3, controller_ids: [7] });
    const { qc, Wrapper } = wrapper();
    const spy = vi.spyOn(qc, 'invalidateQueries');
    const { result } = renderHook(() => useAckAllAlarms(), { wrapper: Wrapper });
    await act(async () => { await result.current.mutateAsync(); });
    expect(client.apiPost).toHaveBeenCalledWith('/alarms/ack-all');
    expect(spy).toHaveBeenCalledWith({ queryKey: ['alarms', 'active'] });
  });
});

describe('useAlarmRealtimeSync', () => {
  it('invalidates active alarms when a WS alarm event arrives (trigger-only payload)', async () => {
    vi.spyOn(client, 'apiGet').mockResolvedValue(rows);
    const { qc, Wrapper } = wrapper();
    const spy = vi.spyOn(qc, 'invalidateQueries');
    renderHook(() => useAlarmRealtimeSync(), { wrapper: Wrapper });
    act(() => {
      subscribers['alarm']?.forEach((h) => h({ type: 'alarm', loop_id: 7, seq: 1, ts: 0,
        data: { controller_id: 7, alarm_type: 'HIHI', priority: 'CRITICAL', transition: 'raised' } }));
    });
    expect(spy).toHaveBeenCalledWith({ queryKey: ['alarms', 'active'] });
  });
});
```

- [ ] **Step 2.2: Run the test — confirm RED**

Run: `cd packages/smart_pid_web && npm run test -- useAlarms`
Expected: FAIL — `Failed to resolve import "../useAlarms"`.

- [ ] **Step 2.3: Implement `useAlarms.ts`**

Create `packages/smart_pid_web/src/features/alarms/useAlarms.ts`:
```ts
import { useEffect } from 'react';
import {
  useQuery, useMutation, useQueryClient,
  type UseQueryResult, type UseMutationResult,
} from '@tanstack/react-query';
import { apiGet, apiPost, type ApiError } from '../../api/client';
import { useRealtime } from '../../realtime/useRealtime';
import type { ActiveAlarm } from './types';

export const alarmsKeys = {
  active: ['alarms', 'active'] as const,
};

export function useActiveAlarms(): UseQueryResult<ActiveAlarm[], ApiError> {
  return useQuery<ActiveAlarm[], ApiError>({
    queryKey: alarmsKeys.active,
    queryFn: () => apiGet<ActiveAlarm[]>('/alarms/active'),
  });
}

export function useAckAlarm(): UseMutationResult<void, ApiError, number> {
  const qc = useQueryClient();
  return useMutation<void, ApiError, number>({
    mutationFn: async (alarmId: number) => {
      await apiPost(`/alarms/${alarmId}/ack`);
    },
    // Backend is the source of truth — revalidate, never optimistic-mutate state.
    onSettled: () => { void qc.invalidateQueries({ queryKey: alarmsKeys.active }); },
  });
}

export function useAckAllAlarms(): UseMutationResult<void, ApiError, void> {
  const qc = useQueryClient();
  return useMutation<void, ApiError, void>({
    mutationFn: async () => {
      await apiPost('/alarms/ack-all');
    },
    onSettled: () => { void qc.invalidateQueries({ queryKey: alarmsKeys.active }); },
  });
}

/**
 * The WS `alarm` envelope is a trigger only (its payload carries `transition`,
 * not a row id/status — see GAP-3b). On any alarm event, refetch the
 * authoritative active list. `EVENT.SYSTEM` events (config/ack echoes) do the same.
 */
export function useAlarmRealtimeSync(): void {
  const qc = useQueryClient();
  const { subscribe, onResync } = useRealtime();
  useEffect(() => {
    const invalidate = (): void => {
      void qc.invalidateQueries({ queryKey: alarmsKeys.active });
    };
    const unsubAlarm = subscribe('alarm', invalidate);
    const unsubResync = onResync(invalidate);
    return () => { unsubAlarm(); unsubResync(); };
  }, [qc, subscribe, onResync]);
}
```

- [ ] **Step 2.4: Run the test — confirm GREEN**

Run: `cd packages/smart_pid_web && npm run test -- useAlarms`
Expected: PASS (4 tests).

- [ ] **Step 2.5: Lint + typecheck**

Run: `cd packages/smart_pid_web && npm run lint && npm run build`
Expected: no errors.
Commit: `feat(web): add alarm data hooks (active query, ack mutations, WS trigger sync)`

---

### Task 3 — AlarmPanel (virtualized active list, dedupe, sort/filter, ack)

**Files:**
- Create: `packages/smart_pid_web/src/features/alarms/AlarmPanel.tsx`
- Create: `packages/smart_pid_web/src/features/alarms/AlarmPanel.css`
- Test: `packages/smart_pid_web/src/features/alarms/__tests__/AlarmPanel.test.tsx`

**Interfaces:**
```ts
export function AlarmPanel(): JSX.Element;
// Design (design-system §5.5/§10): dense virtualized table; columns
// Sev · Tag · Mensagem · Estado · Hora · Ack. 3px severity side-stripe + subtle --alarm-*-bg
// on unacked rows. Sortable by severity/hora; filter by estado/loop. Ack-per-row + ack-all.
// Severity always redundant: geometric icon (octagon/triangle/diamond) + color + text.
// aria-live="assertive" region announces new CRITICAL alarms.
```

- [ ] **Step 3.1: Write failing tests for AlarmPanel**

Create `packages/smart_pid_web/src/features/alarms/__tests__/AlarmPanel.test.tsx`:
```tsx
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, within, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import { AlarmPanel } from '../AlarmPanel';
import * as client from '../../../api/client';
import type { ActiveAlarm } from '../types';

vi.mock('../../../api/client');
vi.mock('../../../realtime/useRealtime', () => ({
  useRealtime: () => ({ connected: true, lastStatus: new Map(), lastStats: new Map(),
    subscribe: () => () => {}, onResync: () => () => {} }),
}));

function mk(over: Partial<ActiveAlarm>): ActiveAlarm {
  return { id: 1, controller_id: 7, controller_name: 'FIC-101', alarm_type: 'HI',
    priority: 'WARNING', value: 80, limit: 75, timestamp: '2026-06-18T10:00:00Z',
    cleared_at: null, acknowledged: 0, ack_by_user: null, ack_at: null,
    status: 'UNACKNOWLEDGED', ...over };
}

function renderPanel(rows: ActiveAlarm[]) {
  vi.spyOn(client, 'apiGet').mockResolvedValue(rows);
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}><AlarmPanel /></QueryClientProvider>,
  );
}

beforeEach(() => vi.clearAllMocks());

describe('AlarmPanel', () => {
  it('renders a row per active alarm with severity text, type, state and a row ack button', async () => {
    renderPanel([mk({ id: 1, priority: 'CRITICAL', alarm_type: 'HIHI', status: 'UNACKNOWLEDGED' })]);
    const row = await screen.findByTestId('alarm-row-1');
    expect(within(row).getByText('CRITICAL')).toBeInTheDocument();
    expect(within(row).getByText('HIHI')).toBeInTheDocument();
    expect(within(row).getByText('UNACKNOWLEDGED')).toBeInTheDocument();
    expect(within(row).getByRole('button', { name: /ack/i })).toBeInTheDocument();
  });

  it('dedupes rows by id (flood with repeated ids → one row each)', async () => {
    renderPanel([
      mk({ id: 1 }), mk({ id: 1 }), mk({ id: 1 }), mk({ id: 2 }),
    ]);
    await screen.findByTestId('alarm-row-1');
    expect(screen.getByTestId('alarm-row-1')).toBeInTheDocument();
    expect(screen.getByTestId('alarm-row-2')).toBeInTheDocument();
    expect(screen.queryAllByTestId(/alarm-row-/)).toHaveLength(2);
  });

  it('sorts by severity (CRITICAL above WARNING) by default', async () => {
    renderPanel([
      mk({ id: 5, priority: 'WARNING' }),
      mk({ id: 9, priority: 'CRITICAL', alarm_type: 'HIHI' }),
    ]);
    await screen.findByTestId('alarm-row-9');
    const rows = screen.getAllByTestId(/alarm-row-/);
    expect(rows[0]).toHaveAttribute('data-testid', 'alarm-row-9'); // CRITICAL first
  });

  it('filters the list by state', async () => {
    renderPanel([
      mk({ id: 1, status: 'UNACKNOWLEDGED' }),
      mk({ id: 2, status: 'ACKNOWLEDGED', acknowledged: 1, ack_by_user: 'admin' }),
    ]);
    await screen.findByTestId('alarm-row-1');
    fireEvent.change(screen.getByLabelText(/filter.*state/i), { target: { value: 'ACKNOWLEDGED' } });
    expect(screen.queryByTestId('alarm-row-1')).not.toBeInTheDocument();
    expect(screen.getByTestId('alarm-row-2')).toBeInTheDocument();
  });

  it('acks a single row → POST /alarms/{id}/ack', async () => {
    const post = vi.spyOn(client, 'apiPost').mockResolvedValue({ status: 'acknowledged' });
    renderPanel([mk({ id: 42, status: 'UNACKNOWLEDGED' })]);
    const row = await screen.findByTestId('alarm-row-42');
    fireEvent.click(within(row).getByRole('button', { name: /ack/i }));
    expect(post).toHaveBeenCalledWith('/alarms/42/ack');
  });
});
```

- [ ] **Step 3.2: Run the test — confirm RED**

Run: `cd packages/smart_pid_web && npm run test -- AlarmPanel`
Expected: FAIL — `Failed to resolve import "../AlarmPanel"`.

- [ ] **Step 3.3: Implement `AlarmPanel.tsx` + `AlarmPanel.css`**

Create `packages/smart_pid_web/src/features/alarms/AlarmPanel.tsx`:
```tsx
import { useMemo, useRef, useState } from 'react';
import { useVirtualizer } from '@tanstack/react-virtual';
import { useActiveAlarms, useAckAlarm, useAckAllAlarms, useAlarmRealtimeSync } from './useAlarms';
import { priorityRank, severityIcon, severityClass, isUnacked } from './severity';
import type { ActiveAlarm, AlarmStatus } from './types';
import './AlarmPanel.css';

const ROW_HEIGHT = 32;

function formatLocal(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString();
}

type SortKey = 'severity' | 'time';

export function AlarmPanel(): JSX.Element {
  useAlarmRealtimeSync();
  const { data, isLoading, isError } = useActiveAlarms();
  const ackOne = useAckAlarm();
  const ackAll = useAckAllAlarms();

  const [sortKey, setSortKey] = useState<SortKey>('severity');
  const [stateFilter, setStateFilter] = useState<'ALL' | AlarmStatus>('ALL');
  const [loopFilter, setLoopFilter] = useState<'ALL' | number>('ALL');

  const rows = useMemo(() => {
    // Dedupe by id (flood protection) — last write wins.
    const byId = new Map<number, ActiveAlarm>();
    for (const a of data ?? []) byId.set(a.id, a);
    let list = [...byId.values()];
    if (stateFilter !== 'ALL') list = list.filter((a) => a.status === stateFilter);
    if (loopFilter !== 'ALL') list = list.filter((a) => a.controller_id === loopFilter);
    list.sort((a, b) =>
      sortKey === 'severity'
        ? priorityRank(a.priority) - priorityRank(b.priority) ||
          b.timestamp.localeCompare(a.timestamp)
        : b.timestamp.localeCompare(a.timestamp),
    );
    return list;
  }, [data, stateFilter, loopFilter, sortKey]);

  const loopIds = useMemo(
    () => [...new Set((data ?? []).map((a) => a.controller_id))].sort((a, b) => a - b),
    [data],
  );
  const newCritical = useMemo(
    () => rows.filter((a) => a.priority === 'CRITICAL' && isUnacked(a.status)).length,
    [rows],
  );

  const parentRef = useRef<HTMLDivElement>(null);
  const virt = useVirtualizer({
    count: rows.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => ROW_HEIGHT,
    overscan: 12,
  });

  if (isLoading) return <p className="alarm-panel__status">Loading alarms…</p>;
  if (isError) return <p className="alarm-panel__status" role="alert">Failed to load alarms.</p>;

  return (
    <section className="alarm-panel" aria-label="Active alarms">
      <header className="alarm-panel__toolbar">
        <label>
          Sort
          <select value={sortKey} onChange={(e) => setSortKey(e.target.value as SortKey)}>
            <option value="severity">Severity</option>
            <option value="time">Time</option>
          </select>
        </label>
        <label>
          Filter by state
          <select value={stateFilter} onChange={(e) => setStateFilter(e.target.value as 'ALL' | AlarmStatus)}>
            <option value="ALL">All</option>
            <option value="UNACKNOWLEDGED">Unacknowledged</option>
            <option value="ACKNOWLEDGED">Acknowledged</option>
            <option value="CLEARED_UNACK">Cleared (unacked)</option>
          </select>
        </label>
        <label>
          Filter by loop
          <select
            value={loopFilter}
            onChange={(e) => setLoopFilter(e.target.value === 'ALL' ? 'ALL' : Number(e.target.value))}
          >
            <option value="ALL">All loops</option>
            {loopIds.map((id) => <option key={id} value={id}>{id}</option>)}
          </select>
        </label>
        <button type="button" className="alarm-panel__ack-all" disabled={ackAll.isPending}
          onClick={() => ackAll.mutate()}>ACK ALL</button>
      </header>

      <div className="alarm-panel__live" role="status" aria-live="assertive">
        {newCritical > 0 ? `${newCritical} new critical alarm(s)` : ''}
      </div>

      <div className="alarm-panel__head" role="row">
        <span>Sev</span><span>Tag</span><span>Message</span><span>State</span><span>Time</span><span>Ack</span>
      </div>

      <div ref={parentRef} className="alarm-panel__scroll" data-testid="alarm-scroll">
        <div style={{ height: virt.getTotalSize(), position: 'relative' }}>
          {virt.getVirtualItems().map((vi) => {
            const a = rows[vi.index];
            const unacked = isUnacked(a.status);
            return (
              <div
                key={a.id}
                role="row"
                data-testid={`alarm-row-${a.id}`}
                className={`alarm-row ${severityClass(a.priority)} ${unacked ? 'is-unacked' : ''}`}
                style={{ position: 'absolute', top: 0, left: 0, width: '100%',
                  height: ROW_HEIGHT, transform: `translateY(${vi.start}px)` }}
              >
                <span className="alarm-row__sev">
                  <span className={`sev-icon sev-icon--${severityIcon(a.priority)}`} aria-hidden="true" />
                  {a.priority}
                </span>
                <span className="alarm-row__tag">{a.controller_name}</span>
                <span className="alarm-row__msg">{a.alarm_type} {a.value} (lim {a.limit})</span>
                <span className="alarm-row__state">{a.status}</span>
                <span className="alarm-row__time">{formatLocal(a.timestamp)}</span>
                <span className="alarm-row__ack">
                  <button type="button" disabled={ackOne.isPending}
                    onClick={() => ackOne.mutate(a.id)}>Ack</button>
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
```

Create `packages/smart_pid_web/src/features/alarms/AlarmPanel.css`:
```css
.alarm-panel { display: flex; flex-direction: column; height: 100%; min-height: 0; }
.alarm-panel__toolbar { display: flex; gap: var(--space-3, 12px); align-items: end;
  padding: var(--space-2, 8px); border-bottom: 1px solid var(--divider); }
.alarm-panel__toolbar label { display: flex; flex-direction: column; font-size: 0.75rem; gap: 2px; }
.alarm-panel__ack-all { margin-left: auto; }
.alarm-panel__live { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); }
.alarm-panel__head, .alarm-row {
  display: grid;
  grid-template-columns: 9rem 8rem 1fr 9rem 12rem 4rem;
  align-items: center; gap: var(--space-2, 8px);
  padding: 0 var(--space-2, 8px);
}
.alarm-panel__head { height: 28px; font-size: 0.7rem; text-transform: uppercase;
  border-bottom: 1px solid var(--divider); color: var(--text-muted, inherit); }
.alarm-panel__scroll { flex: 1 1 auto; min-height: 0; overflow: auto; }
.alarm-row { border-bottom: 1px solid var(--divider); font-size: 0.8rem; }
.alarm-row:nth-child(even) { background: var(--zebra, transparent); }
/* 3px severity side-stripe + subtle bg on unacked (design-system §5.5/§10). */
.alarm-row.is-unacked { box-shadow: inset 3px 0 0 0 var(--alarm-stripe, currentColor); }
.alarm-row.sev-critical.is-unacked { background: var(--alarm-critical-bg, transparent); --alarm-stripe: var(--alarm-critical); }
.alarm-row.sev-warning.is-unacked  { background: var(--alarm-warning-bg, transparent);  --alarm-stripe: var(--alarm-warning); }
.alarm-row.sev-advisory.is-unacked { background: var(--alarm-advisory-bg, transparent); --alarm-stripe: var(--alarm-advisory); }
.alarm-row__time { font-variant-numeric: tabular-nums; }
.alarm-row__sev { display: inline-flex; align-items: center; gap: 6px; }
/* ISA-101 §8.2 — geometric shape, never color alone. */
.sev-icon { width: 10px; height: 10px; display: inline-block; background: currentColor; }
.sev-icon--octagon  { clip-path: polygon(30% 0,70% 0,100% 30%,100% 70%,70% 100%,30% 100%,0 70%,0 30%); color: var(--alarm-critical); }
.sev-icon--triangle { clip-path: polygon(50% 0,100% 100%,0 100%); color: var(--alarm-warning); }
.sev-icon--diamond  { clip-path: polygon(50% 0,100% 50%,50% 100%,0 50%); color: var(--alarm-advisory); }
.sev-icon--dot      { border-radius: 50%; color: var(--text-muted, currentColor); }
/* §6.4 — blink ONLY the icon opacity on unacked; never the whole row. */
.alarm-row.is-unacked .sev-icon { animation: alarm-blink 1s step-start infinite; }
@keyframes alarm-blink { 0%,50% { opacity: 1; } 51%,100% { opacity: 0.4; } }
@media (prefers-reduced-motion: reduce) {
  .alarm-row.is-unacked .sev-icon { animation: none; }
  .alarm-row.is-unacked .alarm-row__state { font-weight: 700; text-decoration: underline; }
}
```

- [ ] **Step 3.4: Run the test — confirm GREEN**

Run: `cd packages/smart_pid_web && npm run test -- AlarmPanel`
Expected: PASS (5 tests).

- [ ] **Step 3.5: Lint + typecheck**

Run: `cd packages/smart_pid_web && npm run lint && npm run build`
Expected: no errors. (`@tanstack/react-virtual` is already a Fatia 0+1 dependency; if missing, `npm i @tanstack/react-virtual` and note it in `package.json`.)
Commit: `feat(web): add virtualized AlarmPanel with dedupe, sort/filter and per-row ack`

---

### Task 4 — AlarmBar (persistent shell footer: counts, blink, ack-all)

**Files:**
- Create: `packages/smart_pid_web/src/features/alarms/AlarmBar.tsx`
- Create: `packages/smart_pid_web/src/features/alarms/AlarmBar.css`
- Modify: `packages/smart_pid_web/src/components/shell/AppShell.tsx`
- Test: `packages/smart_pid_web/src/features/alarms/__tests__/AlarmBar.test.tsx`

**Interfaces:**
```ts
export function AlarmBar(): JSX.Element;
// Design (design-system §5.5/§6.4): footer 36px. Counters per priority
// (● n CRIT  ▲ n WARN  ◆ n DIAG) + last-event text (muted) + [ ACK ALL ] right.
// Unacked counters blink (icon/counter opacity, 1s); reduced-motion → weight/underline.
```

- [ ] **Step 4.1: Write failing tests for AlarmBar**

Create `packages/smart_pid_web/src/features/alarms/__tests__/AlarmBar.test.tsx`:
```tsx
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, within } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AlarmBar } from '../AlarmBar';
import * as client from '../../../api/client';
import type { ActiveAlarm } from '../types';

vi.mock('../../../api/client');
vi.mock('../../../realtime/useRealtime', () => ({
  useRealtime: () => ({ connected: true, lastStatus: new Map(), lastStats: new Map(),
    subscribe: () => () => {}, onResync: () => () => {} }),
}));

function mk(over: Partial<ActiveAlarm>): ActiveAlarm {
  return { id: 1, controller_id: 7, controller_name: 'FIC-101', alarm_type: 'HI',
    priority: 'WARNING', value: 80, limit: 75, timestamp: '2026-06-18T10:00:00Z',
    cleared_at: null, acknowledged: 0, ack_by_user: null, ack_at: null,
    status: 'UNACKNOWLEDGED', ...over };
}

function renderBar(rows: ActiveAlarm[]) {
  vi.spyOn(client, 'apiGet').mockResolvedValue(rows);
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}><AlarmBar /></QueryClientProvider>);
}

beforeEach(() => vi.clearAllMocks());

describe('AlarmBar', () => {
  it('shows counts per priority bucket', async () => {
    renderBar([
      mk({ id: 1, priority: 'CRITICAL' }),
      mk({ id: 2, priority: 'CRITICAL' }),
      mk({ id: 3, priority: 'WARNING' }),
      mk({ id: 4, priority: 'ADVISORY' }),
    ]);
    expect(await within(await screen.findByTestId('count-critical')).findByText('2')).toBeInTheDocument();
    expect(within(screen.getByTestId('count-warning')).getByText('1')).toBeInTheDocument();
    expect(within(screen.getByTestId('count-advisory')).getByText('1')).toBeInTheDocument();
  });

  it('marks a bucket as blinking when it has unacked alarms', async () => {
    renderBar([mk({ id: 1, priority: 'CRITICAL', status: 'UNACKNOWLEDGED' })]);
    const crit = await screen.findByTestId('count-critical');
    expect(crit).toHaveClass('is-unacked');
  });

  it('does not blink a bucket whose alarms are all acknowledged', async () => {
    renderBar([mk({ id: 1, priority: 'CRITICAL', status: 'ACKNOWLEDGED', acknowledged: 1 })]);
    const crit = await screen.findByTestId('count-critical');
    expect(crit).not.toHaveClass('is-unacked');
  });

  it('triggers ack-all → POST /alarms/ack-all', async () => {
    const post = vi.spyOn(client, 'apiPost').mockResolvedValue({ status: 'acknowledged', acknowledged_count: 1, controller_ids: [7] });
    renderBar([mk({ id: 1, priority: 'CRITICAL' })]);
    fireEvent.click(await screen.findByRole('button', { name: /ack all/i }));
    expect(post).toHaveBeenCalledWith('/alarms/ack-all');
  });
});
```

- [ ] **Step 4.2: Run the test — confirm RED**

Run: `cd packages/smart_pid_web && npm run test -- AlarmBar`
Expected: FAIL — `Failed to resolve import "../AlarmBar"`.

- [ ] **Step 4.3: Implement `AlarmBar.tsx` + `AlarmBar.css`**

Create `packages/smart_pid_web/src/features/alarms/AlarmBar.tsx`:
```tsx
import { useMemo } from 'react';
import { useActiveAlarms, useAckAllAlarms, useAlarmRealtimeSync } from './useAlarms';
import { severityIcon, isUnacked } from './severity';
import type { ActiveAlarm, AlarmPriority } from './types';
import './AlarmBar.css';

const BUCKETS: { priority: AlarmPriority; label: string; testid: string }[] = [
  { priority: 'CRITICAL', label: 'CRIT', testid: 'count-critical' },
  { priority: 'WARNING', label: 'WARN', testid: 'count-warning' },
  { priority: 'ADVISORY', label: 'DIAG', testid: 'count-advisory' },
];

export function AlarmBar(): JSX.Element {
  useAlarmRealtimeSync();
  const { data } = useActiveAlarms();
  const ackAll = useAckAllAlarms();
  const rows: ActiveAlarm[] = data ?? [];

  const buckets = useMemo(
    () => BUCKETS.map((b) => {
      const inBucket = rows.filter((a) => a.priority === b.priority);
      return { ...b, count: inBucket.length, unacked: inBucket.some((a) => isUnacked(a.status)) };
    }),
    [rows],
  );

  const last = useMemo(
    () => [...rows].sort((a, b) => b.timestamp.localeCompare(a.timestamp))[0],
    [rows],
  );

  return (
    <footer className="alarm-bar" aria-label="Alarm summary">
      <div className="alarm-bar__counts">
        {buckets.map((b) => (
          <span
            key={b.priority}
            data-testid={b.testid}
            className={`alarm-bar__bucket sev-${b.priority.toLowerCase()} ${b.unacked ? 'is-unacked' : ''}`}
          >
            <span className={`sev-icon sev-icon--${severityIcon(b.priority)}`} aria-hidden="true" />
            <span className="alarm-bar__n">{b.count}</span> {b.label}
          </span>
        ))}
      </div>
      <span className="alarm-bar__last">
        {last ? `${last.controller_name}: ${last.alarm_type} ${last.status}` : 'No active alarms'}
      </span>
      <button type="button" className="alarm-bar__ack-all" disabled={ackAll.isPending}
        onClick={() => ackAll.mutate()}>ACK ALL</button>
    </footer>
  );
}
```

Create `packages/smart_pid_web/src/features/alarms/AlarmBar.css`:
```css
.alarm-bar {
  height: 36px; display: flex; align-items: center; gap: var(--space-4, 16px);
  padding: 0 var(--space-3, 12px); border-top: 1px solid var(--divider);
  background: var(--surface-2, transparent); font-size: 0.8rem;
}
.alarm-bar__counts { display: flex; gap: var(--space-3, 12px); }
.alarm-bar__bucket { display: inline-flex; align-items: center; gap: 6px; color: var(--text-muted, inherit); }
.alarm-bar__n { font-variant-numeric: tabular-nums; font-weight: 600; }
.alarm-bar__last { color: var(--text-muted, inherit); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.alarm-bar__ack-all { margin-left: auto; }
/* §6.4 — blink only the icon/counter opacity on unacked buckets. */
.alarm-bar__bucket.is-unacked .sev-icon,
.alarm-bar__bucket.is-unacked .alarm-bar__n { animation: alarm-blink 1s step-start infinite; }
@media (prefers-reduced-motion: reduce) {
  .alarm-bar__bucket.is-unacked .sev-icon,
  .alarm-bar__bucket.is-unacked .alarm-bar__n { animation: none; }
  .alarm-bar__bucket.is-unacked .alarm-bar__n { font-weight: 700; text-decoration: underline; }
}
```

- [ ] **Step 4.4: Run the test — confirm GREEN**

Run: `cd packages/smart_pid_web && npm run test -- AlarmBar`
Expected: PASS (4 tests).

- [ ] **Step 4.5: Mount `<AlarmBar/>` in the canonical AppShell**

In `packages/smart_pid_web/src/components/shell/AppShell.tsx`, import `AlarmBar` and render it in the persistent footer slot (after `<main>{children}</main>` / `<Outlet/>`), e.g.:
```tsx
import { AlarmBar } from '../../features/alarms/AlarmBar';
// …inside the shell layout, as the last child of the shell container:
<AlarmBar />
```
Add a basic smoke assertion to the existing AppShell test (or create one) verifying `getByLabelText('Alarm summary')` is present when the shell renders.

- [ ] **Step 4.6: Run the AppShell test + lint + build**

Run: `cd packages/smart_pid_web && npm run test -- AppShell && npm run lint && npm run build`
Expected: PASS; no lint errors; build succeeds.
Commit: `feat(web): add persistent AlarmBar to AppShell with priority counts and ack-all`

---

### Task 5 — Per-loop alarm-config form (limits/severities, persists + retriggers)

**Files:**
- Create: `packages/smart_pid_web/src/features/alarms/useAlarmConfig.ts`
- Create: `packages/smart_pid_web/src/features/alarms/AlarmConfigForm.tsx`
- Create: `packages/smart_pid_web/src/features/alarms/AlarmConfigForm.css`
- Test: `packages/smart_pid_web/src/features/alarms/__tests__/AlarmConfigForm.test.tsx`

**Interfaces:**
```ts
export function useAlarmConfig(controllerId: number): UseQueryResult<AlarmConfigResponse, ApiError>;
export function useUpdateAlarmConfig(controllerId: number): UseMutationResult<AlarmConfigResponse, ApiError, AlarmThreshold[]>;
export function AlarmConfigForm(props: { controllerId: number }): JSX.Element;
// 6 alarm types (HIHI/HI/LO/LOLO/DV_HI/DV_LO): enabled, limit (number), priority (select).
// PUT requires the FULL thresholds[] (backend replaces all). Save → revalidate config query.
```

- [ ] **Step 5.1: Write failing tests for the config hooks + form**

Create `packages/smart_pid_web/src/features/alarms/__tests__/AlarmConfigForm.test.tsx`:
```tsx
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AlarmConfigForm } from '../AlarmConfigForm';
import * as client from '../../../api/client';

vi.mock('../../../api/client');

const config = {
  controller_id: 7,
  thresholds: [
    { alarm_type: 'HIHI', priority: 'CRITICAL', limit: 90, enabled: true, deadband: 1, delay_on_s: 0, delay_off_s: 0 },
    { alarm_type: 'HI', priority: 'WARNING', limit: 80, enabled: true, deadband: 1, delay_on_s: 0, delay_off_s: 0 },
  ],
};

function renderForm() {
  vi.spyOn(client, 'apiGet').mockResolvedValue(config);
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}><AlarmConfigForm controllerId={7} /></QueryClientProvider>);
}

beforeEach(() => vi.clearAllMocks());

describe('AlarmConfigForm', () => {
  it('loads GET /controllers/{id}/alarm-config and renders a row per threshold', async () => {
    renderForm();
    expect(await screen.findByTestId('threshold-HIHI')).toBeInTheDocument();
    expect(screen.getByTestId('threshold-HI')).toBeInTheDocument();
    expect(client.apiGet).toHaveBeenCalledWith('/controllers/7/alarm-config');
  });

  it('saves with PUT carrying the full thresholds array and the edited limit', async () => {
    const put = vi.spyOn(client, 'apiPut').mockResolvedValue(config);
    renderForm();
    const hihi = await screen.findByTestId('threshold-HIHI');
    const limit = within(hihi).getByLabelText(/limit/i);
    fireEvent.change(limit, { target: { value: '95' } });
    fireEvent.click(screen.getByRole('button', { name: /save/i }));
    await waitFor(() => expect(put).toHaveBeenCalled());
    const [url, body] = put.mock.calls[0];
    expect(url).toBe('/controllers/7/alarm-config');
    expect(body).toMatchObject({ thresholds: expect.any(Array) });
    expect(body.thresholds).toHaveLength(2);
    expect(body.thresholds.find((t: { alarm_type: string }) => t.alarm_type === 'HIHI').limit).toBe(95);
  });
});

// helper import kept local to the file
import { within } from '@testing-library/react';
```

- [ ] **Step 5.2: Run the test — confirm RED**

Run: `cd packages/smart_pid_web && npm run test -- AlarmConfigForm`
Expected: FAIL — `Failed to resolve import "../AlarmConfigForm"`.

- [ ] **Step 5.3: Implement `useAlarmConfig.ts`**

Create `packages/smart_pid_web/src/features/alarms/useAlarmConfig.ts`:
```ts
import {
  useQuery, useMutation, useQueryClient,
  type UseQueryResult, type UseMutationResult,
} from '@tanstack/react-query';
import { apiGet, apiPut, type ApiError } from '../../api/client';
import type { AlarmConfigResponse, AlarmThreshold } from './types';

export const alarmConfigKey = (controllerId: number) =>
  ['alarms', 'config', controllerId] as const;

export function useAlarmConfig(controllerId: number): UseQueryResult<AlarmConfigResponse, ApiError> {
  return useQuery<AlarmConfigResponse, ApiError>({
    queryKey: alarmConfigKey(controllerId),
    queryFn: () => apiGet<AlarmConfigResponse>(`/controllers/${controllerId}/alarm-config`),
  });
}

export function useUpdateAlarmConfig(
  controllerId: number,
): UseMutationResult<AlarmConfigResponse, ApiError, AlarmThreshold[]> {
  const qc = useQueryClient();
  return useMutation<AlarmConfigResponse, ApiError, AlarmThreshold[]>({
    // Backend PUT replaces ALL thresholds — always send the full array.
    mutationFn: (thresholds) =>
      apiPut<AlarmConfigResponse>(`/controllers/${controllerId}/alarm-config`, { thresholds }),
    onSuccess: (data) => { qc.setQueryData(alarmConfigKey(controllerId), data); },
  });
}
```

- [ ] **Step 5.4: Implement `AlarmConfigForm.tsx` + `AlarmConfigForm.css`**

Create `packages/smart_pid_web/src/features/alarms/AlarmConfigForm.tsx`:
```tsx
import { useEffect, useState } from 'react';
import { useAlarmConfig, useUpdateAlarmConfig } from './useAlarmConfig';
import type { AlarmThreshold, AlarmType, AlarmPriority } from './types';
import './AlarmConfigForm.css';

const ALARM_TYPES: AlarmType[] = ['HIHI', 'HI', 'LO', 'LOLO', 'DV_HI', 'DV_LO'];
const PRIORITIES: AlarmPriority[] = ['CRITICAL', 'WARNING', 'ADVISORY', 'LOG'];

function blank(t: AlarmType): AlarmThreshold {
  return { alarm_type: t, priority: 'WARNING', limit: 0, enabled: false, deadband: 0, delay_on_s: 0, delay_off_s: 0 };
}

export function AlarmConfigForm({ controllerId }: { controllerId: number }): JSX.Element {
  const { data, isLoading, isError } = useAlarmConfig(controllerId);
  const update = useUpdateAlarmConfig(controllerId);
  const [draft, setDraft] = useState<AlarmThreshold[]>([]);

  useEffect(() => {
    if (!data) return;
    const byType = new Map(data.thresholds.map((t) => [t.alarm_type, t]));
    setDraft(ALARM_TYPES.map((t) => byType.get(t) ?? blank(t)));
  }, [data]);

  if (isLoading) return <p>Loading alarm config…</p>;
  if (isError) return <p role="alert">Failed to load alarm config.</p>;

  const patch = (t: AlarmType, p: Partial<AlarmThreshold>): void =>
    setDraft((d) => d.map((row) => (row.alarm_type === t ? { ...row, ...p } : row)));

  return (
    <form
      className="alarm-config"
      onSubmit={(e) => { e.preventDefault(); update.mutate(draft); }}
      aria-label={`Alarm configuration for controller ${controllerId}`}
    >
      {draft.map((row) => (
        <fieldset key={row.alarm_type} data-testid={`threshold-${row.alarm_type}`} className="alarm-config__row">
          <legend>{row.alarm_type}</legend>
          <label>
            Enabled
            <input type="checkbox" checked={row.enabled}
              onChange={(e) => patch(row.alarm_type, { enabled: e.target.checked })} />
          </label>
          <label>
            Limit
            <input type="number" value={row.limit}
              onChange={(e) => patch(row.alarm_type, { limit: Number(e.target.value) })} />
          </label>
          <label>
            Priority
            <select value={row.priority}
              onChange={(e) => patch(row.alarm_type, { priority: e.target.value as AlarmPriority })}>
              {PRIORITIES.map((p) => <option key={p} value={p}>{p}</option>)}
            </select>
          </label>
        </fieldset>
      ))}
      <button type="submit" disabled={update.isPending}>Save</button>
      {update.isError && <p role="alert">Save failed.</p>}
      {update.isSuccess && <p role="status">Saved.</p>}
    </form>
  );
}
```

Create `packages/smart_pid_web/src/features/alarms/AlarmConfigForm.css`:
```css
.alarm-config { display: flex; flex-direction: column; gap: var(--space-2, 8px); }
.alarm-config__row {
  display: grid; grid-template-columns: 5rem repeat(3, 1fr); align-items: center;
  gap: var(--space-2, 8px); border: 1px solid var(--divider); padding: var(--space-2, 8px);
}
.alarm-config__row legend { font-weight: 600; }
.alarm-config__row label { display: flex; flex-direction: column; font-size: 0.75rem; gap: 2px; }
```

- [ ] **Step 5.5: Run the test — confirm GREEN**

Run: `cd packages/smart_pid_web && npm run test -- AlarmConfigForm`
Expected: PASS (2 tests).

- [ ] **Step 5.6: Add the `/alarms` route + lint + build**

In `packages/smart_pid_web/src/App.tsx`, add a guarded route `<Route path="alarms" element={<AlarmPanel />} />` inside the existing `<RequireAuth>`-protected shell route. (The config form is reachable per-controller from the controller detail page if one exists; otherwise expose `AlarmConfigForm` from the panel via a per-loop affordance — keep scope minimal.)
Run: `cd packages/smart_pid_web && npm run lint && npm run build`
Expected: no errors.
Commit: `feat(web): add per-loop alarm-config form with full-array PUT persistence`

---

### Task 6 — Playwright e2e: alarm fires → appears → ack → state ACKNOWLEDGED (not removed); clear only after condition ceases

**Files:**
- Create: `packages/smart_pid_web/tests-e2e/alarms.spec.ts`

**Interfaces:** Drives the running SPA against a backend (or mocked routes) and asserts the GAP-3a lifecycle end-to-end.

- [ ] **Step 6.1: Write the e2e spec (mock the alarm REST routes; drive the WS trigger)**

Create `packages/smart_pid_web/tests-e2e/alarms.spec.ts`:
```ts
import { test, expect } from '@playwright/test';

// Stateful in-test backend double for the alarm endpoints.
const state = {
  alarms: [] as Array<Record<string, unknown>>,
};

test.beforeEach(async ({ page }) => {
  state.alarms = [{
    id: 1, controller_id: 7, controller_name: 'FIC-101', alarm_type: 'HIHI',
    priority: 'CRITICAL', value: 99, limit: 90, timestamp: new Date().toISOString(),
    cleared_at: null, acknowledged: 0, ack_by_user: null, ack_at: null, status: 'UNACKNOWLEDGED',
  }];

  await page.route('**/api/alarms/active', (route) =>
    route.fulfill({ json: state.alarms.filter((a) => !(a.cleared_at && a.acknowledged)) }));

  await page.route('**/api/alarms/1/ack', (route) => {
    const a = state.alarms.find((x) => x.id === 1)!;
    a.acknowledged = 1; a.ack_by_user = 'admin';
    a.status = a.cleared_at ? 'CLEARED_UNACK' : 'ACKNOWLEDGED'; // ack does NOT clear
    return route.fulfill({ json: { status: 'acknowledged' } });
  });

  await page.route('**/api/alarms/ack-all', (route) => {
    for (const a of state.alarms) { a.acknowledged = 1; a.status = a.cleared_at ? 'CLEARED_UNACK' : 'ACKNOWLEDGED'; }
    return route.fulfill({ json: { status: 'acknowledged', acknowledged_count: 1, controller_ids: [7] } });
  });
});

test('alarm fires → appears → ack → state ACKNOWLEDGED (not removed); clear only after condition ceases', async ({ page }) => {
  await page.goto('/alarms');

  // Appears live from GET /alarms/active.
  const row = page.getByTestId('alarm-row-1');
  await expect(row).toBeVisible();
  await expect(row.getByText('UNACKNOWLEDGED')).toBeVisible();

  // Ack → state becomes ACKNOWLEDGED and the row is NOT removed (ack ≠ clear).
  await row.getByRole('button', { name: /ack/i }).click();
  await expect(page.getByTestId('alarm-row-1')).toBeVisible();
  await expect(page.getByTestId('alarm-row-1').getByText('ACKNOWLEDGED')).toBeVisible();

  // Condition ceases (cleared) AFTER ack → cleared+acked → row leaves the active list.
  const a = state.alarms.find((x) => x.id === 1)!;
  a.cleared_at = new Date().toISOString(); // get_active filters NOT(cleared AND acked)
  await page.reload();
  await page.goto('/alarms');
  await expect(page.getByTestId('alarm-row-1')).toHaveCount(0);
});
```

- [ ] **Step 6.2: Run the e2e spec**

Run: `cd packages/smart_pid_web && npm run test:e2e -- alarms`
Expected: PASS — the alarm appears, ack flips the state to `ACKNOWLEDGED` without removing the row, and a cleared+acked alarm drops out of the active list. (If auth gating blocks `/alarms`, seed the session token in a `beforeEach` exactly as Fatia 0+1's e2e helper does.)
Commit: `test(web): e2e alarm lifecycle (fire → ack ≠ clear → drop on cleared+acked)`

---

### Task 7 — Specs upkeep + full-suite verification

**Files:**
- Modify: `docs/smartPIDv2.md` (note the web alarm surface: AlarmBar + AlarmPanel + alarm-config parity with PySide6 `alarm_panel`/`alarm_bar`)
- Modify: relevant `docs/identidade_visual_*.md` if alarm color/motion tokens were referenced

- [ ] **Step 7.1: Update the UI specs (contract §9 "UI specs upkeep")**

Document the React alarm surface (AlarmBar in `AppShell`, `/alarms` AlarmPanel, per-loop alarm-config), the ISA-101 redundant-coding (icon shape + color + text), the §6.4 blink/reduced-motion rules, and the GAP-3a 3-state model in `docs/smartPIDv2.md`. Keep `identidade_visual_*.md` consistent if any `--alarm-*` token name is referenced.

- [ ] **Step 7.2: Full frontend verification**

Run: `cd packages/smart_pid_web && npm run lint && npm run test && npm run build`
Expected: lint clean; all Vitest suites green; build succeeds.

- [ ] **Step 7.3: Confirm no backend regressions (read-only fatia)**

Run: `uv run --with ruff ruff check . && uv run mypy packages/ && uv run pytest -q`
Expected: ruff clean; mypy error count not increased over the ~540 baseline; pytest green except the 3 known-environmental `test_opcua_endpoint.py::TestProjectServiceOPCUA` failures (NOT regressions — do not "fix").
Commit: `docs(web): document fatia 3 alarm surface (AlarmBar/AlarmPanel/alarm-config)`

---

## Self-Review

Before declaring this fatia complete, verify against the spec and contract:

- [ ] **Backend untouched.** No file under `packages/smart_pid_core/` or `packages/smart_pid_domain/` was modified. The fatia consumes `routers/alarms` + `routers/controllers` alarm-config + the `EVENT.ALARM`/`EVENT.SYSTEM` WS stream only. (`response_model` gap on `/alarms/active|ack|ack-all` is noted, not patched.)
- [ ] **GAP-3a — real enum used.** Only `UNACKNOWLEDGED` / `ACKNOWLEDGED` / `CLEARED_UNACK` appear in code; no invented 4th state. The "cleared+acked" case is represented by the row leaving the active list (backend `get_active` filter), and tests assert it.
- [ ] **GAP-3b — WS is a trigger.** The `alarm` envelope handler invalidates `['alarms','active']` and refetches; it never reads `id`/`status` off the WS payload. `onResync` also refetches.
- [ ] **Ack ≠ clear.** Vitest + Playwright prove ack flips state to `ACKNOWLEDGED` and keeps the row; clear is driven only by the backend condition ceasing.
- [ ] **Backend is source of truth.** Both ack mutations and ack-all `invalidateQueries(['alarms','active'])`; no optimistic state surgery. Per spec risk "estado de ack dessincronizado".
- [ ] **Flood survivable.** `AlarmPanel` is virtualized (`@tanstack/react-virtual`) and deduped by `id`; tests cover both.
- [ ] **AlarmBar mounts in canonical AppShell** (footer 36px), counts by `AlarmPriority`, blink on unacked, `ACK ALL` affordance — and the AppShell test asserts its presence.
- [ ] **alarm-config persists + retriggers.** PUT sends the full `thresholds[]` (backend replaces all) and the backend hot-reloads the running `AlarmWorker`; e2e/Vitest assert the edited limit is in the PUT body.
- [ ] **ISA-101 §8.2 redundant coding.** Severity is icon-shape + color + text everywhere; reduced-motion replaces blink with weight/underline (§6.4). `aria-live` announces new CRITICAL.
- [ ] **Single-admin (contract §1).** No role-based UI gating; any authenticated admin acks/edits; negative auth = 401-when-unauthenticated, not 403-by-role.
- [ ] **Toolchain gates.** `npm run lint`, `npm run test`, `npm run build`, `npm run test:e2e` green; mypy/ruff/pytest unchanged vs. baseline; commits conventional with no attribution trailers; all work on `feat/web-fatia3-alarms` from `main`.
