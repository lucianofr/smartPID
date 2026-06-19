# Web HMI (React/Vite) — Implementation INDEX & TODO Tracker

> **Purpose.** Single tracker for the sequential, subagent-driven execution of the 8
> Web HMI fatia plans. Mark a task `- [x]` when its plan task is fully executed (tests
> green + committed). Mark a fatia **DONE** when all its tasks are checked, its branch is
> reviewed, and it is merged to `main` with user approval.
>
> **Shared anchors (read before executing any fatia):**
> - [`_web-hmi-foundation-contract.md`](./_web-hmi-foundation-contract.md) — canonical package
>   layout, WS envelope + `useRealtime` types, global constraints, GAP register, order.
> - [`_web-hmi-backend-surface.md`](./_web-hmi-backend-surface.md) — real backend paths,
>   endpoints, models, event topics (ground every backend reference here).
>
> **Specs (source):** umbrella `2026-06-18-web-hmi-react-migration-design.md`,
> design-system `2026-06-18-web-frontend-design-system-design.md`, per-fatia
> `2026-06-18-web-fatiaNN-*-design.md`.

---

## How to execute (protocol)

1. **One fatia at a time, in order** (0+1 → 2 → 3 → 4 → 5 → 6 → 7 → 8). Each fatia depends on 0+1; later ones add deps (see table).
2. **New dedicated branch from `main`** per fatia (name given in each section). Never reuse another fatia's branch, never commit to `main` directly, never touch `feat/windows-installers`. Merge to `main` only with explicit user approval.
3. **Subagent-driven** (`superpowers:subagent-driven-development`): fresh subagent per task, two-stage review between tasks. Subagents use `model: opus`.
4. **TDD**: each task is failing test → red → minimal impl → green → commit (conventional commit, no attribution trailer).
5. On finishing a fatia: save `.claude/docs/estado-atual.md`, mark the fatia **DONE** here, **stop**, and wait for the user.

## Preconditions (do BEFORE Fatia 0+1) — from the migration handoff

These are NOT fatia tasks; they land on `main` first (see `.claude/docs/handoff-web-hmi-migration-2026-06-18.md`):

- [x] **P1** — Merge `fix/backend-security-hardening` → `main` (TD-001/002/003/005: project auth, path sanitization, `/commands/tuning` guardrails, upload 413). *All fatias assume this.* — DONE merge `1f90c2b`
- [x] **P2** — Merge `feat/pid-optimization-enable-toggle` → `main` (`Controller.optimization_enabled`, `POST /commands/optimization`, `AIWorker.set_enabled`). *Fatia 2 GAP-2b depends on this.* — DONE merge `903f7a6` (DTO conflict resolved: kept both TuningCommand + OptimizationCommand)
- [x] **P3** — **TD-007** single-admin collapse: replace `require_operator|supervisor|admin` with one `require_authenticated_admin`; **remove `routers/users`** + `POST /register`; keep admin login + bootstrap. *Fatia 7 assumes this.* — DONE merge `cb8316d` (reviewed: 66 handlers, no route ungated, no 403-by-role)
- [ ] **P4** — **TD-004** CORS/bind/headers (some overlaps Fatia 0+1 Task 5 — coordinate; do not double-implement).

## Progress summary

| Fatia | Plan | Branch | Deps | Tasks | DONE |
|---|---|---|---|---|---|
| 0+1 | [foundation-dashboard](./2026-06-18-web-fatia01-foundation-dashboard.md) | `feat/web-fatia01-foundation-dashboard` | — | 12 | ⬜ |
| 2 | [commands-loop-config](./2026-06-18-web-fatia2-commands-loop-config.md) | `feat/web-fatia2-commands-loop-config` | 0+1 | 8 | ⬜ |
| 3 | [alarms](./2026-06-18-web-fatia3-alarms.md) | `feat/web-fatia3-alarms` | 0+1 | 8 | ⬜ |
| 4 | [multitrend-stats-export](./2026-06-18-web-fatia4-multitrend-stats-export.md) | `feat/web-fatia4-multitrend-stats-export` | 0+1, (2) | 12 | ⬜ |
| 5 | [simulator](./2026-06-18-web-fatia5-simulator.md) | `feat/web-fatia5-simulator` | 0+1, (2) | 12 | ⬜ |
| 6 | [executive-dashboard](./2026-06-18-web-fatia6-executive-dashboard.md) | `feat/web-fatia6-executive-dashboard` | 0+1, (4),(2) | 10 | ⬜ |
| 7 | [settings-connection-projects](./2026-06-18-web-fatia7-settings-connection-projects.md) | `feat/web-fatia7-settings-connection-projects` | 0+1 | 11 | ⬜ |
| 8 | [themes-faceplate](./2026-06-18-web-fatia8-themes-faceplate.md) | `feat/web-fatia8-themes-faceplate` | 0+1, 2 | 10 | ⬜ |

