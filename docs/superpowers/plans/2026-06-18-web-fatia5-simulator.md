# Fatia 5: Simulator — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** Build the Web HMI Simulator page (digital-twin control surface) in `packages/smart_pid_web/`: a process-preset selector, dynamics parameter sliders, disturbance inject/remove, twin output + mode control, start/stop, and auto-disturbance / auto-SP toggles — with a persistent **SIMULATION MODE** banner and a live `RealtimeTrend` of the twin response (via `useRealtime`). The backend `routers/simulator` is reused **without modification**.

**Architecture:** A single route `/simulator` → `src/pages/SimulatorPage.tsx`, composed from a feature folder `src/features/simulator/`. The page is split: a left **control panel** (preset, sliders, disturbance, output/mode, auto-toggles, start/stop) and a right **live trend** of the twin. All REST calls go through the canonical `apiClient` (`src/api/client.ts`, `apiGet/apiPost/apiPut/apiDelete` prefixing `/api`); typed bodies come from the generated OpenAPI types. Live twin response (`pv`/`sp`/`co`) arrives via the canonical `useRealtime` hook reading the coalesced `lastStatus` map (keyed by `loop_id`/controller id). Mutations use TanStack Query `useMutation`; the simulator config snapshot is read via `useQuery` on `GET /api/simulator/status`. The page reuses the existing `RealtimeTrend.tsx` component for the twin chart. No new endpoints, no backend change.

**Tech Stack:** React 18 + Vite 5 + TypeScript 5 (strict); TanStack Query v5; native `WebSocket` via `useRealtime`; uPlot via `RealtimeTrend`; Vitest + @testing-library/react (unit/component); Playwright (e2e); `openapi-typescript` for API types. Tooling: `npm` inside `packages/smart_pid_web/`.

## Global Constraints

The following are inherited verbatim from `_web-hmi-foundation-contract.md` §9 ("Global constraints — every task inherits these"):

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

**Branch for this fatia:** `feat/web-fatia5-simulator` (new branch from `main`).

**Fatia-specific overrides (from contract §1 + Fatia 5 spec):**

- **Mono-user / NO RBAC.** The backend `routers/simulator` source declares `Depends(require_supervisor)`, but the target system is single-admin (`require_authenticated_admin`, contract §1 TD-007). Plans assume the single-admin model: every simulator call requires a valid admin JWT; **negative tests assert `401` when unauthenticated**, NOT `403` by role. Do not add role-gating to the UI.
- **Backend: NO change.** This fatia reuses `routers/simulator` exactly as-is and adds **zero** backend endpoints, models, or migrations. The only backend precondition is the OpenAPI `response_model` audit (Task 1).
- **Dependencies:** requires Fatia 0+1 (scaffold, `apiClient`, `useRealtime`, `RealtimeProvider`, `RealtimeTrend`, theme tokens, `AppShell`/route table). Recommended after Fatia 2 (loop/output controls), but not a hard blocker.

## File Structure

New files under `packages/smart_pid_web/`:

```
src/
  features/
    simulator/
      api.ts                       # typed thin wrappers over apiClient for every simulator route
      types.ts                     # re-exports + view-model types derived from generated OpenAPI types
      useSimulatorStatus.ts        # useQuery(GET /simulator/status) + useRealtime twin status merge
      useSimulatorMutations.ts     # useMutation hooks: preset, params, disturbance, clear, co, mode, auto-sp, auto-dist, start/stop
      SimulationModeBanner.tsx     # persistent "MODO SIMULAÇÃO — digital twin" diag-strip banner
      PresetSelector.tsx           # segmented/dropdown FLOW|PRESSURE|LEVEL|TEMPERATURE|CUSTOM
      DynamicsSliders.tsx          # gain / dead_time (L) / tau1 / tau2 sliders w/ mono readout
      DisturbanceControls.tsx      # type(step|noise) + amplitude → [Inject] [Remove]
      TwinOutputModeControl.tsx    # CO (0-100) entry + MAN|AUTO mode toggle
      AutoToggles.tsx              # auto-SP (+ sp_min/sp_max) and auto-disturbance (+ max_amplitude) toggles
      StartStopControl.tsx         # [Start | Stop] + running indicator
      SimulatorControlPanel.tsx    # composes the left panel; owns the selected controller id
  pages/
    SimulatorPage.tsx              # route component: banner + (control panel | RealtimeTrend)
src/features/simulator/__tests__/
  PresetSelector.test.tsx
  DynamicsSliders.test.tsx
  DisturbanceControls.test.tsx
  AutoToggles.test.tsx
  TwinOutputModeControl.test.tsx
  SimulatorControlPanel.test.tsx
e2e/
  simulator.spec.ts                # Playwright: apply preset → trend response; inject disturbance → step in trend
```

Modified files:

```
src/App.tsx                        # add <Route path="/simulator" .../> inside <RequireAuth>
src/components/shell/NavRail.tsx   # add Simulator nav entry
docs/smartPIDv2.md                 # document web Simulator page
docs/identidade_visual_ISA101.md   # note SIMULATION MODE banner semantics
```

**Canonical names consumed (do NOT redefine):** `apiGet/apiPost/apiPut/apiDelete`, `ApiError` (`src/api/client.ts`); generated types in `src/api/generated/openapi.ts`; `useRealtime`, `StatusData`, `RealtimeEnvelope` (`src/realtime/`); `RealtimeTrend` (`src/components/RealtimeTrend.tsx`); theme token `--alarm-diag` (`src/theme/tokens.css`).

**Backend route facts (confirmed from `routers/simulator.py`, registered `prefix="/simulator"` → client path `/api/simulator/...`):**

| Action | Method + path | Request body (DTO) | Response |
|---|---|---|---|
| Start | `POST /simulator/start` | _(none)_ | `CommandResponse` |
| Stop | `POST /simulator/stop` | _(none)_ | `CommandResponse` |
| Status (poll) | `GET /simulator/status` | _(none)_ | `SimulatorStatusResponse` `{enabled, running, controllers: {int: ControllerSimStatus}}` |
| Preset | `POST /simulator/preset` | `SimulatorPresetRequest` `{controller_id:int, preset: "FLOW"|"PRESSURE"|"LEVEL"|"TEMPERATURE"|"CUSTOM"}` | `CommandResponse` |
| Dynamics params | `PUT /simulator/parameters` | `SimulatorParametersRequest` `{controller_id:int, gain:float, tau1:float, tau2:float|null, dead_time:float}` | `CommandResponse` |
| Inject disturbance | `POST /simulator/disturbance` | `SimulatorDisturbanceRequest` `{controller_id:int, type:"step"|"noise", amplitude:float}` | `CommandResponse` |
| Remove disturbance | `DELETE /simulator/disturbance/{controller_id}` | _(path only)_ | `CommandResponse` |
| Twin output (CO) | `POST /simulator/{controller_id}/co` | `SimulatorPIDSPRequest` `{controller_id:int, sp:float (0-100)}` (reused shape; `sp` carries CO%) | `CommandResponse` |
| Twin PID mode | `POST /simulator/{controller_id}/pid/mode` | `SimulatorPIDModeRequest` `{controller_id:int, mode:"MAN"|"AUTO"}` | `CommandResponse` |
| Auto-SP | `PUT /simulator/{controller_id}/auto-sp` | `AutoSPRequest` `{enabled:bool, sp_min_pct:float=30, sp_max_pct:float=70}` | `ControllerSimStatus` |
| Auto-disturbance | `PUT /simulator/{controller_id}/auto-disturbance` | `AutoDisturbanceRequest` `{enabled:bool, max_amplitude_pct:float=10}` | `ControllerSimStatus` |

> **NOTE (route shape — do not invent):** output is `POST /simulator/{controller_id}/co` and mode is `POST /simulator/{controller_id}/pid/mode` — NOT `/simulator/output` or `/simulator/mode`. The CO endpoint reuses `SimulatorPIDSPRequest` (field `sp` is the CO%, 0–100). Live twin values (`pv`, `sp`, `co`) come from the WS `status` frame (`StatusData`) via `useRealtime`; `GET /simulator/status` is the authoritative source for the **config** snapshot (preset, gain, taus, dead_time, auto_sp/auto_disturbance, running).

