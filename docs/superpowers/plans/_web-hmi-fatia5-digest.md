# Fatia 5 digest — Simulator / Digital Twin (merged main `71e0ca7`, 2026-06-19)

Web Simulator page (`/simulator`) driving the Phase-4 digital-twin backend via the existing
`/simulator/*` REST routes + `/ws/realtime` status frames. **Zero backend change** (verified
`git diff main...HEAD -- '*.py'` empty). Forked main `4ea9df6`; merged `--no-ff` → `71e0ca7`
(parents `4ea9df6` + `28bbee8`). 13 commits. Gates: vitest 157/157 (44 files), tsc 0, vite build OK,
e2e simulator 2/2, lint 0 err (2 pre-existing warns).

## Delivered (all under `packages/smart_pid_web/src/features/simulator/` unless noted)
- `types.ts` — HAND-TYPED DTOs mirroring `smart_pid_domain/dtos/simulator.py` (generated/ gitignored → NO gen:api): `ProcessPresetName` union, Simulator{Preset,Parameters,Disturbance}Request, Auto{SP,Disturbance}Request, `ControllerSimStatus`, `SimulatorStatusResponse`, SimulatorPID{Mode,SP}Request, `CommandResponse` (==dtos/commands.py), `TwinMode`, `DisturbanceType`, `PRESET_NAMES`.
- `api.ts` — wrappers over real routes: start/stop/getStatus, setPreset, setParameters, injectDisturbance, clearDisturbance, **setCo (POSTs `{controller_id, sp: co}` — sp CARRIES CO%)**, setMode, setAutoSp, setAutoDisturbance.
- `SimulationModeBanner.tsx`/`.css` — persistent `role="status"` "MODO SIMULAÇÃO — digital twin"; `--alarm-diag` desat bg + `--on-alarm` text (twin never confused w/ real process).
- `PresetSelector.tsx` — controlled `<select>` (FLOW/PRESSURE/LEVEL/TEMPERATURE/CUSTOM).
- `DynamicsSliders.tsx`/`.css` — 4 range sliders (gain/dead_time L/tau1/tau2) + `.numeric` readouts; `onCommit(fullDynamics)` per change; exports `Dynamics`.
- `DisturbanceControls.tsx` — type step|noise + amplitude + inject/remove (Remove disabled when inactive).
- `TwinOutputModeControl.tsx` — CO% entry (clamp 0-100) + MAN/AUTO aria-pressed; CO input+Apply disabled in AUTO.
- `AutoToggles.tsx` — auto-SP / auto-disturbance `role="switch"`, defaults 30/70/10, preserve existing bounds.
- `StartStopControl.tsx` — Start/Stop + `data-testid="sim-running"`.
- `SimulatorControlPanel.tsx`/`.css` — composes all children; reads REST `data.controllers[id]` (plain numbers, NOT live FFSignal); `disturbanceActive=step_active||noise_active`; twinMode from `pid_mode` (0=MAN/1=AUTO); **debounced params (250ms trailing, cleanup on unmount)**; loading fallback `role="status"`.
- `useSimulatorStatus.ts` — `useQuery(['simulator','status'])` + `useRealtime().lastStatus` passthrough + `onResync`→invalidate.
- `useSimulatorMutations.ts` — 10 mutations, each `onSuccess` invalidates `['simulator','status']`.
- `twinTrend.ts` — pure `appendTwinSample(prev,status,cap=600)` (FFSignal `.value`; drop-from-front newest; equal-length; NaN-guarded monotonic x) + `useTwinTrend(id)` (appends once per per-loop `StatusData` frame — no render loop; resets on id change). `TrendData=[t,pv,sp,co]`.
- `src/pages/SimulatorPage.tsx`/`.css` — self-shells `<AppShell opcDown>` (own `/opcua/status` 5s poll), banner + 2-col (panel / `<RealtimeTrend data={useTwinTrend(id)}>`), loop selector when >1 loop.
- `src/App.tsx` — `/simulator` = `RequireAuth > SimulatorPage`. `src/components/shell/NavRail.tsx` — `{to:'/simulator',label:'Simulator'}`.
- `e2e/simulator.spec.ts` — reused StubWS harness + STATEFUL `/simulator/*` route doubles; preset→trend-alive + disturbance inject→Remove-enabled→remove→disabled (no sleeps). Docs: smartPIDv2 §15, identidade_visual_ISA101 §4.6.

## Contract facts (for downstream — verified vs real backend)
- **CO via `sp`:** `POST /simulator/{id}/co` body `SimulatorPIDSPRequest {controller_id, sp:0..100}` — `sp` CARRIES CO% (counterintuitive). Mode `POST /simulator/{id}/pid/mode` (MAN|AUTO). Preset `POST /simulator/preset`. Params `PUT /simulator/parameters` (gain/tau1/tau2?/dead_time). Disturbance `POST /simulator/disturbance` + `DELETE /simulator/disturbance/{id}` (type step|noise). Auto `PUT /simulator/{id}/auto-sp|auto-disturbance`. Start/stop `POST /simulator/start|stop`. Status `GET /simulator/status` → `{enabled,running,controllers:dict[int,ControllerSimStatus]}`. All `require_supervisor`; unauth→401 (NOT 403).
- **`--sp-N` is the real spacing scale** (`--sp-1..--sp-12` in tokens.css); `--space-N` does NOT exist — use `--sp-N` in all future CSS.
- **`RealtimeTrend` is presentational:** `RealtimeTrend({data: TrendData})`, `TrendData=[number[],number[],number[],number[]]` = `[t,pv,sp,co]`, `co` scale `[0,100]`; NO `loopId` prop. Feed via a live ring-buffer (see `twinTrend.useTwinTrend`).
- **DTOs HAND-TYPED** (no gen:api — `src/api/generated/` is gitignored & unimported); keep in lockstep if backend sim DTOs change.
- **Reusable:** `twinTrend.useTwinTrend(id)` is the single-loop live-trend ring buffer (first production consumer of `RealtimeTrend`).

## Deferred (non-blocking; full list in `.git/.../sdd/fatia5-minor-findings.md`)
2 Low FIXED pre-merge (`28bbee8`): SimulationModeBanner.css `--space-N`→`--sp-N`; panel loading `role="status"`.
Remaining LOW (none merge-blocking): hardcoded preset `id` (single instance/panel); `--text-secondary` no fallback; CO `draft=useState(co)` no prop re-sync (intentional operator entry buffer); useSimulatorStatus test asserts flat mock not real FFSignal (brief-mandated; hook is passthrough) + no explicit hook return types; `useRef` no-arg (React19 migration nit); twinTrend NaN x-fallback / page test stubs RealtimeTrend (live path covered by e2e); e2e StubWS/mockShell helpers duplicated across specs (repo convention).
