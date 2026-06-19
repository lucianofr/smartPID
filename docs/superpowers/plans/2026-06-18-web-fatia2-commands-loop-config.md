# Fatia 2: Commands + Loop Config — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** Add operator/supervisor control to the Web HMI: inline command controls on the canonical `ControllerCard` (setpoint, mode, manual CO, AI-optimizer enable toggle), a new `LoopConfigDialog` for editing PID tuning + AI engine selection + ARW/filter limits, an AI panel (start/stop/pause/status), and a guarded apply-tuning write-back that requires explicit confirmation. All wired to the **existing** real backend routers; no backend code changes in this fatia.

**Architecture:** New feature folder `src/features/loop-config/` (dialog, AI panel, command hooks, validation, types). It consumes — never redefines — the canonical `ControllerCard.tsx` (design-system §5.2; Fatia 0+1 ships the card and explicitly reserves "control inline added by Fatia 2"), the canonical REST client `api/client.ts` (`apiGet/apiPost/apiPut/apiDelete`), the canonical `useRealtime()` hook + `RealtimeEnvelope`/`StatusData`/`AiData` types (contract §4/§5), and the canonical UI primitives from Fatia 0+1 (`Dialog`, `Button`, field/select primitives, toast/error surface). Data flow: TanStack Query `useMutation` → `apiPost`/`apiPut` → backend router → audit + ZMQ broadcast → `status`/`ai` WS frames → `useRealtime` last-value Map / event subscription → UI reflects new state. Apply-tuning is a two-phase physical action gated behind a confirmation dialog.

**Tech Stack:** React 18 + TypeScript (strict), Vite, TanStack Query, Vitest + Testing Library (jsdom), Playwright (e2e), CSS token contract from `theme/tokens.css`. Backend (unchanged, consumed): FastAPI routers `commands`, `ai`, `controllers`.

**Spec:** `docs/superpowers/specs/2026-06-18-web-fatia2-commands-loop-config-design.md` (UI authority: `docs/superpowers/specs/2026-06-18-web-frontend-design-system-design.md` §5.2, §5.6, §10 "Fatia 2"). Contract: `docs/superpowers/plans/_web-hmi-foundation-contract.md`. Backend surface: `docs/superpowers/plans/_web-hmi-backend-surface.md`.

---

## Global Constraints

_(Copied verbatim from `_web-hmi-foundation-contract.md` §9. Every task inherits these.)_

- **Backend:** bind `127.0.0.1` (config `SPID_API_HOST`); serve SPA via `app.mount('/', StaticFiles(directory=dist, html=True))` mounted **after** routers (single-origin → no CORS in prod); dev CORS allowlist `http://127.0.0.1:5173` only; add security headers (`X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`, basic CSP). Validate `Origin` on `/ws/realtime`.
- **RealtimeWS:** it is the **2nd EventBus consumer**, structurally analogous to `TelemetryPublisher`. The bus `recv()` is **blocking ZMQ** — a naive `await sub.recv()` freezes the daemon loop. Use `zmq.asyncio` **or** a single shared consumer in `run_in_executor` (single-flight) that fans out to all clients. **Never** a recv-loop per client; **never** concurrent recv on the same socket. Coalesce last-value only for `status`/`stats`; `alarm`/`ai`/system are **lossless bounded** (on overflow, close the socket so the client re-syncs via REST). `ConnectionManager` with async lock + resilient broadcast.
- **TDD (mandatory):** failing test → run it red → minimal impl → run it green → commit. Bite-sized steps (2–5 min each), checkbox `- [ ]` syntax.
- **Branching (inviolable):** each fatia is implemented on a **new dedicated branch from `main`** (e.g. `feat/web-fatia01-foundation-dashboard`). Never reuse another task's branch, never commit to `main` directly, never touch `feat/windows-installers`. Merge to `main` only with explicit user approval.
- **Subagents:** `model: opus` (project rule).
- **Commits:** conventional (`feat(web): …`, `fix(web): …`); **no attribution trailers**.
- **Python toolchain:** Python 3.13, `uv`. Lint `uv run --with ruff ruff check .` (line-length 100). Types `uv run mypy packages/` (baseline ~540 errors — must not increase). Tests `uv run pytest`. uv fallback in Flatpak: `/home/luciano/.var/app/com.visualstudio.code/bin/uv`.
- **Frontend toolchain:** `npm` inside `packages/smart_pid_web/`. `npm run test` (Vitest), `npm run test:e2e` (Playwright), `npm run build` (Vite), `npm run gen:api`.
- **Known-environmental:** 3 pre-existing failures in `tests/.../test_opcua_endpoint.py::TestProjectServiceOPCUA` (Py3.14 `asyncio.get_event_loop()`) are NOT regressions — do not "fix" them inside a fatia.
- **UI specs upkeep:** any UI change updates `docs/smartPIDv2.md` + the relevant `docs/identidade_visual_*.md`; this design-system spec is the web UI authority.
- **GateGuard:** the first `Write` of each new file may be blocked by a PreToolUse hook — present the facts (no importers yet / no API or schema change / instructed to create) and retry the same Write, or the operator may `export ECC_GATEGUARD=off`.

**This fatia's branch (create from `main`):** `feat/web-fatia2-commands-loop-config`

**Dependency:** This fatia depends on Fatia 0+1 having scaffolded `packages/smart_pid_web/` (the `src/` tree, `api/client.ts`, `realtime/useRealtime.ts` + `envelope.ts`, `components/ControllerCard.tsx`, the UI primitives, and `api/generated/openapi.ts`). If those are absent, stop and confirm Fatia 0+1 is merged before proceeding.

---

## Backend: NO CHANGE

**This fatia adds ZERO backend code.** It reuses the existing routers verbatim. Every endpoint below was confirmed against the real source in the worktree:

| UI action | Real endpoint (verbatim) | Real body / params | Auth | Response |
|-----------|--------------------------|--------------------|------|----------|
| Set SP | `POST /commands/setpoint` | `SetpointCommand` body `{ "controller_id": int, "value": float }` | `require_operator` | `CommandResponse { ok, controller_id, detail }` |
| Set mode | `POST /commands/mode` | `ModeCommand` body `{ "controller_id": int, "mode": ControllerMode }` | `require_operator` | `CommandResponse` |
| Manual CO | `POST /commands/output` | `OutputCommand` body `{ "controller_id": int, "value": float }` | `require_operator` | `CommandResponse` |
| Write PID params (GAP-2a) | `POST /commands/tuning` | body (`dict`) `{ "controller_id": int, "kp": float, "ti": float, "td": float }` | `require_operator` | `CommandResponse` |
| Read recommendation | `GET /commands/tuning-recommendations/{controller_id}` | path `controller_id` | `require_operator` | `TuningRecommendationResponse` (see below) |
| Apply tuning (write-back) | `POST /commands/apply-tuning/{controller_id}` | path `controller_id`, **no body** (server reads pending rec from `app.state.tuning_recommendations` and clamps via `clamp_tuning_params`) | `require_supervisor` | `dict` (ok/detail) |
| Enable/disable AI optimizer (GAP-2b) | `POST /commands/optimization` | body `{ "controller_id": int, "enabled": bool }` | JWT (`401` if missing, `404` unknown controller) | `CommandResponse { ok, controller_id, enabled, detail }` |
| AI start | `POST /controllers/{controller_id}/ai/start` | path `controller_id` | `require_operator` | `dict` |
| AI stop | `POST /controllers/{controller_id}/ai/stop` | path `controller_id` | `require_operator` | `dict` |
| AI pause | `POST /controllers/{controller_id}/ai/pause` | path `controller_id` | `require_operator` | `dict` |
| AI status | `GET /controllers/{controller_id}/ai/status` | path `controller_id` | `require_operator` | `AIStatusResponse` (see below) |
| Edit loop config (PID/limits) | `PUT /controllers/{controller_id}` | `ControllerUpdate` body (all fields optional; see below) | (controllers router auth) | `ControllerResponse` |

**Real DTO shapes (verbatim from `smart_pid_domain`):**

- `SetpointCommand` / `OutputCommand`: `{ controller_id: int, value: float }`. **Note the key is `value`, NOT `setpoint`/`output`.**
- `ModeCommand`: `{ controller_id: int, mode: ControllerMode }`.
- `CommandResponse`: `{ ok: bool, controller_id: int | None, detail: str | None }`.
- `AIStatusResponse`: `{ controller_id: int, engine: AIEngine, objective: ControlObjective, speed: ProcessSpeed, current_ki: float, last_gamma: float | None, enabled: bool }`.
- `TuningRecommendationResponse`: `{ controller_id, current_kp, current_ti, current_td, recommended_kp, recommended_ti, recommended_td, reason: str, timestamp: float, status: TuningRecStatus, source: str | None }`.
- `ControllerUpdate` (PATCH/PUT body, all optional): `name, description, execution_mode, scan_rate_s, tss_s, process_speed, pid_params (PIDParamsDTO), pid_structure, integral_type, pv_scale, out_scale, tag_bindings, control_opts, sp_rate_up, sp_rate_dn, out_hi_lim, out_lo_lim, arw_hi_lim, arw_lo_lim, pv_ftime, sp_ftime, low_cut, ff_enable, ff_gain, shed_opt, shed_time_s`.
- `PIDParamsDTO`: `{ gain: float=1.0, reset: float=10.0, rate: float=0.0, alpha: float=0.125, deadband: float=0.0 }`. **The web/domain field names are `gain`(=Kp), `reset`(=Ti), `rate`(=Td), `alpha`(deriv filter), `deadband`. The `STATUS` WS frame and `/commands/tuning` use the `kp/ti/td` aliases.**

**Real enums (verbatim):**
- `ControllerMode`: `OOS, IMAN, LO, MAN, AUTO, CAS, RCAS, ROUT, BYPASS` (9 values: the 8 modes + BYPASS).
- `AIEngine`: `NONE, FUZZY, RL`.
- `PIDStructure`: `ISA, PARALLEL, SERIES`.
- `IntegralType`: `GAIN_KI, TIME_TI`.
- `ControlObjective`: `SP_TRACKING, DISTURBANCE_REJECTION, SURGE_LEVEL`.

**WS frames consumed (contract §4 — CANONICAL `envelope.ts`):**
- `type: 'status'` → `StatusData { pv, sp, co, bkcal_in, bkcal_out, mode, kp, ti, td, integral_val, timestamp }` (last-value Map keyed by `loop_id`). Reflects SP/mode/CO/tuning changes.
- `type: 'ai'` → `AiData { gamma: number, ki: number, strategy: string }` (`ACTION.AI.{id}`, lossless event subscription). Reflects live AI tuning state.

---

## GAP resolutions (investigation in Task 1)

- **GAP-2a (PID params):** there is no `POST /commands/pid/params`. **Resolved → use `POST /commands/tuning`** with body `{ controller_id, kp, ti, td }`. On the current worktree the handler signature is `async def write_tuning(request, body: dict, ...)` — it reads `body.get("controller_id"/"kp"/"ti"/"td")` and writes to OPC-UA. The Fatia 2 design spec states this endpoint is being hardened on branch `fix/backend-security-hardening` (TD-003: typed `TuningCommand` + clamp by `max_tuning_change_pct`). The `{ controller_id, kp, ti, td }` body is forward-compatible with both the raw-dict handler and the typed `TuningCommand`. **No frontend change needed when the hardening lands.** Task 1 records this dependency.
- **GAP-2b ("enable PID"):** the umbrella's "enable PID" does **not** exist as a PID-block enable in `routers/commands`. The real, intended mechanism (per the Fatia 2 design spec) is the **AI optimizer** enable/disable: `POST /commands/optimization` body `{ controller_id, enabled }`, persisting `Controller.optimization_enabled`. **Resolved → GAP-2b option (a): map the inline toggle to `/commands/optimization`, labeled "Enable AI Optimization" (NOT "Enable PID").** Task 1 confirms from backend code whether `/commands/optimization` is present on the implementation branch; if absent on the merge target, the toggle is rendered **disabled with a tooltip** ("requires optimization-toggle backend") rather than invented. No PID-block enable endpoint exists; we do not invent one.