**Total: 83 tasks across 8 fatias.**

---

## Fatia 0+1 — Foundation + Live Dashboard  ⬜ DONE-when-all-checked
Branch `feat/web-fatia01-foundation-dashboard` · deps: none (linchpin — creates the canonical scaffold)

- [ ] Task 1 — Branch + backend `response_model` audit for fatia-0+1 routers
- [ ] Task 2 — `ConnectionManager` (resilient async broadcast)
- [ ] Task 3 — `RealtimeBridge` — single non-blocking bus consumer + topic→envelope mapping
- [ ] Task 4 — `/ws/realtime` endpoint — first-message auth, Origin validation, coalescing/lossless queue
- [ ] Task 5 — Wire RealtimeWS, security headers, dev CORS, SPA mount into `create_app`
- [ ] Task 6 — Frontend scaffold (`packages/smart_pid_web/`) — Vite/React/TS toolchain
- [ ] Task 7 — Theme tokens + ThemeProvider (design-system §2.0 / §2.2)
- [ ] Task 8 — API client + AuthContext + LoginPage (consumes `POST /auth/login`)
- [ ] Task 9 — `envelope.ts` (CANONICAL) + `RealtimeProvider` + `useRealtime` (CANONICAL)
- [ ] Task 10 — `AnalogBar`, `ControllerCard`, `RealtimeTrend`, shell, `DashboardPage`
- [ ] Task 11 — Playwright e2e — login → dashboard receives a `status` frame
- [ ] Task 12 — Spec upkeep + full verification + state save

## Fatia 2 — Commands + Loop Config  ⬜ DONE-when-all-checked
Branch `feat/web-fatia2-commands-loop-config` · deps: 0+1

- [ ] Task 1 — Investigation: confirm real command/AI mechanism (GAP-2a, GAP-2b)
- [ ] Task 2 — Types + validation (pure, fully unit-tested)
- [ ] Task 3 — Command API wrappers + mutation hooks
- [ ] Task 4 — AI controls hooks (start/stop/pause/status + recommendation)
- [ ] Task 5 — `CardControls` inline row + extend canonical `ControllerCard`
- [ ] Task 6 — `LoopConfigDialog` (PID / IA / Limites)
- [ ] Task 7 — Apply-tuning confirmation guard + AI panel
- [ ] Task 8 — Wire into dashboard + Playwright e2e + specs

## Fatia 3 — Alarms  ⬜ DONE-when-all-checked
Branch `feat/web-fatia3-alarms` · deps: 0+1

- [ ] Task 0 — Investigate backend alarm surface & regenerate OpenAPI types
- [ ] Task 1 — Alarm domain types + severity helpers (ISA-101 redundant coding)
- [ ] Task 2 — Alarm data hooks (active query + ack mutations + WS trigger)
- [ ] Task 3 — AlarmPanel (virtualized active list, dedupe, sort/filter, ack)
- [ ] Task 4 — AlarmBar (persistent shell footer: counts, blink, ack-all)
- [ ] Task 5 — Per-loop alarm-config form (limits/severities, persists + retriggers)
- [ ] Task 6 — Playwright e2e: alarm fires → appears → ack → ACKNOWLEDGED (not removed); clear only after condition ceases
- [ ] Task 7 — Specs upkeep + full-suite verification

## Fatia 4 — Multi-trend + Stats + Export  ⬜ DONE-when-all-checked
Branch `feat/web-fatia4-multitrend-stats-export` · deps: 0+1, (recommended after 2)

- [ ] Task 1 — View types + signal catalog (pure, no I/O)
- [ ] Task 2 — Series aggregation + selection (pure)
- [ ] Task 3 — Min/max decimation with window cap (pure, performance-critical)
- [ ] Task 4 — Live model hook (ring buffers from `useRealtime.lastStatus`)
- [ ] Task 5 — Stats hooks + formatting (REST `/controllers/stats` + live `lastStats`)
- [ ] Task 6 — History query hook (`GET /history/{controller_id}`)
- [ ] Task 7 — Export hook — create → poll → download (GAP-4a handled)
- [ ] Task 8 — Chart + selector + stats panel components
- [ ] Task 9 — History + Export UI components
- [ ] Task 10 — MultiTrendPage + route wiring (bento layout)
- [ ] Task 11 — Playwright e2e (multiple live series + export download)
- [ ] Task 12 — Response-model audit + spec upkeep + final verification