---

### Task 1: OpenAPI audit + generated types + typed simulator API wrapper

**Files:** `src/features/simulator/api.ts`, `src/features/simulator/types.ts`, `src/api/generated/openapi.ts` (regenerated)

**Interfaces:**
- `api.ts` exports: `startSimulator()`, `stopSimulator()`, `getSimulatorStatus()`, `setPreset(b)`, `setParameters(b)`, `injectDisturbance(b)`, `clearDisturbance(controllerId)`, `setCo(controllerId, co)`, `setMode(controllerId, mode)`, `setAutoSp(controllerId, b)`, `setAutoDisturbance(controllerId, b)`.
- `types.ts` re-exports the generated DTO types under stable aliases: `ControllerSimStatus`, `SimulatorStatusResponse`, `ProcessPresetName`, etc.

- [ ] **Step 1: Audit simulator router `response_model` coverage.** Confirm every consumed simulator route declares a Pydantic `response_model` (contract §6 precondition). Run:
```bash
cd /tmp/web-hmi-plans-wt/packages/smart_pid_core
grep -nE '@router\.(get|post|put|delete)' -A1 src/smart_pid_core/adapters/inbound/api/routers/simulator.py | grep -E 'response_model|@router'
```
**Expected:** every consumed route (`/start`, `/stop`, `/status`, `/preset`, `/parameters`, `/disturbance`, `/disturbance/{controller_id}`, `/{controller_id}/co`, `/{controller_id}/pid/mode`, `/{controller_id}/auto-sp`, `/{controller_id}/auto-disturbance`) shows a `response_model=` (already true in source: `CommandResponse`, `SimulatorStatusResponse`, `ControllerSimStatus`). If any lacks one, add it (backend code only) in this step; otherwise no backend change. Record the result in the commit message.

- [ ] **Step 2: Regenerate OpenAPI types.** With the backend running on `127.0.0.1:8000`:
```bash
cd /tmp/web-hmi-plans-wt/packages/smart_pid_web
npm run gen:api
```
**Expected:** `src/api/generated/openapi.ts` updates with `SimulatorStatusResponse`, `ControllerSimStatus`, `SimulatorPresetRequest`, `SimulatorParametersRequest`, `SimulatorDisturbanceRequest`, `SimulatorPIDSPRequest`, `SimulatorPIDModeRequest`, `AutoSPRequest`, `AutoDisturbanceRequest`, `CommandResponse`, `ProcessPresetName` schemas, and paths under `/simulator`. `git diff --stat` shows only the generated file changed.

- [ ] **Step 3: Write the failing test for the API wrapper (`api.test.ts`).** Mock `apiClient` and assert each wrapper hits the correct method + path + body.
```ts
// src/features/simulator/__tests__/api.test.ts
import { describe, it, expect, vi, beforeEach } from 'vitest';
import * as client from '../../../api/client';
import {
  setPreset, injectDisturbance, clearDisturbance, setCo, setMode,
  setAutoSp, setAutoDisturbance, startSimulator, stopSimulator, getSimulatorStatus,
} from '../api';

vi.mock('../../../api/client');

beforeEach(() => vi.clearAllMocks());

describe('simulator api wrappers', () => {
  it('setPreset POSTs /simulator/preset with controller_id + preset', async () => {
    vi.mocked(client.apiPost).mockResolvedValue({ ok: true });
    await setPreset({ controller_id: 1, preset: 'FLOW' });
    expect(client.apiPost).toHaveBeenCalledWith('/simulator/preset', { controller_id: 1, preset: 'FLOW' });
  });
  it('injectDisturbance POSTs /simulator/disturbance', async () => {
    vi.mocked(client.apiPost).mockResolvedValue({ ok: true });
    await injectDisturbance({ controller_id: 1, type: 'step', amplitude: 10 });
    expect(client.apiPost).toHaveBeenCalledWith('/simulator/disturbance', { controller_id: 1, type: 'step', amplitude: 10 });
  });
  it('clearDisturbance DELETEs /simulator/disturbance/{id}', async () => {
    vi.mocked(client.apiDelete).mockResolvedValue({ ok: true });
    await clearDisturbance(1);
    expect(client.apiDelete).toHaveBeenCalledWith('/simulator/disturbance/1');
  });
  it('setCo POSTs /simulator/{id}/co with sp carrying CO%', async () => {
    vi.mocked(client.apiPost).mockResolvedValue({ ok: true });
    await setCo(1, 42);
    expect(client.apiPost).toHaveBeenCalledWith('/simulator/1/co', { controller_id: 1, sp: 42 });
  });
  it('setMode POSTs /simulator/{id}/pid/mode', async () => {
    vi.mocked(client.apiPost).mockResolvedValue({ ok: true });
    await setMode(1, 'AUTO');
    expect(client.apiPost).toHaveBeenCalledWith('/simulator/1/pid/mode', { controller_id: 1, mode: 'AUTO' });
  });
  it('setAutoSp PUTs /simulator/{id}/auto-sp', async () => {
    vi.mocked(client.apiPut).mockResolvedValue({});
    await setAutoSp(1, { enabled: true, sp_min_pct: 30, sp_max_pct: 70 });
    expect(client.apiPut).toHaveBeenCalledWith('/simulator/1/auto-sp', { enabled: true, sp_min_pct: 30, sp_max_pct: 70 });
  });
  it('setAutoDisturbance PUTs /simulator/{id}/auto-disturbance', async () => {
    vi.mocked(client.apiPut).mockResolvedValue({});
    await setAutoDisturbance(1, { enabled: true, max_amplitude_pct: 10 });
    expect(client.apiPut).toHaveBeenCalledWith('/simulator/1/auto-disturbance', { enabled: true, max_amplitude_pct: 10 });
  });
  it('start/stop/status hit the right paths', async () => {
    vi.mocked(client.apiPost).mockResolvedValue({ ok: true });
    vi.mocked(client.apiGet).mockResolvedValue({ enabled: true, running: false, controllers: {} });
    await startSimulator(); expect(client.apiPost).toHaveBeenCalledWith('/simulator/start', undefined);
    await stopSimulator();  expect(client.apiPost).toHaveBeenCalledWith('/simulator/stop', undefined);
    await getSimulatorStatus(); expect(client.apiGet).toHaveBeenCalledWith('/simulator/status');
  });
});
```

- [ ] **Step 4: Run the test to confirm it fails.**
```bash
cd /tmp/web-hmi-plans-wt/packages/smart_pid_web && npm run test -- src/features/simulator/__tests__/api.test.ts
```
**Expected:** fails — `../api` and `../types` do not exist yet.