---

## File Structure

```
packages/smart_pid_web/src/
  features/
    loop-config/
      types.ts                  # NEW — TS mirrors of real DTOs + enums (ControllerMode, AIEngine, PIDStructure, PidParamsForm, AiConfigForm)
      validation.ts             # NEW — pure client-side validators mirroring backend constraints
      commandApi.ts             # NEW — typed REST wrappers over api/client.ts for all Fatia 2 endpoints
      useCommands.ts            # NEW — TanStack useMutation hooks (setpoint, mode, output, optimization toggle, tuning)
      useAiControls.ts          # NEW — useMutation (start/stop/pause) + useQuery (ai/status) + tuning-recommendations query
      LoopConfigDialog.tsx      # NEW — collapsible PID / IA / Limites form (design-system §5.6)
      ConfirmApplyTuningDialog.tsx  # NEW — explicit confirmation modal before write-back
      AiPanel.tsx               # NEW — start/stop/pause buttons + live status (engine/objective/ki/enabled)
      CardControls.tsx          # NEW — inline SP/mode/CO/optimizer-toggle row, mounted INTO ControllerCard slot
  components/
    ControllerCard.tsx          # MODIFY (extend canonical) — add ⚙ config button + render <CardControls/> slot; DO NOT redefine
  features/loop-config/__tests__/
    validation.test.ts          # NEW — Vitest
    LoopConfigDialog.test.tsx   # NEW — Vitest
    AiPanel.test.tsx            # NEW — Vitest
    CardControls.test.tsx       # NEW — Vitest
    ConfirmApplyTuning.test.tsx # NEW — Vitest
e2e/
  fatia2-commands.spec.ts       # NEW — Playwright
```

---

### Task 1 — Investigation: confirm real command/AI mechanism (GAP-2a, GAP-2b)

**Files:**
- Read-only: `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/commands.py`, `.../routers/ai.py`, `.../routers/controllers.py`, `packages/smart_pid_domain/src/smart_pid_domain/dtos/commands.py`, `.../dtos/ai.py`, `.../dtos/controllers.py`, `.../enums.py`
- Modify (record findings): this plan file's GAP block if reality differs; `docs/smartPIDv2.md` (note web command surface)

- [ ] **Step 1:** Grep the live backend for the optimization endpoint, the tuning handler shape, and any `pid/enable` route. Run:
  ```bash
  grep -rn 'optimization\|/commands/tuning\|TuningCommand\|optimization_enabled\|pid/enable' \
    packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/ \
    packages/smart_pid_domain/src/smart_pid_domain/dtos/
  ```
  Expected output: confirms `POST /commands/tuning` exists; shows whether `POST /commands/optimization` and `Controller.optimization_enabled` exist on this branch. **Note (from backend surface map):** the only literal `pid/enable` route is `POST /simulator/{controller_id}/pid/enable` (`enable_pid`, `require_supervisor`) — that is a **simulator** control, NOT a production loop-enable. Do not map the production "enable" UI to the simulator route. This is the concrete evidence backing GAP-2b's resolution.

- [ ] **Step 2:** Confirm the AI control verbs and paths. Run:
  ```bash
  grep -n '@router' packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/ai.py
  ```
  Expected output includes: `POST "/{controller_id}/ai/start"`, `POST "/{controller_id}/ai/stop"`, `POST "/{controller_id}/ai/pause"`, `GET "/{controller_id}/ai/status"`, `GET "/{controller_id}/ai/history"`. (Verbs are **POST** for start/stop/pause — not PATCH.)

- [ ] **Step 3:** Record the resolution in this plan (already drafted in the "GAP resolutions" block above): GAP-2a → `/commands/tuning` `{controller_id,kp,ti,td}`; GAP-2b → `/commands/optimization` `{controller_id,enabled}` labeled "Enable AI Optimization". If `/commands/optimization` is **absent** on the merge target, mark the toggle disabled-with-tooltip and add a `> **GAP-2b (deferred):**` note. Do not invent endpoints.

- [ ] **Step 4 (Commit):**
  ```bash
  git checkout -b feat/web-fatia2-commands-loop-config main
  git add docs/superpowers/plans/2026-06-18-web-fatia2-commands-loop-config.md docs/smartPIDv2.md
  git commit -m "docs(web): record fatia 2 command surface investigation (GAP-2a/2b)"
  ```
  Expected: branch created from `main`; commit recorded.

---

### Task 2 — Types + validation (pure, fully unit-tested)

**Files:**
- Create: `src/features/loop-config/types.ts`
- Create: `src/features/loop-config/validation.ts`
- Test: `src/features/loop-config/__tests__/validation.test.ts`

**Interfaces:**
```ts
// types.ts
export type ControllerMode =
  | 'OOS' | 'IMAN' | 'LO' | 'MAN' | 'AUTO' | 'CAS' | 'RCAS' | 'ROUT' | 'BYPASS';
export const CONTROLLER_MODES: ControllerMode[] =
  ['OOS','IMAN','LO','MAN','AUTO','CAS','RCAS','ROUT','BYPASS'];
export type AiEngine = 'NONE' | 'FUZZY' | 'RL';
export type PidStructure = 'ISA' | 'PARALLEL' | 'SERIES';

export interface PidParamsForm { gain: number; reset: number; rate: number; alpha: number; deadband: number; }
export interface LimitsForm {
  out_hi_lim: number; out_lo_lim: number; arw_hi_lim: number; arw_lo_lim: number;
  pv_ftime: number; sp_ftime: number; sp_rate_up: number; sp_rate_dn: number;
}
export interface AiConfigForm { engine: AiEngine; objective: string; }

export interface FieldErrors { [field: string]: string | undefined; }
```
```ts
// validation.ts
export function validatePidParams(p: PidParamsForm): FieldErrors;
export function validateLimits(l: LimitsForm): FieldErrors;
export function validateSetpoint(v: number): string | undefined;
export function validateOutput(v: number): string | undefined;
export function hasErrors(e: FieldErrors): boolean;
```

