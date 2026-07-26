# PRD — Web HMI Migration (PySide6 → React/Vite)

**Project:** Smart PID Edge Platform v2
**Scope:** Replacement of the legacy PySide6 desktop HMI with a browser-first React/Vite web client, reusing the existing headless backend essentially intact.
**Status:** Proposed
**Authority documents:**
- Architecture: `docs/superpowers/specs/2026-06-18-web-hmi-react-migration-design.md` (umbrella)
- Visual/design: `docs/superpowers/specs/2026-06-18-web-frontend-design-system-design.md`
- Per-slice detail: `docs/superpowers/specs/2026-06-18-web-fatia{01..8}-*-design.md`
- Original product spec: `docs/smartPIDv2.md`, `docs/smartPID.md`

---

## Problem Statement

The Smart PID Edge Platform today ships with a PySide6 (Qt for Python) desktop HMI. The backend — a headless daemon hosting a velocity-form PID engine, Fuzzy + Reinforcement-Learning tuning, OPC-UA I/O, alarms, RBAC, an SQLite historian and a FastAPI REST API — is mature and complete. The HMI, however, is coupled to a heavy desktop runtime that constrains who can operate the plant and from where:

- **Install friction.** Every operator workstation needs a Python + PySide6 stack, native Qt binaries and dependency alignment with the backend. This blocks casual, cross-machine, or quick handover use.
- **Deployment / upgrade pain.** Distributing and upgrading a desktop client across a control room is operationally heavy compared with serving a static web bundle from the backend itself.
- **Platform lock-in.** PySide6 ties the operator surface to desktop OSes that ship a compatible Qt runtime; mobile tablets, thin clients and locked-down kiosks are effectively excluded.
- **Parallel maintenance burden.** New UI work has to land in the PySide6 client while the team simultaneously wants to modernize the operator experience.

The platform does not need a new control engine, a new AI stack, a new bus, or a new persistence model — those already exist and work. It needs the **operator surface** to become a modern, browser-served, real-time web application while the backend stays intact and the legacy client is frozen and then retired at parity.

## Solution

Introduce a new **`smart_pid_web`** package (React + Vite + TypeScript) into the existing monorepo, served as a single-origin static SPA by the backend itself. The backend gains exactly **one** new component — a **RealtimeWS bridge** that turns the internal EventBus into a WebSocket channel — plus a small amount of plumbing (static-file mount, dev-only CORS allowlist, typed `response_model` audit). No engine, worker, OPC-UA, fuzzy/RL, persistence or auth logic is rewritten.

The migration is decomposed into **8 slices** (Fatia 0+1 through Fatia 8), each a self-contained increment of parity with the PySide6 HMI, each delivered on its own branch off `main`. Fatia 0+1 establishes the end-to-end foundation (WebSocket bridge + login + live dashboard); subsequent slices add commands, alarms, multi-trend/stats/export, the simulator, the executive dashboard, settings/projects, and finally themes/faceplate. Once full parity is reached, the PySide6 client is retired.

**Product decisions locked during brainstorming (2026-06-18):**
- Browser-only delivery — the user opens `localhost` manually; no Tauri/Electron wrapper.
- **Single-admin (mono-user) model** — RBAC is collapsed to one authenticated admin role; multi-user CRUD and per-role UI gating are dropped.
- Single-origin SPA — backend serves the build; no cross-origin deployment in production.
- Bind default `127.0.0.1` — the HMI is intentionally not exposed to the LAN.

---

## User Stories

### Foundation & Access (Fatia 0+1)

1. As a process operator, I want to open the Smart PID HMI in any modern browser pointed at `localhost`, so that I can operate the plant without installing desktop software.
2. As a process operator, I want to log in with my admin credentials before reaching any feature, so that an unauthenticated user cannot operate the plant.
3. As a process operator, I want protected routes to redirect to login when my JWT is missing or expired, so that direct-URL access cannot bypass authentication.
4. As a process operator, I want to log out explicitly and have my token cleared from the client, so that a shared workstation cannot be abused after I step away.
5. As a process operator, I want the web HMI to reconnect to the backend automatically when the WebSocket drops, so that transient network glitches don't cost me visibility.
6. As a process operator, I want the dashboard to re-synchronize state (controllers, active alarms, AI status) via REST after a WebSocket reconnect, so that any events missed during the gap are recovered instead of silently stale.
7. As a process operator, I want the SPA to be served by the backend itself on a single origin, so that there is no separate web server to install or configure.
8. As a developer, I want the SPA production build mounted by the backend via static files after the API routers, so that deployment is one process with no CORS in production.
9. As a developer, I want the Vite dev server at `127.0.0.1:5173` to proxy `/api` and `/ws` to the backend at `:8000`, so that I can iterate on the frontend without CORS friction.
10. As a process operator, I want the WebSocket to reject missing/invalid/expired tokens with a clear close code, so that authentication failures are diagnosable rather than silent.
11. As a process operator, I want the WebSocket to validate the request origin, so that a malicious page in another browser tab cannot connect to my backend.