- [ ] **Step 5: Implement `types.ts` and `api.ts`.**
```ts
// src/features/simulator/types.ts
import type { components } from '../../api/generated/openapi';

export type ControllerSimStatus = components['schemas']['ControllerSimStatus'];
export type SimulatorStatusResponse = components['schemas']['SimulatorStatusResponse'];
export type SimulatorPresetRequest = components['schemas']['SimulatorPresetRequest'];
export type SimulatorParametersRequest = components['schemas']['SimulatorParametersRequest'];
export type SimulatorDisturbanceRequest = components['schemas']['SimulatorDisturbanceRequest'];
export type AutoSPRequest = components['schemas']['AutoSPRequest'];
export type AutoDisturbanceRequest = components['schemas']['AutoDisturbanceRequest'];
export type CommandResponse = components['schemas']['CommandResponse'];
export type ProcessPresetName = SimulatorPresetRequest['preset'];
export type TwinMode = 'MAN' | 'AUTO';
export type DisturbanceType = 'step' | 'noise';

export const PRESET_NAMES: ProcessPresetName[] = ['FLOW', 'PRESSURE', 'LEVEL', 'TEMPERATURE', 'CUSTOM'];
```
```ts
// src/features/simulator/api.ts
import { apiGet, apiPost, apiPut, apiDelete } from '../../api/client';
import type {
  SimulatorStatusResponse, SimulatorPresetRequest, SimulatorParametersRequest,
  SimulatorDisturbanceRequest, AutoSPRequest, AutoDisturbanceRequest,
  CommandResponse, ControllerSimStatus, TwinMode,
} from './types';

export const startSimulator = () => apiPost<CommandResponse>('/simulator/start', undefined);
export const stopSimulator = () => apiPost<CommandResponse>('/simulator/stop', undefined);
export const getSimulatorStatus = () => apiGet<SimulatorStatusResponse>('/simulator/status');

export const setPreset = (b: SimulatorPresetRequest) =>
  apiPost<CommandResponse>('/simulator/preset', b);
export const setParameters = (b: SimulatorParametersRequest) =>
  apiPut<CommandResponse>('/simulator/parameters', b);

export const injectDisturbance = (b: SimulatorDisturbanceRequest) =>
  apiPost<CommandResponse>('/simulator/disturbance', b);
export const clearDisturbance = (controllerId: number) =>
  apiDelete<CommandResponse>(`/simulator/disturbance/${controllerId}`);

export const setCo = (controllerId: number, co: number) =>
  apiPost<CommandResponse>(`/simulator/${controllerId}/co`, { controller_id: controllerId, sp: co });
export const setMode = (controllerId: number, mode: TwinMode) =>
  apiPost<CommandResponse>(`/simulator/${controllerId}/pid/mode`, { controller_id: controllerId, mode });

export const setAutoSp = (controllerId: number, b: AutoSPRequest) =>
  apiPut<ControllerSimStatus>(`/simulator/${controllerId}/auto-sp`, b);
export const setAutoDisturbance = (controllerId: number, b: AutoDisturbanceRequest) =>
  apiPut<ControllerSimStatus>(`/simulator/${controllerId}/auto-disturbance`, b);
```

- [ ] **Step 6: Run the test to confirm it passes.**
```bash
cd /tmp/web-hmi-plans-wt/packages/smart_pid_web && npm run test -- src/features/simulator/__tests__/api.test.ts
```
**Expected:** all green.

- [ ] **Step 7: Commit.** `feat(web): typed simulator API wrapper over real routers/simulator routes`

---

### Task 2: SimulationModeBanner (never confuse twin with real process)

**Files:** `src/features/simulator/SimulationModeBanner.tsx`, `src/features/simulator/__tests__/SimulationModeBanner.test.tsx`

**Interfaces:** `SimulationModeBanner(): JSX.Element` — a persistent strip using the desaturated `--alarm-diag` token + text `MODO SIMULAÇÃO — digital twin`, `role="status"`, `aria-label="Simulation mode"`.

- [ ] **Step 1: Write the failing test.**
```tsx
// src/features/simulator/__tests__/SimulationModeBanner.test.tsx
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { SimulationModeBanner } from '../SimulationModeBanner';

describe('SimulationModeBanner', () => {
  it('renders persistent SIMULATION MODE label with status role', () => {
    render(<SimulationModeBanner />);
    const banner = screen.getByRole('status', { name: /simulation mode/i });
    expect(banner).toBeInTheDocument();
    expect(banner).toHaveTextContent(/MODO SIMULAÇÃO/i);
    expect(banner).toHaveTextContent(/digital twin/i);
  });
});
```

- [ ] **Step 2: Run the test to confirm it fails.**
```bash
cd /tmp/web-hmi-plans-wt/packages/smart_pid_web && npm run test -- src/features/simulator/__tests__/SimulationModeBanner.test.tsx
```
**Expected:** fails — component missing.

- [ ] **Step 3: Implement `SimulationModeBanner.tsx`.**
```tsx
// src/features/simulator/SimulationModeBanner.tsx
export function SimulationModeBanner(): JSX.Element {
  return (
    <div
      role="status"
      aria-label="Simulation mode"
      style={{
        background: 'var(--alarm-diag)',
        color: 'var(--text-on-diag, #fff)',
        padding: '6px 12px',
        fontWeight: 600,
        letterSpacing: '0.04em',
        textAlign: 'center',
      }}
    >
      MODO SIMULAÇÃO — digital twin
    </div>
  );
}
```

- [ ] **Step 4: Run the test to confirm it passes.**
```bash
cd /tmp/web-hmi-plans-wt/packages/smart_pid_web && npm run test -- src/features/simulator/__tests__/SimulationModeBanner.test.tsx
```
**Expected:** green.

- [ ] **Step 5: Commit.** `feat(web): persistent SIMULATION MODE banner for simulator page`

---

### Task 3: PresetSelector

**Files:** `src/features/simulator/PresetSelector.tsx`, `src/features/simulator/__tests__/PresetSelector.test.tsx`

**Interfaces:** `PresetSelector({ value, onChange }: { value: ProcessPresetName; onChange: (p: ProcessPresetName) => void })`.

- [ ] **Step 1: Write the failing test.**
```tsx
// src/features/simulator/__tests__/PresetSelector.test.tsx
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { PresetSelector } from '../PresetSelector';

describe('PresetSelector', () => {
  it('renders all five preset options and reflects value', () => {
    render(<PresetSelector value="FLOW" onChange={() => {}} />);
    const select = screen.getByRole('combobox', { name: /process preset/i }) as HTMLSelectElement;
    ['FLOW', 'PRESSURE', 'LEVEL', 'TEMPERATURE', 'CUSTOM'].forEach((p) =>
      expect(screen.getByRole('option', { name: p })).toBeInTheDocument());
    expect(select.value).toBe('FLOW');
  });
  it('calls onChange with the selected preset', () => {
    const onChange = vi.fn();
    render(<PresetSelector value="FLOW" onChange={onChange} />);
    fireEvent.change(screen.getByRole('combobox', { name: /process preset/i }), { target: { value: 'LEVEL' } });
    expect(onChange).toHaveBeenCalledWith('LEVEL');
  });
});
```

- [ ] **Step 2: Run the test to confirm it fails.**
```bash
cd /tmp/web-hmi-plans-wt/packages/smart_pid_web && npm run test -- src/features/simulator/__tests__/PresetSelector.test.tsx
```
**Expected:** fails — component missing.

- [ ] **Step 3: Implement `PresetSelector.tsx`.**
```tsx
// src/features/simulator/PresetSelector.tsx
import { PRESET_NAMES, type ProcessPresetName } from './types';

interface Props { value: ProcessPresetName; onChange: (p: ProcessPresetName) => void; }

export function PresetSelector({ value, onChange }: Props): JSX.Element {
  return (
    <label>
      <span>Process preset</span>
      <select
        aria-label="Process preset"
        value={value}
        onChange={(e) => onChange(e.target.value as ProcessPresetName)}
      >
        {PRESET_NAMES.map((p) => (
          <option key={p} value={p}>{p}</option>
        ))}
      </select>
    </label>
  );
}
```

- [ ] **Step 4: Run the test to confirm it passes.**
```bash
cd /tmp/web-hmi-plans-wt/packages/smart_pid_web && npm run test -- src/features/simulator/__tests__/PresetSelector.test.tsx
```
**Expected:** green.

- [ ] **Step 5: Commit.** `feat(web): simulator process-preset selector`

---

### Task 4: DynamicsSliders (gain / dead-time L / tau1 / tau2)

**Files:** `src/features/simulator/DynamicsSliders.tsx`, `src/features/simulator/__tests__/DynamicsSliders.test.tsx`

**Interfaces:** `DynamicsSliders({ value, onCommit }: { value: { gain: number; dead_time: number; tau1: number; tau2: number | null }; onCommit: (v) => void })`. Each slider has a mono numeric readout beside it; `onCommit` fires on release/change with the full param object.