## Fatia 5 — Simulator  ⬜ DONE-when-all-checked
Branch `feat/web-fatia5-simulator` · deps: 0+1, (recommended after 2)

- [ ] Task 1 — OpenAPI audit + generated types + typed simulator API wrapper
- [ ] Task 2 — SimulationModeBanner (never confuse twin with real process)
- [ ] Task 3 — PresetSelector
- [ ] Task 4 — DynamicsSliders (gain / dead-time L / tau1 / tau2)
- [ ] Task 5 — DisturbanceControls (inject / remove)
- [ ] Task 6 — TwinOutputModeControl (CO entry + MAN/AUTO mode)
- [ ] Task 7 — AutoToggles (auto-SP and auto-disturbance)
- [ ] Task 8 — Status query + mutations hooks
- [ ] Task 9 — SimulatorControlPanel + StartStopControl (compose the left panel)
- [ ] Task 10 — SimulatorPage + route + nav
- [ ] Task 11 — Playwright e2e — preset → trend response; disturbance → visible step
- [ ] Task 12 — Negative-auth + full-suite + lint + spec docs

## Fatia 6 — Executive Dashboard  ⬜ DONE-when-all-checked
Branch `feat/web-fatia6-executive-dashboard` · deps: 0+1, (recommended after 4 & 2)

- [ ] Task 1 — Investigation + branch + types preflight
- [ ] Task 2 — Period window (`src/lib/period.ts`)
- [ ] Task 3 — KPI normalization, aggregation, formatting (`src/lib/kpi.ts`)
- [ ] Task 4 — Data hooks (`src/api/executive.ts`)
- [ ] Task 5 — `ExecutiveKPICard` (`src/components/ExecutiveKPICard.tsx`)
- [ ] Task 6 — Presentational sub-components (health, period, tuning rec)
- [ ] Task 7 — `ExecutiveDashboardPage` wiring
- [ ] Task 8 — Page integration test: numeric assertion vs mocked REST (Vitest)
- [ ] Task 9 — Playwright e2e: dashboard loads + updates live
- [ ] Task 10 — Full suite, lint, build, spec docs

## Fatia 7 — Settings + Connection + Projects  ⬜ DONE-when-all-checked
Branch `feat/web-fatia7-settings-connection-projects` · deps: 0+1 · **mono-user: no users/RBAC**

- [ ] Task 0 — Branch, precondition check, OpenAPI types refresh
- [ ] Task 1 — App preferences model + `useSettings` hook
- [ ] Task 2 — SettingsForm + SettingsPage
- [ ] Task 3 — OPC connection data layer — `opcuaApi.ts` + `useOpcua.ts`
- [ ] Task 4 — ConnectionPanel + TagBrowser + ConnectionPage
- [ ] Task 5 — Project data layer — `projectApi.ts` + `useProjects.ts`
- [ ] Task 6 — Backend contract tests — auth required + credential boundary
- [ ] Task 7 — ProjectList + ProjectImportDropzone + ProjectsPage
- [ ] Task 8 — WelcomeDialog (post-login project picker)
- [ ] Task 9 — End-to-end (Playwright) — connection, projects, negative auth
- [ ] Task 10 — Specs upkeep + final verification

## Fatia 8 — Themes + Faceplate  ⬜ DONE-when-all-checked
Branch `feat/web-fatia8-themes-faceplate` · deps: 0+1, 2 · **closes total parity → PySide6 retires**

- [ ] Task 1 — Branch + theme registry scaffolding
- [ ] Task 2 — Persistence test + ThemeSwitcher
- [ ] Task 3 — Complete the 4 remaining theme token blocks
- [ ] Task 4 — Per-theme contrast gate (WCAG AA + alarm matrix)
- [ ] Task 5 — Pure scale-mapping helper (PV → bar fraction)
- [ ] Task 6 — Instrument AnalogBar (value/scale/alarm reflect real data)
- [ ] Task 7 — uPlot per-palette theming
- [ ] Task 8 — Faceplate widget — render by mode/state
- [ ] Task 9 — Visual regression snapshots per theme + faceplate (Playwright)
- [ ] Task 10 — Full suite, lint, build, parity note, PR

---

## Cross-cutting reconciliations (verified against real backend — carry these into execution)