### Live Dashboard (Fatia 0+1)

12. As a process operator, I want a card per active loop showing PV, SP, CO, mode and alarm state at a glance, so that I can scan plant health in one view.
13. As a process operator, I want loop cards to update in real time over WebSocket (not polling), so that the numbers reflect the actual process within milliseconds.
14. As a process operator, I want to select a loop card and see its real-time trend chart update at a high frame rate, so that I can judge process dynamics visually.
15. As a process operator, I want the trend chart to keep a bounded sliding window of recent data with configurable size, so that the chart never freezes from unbounded data growth.
16. As a process operator, I want the OPC-UA connection status to be visible per loop, so that I immediately know when telemetry is stale because the PLC link is down.
17. As a control engineer, I want trend lines for PV, SP and CO to be visually distinguishable (PV gray, SP blue/info, CO amber) consistently across themes, so that I never confuse which series is which.
18. As a process operator, I want a slow or backgrounded client tab to drop stale status frames rather than backlog, so that returning to the tab shows current state, not a replay.
19. As a plant manager, I want the dashboard to remain responsive under high telemetry rates (target ~60 fps), so that operators can trust the screen during fast processes.
20. As a developer, I want the dashboard's live frame to be the enriched `STATUS` topic (PV/SP/CO/mode/error/saturated/Kp/Ti/Td) produced by the monitor worker, not the raw internal telemetry topic, so that the dashboard gets the same richness the PySide6 client already consumes.

### Commands & Loop Configuration (Fatia 2)

21. As a process operator, I want to change a loop's setpoint (SP) from the web UI, so that I can drive the process to a new target.
22. As a process operator, I want to switch a loop between Manual and Auto modes, so that I can take direct control or return control to the PID.
23. As a process operator, I want to manually drive the control output (CO) while in Manual mode, so that I can move the actuator directly.
24. As a control engineer, I want a per-loop configuration dialog showing PID parameters (Kp, Ti, Td, structure, anti-reset-windup limits, filters), so that I can fine-tune the controller.
25. As a control engineer, I want to choose the AI optimization strategy per loop (NONE / FUZZY / RL) and configure its parameters, so that each loop uses the most appropriate tuning method.
26. As a control engineer, I want to apply tuning changes only after an explicit confirmation step, so that I never push bad gains to a live process by accident.
27. As a control engineer, I want raw tuning parameters to be clamped to safe guardrails on the backend before being written, so that a typo can't destabilize a loop.
28. As a control engineer, I want to start, pause and stop the AI worker per loop, so that I control when automatic optimization is active.
29. As a control engineer, I want the AI worker's current state (running / paused / stopped) reflected in real time, so that I'm never confused about whether optimization is active.
30. As a control engineer, I want to enable or disable PID optimization per loop independently of Man/Auto mode, so that I can isolate the PID from the optimizer when needed.
31. As a process operator, I want write actions that the loop's current state forbids (monitor mode, OPC down, conflicting mode) to fail with a clear error, so that I get feedback instead of silent rejection.
32. As a control engineer, I want to register, edit and delete controllers from the web UI, so that I can manage the loop inventory without touching the database.
33. As a control engineer, I want to see per-loop tuning recommendations produced by the backend, so that I can act on data-driven suggestions.

### Alarms (Fatia 3)