- [ ] **Step 1: Write the failing test.**
```tsx
// src/features/simulator/__tests__/DynamicsSliders.test.tsx
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { DynamicsSliders } from '../DynamicsSliders';

const base = { gain: 1.2, dead_time: 1.0, tau1: 3.0, tau2: null };

describe('DynamicsSliders', () => {
  it('renders gain, dead time, tau1, tau2 sliders with mono readouts', () => {
    render(<DynamicsSliders value={base} onCommit={() => {}} />);
    expect(screen.getByRole('slider', { name: /gain/i })).toHaveValue('1.2');
    expect(screen.getByRole('slider', { name: /dead time/i })).toHaveValue('1');
    expect(screen.getByRole('slider', { name: /tau1/i })).toHaveValue('3');
    expect(screen.getByTestId('readout-gain')).toHaveTextContent('1.20');
  });
  it('commits the full dynamics object when gain changes', () => {
    const onCommit = vi.fn();
    render(<DynamicsSliders value={base} onCommit={onCommit} />);
    fireEvent.change(screen.getByRole('slider', { name: /gain/i }), { target: { value: '2.0' } });
    expect(onCommit).toHaveBeenCalledWith({ gain: 2.0, dead_time: 1.0, tau1: 3.0, tau2: null });
  });
});
```

- [ ] **Step 2: Run the test to confirm it fails.**
```bash
cd /tmp/web-hmi-plans-wt/packages/smart_pid_web && npm run test -- src/features/simulator/__tests__/DynamicsSliders.test.tsx
```
**Expected:** fails — component missing.

- [ ] **Step 3: Implement `DynamicsSliders.tsx`.**
```tsx
// src/features/simulator/DynamicsSliders.tsx
export interface Dynamics { gain: number; dead_time: number; tau1: number; tau2: number | null; }
interface Props { value: Dynamics; onCommit: (v: Dynamics) => void; }

const FIELDS: { key: keyof Dynamics; label: string; min: number; max: number; step: number }[] = [
  { key: 'gain', label: 'Gain', min: 0, max: 5, step: 0.1 },
  { key: 'dead_time', label: 'Dead time L', min: 0, max: 30, step: 0.1 },
  { key: 'tau1', label: 'Tau1', min: 0, max: 60, step: 0.1 },
  { key: 'tau2', label: 'Tau2', min: 0, max: 60, step: 0.1 },
];

export function DynamicsSliders({ value, onCommit }: Props): JSX.Element {
  const change = (key: keyof Dynamics, raw: string) =>
    onCommit({ ...value, [key]: Number(raw) });
  return (
    <div>
      {FIELDS.map(({ key, label, min, max, step }) => {
        const v = value[key] ?? 0;
        return (
          <div key={key} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <input
              type="range"
              aria-label={label}
              min={min}
              max={max}
              step={step}
              value={v}
              onChange={(e) => change(key, e.target.value)}
            />
            <span data-testid={`readout-${key}`} style={{ fontFamily: 'var(--font-mono, monospace)' }}>
              {v.toFixed(2)}
            </span>
          </div>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 4: Run the test to confirm it passes.**
```bash
cd /tmp/web-hmi-plans-wt/packages/smart_pid_web && npm run test -- src/features/simulator/__tests__/DynamicsSliders.test.tsx
```
**Expected:** green.

- [ ] **Step 5: Commit.** `feat(web): simulator dynamics sliders with mono readouts`

---

### Task 5: DisturbanceControls (inject / remove)

**Files:** `src/features/simulator/DisturbanceControls.tsx`, `src/features/simulator/__tests__/DisturbanceControls.test.tsx`

**Interfaces:** `DisturbanceControls({ active, onInject, onRemove }: { active: boolean; onInject: (type: DisturbanceType, amplitude: number) => void; onRemove: () => void })`.

- [ ] **Step 1: Write the failing test.**
```tsx
// src/features/simulator/__tests__/DisturbanceControls.test.tsx
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { DisturbanceControls } from '../DisturbanceControls';