- [ ] **Step 1: Write the failing test.** Create `src/features/loop-config/__tests__/validation.test.ts`:
  ```ts
  import { describe, it, expect } from 'vitest';
  import { validatePidParams, validateLimits, validateSetpoint, hasErrors } from '../validation';

  describe('validatePidParams', () => {
    it('accepts physically valid params', () => {
      const e = validatePidParams({ gain: 1.2, reset: 10, rate: 0.5, alpha: 0.125, deadband: 0 });
      expect(hasErrors(e)).toBe(false);
    });
    it('rejects non-positive reset (Ti must be > 0)', () => {
      const e = validatePidParams({ gain: 1, reset: 0, rate: 0, alpha: 0.125, deadband: 0 });
      expect(e.reset).toMatch(/greater than 0/i);
    });
    it('rejects negative gain magnitude rule and NaN', () => {
      const e = validatePidParams({ gain: Number.NaN, reset: 10, rate: -1, alpha: 2, deadband: -1 });
      expect(e.gain).toBeDefined();
      expect(e.rate).toMatch(/0 or greater/i);
      expect(e.alpha).toMatch(/between 0 and 1/i);
      expect(e.deadband).toBeDefined();
    });
  });

  describe('validateLimits', () => {
    it('rejects out_lo >= out_hi', () => {
      const e = validateLimits({ out_hi_lim: 10, out_lo_lim: 20, arw_hi_lim: 100, arw_lo_lim: 0, pv_ftime: 0, sp_ftime: 0, sp_rate_up: 0, sp_rate_dn: 0 });
      expect(e.out_lo_lim).toMatch(/below/i);
    });
    it('rejects negative filter times', () => {
      const e = validateLimits({ out_hi_lim: 100, out_lo_lim: 0, arw_hi_lim: 100, arw_lo_lim: 0, pv_ftime: -1, sp_ftime: 0, sp_rate_up: 0, sp_rate_dn: 0 });
      expect(e.pv_ftime).toBeDefined();
    });
  });

  describe('validateSetpoint', () => {
    it('rejects NaN', () => { expect(validateSetpoint(Number.NaN)).toBeDefined(); });
    it('accepts finite', () => { expect(validateSetpoint(42)).toBeUndefined(); });
  });
  ```

- [ ] **Step 2: Run red.** `cd packages/smart_pid_web && npm run test -- validation`
  Expected: FAIL — `Cannot find module '../validation'`.

- [ ] **Step 3: Implement `types.ts` then `validation.ts`.** Create `src/features/loop-config/types.ts` with the interfaces above. Create `src/features/loop-config/validation.ts`:
  ```ts
  import type { PidParamsForm, LimitsForm, FieldErrors } from './types';

  const finite = (n: number) => Number.isFinite(n);

  export function validatePidParams(p: PidParamsForm): FieldErrors {
    const e: FieldErrors = {};
    if (!finite(p.gain)) e.gain = 'Gain (Kp) must be a number';
    if (!finite(p.reset) || p.reset <= 0) e.reset = 'Reset (Ti) must be greater than 0';
    if (!finite(p.rate) || p.rate < 0) e.rate = 'Rate (Td) must be 0 or greater';
    if (!finite(p.alpha) || p.alpha < 0 || p.alpha > 1) e.alpha = 'Derivative filter (alpha) must be between 0 and 1';
    if (!finite(p.deadband) || p.deadband < 0) e.deadband = 'Deadband must be 0 or greater';
    return e;
  }

  export function validateLimits(l: LimitsForm): FieldErrors {
    const e: FieldErrors = {};
    if (!finite(l.out_hi_lim)) e.out_hi_lim = 'Output high limit must be a number';
    if (!finite(l.out_lo_lim)) e.out_lo_lim = 'Output low limit must be a number';
    if (finite(l.out_hi_lim) && finite(l.out_lo_lim) && l.out_lo_lim >= l.out_hi_lim)
      e.out_lo_lim = 'Output low limit must be below the high limit';
    if (finite(l.arw_hi_lim) && finite(l.arw_lo_lim) && l.arw_lo_lim >= l.arw_hi_lim)
      e.arw_lo_lim = 'ARW low limit must be below the ARW high limit';
    for (const k of ['pv_ftime', 'sp_ftime', 'sp_rate_up', 'sp_rate_dn'] as const) {
      const v = l[k];
      if (!finite(v) || v < 0) e[k] = 'Must be 0 or greater';
    }
    return e;
  }

  export function validateSetpoint(v: number): string | undefined {
    return Number.isFinite(v) ? undefined : 'Setpoint must be a number';
  }
  export function validateOutput(v: number): string | undefined {
    if (!Number.isFinite(v)) return 'Output must be a number';
    if (v < 0 || v > 100) return 'Output must be between 0 and 100 %';
    return undefined;
  }
  export function hasErrors(e: FieldErrors): boolean {
    return Object.values(e).some((m) => m !== undefined);
  }
  ```

- [ ] **Step 4: Run green.** `npm run test -- validation` → Expected: all pass.

- [ ] **Step 5 (Commit):** `git add src/features/loop-config/types.ts src/features/loop-config/validation.ts src/features/loop-config/__tests__/validation.test.ts && git commit -m "feat(web): fatia 2 loop-config types and client-side validation"`