34. As a process operator, I want alarms to appear in real time in a dedicated panel, so that I'm alerted the moment a limit is crossed.
35. As a process operator, I want a persistent alarm bar in the shell showing counts by severity, so that alarms are visible from any page.
36. As a process operator, I want to acknowledge an alarm individually, so that I can indicate I've seen it.
37. As a process operator, I want to acknowledge all active alarms at once, so that I can clear a flood efficiently.
38. As a process operator, I want acknowledging an alarm to **not** clear it, so that the alarm only disappears when the process condition actually returns to normal.
39. As a process operator, I want the alarm state machine to distinguish **active / acknowledged / cleared-unacknowledged / cleared-acknowledged**, so that I never lose track of an alarm that returned to normal before I saw it.
40. As a process operator, I want alarm floods to be deduplicated and the list virtualized, so that hundreds of simultaneous alarms don't freeze the browser.
41. As a control engineer, I want to configure per-loop alarm limits (HIHI/HI/LO/LOLO) and their severities, so that thresholds match the process's safety requirements.
42. As a control engineer, I want alarm configuration changes to alter actual alarm triggering immediately, so that adjustments take effect without a restart.
43. As a process operator, I want the UI to revalidate alarm state against the backend after each acknowledgement, so that local UI state never diverges from server truth.
44. As a process operator, I want alarm transitions delivered losslessly over WebSocket (no coalescing), so that I never miss an alarm transition because of frame dropping.

### Multi-trend, Statistics, History & Export (Fatia 4)

45. As a control engineer, I want a multi-trend page plotting multiple loops and signals simultaneously, so that I can correlate interactions between loops.
46. As a control engineer, I want zoom or pan on one trend to time-sync the others, so that I can inspect the same time window across multiple signals.
47. As a control engineer, I want to query historical data for any time window, so that I can investigate past incidents.
48. As a control engineer, I want per-loop performance statistics (IAE, ITAE, ISE, MSE, σ, TV, variability vs span and vs SP) computed by the backend, so that I can quantify loop health consistently.
49. As a control engineer, I want to export the currently displayed trend data to CSV, so that I can analyze it offline or share it.
50. As a plant manager, I want to export a formatted executive report (PDF) containing charts, statistics and the AI justification log, so that I can present performance to stakeholders.
51. As a control engineer, I want to export per-loop or plant-wide, so that exports match the scope of my analysis.
52. As a control engineer, I want large exports to run in the background without freezing the UI, so that I can keep working while the export is generated.
53. As a control engineer, I want to see a list of past exports available for download, so that I can retrieve a report I generated earlier.

### Simulator / Digital Twin (Fatia 5)

54. As a control engineer, I want to start a digital-twin simulator against a process preset (flow / level / pressure / temperature / custom SOPTD), so that I can validate control strategies before commissioning.
55. As a control engineer, I want to adjust simulator dynamics (gain, time constants, dead time) via sliders in real time, so that I can explore scenarios interactively.
56. As a control engineer, I want to inject load disturbances and measurement noise into the simulation, so that I can test the AI's robustness.
57. As a control engineer, I want to control the simulator's output and mode, so that I can drive the twin the same way I drive a real loop.
58. As a control engineer, I want auto-disturbance and auto-setpoint toggles, so that I can run unattended stress tests.
59. As a control engineer, I want the simulator context to be visually distinct from real-process context, so that I never confuse simulation with live operation.
60. As a control engineer, I want the simulator's process response to render in the same trend component as real loops, so that I have one consistent visualization.

### Executive Dashboard (Fatia 6)

61. As a plant manager, I want an executive dashboard showing plant-wide KPIs (% loops in AUTO, AI coverage, bad actors), so that I can assess plant health at a glance.
62. As a plant manager, I want a ranking of the worst-performing loops (highest IAE or variability), so that I can prioritize tuning effort.
63. As a plant manager, I want before/after AI comparison metrics, so that I can quantify the optimizer's ROI.
64. As a plant manager, I want KPI cards to update live from backend aggregations, so that the executive view reflects current operation rather than a stale snapshot.
65. As a plant manager, I want aggregation to happen on the backend (not heavy client-side computation), so that the executive dashboard stays fast even with many loops.
66. As a control engineer, I want to see per-loop tuning recommendations surfaced in the executive view, so that I can act on the worst actors directly.

### Settings, OPC Connection & Projects (Fatia 7)

67. As a system administrator, I want a settings page to manage application preferences, so that I can configure the HMI without editing files.
68. As a system administrator, I want to configure the OPC-UA endpoint (host, port, credentials) from the web UI, so that I can point the backend at the right PLC.
69. As a system administrator, I want to connect and disconnect the OPC-UA session explicitly, so that I control when the backend talks to the PLC.
70. As a control engineer, I want a modal OPC-UA tag browser with search, so that I can map internal variables (PV/SP/CO/Ti) to PLC NodeIDs without memorizing them.
71. As a system administrator, I want to manage `.spid` project files (list, new, open, import, download, delete) from the web UI, so that I can move configurations between machines.
72. As a system administrator, I want a welcome screen after login that lists the backend's projects, so that I can pick up where I left off.
73. As a system administrator, I want user credentials to live outside `.spid` project files (in a separate credential store), so that importing a project never leaks or overwrites credentials.
74. As a system administrator, I want malicious `.spid` uploads to be rejected (size cap, path sanitization), so that I can't accidentally compromise the backend.