describe('DisturbanceControls', () => {
  it('injects a step disturbance with the entered amplitude', () => {
    const onInject = vi.fn();
    render(<DisturbanceControls active={false} onInject={onInject} onRemove={() => {}} />);
    fireEvent.change(screen.getByRole('spinbutton', { name: /amplitude/i }), { target: { value: '15' } });
    fireEvent.click(screen.getByRole('button', { name: /inject/i }));
    expect(onInject).toHaveBeenCalledWith('step', 15);
  });
  it('disables Remove when no disturbance is active', () => {
    render(<DisturbanceControls active={false} onInject={() => {}} onRemove={() => {}} />);
    expect(screen.getByRole('button', { name: /remove/i })).toBeDisabled();
  });
  it('calls onRemove when active and Remove clicked', () => {
    const onRemove = vi.fn();
    render(<DisturbanceControls active onInject={() => {}} onRemove={onRemove} />);
    fireEvent.click(screen.getByRole('button', { name: /remove/i }));
    expect(onRemove).toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run the test to confirm it fails.**
```bash
cd /tmp/web-hmi-plans-wt/packages/smart_pid_web && npm run test -- src/features/simulator/__tests__/DisturbanceControls.test.tsx
```
**Expected:** fails — component missing.

- [ ] **Step 3: Implement `DisturbanceControls.tsx`.**
```tsx
// src/features/simulator/DisturbanceControls.tsx
import { useState } from 'react';
import type { DisturbanceType } from './types';

interface Props {
  active: boolean;
  onInject: (type: DisturbanceType, amplitude: number) => void;
  onRemove: () => void;
}

export function DisturbanceControls({ active, onInject, onRemove }: Props): JSX.Element {
  const [type, setType] = useState<DisturbanceType>('step');
  const [amplitude, setAmplitude] = useState(10);
  return (
    <fieldset>
      <legend>Disturbance</legend>
      <label>
        <span>Type</span>
        <select aria-label="Disturbance type" value={type}
          onChange={(e) => setType(e.target.value as DisturbanceType)}>
          <option value="step">step</option>
          <option value="noise">noise</option>
        </select>
      </label>
      <label>
        <span>Amplitude</span>
        <input type="number" aria-label="Amplitude" value={amplitude}
          onChange={(e) => setAmplitude(Number(e.target.value))} />
      </label>
      <button type="button" onClick={() => onInject(type, amplitude)}>Inject disturbance</button>
      <button type="button" disabled={!active} onClick={onRemove}>Remove</button>
    </fieldset>
  );
}
```

- [ ] **Step 4: Run the test to confirm it passes.**
```bash
cd /tmp/web-hmi-plans-wt/packages/smart_pid_web && npm run test -- src/features/simulator/__tests__/DisturbanceControls.test.tsx
```
**Expected:** green.

- [ ] **Step 5: Commit.** `feat(web): simulator disturbance inject/remove controls`

---

### Task 6: TwinOutputModeControl (CO entry + MAN/AUTO mode)

**Files:** `src/features/simulator/TwinOutputModeControl.tsx`, `src/features/simulator/__tests__/TwinOutputModeControl.test.tsx`

**Interfaces:** `TwinOutputModeControl({ co, mode, onSetCo, onSetMode }: { co: number; mode: TwinMode; onSetCo: (co: number) => void; onSetMode: (m: TwinMode) => void })`. CO is bounded 0–100 (matches `SimulatorPIDSPRequest.sp` Field `ge=0 le=100`).

- [ ] **Step 1: Write the failing test.**
```tsx
// src/features/simulator/__tests__/TwinOutputModeControl.test.tsx
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { TwinOutputModeControl } from '../TwinOutputModeControl';

describe('TwinOutputModeControl', () => {
  it('sets twin CO within 0-100 on apply', () => {
    const onSetCo = vi.fn();
    render(<TwinOutputModeControl co={0} mode="MAN" onSetCo={onSetCo} onSetMode={() => {}} />);
    fireEvent.change(screen.getByRole('spinbutton', { name: /output co/i }), { target: { value: '42' } });
    fireEvent.click(screen.getByRole('button', { name: /apply output/i }));
    expect(onSetCo).toHaveBeenCalledWith(42);
  });
  it('toggles twin mode to AUTO', () => {
    const onSetMode = vi.fn();
    render(<TwinOutputModeControl co={0} mode="MAN" onSetCo={() => {}} onSetMode={onSetMode} />);
    fireEvent.click(screen.getByRole('button', { name: /auto/i }));
    expect(onSetMode).toHaveBeenCalledWith('AUTO');
  });
  it('disables CO apply when in AUTO (CO is computed by the twin PID)', () => {
    render(<TwinOutputModeControl co={0} mode="AUTO" onSetCo={() => {}} onSetMode={() => {}} />);
    expect(screen.getByRole('button', { name: /apply output/i })).toBeDisabled();
  });
});
```

- [ ] **Step 2: Run the test to confirm it fails.**
```bash
cd /tmp/web-hmi-plans-wt/packages/smart_pid_web && npm run test -- src/features/simulator/__tests__/TwinOutputModeControl.test.tsx
```
**Expected:** fails — component missing.

- [ ] **Step 3: Implement `TwinOutputModeControl.tsx`.**
```tsx
// src/features/simulator/TwinOutputModeControl.tsx
import { useState } from 'react';
import type { TwinMode } from './types';

interface Props {
  co: number;
  mode: TwinMode;
  onSetCo: (co: number) => void;
  onSetMode: (m: TwinMode) => void;
}

const clamp = (n: number) => Math.max(0, Math.min(100, n));

export function TwinOutputModeControl({ co, mode, onSetCo, onSetMode }: Props): JSX.Element {
  const [draft, setDraft] = useState(co);
  const auto = mode === 'AUTO';
  return (
    <fieldset>
      <legend>Twin output / mode</legend>
      <div role="group" aria-label="Twin mode">
        <button type="button" aria-pressed={!auto} onClick={() => onSetMode('MAN')}>MAN</button>
        <button type="button" aria-pressed={auto} onClick={() => onSetMode('AUTO')}>AUTO</button>
      </div>
      <label>
        <span>Output CO (%)</span>
        <input type="number" aria-label="Output CO" min={0} max={100} value={draft}
          disabled={auto} onChange={(e) => setDraft(Number(e.target.value))} />
      </label>
      <button type="button" disabled={auto} onClick={() => onSetCo(clamp(draft))}>Apply output</button>
    </fieldset>
  );
}
```

- [ ] **Step 4: Run the test to confirm it passes.**
```bash
cd /tmp/web-hmi-plans-wt/packages/smart_pid_web && npm run test -- src/features/simulator/__tests__/TwinOutputModeControl.test.tsx
```
**Expected:** green.

- [ ] **Step 5: Commit.** `feat(web): simulator twin output + MAN/AUTO mode control`

---

### Task 7: AutoToggles (auto-SP and auto-disturbance)

**Files:** `src/features/simulator/AutoToggles.tsx`, `src/features/simulator/__tests__/AutoToggles.test.tsx`

**Interfaces:** `AutoToggles({ autoSp, autoDisturbance, onSetAutoSp, onSetAutoDisturbance })` where `autoSp: AutoSPRequest | null`, `autoDisturbance: AutoDisturbanceRequest | null`. Callbacks send the full request bodies (with defaults `sp_min_pct=30, sp_max_pct=70, max_amplitude_pct=10`).

- [ ] **Step 1: Write the failing test.**
```tsx
// src/features/simulator/__tests__/AutoToggles.test.tsx
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { AutoToggles } from '../AutoToggles';

describe('AutoToggles', () => {
  it('enables auto-SP with default bounds when toggled on', () => {
    const onSetAutoSp = vi.fn();
    render(<AutoToggles autoSp={null} autoDisturbance={null}
      onSetAutoSp={onSetAutoSp} onSetAutoDisturbance={() => {}} />);
    fireEvent.click(screen.getByRole('switch', { name: /auto.?sp/i }));
    expect(onSetAutoSp).toHaveBeenCalledWith({ enabled: true, sp_min_pct: 30, sp_max_pct: 70 });
  });
  it('enables auto-disturbance with default amplitude when toggled on', () => {
    const onSetAutoDisturbance = vi.fn();
    render(<AutoToggles autoSp={null} autoDisturbance={null}
      onSetAutoSp={() => {}} onSetAutoDisturbance={onSetAutoDisturbance} />);
    fireEvent.click(screen.getByRole('switch', { name: /auto.?disturbance/i }));
    expect(onSetAutoDisturbance).toHaveBeenCalledWith({ enabled: true, max_amplitude_pct: 10 });
  });
  it('reflects an already-enabled auto-SP as checked', () => {
    render(<AutoToggles autoSp={{ enabled: true, sp_min_pct: 20, sp_max_pct: 80 }} autoDisturbance={null}
      onSetAutoSp={() => {}} onSetAutoDisturbance={() => {}} />);
    expect(screen.getByRole('switch', { name: /auto.?sp/i })).toBeChecked();
  });
});
```

- [ ] **Step 2: Run the test to confirm it fails.**
```bash
cd /tmp/web-hmi-plans-wt/packages/smart_pid_web && npm run test -- src/features/simulator/__tests__/AutoToggles.test.tsx
```
**Expected:** fails — component missing.

- [ ] **Step 3: Implement `AutoToggles.tsx`.**
```tsx
// src/features/simulator/AutoToggles.tsx
import type { AutoSPRequest, AutoDisturbanceRequest } from './types';

interface Props {
  autoSp: AutoSPRequest | null;
  autoDisturbance: AutoDisturbanceRequest | null;
  onSetAutoSp: (b: AutoSPRequest) => void;
  onSetAutoDisturbance: (b: AutoDisturbanceRequest) => void;
}

export function AutoToggles({ autoSp, autoDisturbance, onSetAutoSp, onSetAutoDisturbance }: Props): JSX.Element {
  const spOn = autoSp?.enabled ?? false;
  const distOn = autoDisturbance?.enabled ?? false;
  return (
    <fieldset>
      <legend>Automation</legend>
      <label>
        <span>Auto-SP</span>
        <input
          type="checkbox" role="switch" aria-label="Auto-SP" checked={spOn}
          onChange={(e) =>
            onSetAutoSp({
              enabled: e.target.checked,
              sp_min_pct: autoSp?.sp_min_pct ?? 30,
              sp_max_pct: autoSp?.sp_max_pct ?? 70,
            })
          }
        />
      </label>
      <label>
        <span>Auto-disturbance</span>
        <input
          type="checkbox" role="switch" aria-label="Auto-disturbance" checked={distOn}
          onChange={(e) =>
            onSetAutoDisturbance({
              enabled: e.target.checked,
              max_amplitude_pct: autoDisturbance?.max_amplitude_pct ?? 10,
            })
          }
        />
      </label>
    </fieldset>
  );
}
```

- [ ] **Step 4: Run the test to confirm it passes.**
```bash
cd /tmp/web-hmi-plans-wt/packages/smart_pid_web && npm run test -- src/features/simulator/__tests__/AutoToggles.test.tsx
```
**Expected:** green.

- [ ] **Step 5: Commit.** `feat(web): simulator auto-SP and auto-disturbance toggles`

---

### Task 8: Status query + mutations hooks

**Files:** `src/features/simulator/useSimulatorStatus.ts`, `src/features/simulator/useSimulatorMutations.ts`, `src/features/simulator/__tests__/useSimulatorStatus.test.tsx`

**Interfaces:**
- `useSimulatorStatus(): { data: SimulatorStatusResponse | undefined; isLoading; live: ReadonlyMap<number, StatusData> }` — `useQuery(['simulator','status'], getSimulatorStatus)` for config, plus `useRealtime().lastStatus` for live twin values. Registers `onResync` to refetch status after WS reconnect.
- `useSimulatorMutations(controllerId)` returns the named mutations; each invalidates `['simulator','status']` on success.

- [ ] **Step 1: Write the failing test for `useSimulatorStatus` (merges REST config + WS live).**
```tsx
// src/features/simulator/__tests__/useSimulatorStatus.test.tsx
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import * as api from '../api';
import { useSimulatorStatus } from '../useSimulatorStatus';

vi.mock('../api');
vi.mock('../../../realtime/useRealtime', () => ({
  useRealtime: () => ({
    connected: true,
    lastStatus: new Map([[1, { pv: 55, sp: 50, co: 42, mode: 'AUTO' }]]),
    lastStats: new Map(),
    subscribe: () => () => {},
    onResync: () => () => {},
  }),
}));

const wrapper = ({ children }: { children: React.ReactNode }) => {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
};

beforeEach(() => vi.clearAllMocks());

describe('useSimulatorStatus', () => {
  it('returns REST config and live WS twin status', async () => {
    vi.mocked(api.getSimulatorStatus).mockResolvedValue({
      enabled: true, running: true,
      controllers: { 1: { preset: 'FLOW', gain: 1.2, tau1: 3, tau2: null, dead_time: 1 } as never },
    });
    const { result } = renderHook(() => useSimulatorStatus(), { wrapper });
    await waitFor(() => expect(result.current.data?.running).toBe(true));
    expect(result.current.live.get(1)?.co).toBe(42);
  });
});
```

- [ ] **Step 2: Run the test to confirm it fails.**
```bash
cd /tmp/web-hmi-plans-wt/packages/smart_pid_web && npm run test -- src/features/simulator/__tests__/useSimulatorStatus.test.tsx
```
**Expected:** fails — hooks missing.

- [ ] **Step 3: Implement `useSimulatorStatus.ts` and `useSimulatorMutations.ts`.**
```ts
// src/features/simulator/useSimulatorStatus.ts
import { useEffect } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useRealtime } from '../../realtime/useRealtime';
import { getSimulatorStatus } from './api';

export function useSimulatorStatus() {
  const qc = useQueryClient();
  const rt = useRealtime();
  const query = useQuery({ queryKey: ['simulator', 'status'], queryFn: getSimulatorStatus });
  useEffect(() => rt.onResync(() => qc.invalidateQueries({ queryKey: ['simulator', 'status'] })), [rt, qc]);
  return { data: query.data, isLoading: query.isLoading, live: rt.lastStatus };
}
```
```ts
// src/features/simulator/useSimulatorMutations.ts
import { useMutation, useQueryClient } from '@tanstack/react-query';
import {
  startSimulator, stopSimulator, setPreset, setParameters,
  injectDisturbance, clearDisturbance, setCo, setMode, setAutoSp, setAutoDisturbance,
} from './api';
import type {
  ProcessPresetName, DisturbanceType, TwinMode, AutoSPRequest, AutoDisturbanceRequest,
} from './types';
import type { Dynamics } from './DynamicsSliders';

export function useSimulatorMutations(controllerId: number) {
  const qc = useQueryClient();
  const invalidate = () => qc.invalidateQueries({ queryKey: ['simulator', 'status'] });
  const opts = { onSuccess: invalidate };

  return {
    start: useMutation({ mutationFn: () => startSimulator(), ...opts }),
    stop: useMutation({ mutationFn: () => stopSimulator(), ...opts }),
    preset: useMutation({
      mutationFn: (p: ProcessPresetName) => setPreset({ controller_id: controllerId, preset: p }), ...opts }),
    params: useMutation({
      mutationFn: (d: Dynamics) =>
        setParameters({ controller_id: controllerId, gain: d.gain, tau1: d.tau1, tau2: d.tau2, dead_time: d.dead_time }),
      ...opts }),
    inject: useMutation({
      mutationFn: (v: { type: DisturbanceType; amplitude: number }) =>
        injectDisturbance({ controller_id: controllerId, type: v.type, amplitude: v.amplitude }), ...opts }),
    clear: useMutation({ mutationFn: () => clearDisturbance(controllerId), ...opts }),
    co: useMutation({ mutationFn: (co: number) => setCo(controllerId, co), ...opts }),
    mode: useMutation({ mutationFn: (m: TwinMode) => setMode(controllerId, m), ...opts }),
    autoSp: useMutation({ mutationFn: (b: AutoSPRequest) => setAutoSp(controllerId, b), ...opts }),
    autoDist: useMutation({ mutationFn: (b: AutoDisturbanceRequest) => setAutoDisturbance(controllerId, b), ...opts }),
  };
}
```

- [ ] **Step 4: Run the test to confirm it passes.**
```bash
cd /tmp/web-hmi-plans-wt/packages/smart_pid_web && npm run test -- src/features/simulator/__tests__/useSimulatorStatus.test.tsx
```
**Expected:** green.

- [ ] **Step 5: Commit.** `feat(web): simulator status query + mutation hooks (REST + useRealtime)`

---

### Task 9: SimulatorControlPanel + StartStopControl (compose the left panel)

**Files:** `src/features/simulator/StartStopControl.tsx`, `src/features/simulator/SimulatorControlPanel.tsx`, `src/features/simulator/__tests__/SimulatorControlPanel.test.tsx`

**Interfaces:** `StartStopControl({ running, onStart, onStop })`. `SimulatorControlPanel({ controllerId })` reads `useSimulatorStatus()` + `useSimulatorMutations(controllerId)`, wires each child to its mutation, and derives `disturbanceActive = step_active || noise_active` from the controller's `ControllerSimStatus`.

- [ ] **Step 1: Write the failing test (control panel wires preset + disturbance mutations).**
```tsx
// src/features/simulator/__tests__/SimulatorControlPanel.test.tsx
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import * as api from '../api';
import { SimulatorControlPanel } from '../SimulatorControlPanel';

vi.mock('../api');
vi.mock('../../../realtime/useRealtime', () => ({
  useRealtime: () => ({
    connected: true, lastStatus: new Map([[1, { pv: 50, sp: 50, co: 0, mode: 'MAN' }]]),
    lastStats: new Map(), subscribe: () => () => {}, onResync: () => () => {},
  }),
}));

const wrapper = ({ children }: { children: React.ReactNode }) => {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
};

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(api.getSimulatorStatus).mockResolvedValue({
    enabled: true, running: false,
    controllers: { 1: {
      preset: 'FLOW', gain: 1.2, tau1: 3, tau2: null, dead_time: 1,
      step_active: false, step_amplitude: 0, noise_active: false, noise_amplitude: 0,
      pid_mode: 0, co: 0, sp: 50, pv: 50, auto_sp: null, auto_disturbance: null,
    } as never },
  });
  vi.mocked(api.setPreset).mockResolvedValue({ ok: true });
  vi.mocked(api.injectDisturbance).mockResolvedValue({ ok: true });
});

describe('SimulatorControlPanel', () => {
  it('applies a preset change through the preset mutation', async () => {
    render(<SimulatorControlPanel controllerId={1} />, { wrapper });
    await waitFor(() => expect(screen.getByRole('combobox', { name: /process preset/i })).toBeInTheDocument());
    fireEvent.change(screen.getByRole('combobox', { name: /process preset/i }), { target: { value: 'LEVEL' } });
    await waitFor(() => expect(api.setPreset).toHaveBeenCalledWith({ controller_id: 1, preset: 'LEVEL' }));
  });
  it('injects a disturbance through the disturbance mutation', async () => {
    render(<SimulatorControlPanel controllerId={1} />, { wrapper });
    await waitFor(() => expect(screen.getByRole('button', { name: /inject/i })).toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { name: /inject/i }));
    await waitFor(() => expect(api.injectDisturbance).toHaveBeenCalledWith(
      expect.objectContaining({ controller_id: 1, type: 'step' })));
  });
});
```

- [ ] **Step 2: Run the test to confirm it fails.**
```bash
cd /tmp/web-hmi-plans-wt/packages/smart_pid_web && npm run test -- src/features/simulator/__tests__/SimulatorControlPanel.test.tsx
```
**Expected:** fails — components missing.

- [ ] **Step 3: Implement `StartStopControl.tsx` and `SimulatorControlPanel.tsx`.**
```tsx
// src/features/simulator/StartStopControl.tsx
interface Props { running: boolean; onStart: () => void; onStop: () => void; }
export function StartStopControl({ running, onStart, onStop }: Props): JSX.Element {
  return (
    <div role="group" aria-label="Simulator run state">
      <button type="button" disabled={running} onClick={onStart}>Start</button>
      <button type="button" disabled={!running} onClick={onStop}>Stop</button>
      <span data-testid="sim-running">{running ? 'Running' : 'Stopped'}</span>
    </div>
  );
}
```
```tsx
// src/features/simulator/SimulatorControlPanel.tsx
import { PresetSelector } from './PresetSelector';
import { DynamicsSliders } from './DynamicsSliders';
import { DisturbanceControls } from './DisturbanceControls';
import { TwinOutputModeControl } from './TwinOutputModeControl';
import { AutoToggles } from './AutoToggles';
import { StartStopControl } from './StartStopControl';
import { useSimulatorStatus } from './useSimulatorStatus';
import { useSimulatorMutations } from './useSimulatorMutations';
import type { ProcessPresetName, TwinMode } from './types';

interface Props { controllerId: number; }

export function SimulatorControlPanel({ controllerId }: Props): JSX.Element {
  const { data } = useSimulatorStatus();
  const m = useSimulatorMutations(controllerId);
  const c = data?.controllers?.[controllerId];
  if (!c) return <div>Loading simulator…</div>;

  const disturbanceActive = Boolean(c.step_active || c.noise_active);
  const twinMode: TwinMode = c.pid_mode === 1 ? 'AUTO' : 'MAN';

  return (
    <section aria-label="Simulator controls" style={{ display: 'grid', gap: 16 }}>
      <StartStopControl
        running={Boolean(data?.running)}
        onStart={() => m.start.mutate()}
        onStop={() => m.stop.mutate()}
      />
      <PresetSelector value={c.preset as ProcessPresetName} onChange={(p) => m.preset.mutate(p)} />
      <DynamicsSliders
        value={{ gain: c.gain, dead_time: c.dead_time, tau1: c.tau1, tau2: c.tau2 }}
        onCommit={(d) => m.params.mutate(d)}
      />
      <DisturbanceControls
        active={disturbanceActive}
        onInject={(type, amplitude) => m.inject.mutate({ type, amplitude })}
        onRemove={() => m.clear.mutate()}
      />
      <TwinOutputModeControl
        co={c.co}
        mode={twinMode}
        onSetCo={(co) => m.co.mutate(co)}
        onSetMode={(mode) => m.mode.mutate(mode)}
      />
      <AutoToggles
        autoSp={c.auto_sp ?? null}
        autoDisturbance={c.auto_disturbance ?? null}
        onSetAutoSp={(b) => m.autoSp.mutate(b)}
        onSetAutoDisturbance={(b) => m.autoDist.mutate(b)}
      />
    </section>
  );
}
```

- [ ] **Step 4: Run the test to confirm it passes.**
```bash
cd /tmp/web-hmi-plans-wt/packages/smart_pid_web && npm run test -- src/features/simulator/__tests__/SimulatorControlPanel.test.tsx
```
**Expected:** green.

- [ ] **Step 5: Commit.** `feat(web): compose simulator control panel + start/stop`

---

### Task 10: SimulatorPage + route + nav

**Files:** `src/pages/SimulatorPage.tsx`, `src/App.tsx` (modify), `src/components/shell/NavRail.tsx` (modify), `src/pages/__tests__/SimulatorPage.test.tsx`

**Interfaces:** `SimulatorPage()` renders the `SimulationModeBanner` (top), then a two-column layout: `SimulatorControlPanel` (left) and `RealtimeTrend` of the twin (right). Controller selection: if multiple controllers exist in status, a small selector; default to the lowest id.

- [ ] **Step 1: Write the failing test (page shows banner + trend + control panel).**
```tsx
// src/pages/__tests__/SimulatorPage.test.tsx
import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import * as api from '../../features/simulator/api';
import { SimulatorPage } from '../SimulatorPage';

vi.mock('../../features/simulator/api');
vi.mock('../../realtime/useRealtime', () => ({
  useRealtime: () => ({
    connected: true, lastStatus: new Map([[1, { pv: 50, sp: 50, co: 0, mode: 'MAN' }]]),
    lastStats: new Map(), subscribe: () => () => {}, onResync: () => () => {},
  }),
}));
vi.mock('../../components/RealtimeTrend', () => ({
  RealtimeTrend: () => <div data-testid="twin-trend" />,
}));

const wrapper = ({ children }: { children: React.ReactNode }) => {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
};

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(api.getSimulatorStatus).mockResolvedValue({
    enabled: true, running: false,
    controllers: { 1: {
      preset: 'FLOW', gain: 1.2, tau1: 3, tau2: null, dead_time: 1,
      step_active: false, step_amplitude: 0, noise_active: false, noise_amplitude: 0,
      pid_mode: 0, co: 0, sp: 50, pv: 50, auto_sp: null, auto_disturbance: null,
    } as never },
  });
});

describe('SimulatorPage', () => {
  it('shows the SIMULATION MODE banner, the twin trend and the controls', async () => {
    render(<SimulatorPage />, { wrapper });
    expect(screen.getByRole('status', { name: /simulation mode/i })).toBeInTheDocument();
    await waitFor(() => expect(screen.getByLabelText(/simulator controls/i)).toBeInTheDocument());
    expect(screen.getByTestId('twin-trend')).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run the test to confirm it fails.**
```bash
cd /tmp/web-hmi-plans-wt/packages/smart_pid_web && npm run test -- src/pages/__tests__/SimulatorPage.test.tsx
```
**Expected:** fails — page missing.

- [ ] **Step 3: Implement `SimulatorPage.tsx` and wire route + nav.**
```tsx
// src/pages/SimulatorPage.tsx
import { useState } from 'react';
import { SimulationModeBanner } from '../features/simulator/SimulationModeBanner';
import { SimulatorControlPanel } from '../features/simulator/SimulatorControlPanel';
import { useSimulatorStatus } from '../features/simulator/useSimulatorStatus';
import { RealtimeTrend } from '../components/RealtimeTrend';

export function SimulatorPage(): JSX.Element {
  const { data } = useSimulatorStatus();
  const ids = data ? Object.keys(data.controllers).map(Number).sort((a, b) => a - b) : [];
  const [selected, setSelected] = useState<number | null>(null);
  const controllerId = selected ?? ids[0] ?? null;

  return (
    <div>
      <SimulationModeBanner />
      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(320px, 380px) 1fr', gap: 16, padding: 16 }}>
        <div>
          {ids.length > 1 && (
            <label>
              <span>Loop</span>
              <select aria-label="Simulator loop" value={controllerId ?? ''}
                onChange={(e) => setSelected(Number(e.target.value))}>
                {ids.map((id) => <option key={id} value={id}>{id}</option>)}
              </select>
            </label>
          )}
          {controllerId != null
            ? <SimulatorControlPanel controllerId={controllerId} />
            : <p>No simulator loops available. Start the simulator to begin.</p>}
        </div>
        <div aria-label="Twin response trend">
          {controllerId != null && <RealtimeTrend loopId={controllerId} />}
        </div>
      </div>
    </div>
  );
}
```
Wire the route in `src/App.tsx` (inside the `<RequireAuth>`-guarded route table):
```tsx
import { SimulatorPage } from './pages/SimulatorPage';
// …
<Route path="/simulator" element={<SimulatorPage />} />
```
Add a nav entry in `src/components/shell/NavRail.tsx` (match existing nav-item pattern; label "Simulator", path `/simulator`).

> **Note:** confirm the exact `RealtimeTrend` prop name for the loop selector during implementation (read `src/components/RealtimeTrend.tsx`). If it differs from `loopId`, use the real prop; do not invent.

- [ ] **Step 4: Run the test to confirm it passes.**
```bash
cd /tmp/web-hmi-plans-wt/packages/smart_pid_web && npm run test -- src/pages/__tests__/SimulatorPage.test.tsx
```
**Expected:** green.

- [ ] **Step 5: Commit.** `feat(web): simulator page (banner + control panel + twin trend) wired to route + nav`

---

### Task 11: Playwright e2e — preset → trend response; disturbance → visible step

**Files:** `e2e/simulator.spec.ts`

**Interfaces:** Authenticated session (reuse the project's e2e auth fixture/storage state from Fatia 0+1). Backend simulator running with at least one controller.

- [ ] **Step 1: Write the e2e spec.**
```ts
// e2e/simulator.spec.ts
import { test, expect } from '@playwright/test';

test.describe('Simulator page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/simulator');
    await expect(page.getByRole('status', { name: /simulation mode/i })).toBeVisible();
    // ensure the twin is running
    const start = page.getByRole('button', { name: /^start$/i });
    if (await start.isEnabled()) await start.click();
    await expect(page.getByTestId('sim-running')).toHaveText(/running/i);
  });

  test('applying a preset changes the visible twin dynamics in the trend', async ({ page }) => {
    await expect(page.getByLabel(/twin response trend/i)).toBeVisible();
    await page.getByRole('combobox', { name: /process preset/i }).selectOption('TEMPERATURE');
    // the trend keeps streaming the twin response; assert it stays alive after the preset change
    await expect(page.getByLabel(/twin response trend/i)).toBeVisible();
    await page.waitForTimeout(2000); // allow twin to react to the slower TEMPERATURE dynamics
    await expect(page.getByRole('combobox', { name: /process preset/i })).toHaveValue('TEMPERATURE');
  });

  test('injecting a disturbance produces a visible step then removal returns to normal', async ({ page }) => {
    await page.getByRole('spinbutton', { name: /amplitude/i }).fill('20');
    await page.getByRole('button', { name: /inject disturbance/i }).click();
    // Remove becomes enabled once a disturbance is active (status refetch)
    await expect(page.getByRole('button', { name: /^remove$/i })).toBeEnabled();
    await page.getByRole('button', { name: /^remove$/i }).click();
    await expect(page.getByRole('button', { name: /^remove$/i })).toBeDisabled();
  });
});
```

- [ ] **Step 2: Run the e2e spec.**
```bash
cd /tmp/web-hmi-plans-wt/packages/smart_pid_web && npm run test:e2e -- simulator.spec.ts
```
**Expected:** both tests pass against a running backend + dev server. If the auth/storage fixture name differs, align with the Fatia 0+1 e2e setup (do not re-invent the auth flow).

- [ ] **Step 3: Commit.** `test(web): e2e for simulator preset response and disturbance inject/remove`

---

### Task 12: Negative-auth + full-suite + lint + spec docs

**Files:** `src/features/simulator/__tests__/api.auth.test.ts`, `docs/smartPIDv2.md` (modify), `docs/identidade_visual_ISA101.md` (modify)

- [ ] **Step 1: Write the unauthenticated-rejection test (single-admin model → 401, NOT 403).**
```ts
// src/features/simulator/__tests__/api.auth.test.ts
import { describe, it, expect, vi, beforeEach } from 'vitest';
import * as client from '../../../api/client';
import { setPreset } from '../api';