---

### Task 3 — Command API wrappers + mutation hooks

**Files:**
- Create: `src/features/loop-config/commandApi.ts`
- Create: `src/features/loop-config/useCommands.ts`
- Test: extend later in component tests (these are thin wrappers over `api/client.ts`; covered behaviorally in Tasks 5–7). Add a focused contract test for body shapes.
- Test: `src/features/loop-config/__tests__/commandApi.test.ts`

**Interfaces:**
```ts
// commandApi.ts — every call uses the canonical apiPost/apiPut/apiGet from ../../api/client
export interface CommandResponse { ok: boolean; controller_id: number | null; detail: string | null; }
export interface AiStatus { controller_id: number; engine: AiEngine; objective: string; speed: string; current_ki: number; last_gamma: number | null; enabled: boolean; }
export interface TuningRecommendation { controller_id: number; current_kp: number; current_ti: number; current_td: number; recommended_kp: number; recommended_ti: number; recommended_td: number; reason: string; timestamp: number; status: string; source: string | null; }

export const setSetpoint = (controller_id: number, value: number) =>
  apiPost<CommandResponse>('/commands/setpoint', { controller_id, value });
export const setMode = (controller_id: number, mode: ControllerMode) =>
  apiPost<CommandResponse>('/commands/mode', { controller_id, mode });
export const setOutput = (controller_id: number, value: number) =>
  apiPost<CommandResponse>('/commands/output', { controller_id, value });
export const setOptimization = (controller_id: number, enabled: boolean) =>
  apiPost<CommandResponse>('/commands/optimization', { controller_id, enabled });   // GAP-2b
export const writeTuning = (controller_id: number, kp: number, ti: number, td: number) =>
  apiPost<CommandResponse>('/commands/tuning', { controller_id, kp, ti, td });        // GAP-2a
export const getTuningRecommendation = (controller_id: number) =>
  apiGet<TuningRecommendation>(`/commands/tuning-recommendations/${controller_id}`);
export const applyTuning = (controller_id: number) =>
  apiPost<{ ok: boolean; detail?: string }>(`/commands/apply-tuning/${controller_id}`, {}); // no body; server clamps
export const updateController = (controller_id: number, patch: Record<string, unknown>) =>
  apiPut(`/controllers/${controller_id}`, patch);
```

- [ ] **Step 1: Write the failing test.** Create `src/features/loop-config/__tests__/commandApi.test.ts` that mocks `../../api/client` and asserts each wrapper hits the right path + body:
  ```ts
  import { describe, it, expect, vi, beforeEach } from 'vitest';

  const apiPost = vi.fn(async () => ({ ok: true, controller_id: 1, detail: 'x' }));
  const apiGet = vi.fn(async () => ({}));
  const apiPut = vi.fn(async () => ({}));
  vi.mock('../../../api/client', () => ({ apiPost, apiGet, apiPut, apiDelete: vi.fn() }));

  beforeEach(() => { apiPost.mockClear(); apiGet.mockClear(); apiPut.mockClear(); });

  describe('commandApi body/path shapes', () => {
    it('setSetpoint posts {controller_id,value}', async () => {
      const { setSetpoint } = await import('../commandApi');
      await setSetpoint(7, 55.5);
      expect(apiPost).toHaveBeenCalledWith('/commands/setpoint', { controller_id: 7, value: 55.5 });
    });
    it('setMode posts {controller_id,mode}', async () => {
      const { setMode } = await import('../commandApi');
      await setMode(7, 'AUTO');
      expect(apiPost).toHaveBeenCalledWith('/commands/mode', { controller_id: 7, mode: 'AUTO' });
    });
    it('setOptimization posts {controller_id,enabled} (GAP-2b)', async () => {
      const { setOptimization } = await import('../commandApi');
      await setOptimization(7, true);
      expect(apiPost).toHaveBeenCalledWith('/commands/optimization', { controller_id: 7, enabled: true });
    });
    it('writeTuning posts {controller_id,kp,ti,td} (GAP-2a)', async () => {
      const { writeTuning } = await import('../commandApi');
      await writeTuning(7, 1.2, 10, 0.5);
      expect(apiPost).toHaveBeenCalledWith('/commands/tuning', { controller_id: 7, kp: 1.2, ti: 10, td: 0.5 });
    });
    it('applyTuning posts to path with no meaningful body', async () => {
      const { applyTuning } = await import('../commandApi');
      await applyTuning(7);
      expect(apiPost).toHaveBeenCalledWith('/commands/apply-tuning/7', {});
    });
  });
  ```

- [ ] **Step 2: Run red.** `npm run test -- commandApi` → Expected FAIL (`Cannot find module '../commandApi'`).

- [ ] **Step 3: Implement `commandApi.ts`** importing `{ apiGet, apiPost, apiPut }` from `../../api/client` and the types from `./types`. Implement exactly the wrappers above.

- [ ] **Step 4: Implement `useCommands.ts`** — TanStack `useMutation` hooks, each calling its wrapper and `invalidateQueries(['controllers'])` + `['ai','status', controller_id]` on success; surface `ApiError.detail` via the shared toast. Interface:
  ```ts
  export function useSetpointMutation(): UseMutationResult<CommandResponse, ApiError, { id: number; value: number }>;
  export function useModeMutation(): UseMutationResult<CommandResponse, ApiError, { id: number; mode: ControllerMode }>;
  export function useOutputMutation(): UseMutationResult<CommandResponse, ApiError, { id: number; value: number }>;
  export function useOptimizationMutation(): UseMutationResult<CommandResponse, ApiError, { id: number; enabled: boolean }>;
  export function useWriteTuningMutation(): UseMutationResult<CommandResponse, ApiError, { id: number; kp: number; ti: number; td: number }>;
  export function useUpdateControllerMutation(): UseMutationResult<unknown, ApiError, { id: number; patch: Record<string, unknown> }>;
  ```