### Themes & Faceplate (Fatia 8)

75. As a process operator, I want to switch between themes (Dark Room, ISA-101, MD3 dark, MD3 light, Ocean), so that I can match control-room lighting and corporate standard.
76. As a process operator, I want my theme choice to persist across sessions, so that I don't have to re-select it every time I open the HMI.
77. As a process operator, I want a faceplate widget per loop showing PV/SP/CO bar graphs, mode and alarm state, so that I have the classic controller detail view.
78. As a process operator, I want the analog bar to render real tick scales, SP markers and alarm-limit markers, so that I can read process values precisely.
79. As a process operator, I want numeric process values to use tabular monospace numerals with aligned decimals, so that digits never "jump" while I'm reading.
80. As a process operator working under ISA-101, I want color reserved exclusively for alarms (gray in normal state), so that the only luminous point on the screen is an abnormality.
81. As a visually impaired operator, I want every theme to meet WCAG AA contrast (≥ 4.5:1 for normal text), so that the HMI is readable in all themes.
82. As a keyboard-only operator, I want visible focus rings and full keyboard operability on every interactive control, so that I can run the HMI without a mouse.

### Cross-cutting / Non-functional

83. As a developer, I want the WebSocket bridge to never block the daemon's asyncio event loop, so that the PID engine keeps deterministic timing regardless of WS load.
84. As a developer, I want one slow WebSocket client to not affect the others, so that a frozen browser doesn't slow down the rest of the control room.
85. As a developer, I want frontend types to be generated from the backend's typed OpenAPI schema, so that REST contract drift is caught at compile time.
86. As a developer, I want the backend to bind to `127.0.0.1` by default (overridable via the existing host setting), so that the HMI is not unintentionally exposed to the LAN.
87. As a developer, I want the legacy PySide6 client to keep working unchanged during the migration, so that we can ship incrementally without breaking operators.
88. As a developer, I want the legacy PySide6 client to be removable once the web reaches full parity, so that we can retire the technical debt cleanly.
89. As a developer, I want the existing backend REST contract to be reused without breaking changes, so that the existing backend test suite continues to pass.
90. As a developer, I want the migration to introduce no new database tables and no schema changes, so that existing historians and `.spid` projects keep working.
91. As a developer, I want security hardening (CORS allowlist, trusted-host middleware, security headers) applied to the backend before exposing the SPA, so that the single-origin deployment is safe by default.
92. As a developer, I want each slice delivered on its own branch off `main`, so that integration stays reviewable and rollback is per-slice.

---

## Implementation Decisions

### Architecture (unchanged shape, additive only)

- **Hexagonal monorepo preserved.** `smart_pid_domain` (zero-infra models/enums/events/DTOs), `smart_pid_core` (headless daemon), `smart_pid_hmi` (legacy PySide6, frozen), and a new `smart_pid_web` (React/Vite/TS) package added in parallel to the legacy client.
- **Backend is reused essentially intact.** The only backend additions are the RealtimeWS bridge, the SPA static-file mount, dev-only CORS allowlist, security headers/middleware, and a `response_model` typing audit across routers. No engine, worker, OPC-UA, fuzzy/RL, alarm, persistence or auth logic is rewritten.
- **Dual realtime channels during transition.** The existing ZMQ PUB socket (`tcp://5555`) continues to serve the PySide6 legacy client; the new RealtimeWS serves the web client. Both are independent consumers of the same internal EventBus.
- **Single-origin production deployment.** The backend serves the SPA build via static files mounted **after** the API routers, so production needs no CORS. CORS becomes a dev-only allowlist (Vite at `127.0.0.1:5173`).

### Backend modules to add/modify (finer decomposition)