The plan-writers grounded every reference in real code. These are the deltas between the
idealized contract and the actual backend — already handled in the named plans, restated
here so they are not lost during execution:

- **Stats field naming (Fatia 4 + 6):** REST `StatsResponse` uses
  `std_dev / total_variation / variability_sp / variability_range / sample_count`; the WS
  `StatsData` uses `sigma / tv / var_sp / var_range`. Same metrics, different keys — unify in
  `kpi.ts` (Fatia 6) and the stats hook (Fatia 4).
- **Alarm WS payload (Fatia 3, GAP-3b):** real `EVENT.ALARM.*` =
  `{controller_id, alarm_type, priority, transition, value, limit, timestamp}` (no `alarm_id`/`state`).
  Treat the WS `alarm` frame as a **refetch trigger** for `GET /alarms/active` (backend = truth).
- **Alarm enum (Fatia 3, GAP-3a):** real `AlarmState` = `UNACKNOWLEDGED / ACKNOWLEDGED / CLEARED_UNACK`;
  priorities `CRITICAL/WARNING/ADVISORY/LOG`; types `HIHI/HI/LO/LOLO/DV_HI/DV_LO`. Ack ≠ clear.
- **Commands bodies (Fatia 2):** setpoint/output body key is `value` (not `setpoint`/`output`);
  `controller_id` in BODY for setpoint/mode/output/tuning/optimization, in PATH for
  apply-tuning/recommendations/ai-actions; AI start/stop/pause are **POST**; apply-tuning takes
  no body + clamps server-side; 9 `ControllerMode` incl. BYPASS.
- **GAP-2a (Fatia 2):** PID params via `POST /commands/tuning {controller_id,kp,ti,td}` (forward-compatible with the typed `TuningCommand` from hardening). No `/commands/pid/params`.
- **GAP-2b (Fatia 2):** inline "enable" → `POST /commands/optimization {controller_id,enabled}` labeled **"Enable AI Optimization"** (the optimizer, not a PID block). The only literal `pid/enable` route is simulator-scoped — never use it for production.
- **AI-engine persistence GAP (Fatia 2):** no `ai_config` field on `ControllerCreate/Update` and no `/ai/config` route → engine change (NONE/FUZZY/RL) rendered **disabled-with-tooltip**; live engine readable via `GET /controllers/{id}/ai/status`. Not invented.
- **Simulator (Fatia 5):** output `POST /simulator/{id}/co` reuses `SimulatorPIDSPRequest {controller_id, sp}` (sp 0–100 carries CO%); mode `POST /simulator/{id}/pid/mode`; dynamics `PUT /simulator/parameters` (`gain/tau1/tau2/dead_time`); presets enum `FLOW/PRESSURE/LEVEL/TEMPERATURE/CUSTOM`; `AutoSPRequest{enabled,sp_min_pct,sp_max_pct}`, `AutoDisturbanceRequest{enabled,max_amplitude_pct}`, disturbance type `step|noise`.
- **GAP-4a (Fatia 4):** no `GET /export/list` → export = `POST /export` → `GET /export/{id}` poll → `/download`; export-**history listing scoped out**. History via `GET /history/{controller_id}` (PATH required; `start/end/limit`).
- **Fatia 6:** `GET /alarms/ai-history` requires `start` AND `end` ISO params and lacks a `response_model`; `GET /commands/tuning-recommendations/{id}` returns **404 = "no recommendation"**; loop list is `GET /controllers` (not `/active`); AI status/history are **per-loop** (`/controllers/{id}/ai/status|history`).
- **Fatia 7:** no admin password-change endpoint (out of scope); `GET /project/download` streams the **active** project only (per-name download not supported — GAP, not invented); `/project/*` auth is a **precondition** from `fix/backend-security-hardening`; negative auth test asserts **401** (not 403-by-role).
- **`response_model` gaps:** 25 endpoints lack `response_model` (backend map §4). Each fatia audits the routers it consumes; legit `FileResponse` streams are left as-is.
- **TD-006 (WS auth):** closed **by-design** in Fatia 0+1 (first-message auth + `Origin` validation, not `?token=`).

## Notes
- `packages/smart_pid_web/` is a Node package (not a `uv` workspace member); `smart_pid_hmi` (PySide6) stays frozen until parity (after Fatia 8), then retires.
- 3 pre-existing `test_opcua_endpoint.py::TestProjectServiceOPCUA` failures (Py3.14) are environmental — not regressions; do not "fix" inside a fatia.