- [ ] **Step 5: Run green.** `npm run test -- commandApi` → Expected pass.

- [ ] **Step 6 (Commit):** `git add src/features/loop-config/commandApi.ts src/features/loop-config/useCommands.ts src/features/loop-config/__tests__/commandApi.test.ts && git commit -m "feat(web): fatia 2 command REST wrappers and mutation hooks"`

---

### Task 4 — AI controls hooks (start/stop/pause/status + recommendation)

**Files:**
- Create: `src/features/loop-config/useAiControls.ts`
- Test: `src/features/loop-config/__tests__/useAiControls.test.tsx`

**Interfaces:**
```ts
export function useAiStatus(controllerId: number): UseQueryResult<AiStatus, ApiError>;     // GET /controllers/{id}/ai/status
export function useTuningRecommendation(controllerId: number): UseQueryResult<TuningRecommendation, ApiError>;
export function useAiAction(): UseMutationResult<unknown, ApiError, { id: number; action: 'start' | 'stop' | 'pause' }>;
// action → POST /controllers/{id}/ai/{action}; onSuccess invalidates ['ai','status',id]
```

- [ ] **Step 1: Write the failing test.** Render `useAiAction` inside a `QueryClientProvider`, mock `../../api/client` `apiPost`, dispatch `{ id: 3, action: 'start' }`, assert `apiPost` called with `'/controllers/3/ai/start'`. Repeat for `'stop'`/`'pause'`. Assert `useAiStatus` calls `apiGet('/controllers/3/ai/status')`.

- [ ] **Step 2: Run red.** `npm run test -- useAiControls` → Expected FAIL.

- [ ] **Step 3: Implement `useAiControls.ts`** with the three hooks. `useAiAction` mutation: `apiPost(`/controllers/${id}/ai/${action}`, {})`. `useAiStatus`: `useQuery(['ai','status', id], () => apiGet(...))`. `useTuningRecommendation`: `useQuery(['tuning','rec', id], ...)`, `retry: false` (404 = no pending rec is expected).

- [ ] **Step 4: Run green.** `npm run test -- useAiControls` → Expected pass.

- [ ] **Step 5 (Commit):** `git add src/features/loop-config/useAiControls.ts src/features/loop-config/__tests__/useAiControls.test.tsx && git commit -m "feat(web): fatia 2 AI control hooks (start/stop/pause/status, recommendation)"`

---

### Task 5 — `CardControls` inline row + extend canonical `ControllerCard`

**Files:**
- Create: `src/features/loop-config/CardControls.tsx`
- Modify: `src/components/ControllerCard.tsx` (extend — add ⚙ button + controls slot; **do not redefine the card**)
- Test: `src/features/loop-config/__tests__/CardControls.test.tsx`

**Interfaces:**
```ts
// CardControls.tsx
export interface CardControlsProps {
  controllerId: number;
  mode: ControllerMode;        // from live StatusData.mode
  optimizationEnabled: boolean;// from controllers query (Controller.optimization_enabled)
  onOpenConfig: () => void;
}
// Renders: SP numeric input + "Set" button (useSetpointMutation),
//          mode <select> over CONTROLLER_MODES (useModeMutation),
//          manual CO input (enabled only when mode === 'MAN') (useOutputMutation),
//          "Enable AI Optimization" toggle (useOptimizationMutation)  // GAP-2b — labeled optimizer, NOT PID
```
ControllerCard extension: add a `⚙` config button in the header (design-system §5.2: "Botão ⚙ (config, Fatia 2) à direita") wired to `onOpenConfig`, and render `{controls}` as an optional `ReactNode` slot prop below the body. Keep the existing card contract (width 280px, alarm strip, AnalogBar body, footer Mode + AI strategy chip) untouched.

- [ ] **Step 1: Write the failing test.** Create `CardControls.test.tsx` (render inside `QueryClientProvider`, mock the mutation hooks):
  - Renders a mode `<select>` whose options equal the 9 `CONTROLLER_MODES`.
  - Typing `60` in SP and clicking "Set" calls the setpoint mutation with `{ id, value: 60 }`.
  - Manual CO input is **disabled** when `mode !== 'MAN'` and **enabled** when `mode === 'MAN'`.
  - Toggling "Enable AI Optimization" calls the optimization mutation with `{ id, enabled: !optimizationEnabled }`.
  - The toggle label text contains "Optimization" (NOT "Enable PID") — guards GAP-2b semantics.

- [ ] **Step 2: Run red.** `npm run test -- CardControls` → Expected FAIL.

- [ ] **Step 3: Implement `CardControls.tsx`** using `useCommands` hooks + `validateSetpoint`/`validateOutput`; show inline error text under the field on invalid input; disable submit while mutation `isPending`. Use token classes from `tokens.css` (mono inputs, `--field-bg`, `--focus-ring`).

- [ ] **Step 4: Extend `ControllerCard.tsx`** — add `onOpenConfig?: () => void` and `controls?: React.ReactNode` props; render the `⚙` button and the controls slot. Keep all existing props/markup. Add a minimal test in the existing card test file asserting the ⚙ button calls `onOpenConfig` (do not rewrite existing card tests).

- [ ] **Step 5: Run green.** `npm run test -- CardControls ControllerCard` → Expected pass.

- [ ] **Step 6 (Commit):** `git add src/features/loop-config/CardControls.tsx src/components/ControllerCard.tsx src/features/loop-config/__tests__/CardControls.test.tsx && git commit -m "feat(web): fatia 2 inline card controls (SP/mode/CO/optimizer toggle) and card config button"`

---

### Task 6 — `LoopConfigDialog` (PID / IA / Limites)

**Files:**
- Create: `src/features/loop-config/LoopConfigDialog.tsx`
- Test: `src/features/loop-config/__tests__/LoopConfigDialog.test.tsx`