1. **BusBridge (NEW, deep)** — A second non-blocking consumer of the internal EventBus (analogous to the existing `TelemetryPublisher`). Subscribes to the topic prefixes that actually feed the web client: `STATUS.`, `ACTION.CTRL.`, `ACTION.AI.`, `EVENT.ALARM.`, `EVENT.SYSTEM`, `STATS.`. It does **not** subscribe to the internal-only `TELEMETRY.` topic. The subscriber's blocking ZMQ `recv` is offloaded via `zmq.asyncio` or a single-flight `run_in_executor` so the daemon's event loop is never blocked. There is exactly **one** shared consumer that fans out to all connected clients — never one `recv` loop per client.
2. **EnvelopeSerializer (NEW, pure, deep)** — Converts the frozen domain events coming off the bus into the single JSON envelope shape consumed by the web client: `{ type: "status"|"action"|"alarm"|"ai"|"stats", loop_id, seq, ts, data }`. `type: "status"` maps the enriched `STATUS.{id}` frame (PV/SP/CO/mode/error/saturated/Kp/Ti/Td). Pure function — fully unit-testable in isolation.
3. **QueuePolicy (NEW, pure, deep)** — Encapsulates the per-topic-class delivery policy: **last-value coalescing** for `STATUS`/`STATS` (a slow consumer drops old frames, never back-pressures the producer) and a **bounded lossless queue** for discrete events (`EVENT.ALARM`/`ACTION.AI`/`EVENT.SYSTEM`) where losing a transition would be a safety regression. On queue overflow the policy dictates closing the client socket so the client reconnects and re-syncs via REST. Pure logic, fully unit-testable.
4. **ConnectionManager (NEW, deep)** — Async registry of connected WebSocket clients. Provides thread-safe `connect` / `disconnect` / `broadcast`. Resilient broadcast: a failure on one socket does not propagate to others. Owns the per-client queue that the QueuePolicy feeds.
5. **WSAuth (NEW)** — Validates the existing JWT during the WebSocket handshake, reusing the existing auth/dependencies layer. Authentication is via a **short-lived ws-ticket** or **first message** — never via `?token=` query parameter (which leaks in logs and history). Validates the `Origin` header. On missing/invalid/expired token, the socket is closed with code `4401`.
6. **RealtimeWS endpoint (NEW)** — Thin FastAPI WebSocket route at `GET /ws/realtime`. Composes WSAuth, ConnectionManager and the BusBridge output. This is the only piece that knows about FastAPI's WebSocket primitives; everything above is framework-agnostic and independently testable.
7. **create_app wiring (MODIFY)** — Inject the EventBus into the app, register the RealtimeWS route, mount the SPA static files after the routers, register CORS allowlist (dev), trusted-host middleware and security headers. Bind default `127.0.0.1` (overridable via the existing host setting).
8. **response_model audit (MODIFY, shallow)** — Every router used by the web client must declare a Pydantic `response_model` so the OpenAPI schema is typed and the frontend can generate types from it. Surfaced as a Fatia 0+1 acceptance criterion and re-audited per subsequent slice.
9. **Tech-debt prerequisites (already designed, executed before Fatia 0+1):**
   - **TD-007 — RBAC collapse.** Replace the three role-specific dependencies (`require_operator`/`require_supervisor`/`require_admin`) with a single `require_authenticated_admin`. Remove the user-management CRUD router and per-role gating. Keep mandatory authentication everywhere; keep the credential store separate from `.spid` projects.
   - **TD-004 — CORS / bind / headers.** CORS allowlist (dev only), `TrustedHostMiddleware`, security headers (`X-Content-Type-Options`, `X-Frame-Options: DENY`, `Referrer-Policy`, baseline CSP), default bind `127.0.0.1`.
   - **TD-006 — WebSocket token.** Closed by design: the ws-ticket/first-message requirement and Origin validation are acceptance criteria of Fatia 0+1, not separate work.

### Frontend modules (all NEW, in `smart_pid_web`)

**Realtime layer**
1. **useRealtime hook (deep)** — Owns the WebSocket connection lifecycle: connect, envelope subscription, automatic reconnect with backoff. Exposes the latest state keyed by `loop_id` and `type`. Framework-friendly (React hook) but delegates all heavy logic to the pure modules below.
2. **EnvelopeParser (pure, deep)** — Parses and validates the JSON envelope, normalizes types, and detects sequence gaps via the `seq` field. Pure, fully unit-testable.
3. **RealtimeStateStore (deep)** — Maintains the per-`loop_id`/`type` last-value map; on a detected sequence gap it triggers a REST re-sync (refetch controllers, active alarms, AI status) rather than trusting potentially stale state.

**REST layer**
4. **apiClient (deep)** — Typed REST client built on TanStack Query. Types are generated from the backend's OpenAPI schema. Encapsulates authorization header injection, retry/backoff, error mapping and cache invalidation. All pages and command modules go through this single surface.