vi.mock('../../../api/client');

beforeEach(() => vi.clearAllMocks());

describe('simulator api unauthenticated', () => {
  it('propagates a 401 ApiError when no/invalid admin token', async () => {
    vi.mocked(client.apiPost).mockRejectedValue(
      Object.assign(new Error('Unauthorized'), { status: 401, detail: 'Not authenticated' }));
    await expect(setPreset({ controller_id: 1, preset: 'FLOW' }))
      .rejects.toMatchObject({ status: 401 });
  });
});
```

- [ ] **Step 2: Run the negative-auth test to confirm it passes.**
```bash
cd /tmp/web-hmi-plans-wt/packages/smart_pid_web && npm run test -- src/features/simulator/__tests__/api.auth.test.ts
```
**Expected:** green (asserts the single-admin contract: unauthenticated → 401).

- [ ] **Step 3: Run the full frontend suite + lint + build.**
```bash
cd /tmp/web-hmi-plans-wt/packages/smart_pid_web
npm run test
npm run lint
npm run build
```
**Expected:** all simulator unit/component tests green; no new lint errors; production build succeeds. Fix any issues found (frontend only) and re-run.

- [ ] **Step 4: Run backend lint/types to confirm zero backend regression.**
```bash
cd /tmp/web-hmi-plans-wt
uv run --with ruff ruff check .
uv run mypy packages/
```
**Expected:** ruff clean; mypy error count does NOT increase above the ~540 baseline (this fatia adds no backend code beyond a possible `response_model` annotation from Task 1).

- [ ] **Step 5: Update spec docs.** In `docs/smartPIDv2.md` document the web Simulator page (preset selector, dynamics sliders, disturbance inject/remove, twin output/mode, auto-SP/auto-disturbance toggles, start/stop, persistent SIMULATION MODE banner, live twin trend). In `docs/identidade_visual_ISA101.md` note the SIMULATION MODE banner uses the desaturated `--alarm-diag` strip (never confused with the real process; saturated/alarm colors reserved for abnormal states only).

- [ ] **Step 6: Commit.** `docs(web): document web simulator page + SIMULATION MODE banner semantics`

---

## Self-Review

- [ ] **Backend untouched.** No new endpoints/models/migrations; only a possible `response_model` annotation added in Task 1 if the audit found a gap. Every call uses an existing `routers/simulator` route.
- [ ] **Real routes only.** Output = `POST /api/simulator/{controller_id}/co` (body `SimulatorPIDSPRequest`, `sp` carries CO%); mode = `POST /api/simulator/{controller_id}/pid/mode`; preset = `POST /api/simulator/preset`; params = `PUT /api/simulator/parameters`; disturbance = `POST /api/simulator/disturbance` + `DELETE /api/simulator/disturbance/{controller_id}`; auto = `PUT /api/simulator/{controller_id}/auto-sp` + `PUT /api/simulator/{controller_id}/auto-disturbance`; start/stop = `POST /api/simulator/start|stop`; status = `GET /api/simulator/status`. No invented endpoints (`/simulator/output`, `/simulator/mode` are NOT used).
- [ ] **Canonical names consumed, not redefined:** `apiGet/apiPost/apiPut/apiDelete`, `ApiError`, generated OpenAPI types, `useRealtime`/`StatusData`, `RealtimeTrend`, `--alarm-diag`.
- [ ] **SIMULATION MODE labeling** is persistent at the top of the page (desaturated `--alarm-diag`, `role="status"`), so the twin is never confused with the real process.
- [ ] **WS live twin** flows through `useRealtime().lastStatus` (coalesced, keyed by loop id); REST `GET /simulator/status` supplies the config snapshot; `onResync` refetches after reconnect.
- [ ] **Required coverage present:** preset selector ✓, dynamics sliders ✓, disturbance inject/remove ✓, twin output + mode ✓, start/stop ✓, auto-disturbance + auto-sp toggles ✓.
- [ ] **Tests:** Vitest covers preset selector, sliders, disturbance controls, auto toggles, output/mode, control panel, status hook, and unauthenticated rejection; Playwright covers apply-preset→trend-response and inject-disturbance→visible-step→removal.
- [ ] **Acceptance:** preset changes visible dynamics in telemetry (live trend keeps streaming the twin) ✓; disturbance reflects in trend and removal returns to normal (Remove disabled again) ✓; output/mode controllable (CO disabled in AUTO) ✓; auto-toggles enable/disable with default bounds ✓.
- [ ] **TDD discipline:** every component/hook has a red→green→commit cycle; bite-sized steps.
- [ ] **Single-admin auth:** negative test asserts **401** when unauthenticated (not 403 by role), per contract §1 RBAC removal.
- [ ] **Branch:** all work on `feat/web-fatia5-simulator` from `main`; conventional commits, no attribution trailers; merge only on explicit approval.
- [ ] **Spec docs updated** (`docs/smartPIDv2.md`, `docs/identidade_visual_ISA101.md`).