**Interfaces:**
```ts
export interface LoopConfigDialogProps {
  controllerId: number;
  open: boolean;
  onClose: () => void;
  initial: { pid: PidParamsForm; limits: LimitsForm; pidStructure: PidStructure; ai: AiConfigForm };
}
// Built on the canonical <Dialog> primitive (design-system §5.6): centered modal 520–680px,
// header shows TAG, body = collapsible sections PID / Otimização IA / Limites, footer [Cancelar] [Salvar].
// "Salvar" = local config write → useUpdateControllerMutation (PUT /controllers/{id}) with
//   { pid_params:{gain,reset,rate,alpha,deadband}, pid_structure, out_hi_lim, out_lo_lim,
//     arw_hi_lim, arw_lo_lim, pv_ftime, sp_ftime } — distinct from the physical apply-tuning write.
// IA section: radio NONE/FUZZY/RL (progressive disclosure — reveals only the chosen engine's params).
```

- [ ] **Step 1: Write the failing test.** `LoopConfigDialog.test.tsx`:
  - When `open`, renders three section headers: PID, Otimização IA, Limites.
  - PID section has Kp/Ti/Td/structure/alpha/deadband fields bound to `initial.pid`.
  - Entering `reset=0` shows the inline validation message "must be greater than 0" and "Salvar" is disabled.
  - Selecting engine radio `FUZZY` reveals fuzzy-only params and hides RL-only params (and vice-versa).
  - Clicking "Salvar" with valid data calls `updateController` with `pid_params:{gain,reset,rate,alpha,deadband}` + limits keys.
  - Clicking "Cancelar" calls `onClose` without mutating.

- [ ] **Step 2: Run red.** `npm run test -- LoopConfigDialog` → Expected FAIL.

- [ ] **Step 3: Implement `LoopConfigDialog.tsx`** using the canonical `<Dialog>`, `<Button>`, and field/select primitives; collapsible sections; `validatePidParams`/`validateLimits` for inline errors (text under field, never color-only — design-system §5.6); disable "Salvar" when `hasErrors`. AI engine radio NONE/FUZZY/RL drives progressive disclosure.
  > **GAP note (AI engine persistence):** The real `ControllerCreate`/`ControllerUpdate` DTOs do **not** carry an `ai_config` field, and no `/ai/config` route exists on this branch — so the engine selection cannot be persisted via `PUT /controllers/{id}` today. Render the IA section but mark engine-change persistence as **disabled with a tooltip** ("AI engine selection persistence pending backend `ai_config` support") until the backend exposes it. The live engine is still **readable** via `GET /controllers/{id}/ai/status`. This is a noted GAP, not an invented endpoint.

- [ ] **Step 4: Run green.** `npm run test -- LoopConfigDialog` → Expected pass.

- [ ] **Step 5 (Commit):** `git add src/features/loop-config/LoopConfigDialog.tsx src/features/loop-config/__tests__/LoopConfigDialog.test.tsx && git commit -m "feat(web): fatia 2 LoopConfigDialog (PID/IA/Limites) with inline validation"`

---

### Task 7 — Apply-tuning confirmation guard + AI panel

**Files:**
- Create: `src/features/loop-config/ConfirmApplyTuningDialog.tsx`
- Create: `src/features/loop-config/AiPanel.tsx`
- Test: `src/features/loop-config/__tests__/ConfirmApplyTuning.test.tsx`
- Test: `src/features/loop-config/__tests__/AiPanel.test.tsx`

**Interfaces:**
```ts
export interface ConfirmApplyTuningDialogProps {
  controllerId: number;
  recommendation: TuningRecommendation;   // shows current vs recommended Kp/Ti/Td + reason
  open: boolean;
  onConfirm: () => void;                   // → applyTuning(controllerId) (POST /commands/apply-tuning/{id})
  onCancel: () => void;
}
export interface AiPanelProps { controllerId: number; }
// AiPanel: live useAiStatus → shows engine/objective/current_ki/last_gamma/enabled;
//          live AiData via useRealtime subscribe('ai') filtered by loop_id → strategy/gamma/ki;
//          buttons Start / Stop / Pause → useAiAction; apply-tuning button (strong border) opens ConfirmApplyTuningDialog.
```

- [ ] **Step 1: Write the failing tests.**
  - `ConfirmApplyTuning.test.tsx`: the dialog renders current→recommended Kp/Ti/Td and the `reason`; `applyTuning` is **NOT** called on render; only after clicking "Confirm Write" does `onConfirm` fire; "Cancel" closes without calling `onConfirm`. **This is the apply-tuning confirmation guard.**
  - `AiPanel.test.tsx`: Start button calls `useAiAction` with `action: 'start'`; Stop → `'stop'`; Pause → `'pause'`. Status fields render from a mocked `AiStatus`. An incoming mocked `ai` WS frame (`{ gamma, ki, strategy }`) for the matching `loop_id` updates the displayed strategy; a frame for a different `loop_id` does not.

- [ ] **Step 2: Run red.** `npm run test -- ConfirmApplyTuning AiPanel` → Expected FAIL.

- [ ] **Step 3: Implement `ConfirmApplyTuningDialog.tsx`** (canonical `<Dialog>`, strong-border confirm `<Button>`, explicit "you are writing Kp=… Ti=… Td=… to controller TAG"). Implement `AiPanel.tsx` consuming `useAiStatus`, `useTuningRecommendation`, `useAiAction`, and `useRealtime().subscribe('ai', ...)` (filter `env.loop_id === controllerId`). The apply-tuning button is **disabled** unless a `recommendation` with `status` pending exists; clicking opens the confirm dialog; confirm → `applyTuning`.

- [ ] **Step 4: Run green.** `npm run test -- ConfirmApplyTuning AiPanel` → Expected pass.