**Auth layer**
5. **AuthContext** — Holds the current session (token, username, expiry) and exposes login/logout/refresh.
6. **JWTStorage** — Abstracts where the token lives (in-memory vs. `localStorage`), so the storage strategy is swappable without touching consumers.
7. **RouteGuard** — Protects routes; redirects unauthenticated or expired sessions to login.

**Trend layer**
8. **useTrendChart (deep)** — Wraps uPlot behind a React-friendly interface; owns canvas lifecycle, series binding, axis configuration and render scheduling.
9. **SlidingWindowBuffer (pure, deep)** — Bounded N-points/N-seconds ring buffer with an explicit decimation policy that kicks in when the inbound stream exceeds the cap. Pure, fully unit-testable; keeps the chart jank-free regardless of producer rate.

**Alarm layer**
10. **AlarmStateMachine (pure, deep)** — Encodes the four-state ack-vs-clear transition logic (active / acknowledged / cleared-unacknowledged / cleared-acknowledged). Pure functions; the most heavily unit-tested module on the client.
11. **AlarmStore (deep)** — Deduplicates inbound alarms by `alarm_id`, maintains the active list in an order suitable for virtualized rendering, and revalidates against the backend after each acknowledgement.

**Command layer**
12. **CommandGateway (deep)** — Single surface for all writes: SP/mode/CO commands, raw and applied PID tuning, AI start/stop/pause, optimization enable/disable. Enforces the mandatory confirmation step for destructive writes, surfaces 409 (loop in incompatible state) and 502 (OPC down) branches, and clamps client-side input before sending.
13. **LoopConfigForm (deep)** — The per-loop configuration form (PID params, structure, ARW, filters; AI strategy and its parameters). Field-level validation, dirty-state tracking, confirmation gate.
14. **SimulatorControls** — Preset selection, dynamics sliders, disturbance inject/remove, output/mode control, auto-disturbance and auto-setpoint toggles. Reuses the existing simulator REST surface.

**Administrative layer**
15. **ProjectService (frontend)** — `.spid` project lifecycle: list, new, open, import (multipart upload), download, delete. Owns the welcome-after-login flow that lists backend projects.
16. **OPCConnectionService** — OPC-UA endpoint configuration, connect/disconnect, tag browse and search. Owns the modal tag-browser UX.

**Visual layer**
17. **ThemeProvider + TokenRegistry** — Implements theme switching via CSS custom properties (`[data-theme="…"]` on the root element). TokenRegistry holds the per-theme token maps; ThemeProvider persists the user's choice across sessions. Components reference semantic tokens only, never raw colors — this is what makes theme switching a no-op on component code.
18. **AnalogBar (signature component)** — The instrumented process bar: real tick scale, SP marker and alarm-limit markers drawn on the scale, value clamping, tabular-mono numeric readout with aligned decimal column. Per the design system, this is where the bulk of the visual-design budget is spent; everything else stays disciplined around it.
19. **Faceplate** — Composes three AnalogBars (PV/SP/CO) plus the mode label and alarm icon/border; exposes the same command actions as the loop config dialog via the CommandGateway.

**View layer (thin pages composing the above)**
20. Pages: Login, LiveDashboard, LoopConfig, AlarmPanel, MultiTrend, Simulator, ExecutiveDashboard, Settings, Projects, Faceplate. Pages are intentionally thin — they wire hooks and modules together and contain no business logic of their own.

### API contracts

- **REST reused as-is.** The web client consumes the existing routers: `auth` (login/refresh), `controllers` (list/get/CRUD/stats), `commands` (mode/setpoint/output/tuning/apply-tuning/tuning-recommendations/optimization), `ai` (start/stop/pause/status/history), `alarms` (active/ack/ack-all/alarm-config), `stats`, `history`, `export`, `simulator`, `opcua` (connect/disconnect/endpoint/browse/search), `project` (list/new/open/import/download/delete), `system`.
- **Known backend gaps to resolve before/within their slices:**
  - `POST /commands/tuning` currently bypasses guardrails (no clamp, weak authorization, untyped body). It must be hardened (clamp + `require_authenticated_admin` + typed body) before Fatia 2 exposes raw tuning.
  - No `GET /export/list` endpoint exists. Must be added (or an equivalent listing mechanism agreed) before Fatia 4 surfaces export history.
  - The PID-optimization enable toggle currently lives only on the simulator; confirm the real-loop enable path before Fatia 2 ships.