- [ ] **Step 5 (Commit):** `git add src/features/loop-config/ConfirmApplyTuningDialog.tsx src/features/loop-config/AiPanel.tsx src/features/loop-config/__tests__/ConfirmApplyTuning.test.tsx src/features/loop-config/__tests__/AiPanel.test.tsx && git commit -m "feat(web): fatia 2 AI panel and apply-tuning confirmation guard"`

---

### Task 8 — Wire into dashboard + Playwright e2e + specs

**Files:**
- Modify: the dashboard page (Fatia 0+1) to pass `onOpenConfig`/`controls`/`AiPanel` into each `ControllerCard` and host `LoopConfigDialog`/`ConfirmApplyTuningDialog` state.
- Create: `e2e/fatia2-commands.spec.ts`
- Modify: `docs/smartPIDv2.md`, `docs/identidade_visual_ISA101.md` (UI specs upkeep — constraint §9)
- Modify: `docs/superpowers/plans/_web-hmi-INDEX.md` (add reference to this Fatia 2 plan)

- [ ] **Step 1: Wire the dashboard.** Mount `<CardControls/>` into each card's `controls` slot; open `LoopConfigDialog` from the ⚙ button; render `AiPanel` per selected controller. Add/extend a Vitest integration test asserting the ⚙ opens the dialog and the dashboard passes `controllerId`/live `mode` through.

- [ ] **Step 2: Run red→green on the wiring test.** `npm run test -- dashboard` → Expected pass after wiring.

- [ ] **Step 3: Write the Playwright e2e.** `e2e/fatia2-commands.spec.ts` (against dev server + a running backend, login via Fatia 0+1 flow):
  - Change SP via card → assert the live `status` PV/SP region reflects the new SP (poll the card's SP readout).
  - Change mode via card select → assert the footer `Mode:` updates from the `status` frame.
  - Click apply-tuning → assert nothing is written until the confirmation dialog "Confirm Write" is clicked (network panel shows `POST /commands/apply-tuning/{id}` ONLY after confirm).
  - AI Start → assert status/`ai` reflects started; Pause → reflects paused; Stop → reflects stopped.
  Use deterministic waits (`expect(locator).toHaveText(...)`), not timeouts.

- [ ] **Step 4: Run e2e.** `npm run test:e2e -- fatia2-commands` → Expected: all assertions pass.

- [ ] **Step 5: Full suite + lint + build + types.**
  ```bash
  cd packages/smart_pid_web && npm run test && npm run build
  cd ../.. && uv run --with ruff ruff check . && uv run mypy packages/
  ```
  Expected: Vitest all green; Vite build succeeds; ruff clean; mypy error count ≤ baseline (~540, must not increase — no backend changes this fatia).

- [ ] **Step 6: Update specs + INDEX.** Edit `docs/smartPIDv2.md` and `docs/identidade_visual_ISA101.md` to describe the new web command controls + LoopConfigDialog. Add a row for this plan in `docs/superpowers/plans/_web-hmi-INDEX.md`.

- [ ] **Step 7 (Commit):** `git add -A && git commit -m "feat(web): wire fatia 2 controls into dashboard, add e2e, update specs and INDEX"`

---

## Self-Review

- [ ] **Backend untouched:** No file under `packages/smart_pid_core/` or `packages/smart_pid_domain/` was modified. All endpoints consumed exist in the real routers (confirmed Task 1). mypy backend baseline unchanged.
- [ ] **Canonical reuse, not redefinition:** `ControllerCard.tsx` was *extended* (⚙ + slot), never re-created. `api/client.ts`, `useRealtime`, `envelope.ts` types, and UI primitives (`Dialog`/`Button`/fields) are imported from Fatia 0+1 — not duplicated.
- [ ] **Real bodies/paths:** setpoint/output use key `value` (not `setpoint`/`output`); `controller_id` is in the BODY for setpoint/mode/output/tuning/optimization and in the PATH for apply-tuning/tuning-recommendations/ai-actions. AI start/stop/pause are **POST**. Modes list = the real 9 `ControllerMode` values incl. BYPASS.
- [ ] **GAP-2a resolved:** PID write goes through `POST /commands/tuning` `{controller_id,kp,ti,td}` (forward-compatible with the typed/clamped `TuningCommand` landing on `fix/backend-security-hardening`). No invented `/commands/pid/params`.
- [ ] **GAP-2b resolved:** the inline toggle maps to `POST /commands/optimization` `{controller_id,enabled}` and is **labeled "Enable AI Optimization"** (optimizer, not PID-block). If the endpoint is absent on the merge target, the control is rendered disabled-with-tooltip — never invented. Task 1 confirms presence.
- [ ] **AI engine persistence GAP noted:** `ai_config` is not a field on `ControllerCreate`/`ControllerUpdate` and no `/ai/config` route exists — engine-change persistence is rendered disabled-with-tooltip (read-only via `ai/status`), documented as a deferred GAP. No endpoint invented.
- [ ] **Apply-tuning safety:** `POST /commands/apply-tuning/{id}` fires only after the explicit `ConfirmApplyTuningDialog` "Confirm Write" — proven by Vitest (`ConfirmApplyTuning.test.tsx`) and Playwright (network-panel assertion). Backend additionally requires `require_supervisor` and clamps server-side.
- [ ] **WS consumption:** `status` reflects SP/mode/CO/tuning; `ai` (`AiData {gamma,ki,strategy}`) reflects tuning state via `useRealtime().subscribe('ai')` filtered by `loop_id`.
- [ ] **TDD honored:** every task is red → green → commit, bite-sized, `- [ ]` steps, conventional commits with no attribution trailer.
- [ ] **Acceptance met:** SP/mode/params change reflects in backend + live `status`; apply-tuning writes only after confirmation; AI start/stop/pause changes reported state — all covered by Vitest + Playwright.
- [ ] **Branch + specs:** work is on `feat/web-fatia2-commands-loop-config` from `main`; `feat/windows-installers` untouched; UI specs + INDEX updated.