- **WebSocket envelope** — single JSON shape: `{ type, loop_id, seq, ts, data }`. `type` ∈ {`status`, `action`, `alarm`, `ai`, `stats`}. `loop_id` is `null` for global events (e.g. `EVENT.SYSTEM`). The client filters by `loop_id`/`type` and uses `seq` for gap detection.
- **OpenAPI is the contract.** Routers declare `response_model`; the frontend generates TypeScript types from the served OpenAPI document. Drift between backend and frontend becomes a compile-time error.

### Schema & persistence

- **No schema changes.** No new tables, no migrations. The historian, `.spid` project files, and the separate credential store all continue to work as today.
- **Retention unchanged** — process log retains 7 days, alarms retain 30 days.
- **Credential isolation preserved** — credentials live in their own store, never inside `.spid` files.

### Sequencing

Eight slices, each on its own branch off `main`, in order `0+1 → 2 → 3 → 4 → 5 → 6 → 7 → 8`. Fatia 0+1 is the end-to-end foundation (RealtimeWS + scaffold + login + live dashboard). Each subsequent slice has its own spec and implementation plan. The PySide6 client is retired only after Fatia 8 reaches full parity.

---

## Testing Decisions

### Philosophy

- **Test external behavior, not implementation details.** A test should fail because the system does the wrong thing for a real input, not because a developer renamed an internal helper. Tests assert on observable outcomes: HTTP responses, WebSocket envelopes delivered, UI state transitions, file downloads, rendered values.
- **Deep modules are tested through their public interface.** Pure modules (EnvelopeSerializer, QueuePolicy, EnvelopeParser, SlidingWindowBuffer, AlarmStateMachine) are tested as plain functions with edge-case inputs. Stateful modules (ConnectionManager, useRealtime, RealtimeStateStore, AlarmStore, apiClient) are tested through their public methods/hooks against fakes or in-memory doubles of their dependencies.
- **No tests of PySide6 internals.** The legacy client is frozen; its existing test suite is not extended.

### Full pyramid — every module and page gets tests

**Unit (logic, pure modules)**
- Backend: EnvelopeSerializer (every domain event → envelope), QueuePolicy (coalescing vs lossless, overflow → socket close), WSAuth (valid/invalid/expired/missing token, Origin validation), RealtimeWS route (handshake outcomes, close codes).
- Frontend: EnvelopeParser (parse + seq gap detection), SlidingWindowBuffer (cap, decimation trigger), AlarmStateMachine (all four states and legal/illegal transitions), LoopConfigForm field validation, TokenRegistry (per-theme token resolution), AnalogBar value/marker/clamp math, CommandGateway confirmation gate + 409/502 branch handling.
- Tooling: backend — `pytest` + `pytest-asyncio`; frontend — `Vitest`.

**Integration (module compositions)**
- Backend: RealtimeWS as a second consumer of a real EventBus — multi-client broadcast, drop-on-disconnect, last-value coalescing for STATUS/STATS, lossless delivery for alarm/ai/system, queue-overflow → socket close. Tested against the existing in-memory EventBus and a fake WebSocket client pool.
- Frontend: useRealtime against a fake WebSocket server (connect, reconnect with backoff, envelope routing, gap-triggered REST re-sync). apiClient against a mocked FastAPI (TanStack Query cache, auth header, retry, error mapping). AlarmStore against a stream of envelopes.
- Tooling: backend — `pytest` with the existing fixtures/conftest patterns (see `tests/core/integration/test_telemetry_publisher.py` for the direct prior art — RealtimeWS mirrors that publisher).

**End-to-end (acceptance gates, one per slice)**
- Playwright drives a real browser against the running backend. Each slice ships one E2E that proves its primary user-visible flow:
  - Fatia 0+1: login → dashboard receives live telemetry over WS; invalid token is rejected.
  - Fatia 2: change SP/mode → reflected in live status; apply-tuning writes only after confirmation.
  - Fatia 3: alarm fires → appears → ack changes state to "acknowledged" (does **not** clear); clear only after the condition ends.
  - Fatia 4: multi-trend receives multiple series; export triggers a real file download.
  - Fatia 5: preset applied → response visible in trend; disturbance injected → step visible.
  - Fatia 6: executive dashboard loads and updates live; KPIs numerically match the REST response.
  - Fatia 7: project list/new/open/import/download/delete; OPC browse returns tags.
  - Fatia 8: theme switch applies app-wide and persists across reload; faceplate renders PV/SP/CO + mode + alarm and accepts commands.

**Visual / accessibility regression (Fatia 8)**
- Per-theme visual snapshots at fixed breakpoints (320 / 768 / 1024 / 1440 px) to catch token regressions.
- Automated WCAG AA contrast check (≥ 4.5:1 normal text) per theme, plus ISA-101 color-semantics check (color appears only in alarm/abnormal states).
- Keyboard-only navigation audit per page (visible focus rings, tab order, no mouse-only flows).

### Prior art in the codebase

- **`tests/core/integration/test_telemetry_publisher.py`** — direct template for RealtimeWS integration tests (same EventBus, same "second consumer" shape).
- **`tests/core/unit/test_alarm_engine.py`** and the alarm-engine domain service — template for the frontend AlarmStateMachine's transition table.
- **`tests/hmi/`** — the PySide6 suite shows the breadth of behavioral coverage expected (per-page, per-widget, role/state transitions); the web suite should match that rigor page-for-page.
- **Existing backend pytest configuration** — `asyncio_mode = "auto"`, `testpaths = ["tests"]`; the `integration` marker gates tests needing external services (OPC-UA servers). RealtimeWS tests do **not** need that marker (in-memory EventBus + fake WS clients).

---

## Out of Scope

- **Rebuilding the control engine, AI, OPC-UA stack, simulator physics, or persistence.** These are reused as-is.
- **Replacing the EventBus** with another messaging substrate. The internal ZMQ inproc bus stays.
- **New database tables or schema migrations.** The historian, `.spid` projects and credential store are unchanged.
- **Multi-user / RBAC beyond the single-admin model.** Per-role UI gating, user CRUD and `POST /auth/register` are dropped from frontend scope (backend endpoints may remain dormant).
- **Desktop wrapper packaging** (Tauri / Electron). Browser-only at `localhost`.
- **Remote / LAN / multi-site access.** Bind is `127.0.0.1` by design.
- **Modifying the PySide6 legacy client.** It is frozen for the duration of the migration and retired at parity; no new features land there.
- **Simulator SVG dynamic overlay** and the **"Export Dynamics to Loop"** button — deferred to a later phase (per the project roadmap).
- **AI algorithm changes** (Fuzzy rule matrices, RL reward functions). The web client only operates the AI; it does not retune its internals.
- **Offline / installed-PWA mode.** Reloading the page restarts the realtime window; there is no client-side persistence of historical data.

---

## Further Notes

### Authority documents

- **Architecture authority:** `docs/superpowers/specs/2026-06-18-web-hmi-react-migration-design.md` (the umbrella spec). Any architectural decision in this PRD that conflicts with the umbrella spec is resolved in favor of the umbrella spec.
- **Visual / UI authority:** `docs/superpowers/specs/2026-06-18-web-frontend-design-system-design.md` plus the per-theme identity documents (`docs/identidade_visual_Dark.md`, `docs/identidade_visual_ISA101.md`, `docs/identidade_visual_MD3.md`). UI changes must keep these in sync per the project's "specs obrigatórias ao alterar UI" convention.
- **Per-slice detail:** the eight Fatia specs are the implementation-level elaboration of each slice and take precedence on slice-specific decisions.

### Theme coverage caveat

Five themes are in scope (Dark Room, ISA-101, MD3 dark, MD3 light, Ocean). Only three have dedicated identity documents (Dark / ISA-101 / MD3). The **Ocean theme must be derived from the design-system token contract** and carries the highest drift risk; it should be the last theme validated and may need a follow-up identity document if it diverges.

### Critical non-blocking constraint

The single most important non-functional requirement is that **the RealtimeWS bridge must never block the daemon's asyncio event loop.** The PID engine's deterministic scan timing is a safety property. The BusBridge's non-blocking consumer design (single shared consumer, async fan-out, last-value coalescing) is the mitigation; the RealtimeWS integration tests must explicitly assert event-loop latency stays bounded under client-side slowness.

### Mono-user collapse impact on Fatia 7

The original Fatia 7 spec assumed full three-tier RBAC. The mono-user decision collapses that slice's surface to: Settings page, OPC connection page, `.spid` project management, and the post-login welcome. User-management CRUD and per-role negative tests are dropped; everything else in Fatia 7 stands.

### Retirement of PySide6

The legacy client is removed only after Fatia 8 reaches full parity and the team has validated the web client operationally. Until then both clients coexist, consuming the same backend; the ZMQ `tcp://5555` channel remains live for PySide6.

### Open items to close before the relevant slice

- Harden `POST /commands/tuning` (guardrails + typed body + admin auth) before Fatia 2.
- Add `GET /export/list` (or equivalent) before Fatia 4 exposes export history.
- Confirm the real-loop PID-optimization enable path before Fatia 2 (currently only on the simulator).
