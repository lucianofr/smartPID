# Smart PID Web Rewrite — Agent-Controlled Chrome E2E Validation

## Mandatory execution contract

This runbook is the terminal validation gate for implementation plans `docs/superpowers/plans/2026-07-26-phase00-*.md` through `phase11-*.md`.

The validating agent MUST:

1. Use a real Chrome browser controlled through Chrome DevTools Protocol (Chrome DevTools MCP, `xd://browser`, or equivalent). Playwright mocks do **not** satisfy this runbook.
2. Run the real FastAPI daemon, real WebSocket, real SQLite databases, and internal simulator. Do not intercept, fulfill, or mock network requests.
3. Before each interaction: navigate/wait → capture an accessibility snapshot → interact using the current element reference. Refresh the snapshot after navigation or rerender.
4. Save one screenshot per procedure as `test-evidence/E2E-NNN-<slug>.png`.
5. Inspect browser console and failed network requests after every procedure. Record unexpected console errors or HTTP 4xx/5xx in Notes.
6. Mark every procedure in the results table. Continue after a failure unless boot/login is impossible.
7. Treat implementation as validated only when every procedure passes.

## Environment boot

From the rewrite worktree root:

```bash
rm -rf /tmp/spid-e2e
mkdir -p /tmp/spid-e2e/projects /tmp/spid-e2e/evidence
export SPID_JWT_SECRET='e2e-secret-not-for-production'
export SPID_USERS_DB_PATH='/tmp/spid-e2e/users.db'
export SPID_PROJECTS_DIR='/tmp/spid-e2e/projects'
export SPID_DB_PATH='/tmp/spid-e2e/project.spid'
export SPID_SIMULATOR_ENABLED='true'
export SPID_API_HOST='127.0.0.1'
export SPID_API_PORT='8000'
uv run python -m smart_pid_core
```

Readiness from a second terminal:

```bash
curl --fail --silent http://127.0.0.1:8000/system/status
```

Expected: HTTP 200 JSON system status. The backend logs that default `admin` / `admin` was seeded because the isolated users DB was empty.

Start the frontend:

```bash
cd packages/smart_pid_web
npm run dev
```

Expected: Vite serves `http://127.0.0.1:5173`; `/api/*` proxies to backend port 8000 and strips `/api`; `/ws/*` proxies WebSocket traffic.

Open Chrome at `http://127.0.0.1:5173`. Create `test-evidence/` in the worktree before saving screenshots.

## Procedures

### Authentication and shell

#### E2E-001 — Default admin login
- **Steps:** Open `/login`; fill `Usuário`=`admin`, `Senha`=`admin`; click `Entrar`.
- **Expected:** URL becomes `/`; `Loops` and live dashboard shell appear; network shows POST `/api/auth/login` 200 then GET `/api/auth/me` 200.
- **Evidence:** `test-evidence/E2E-001-admin-login.png`
- **Result:** [ ] PASS [ ] FAIL

#### E2E-002 — Invalid credentials
- **Steps:** Log out with `Sair`; enter `admin` / `senha-incorreta`; click `Entrar`.
- **Expected:** Remains `/login`; visible `Usuário ou senha inválidos`; password is not echoed; POST login is 401.
- **Evidence:** `test-evidence/E2E-002-invalid-login.png`
- **Result:** [ ] PASS [ ] FAIL

#### E2E-003 — Protected deep link
- **Steps:** While logged out navigate directly to `/alarms`; log in with admin/admin.
- **Expected:** Redirects to `/login` before auth; after auth returns to `/alarms` rather than `/`.
- **Evidence:** `test-evidence/E2E-003-deep-link.png`
- **Result:** [ ] PASS [ ] FAIL

#### E2E-004 — Logout invalidates session
- **Steps:** From an authenticated page click `Sair`; press browser Back; reload.
- **Expected:** `/login` remains; protected data is not visible; no authenticated WebSocket remains open.
- **Evidence:** `test-evidence/E2E-004-logout.png`
- **Result:** [ ] PASS [ ] FAIL

#### E2E-005 — Top navigation
- **Steps:** Login; inspect top bar; click `Loops`, `Trends`, `Alarms`, `Sim` in turn.
- **Expected:** Routes are `/`, `/multitrend`, `/alarms`, `/simulator`; no dead link or full-page error.
- **Evidence:** `test-evidence/E2E-005-top-nav.png`
- **Result:** [ ] PASS [ ] FAIL

#### E2E-006 — Command palette
- **Steps:** Press `k` outside a field; search `alarm`; activate `Ir para Alarmes`; repeat while cursor is inside an input.
- **Expected:** Palette opens and navigates to `/alarms`; typing `k` inside a field enters text and does not open the palette.
- **Evidence:** `test-evidence/E2E-006-command-palette.png`
- **Result:** [ ] PASS [ ] FAIL

#### E2E-007 — Configuration menu
- **Steps:** As admin click `Configurações` (`[cfg]`).
- **Expected:** `Projects`, `Settings`, `Connection`, `Users` are visible and navigate to their registered routes.
- **Evidence:** `test-evidence/E2E-007-cfg-menu.png`
- **Result:** [ ] PASS [ ] FAIL

### Simulator-backed operational dashboard

#### E2E-008 — Start internal simulator
- **Steps:** Navigate `Sim`; click `Iniciar simulador`; if shown, start its OPC-UA server.
- **Expected:** Status changes to running/online; `SIMULAÇÃO ATIVA` appears; mutation and refetch are 2xx.
- **Evidence:** `test-evidence/E2E-008-start-simulator.png`
- **Result:** [ ] PASS [ ] FAIL

#### E2E-009 — Create controller bound to twin
- **Steps:** Navigate `Loops`; click controller creation/config affordance; create `TIC-E2E` in DDC mode, scan 1000 ms, bind PV/SP/CO/Ti to nodes exposed by the simulator browser; click `Salvar`.
- **Expected:** `TIC-E2E` card appears; its values update without reload; no direct browser access to `.spid` occurs.
- **Evidence:** `test-evidence/E2E-009-create-controller.png`
- **Result:** [ ] PASS [ ] FAIL

#### E2E-010 — Single-row card strip
- **Steps:** Create or duplicate enough loops to overflow the 1440 px card row; scroll horizontally.
- **Expected:** Cards remain one row, never wrap; edge fade is visible; trend stays above the fold.
- **Evidence:** `test-evidence/E2E-010-card-strip.png`
- **Result:** [ ] PASS [ ] FAIL

#### E2E-011 — Live trend pen
- **Steps:** Select `TIC-E2E`; observe the trend for at least five scan intervals.
- **Expected:** PV/SP/CO advance; leading pen marker tracks the true latest sample without jumping to a decimated tail.
- **Evidence:** `test-evidence/E2E-011-live-pen.png`
- **Result:** [ ] PASS [ ] FAIL

#### E2E-012 — Trend time window
- **Steps:** Set `Janela de tempo` to `30` + `segundo`, then `2` + `minuto`.
- **Expected:** x range changes to the selected duration; no stale samples outside the range remain.
- **Evidence:** `test-evidence/E2E-012-time-window.png`
- **Result:** [ ] PASS [ ] FAIL

#### E2E-013 — Auto/manual scales
- **Steps:** Toggle `Autoescala` off; enter explicit PV min/max and CO min/max; apply; toggle on.
- **Expected:** Axes use exact manual bounds when off and data-driven bounds when on; form remains usable after switching.
- **Evidence:** `test-evidence/E2E-013-scales.png`
- **Result:** [ ] PASS [ ] FAIL

#### E2E-014 — Plotted CSV export
- **Steps:** Click `Exportar CSV` on dashboard trend; inspect Chrome downloads and file text.
- **Expected:** One CSV downloads; header identifies time/PV/SP/CO; rows match currently plotted timestamps and values.
- **Evidence:** `test-evidence/E2E-014-dashboard-csv.png`
- **Result:** [ ] PASS [ ] FAIL

#### E2E-015 — Faceplate consistency
- **Steps:** Compare selected card and faceplate PV/SP/CO/mode; wait one frame.
- **Expected:** Values and mode agree; IAE and `2σ/Range` use monospaced numerals; faceplate width is about 320 px at 1440.
- **Evidence:** `test-evidence/E2E-015-faceplate.png`
- **Result:** [ ] PASS [ ] FAIL

### Commands, configuration, and AI

#### E2E-016 — Setpoint write
- **Steps:** Enter a safe new `Setpoint`; click `Set setpoint`; confirm if prompted.
- **Expected:** POST command is 2xx; SP readout/trend moves to the requested value after REST/realtime confirmation.
- **Evidence:** `test-evidence/E2E-016-setpoint.png`
- **Result:** [ ] PASS [ ] FAIL

#### E2E-017 — AUTO/MAN and manual CO
- **Steps:** Change mode to MAN; enter CO and click `Set output`; return AUTO.
- **Expected:** CO write is disabled outside MAN; in MAN it is accepted and reflected live; mode returns AUTO without stale UI.
- **Evidence:** `test-evidence/E2E-017-mode-output.png`
- **Result:** [ ] PASS [ ] FAIL

#### E2E-018 — Supervisory visibility
- **Steps:** Open `Configurar TIC-E2E`; set mode SUPERVISORY.
- **Expected:** These six sections are absent: `PID Tuning`, `Scaling & Limits`, `Filters & IO`, `Shed & Safety`, `PID Structure`, `Integral Type`.
- **Evidence:** `test-evidence/E2E-018-supervisory.png`
- **Result:** [ ] PASS [ ] FAIL

#### E2E-019 — DDC visibility and scan rate
- **Steps:** Change execution mode to DDC; set scan rate; inspect the six sections; save and reopen.
- **Expected:** All six sections appear; saved scan rate and values persist.
- **Evidence:** `test-evidence/E2E-019-ddc.png`
- **Result:** [ ] PASS [ ] FAIL

#### E2E-020 — Tag mapping browser
- **Steps:** In controller config open tag browser; search simulator PV; select nodes for PV/SP/CO/Ti; save.
- **Expected:** Selected NodeIDs populate their exact fields and persist after reopen.
- **Evidence:** `test-evidence/E2E-020-tag-mapping.png`
- **Result:** [ ] PASS [ ] FAIL

#### E2E-021 — Tuning confirmation
- **Steps:** Click `Apply tuning`; verify no write yet; click `Confirm Write`.
- **Expected:** Confirmation dialog is explicit; apply request occurs only after confirmation; success invalidates/refetches tuning.
- **Evidence:** `test-evidence/E2E-021-tuning-confirm.png`
- **Result:** [ ] PASS [ ] FAIL

#### E2E-022 — AI configuration and lifecycle
- **Steps:** Choose FUZZY, an objective, process speed, dead time, min/max guardrails; save; click `Start`, `Pause`, `Stop`.
- **Expected:** State follows RUN→PAUSE→STOP independently of PID AUTO/MAN; no guardrail is lost.
- **Evidence:** `test-evidence/E2E-022-ai-lifecycle.png`
- **Result:** [ ] PASS [ ] FAIL

#### E2E-023 — AI explanation log
- **Steps:** Start AI and wait for at least one optimization cycle (`3 × dead time`).
- **Expected:** Terminal-style AI log receives a timestamped justification; trend shows an AI intervention tick at the same timestamp.
- **Evidence:** `test-evidence/E2E-023-ai-log.png`
- **Result:** [ ] PASS [ ] FAIL

### Alarms

#### E2E-024 — Quiet alarm footer
- **Steps:** Ensure no unacknowledged alarms; inspect global footer.
- **Expected:** CRIT/WARN/ADV/LOG counts are monochrome `--text-soft`; `ACK ALL` is disabled.
- **Evidence:** `test-evidence/E2E-024-quiet-footer.png`
- **Result:** [ ] PASS [ ] FAIL

#### E2E-025 — Force HI alarm
- **Steps:** As admin configure a HI threshold near current PV; use simulator disturbance to cross it.
- **Expected:** Footer count/color activates only for that severity; `/alarms` shows a row with severity glyph/text and non-color unacknowledged emphasis.
- **Evidence:** `test-evidence/E2E-025-hi-alarm.png`
- **Result:** [ ] PASS [ ] FAIL

#### E2E-026 — Acknowledge and clear lifecycle
- **Steps:** Click row `ACK`; then remove disturbance so PV clears the condition.
- **Expected:** State becomes ACKNOWLEDGED while active; after condition clears, active row resolves and history retains the event.
- **Evidence:** `test-evidence/E2E-026-ack-clear.png`
- **Result:** [ ] PASS [ ] FAIL

#### E2E-027 — Alarm history filters
- **Steps:** Open history tab; filter priority, type, and a range containing E2E-025.
- **Expected:** Matching event remains; nonmatching rows disappear; request includes start and end.
- **Evidence:** `test-evidence/E2E-027-alarm-history.png`
- **Result:** [ ] PASS [ ] FAIL

#### E2E-028 — Reduced-motion alarm state
- **Steps:** Use CDP to emulate `prefers-reduced-motion: reduce`; force another unacknowledged alarm.
- **Expected:** No blink/transition; static highlight, glyph/status, unacked badge, and assertive live region remain.
- **Evidence:** `test-evidence/E2E-028-alarm-reduced-motion.png`
- **Result:** [ ] PASS [ ] FAIL

### Multi-trend, statistics, and export

#### E2E-029 — Populate four slots
- **Steps:** Navigate Trends; assign four controllers and enable PV/SP/CO per slot.
- **Expected:** A 2×2 grid renders four charts with selected signals and no fifth slot.
- **Evidence:** `test-evidence/E2E-029-four-slots.png`
- **Result:** [ ] PASS [ ] FAIL

#### E2E-030 — Time-sync zoom/pan
- **Steps:** Zoom and pan chart 1 using Chrome input; inspect all x ranges.
- **Expected:** Other three charts converge to exactly the same x min/max without oscillation or repeated console errors.
- **Evidence:** `test-evidence/E2E-030-time-sync.png`
- **Result:** [ ] PASS [ ] FAIL

#### E2E-031 — Statistics
- **Steps:** Select a populated loop; inspect stats panel after data arrives.
- **Expected:** IAE, ISE, ITAE, MSE, σ, 2σ/SP, 2σ/Range and TV are present and numeric glyphs use Geist Mono.
- **Evidence:** `test-evidence/E2E-031-stats.png`
- **Result:** [ ] PASS [ ] FAIL

#### E2E-032 — Historical window
- **Steps:** Set history window `1` `hora`; click `Carregar histórico`.
- **Expected:** GET history succeeds; charts show the requested range and retain first/latest samples after decimation.
- **Evidence:** `test-evidence/E2E-032-history.png`
- **Result:** [ ] PASS [ ] FAIL

#### E2E-033 — Server export create/download
- **Steps:** Click the multitrend export action; wait for job completion; download.
- **Expected:** POST body has singular `controller_id`; GET status reaches complete; CSV downloads; no export-history list exists.
- **Evidence:** `test-evidence/E2E-033-server-export.png`
- **Result:** [ ] PASS [ ] FAIL

### Simulator and executive

#### E2E-034 — Simulator preset and dynamics
- **Steps:** In Sim choose a preset; change process gain/time constant/dead time; apply; observe trend response.
- **Expected:** REST status reflects values; response shape visibly changes after excitation without UI freeze.
- **Evidence:** `test-evidence/E2E-034-sim-dynamics.png`
- **Result:** [ ] PASS [ ] FAIL

#### E2E-035 — Disturbance and auto excitation
- **Steps:** Inject disturbance; clear it; toggle auto-SP and auto-disturbance.
- **Expected:** State indicators and twin trend reflect each action; toggles persist after status refetch.
- **Evidence:** `test-evidence/E2E-035-sim-disturbance.png`
- **Result:** [ ] PASS [ ] FAIL

#### E2E-036 — Executive KPIs
- **Steps:** Let loops run; open `/executive` from wordmark/palette.
- **Expected:** AUTO %, AI coverage, average IAE and variability contain real non-placeholder values; no NaN/blank.
- **Evidence:** `test-evidence/E2E-036-executive-kpis.png`
- **Result:** [ ] PASS [ ] FAIL

#### E2E-037 — Bad actors, ROI, health
- **Steps:** Inspect ranking; click its first row; return; inspect AI ROI and backend health.
- **Expected:** Ranking opens the matching loop; ROI shows data or explicit insufficient-data state; CPU/RAM/uptime and OPC health update.
- **Evidence:** `test-evidence/E2E-037-executive-details.png`
- **Result:** [ ] PASS [ ] FAIL

### Connection, projects, users, and permissions

#### E2E-038 — OPC-UA connection
- **Steps:** Open Connection; confirm simulator endpoint; disconnect/connect.
- **Expected:** State transitions ONLINE→OFFLINE→RECONNECTING/ONLINE; reads continue as designed during reconnect.
- **Evidence:** `test-evidence/E2E-038-opcua.png`
- **Result:** [ ] PASS [ ] FAIL

#### E2E-039 — Remote tag browse/search
- **Steps:** Open `Navegar tags`; expand root; search an existing simulator node.
- **Expected:** Tree/search data comes from backend `/opcua/browse` or `/search`; selected NodeID is exact.
- **Evidence:** `test-evidence/E2E-039-tag-browser.png`
- **Result:** [ ] PASS [ ] FAIL

#### E2E-040 — Project download/import/delete
- **Steps:** Open Projects; download active `.spid`; create a new project; import downloaded file; delete the disposable project with confirmation.
- **Expected:** Download is nonempty and contains recent data; import restores controllers; delete confirm uses critical treatment and removes only selected project.
- **Evidence:** `test-evidence/E2E-040-project-cycle.png`
- **Result:** [ ] PASS [ ] FAIL

#### E2E-041 — Create user
- **Steps:** Open Users; click `Novo usuário`; create `operador` / `operador123` with role `user`; save.
- **Expected:** User row appears active with role user; password is never displayed.
- **Evidence:** `test-evidence/E2E-041-create-user.png`
- **Result:** [ ] PASS [ ] FAIL

#### E2E-042 — User allowed capabilities
- **Steps:** Logout; login operador; visit dashboard/alarms/trends; set SP, change mode, write manual CO in MAN, acknowledge an alarm, create/download export.
- **Expected:** All six operations succeed: view, ack, SP, mode, CO and export.
- **Evidence:** `test-evidence/E2E-042-user-allowed.png`
- **Result:** [ ] PASS [ ] FAIL

#### E2E-043 — User forbidden capabilities
- **Steps:** As operador inspect shell/faceplate and direct-navigate to `/settings`, `/connection`, `/projects`, `/users`; inspect config/AI/alarm controls.
- **Expected:** Apply tuning, AI Start/Pause/Stop, controller CRUD, alarm config, OPC config, Projects, Users and Settings are absent; direct routes are denied; backend returns 403 if an admin endpoint is manually invoked.
- **Evidence:** `test-evidence/E2E-043-user-forbidden.png`
- **Result:** [ ] PASS [ ] FAIL

#### E2E-044 — Mid-session role change
- **Steps:** In a second admin session change operador to admin then back to user; in operador session attempt a now-forbidden action without relogin.
- **Expected:** 403 shows toast `sem permissão`; client refetches `/auth/me`; controls update without exposing a successful unauthorized write.
- **Evidence:** `test-evidence/E2E-044-role-change.png`
- **Result:** [ ] PASS [ ] FAIL

### Themes, resilience, responsive, accessibility

#### E2E-045 — Theme switch and persistence
- **Steps:** Switch Recorder→Phosphor→ISA-101; inspect `<html data-theme>`; reload each.
- **Expected:** Attribute and visual treatment change and persist; Recorder is default in a fresh browser storage profile.
- **Evidence:** `test-evidence/E2E-045-themes.png`
- **Result:** [ ] PASS [ ] FAIL

#### E2E-046 — Phosphor-only halo and legacy migration
- **Steps:** Compare PV trace Recorder/Phosphor; set localStorage `spid.theme='ocean'` through CDP and reload.
- **Expected:** Static PV halo appears only in Phosphor; no `shadowBlur`-style frame collapse; legacy ocean migrates to Recorder and storage updates.
- **Evidence:** `test-evidence/E2E-046-halo-migration.png`
- **Result:** [ ] PASS [ ] FAIL

#### E2E-047 — Backend outage and resync
- **Steps:** While live, stop backend; observe; restart it; during outage use simulator/backend means to create then clear an alarm if feasible before WS reconnect.
- **Expected:** Offline banner appears; queries pause; WS reconnects with backoff; full resync completes before live render; fired-and-cleared alarm appears in history.
- **Evidence:** `test-evidence/E2E-047-resync.png`
- **Result:** [ ] PASS [ ] FAIL

#### E2E-048 — Invalid token
- **Steps:** Through CDP replace stored token with invalid text; reload; separately test WS close 4401 if observable.
- **Expected:** Session clears and redirects to `/login`; no blank protected page.
- **Evidence:** `test-evidence/E2E-048-invalid-token.png`
- **Result:** [ ] PASS [ ] FAIL

#### E2E-049 — Four responsive breakpoints
- **Steps:** Use CDP viewports 1440×900, 1024×768, 768×900, 320×800; capture dashboard at each.
- **Expected:** ≥1024 trend/faceplate side-by-side; <1024 faceplate stacks; <768 cards scroll and alarm count chip replaces full footer; 320 retains monitoring, ACK and SP input without horizontal page overflow.
- **Evidence:** `test-evidence/E2E-049-responsive.png`
- **Result:** [ ] PASS [ ] FAIL

#### E2E-050 — Keyboard, focus, and target size
- **Steps:** At 1440 and 320 tab through login, top bar, card/config, trend controls, faceplate and footer; use CDP bounding boxes for representative buttons/inputs.
- **Expected:** Logical focus order; visible ≥2 px focus ring with ≥3:1 contrast; representative interactive targets are ≥44×44 CSS px; dialogs trap and restore focus.
- **Evidence:** `test-evidence/E2E-050-a11y.png`
- **Result:** [ ] PASS [ ] FAIL

## Results table

| ID | Title | Pass/Fail | Evidence | Notes |
|---|---|---|---|---|
| E2E-001 | Default admin login | | `E2E-001-admin-login.png` | |
| E2E-002 | Invalid credentials | | `E2E-002-invalid-login.png` | |
| E2E-003 | Protected deep link | | `E2E-003-deep-link.png` | |
| E2E-004 | Logout invalidates session | | `E2E-004-logout.png` | |
| E2E-005 | Top navigation | | `E2E-005-top-nav.png` | |
| E2E-006 | Command palette | | `E2E-006-command-palette.png` | |
| E2E-007 | Configuration menu | | `E2E-007-cfg-menu.png` | |
| E2E-008 | Start internal simulator | | `E2E-008-start-simulator.png` | |
| E2E-009 | Create controller bound to twin | | `E2E-009-create-controller.png` | |
| E2E-010 | Single-row card strip | | `E2E-010-card-strip.png` | |
| E2E-011 | Live trend pen | | `E2E-011-live-pen.png` | |
| E2E-012 | Trend time window | | `E2E-012-time-window.png` | |
| E2E-013 | Auto/manual scales | | `E2E-013-scales.png` | |
| E2E-014 | Plotted CSV export | | `E2E-014-dashboard-csv.png` | |
| E2E-015 | Faceplate consistency | | `E2E-015-faceplate.png` | |
| E2E-016 | Setpoint write | | `E2E-016-setpoint.png` | |
| E2E-017 | AUTO/MAN and manual CO | | `E2E-017-mode-output.png` | |
| E2E-018 | Supervisory visibility | | `E2E-018-supervisory.png` | |
| E2E-019 | DDC visibility and scan rate | | `E2E-019-ddc.png` | |
| E2E-020 | Tag mapping browser | | `E2E-020-tag-mapping.png` | |
| E2E-021 | Tuning confirmation | | `E2E-021-tuning-confirm.png` | |
| E2E-022 | AI configuration/lifecycle | | `E2E-022-ai-lifecycle.png` | |
| E2E-023 | AI explanation log | | `E2E-023-ai-log.png` | |
| E2E-024 | Quiet alarm footer | | `E2E-024-quiet-footer.png` | |
| E2E-025 | Force HI alarm | | `E2E-025-hi-alarm.png` | |
| E2E-026 | Acknowledge/clear | | `E2E-026-ack-clear.png` | |
| E2E-027 | Alarm history filters | | `E2E-027-alarm-history.png` | |
| E2E-028 | Reduced-motion alarm | | `E2E-028-alarm-reduced-motion.png` | |
| E2E-029 | Populate four slots | | `E2E-029-four-slots.png` | |
| E2E-030 | Time-sync zoom/pan | | `E2E-030-time-sync.png` | |
| E2E-031 | Statistics | | `E2E-031-stats.png` | |
| E2E-032 | Historical window | | `E2E-032-history.png` | |
| E2E-033 | Server export | | `E2E-033-server-export.png` | |
| E2E-034 | Simulator dynamics | | `E2E-034-sim-dynamics.png` | |
| E2E-035 | Simulator disturbance | | `E2E-035-sim-disturbance.png` | |
| E2E-036 | Executive KPIs | | `E2E-036-executive-kpis.png` | |
| E2E-037 | Executive details | | `E2E-037-executive-details.png` | |
| E2E-038 | OPC-UA connection | | `E2E-038-opcua.png` | |
| E2E-039 | Tag browse/search | | `E2E-039-tag-browser.png` | |
| E2E-040 | Project cycle | | `E2E-040-project-cycle.png` | |
| E2E-041 | Create user | | `E2E-041-create-user.png` | |
| E2E-042 | User allowed capabilities | | `E2E-042-user-allowed.png` | |
| E2E-043 | User forbidden capabilities | | `E2E-043-user-forbidden.png` | |
| E2E-044 | Mid-session role change | | `E2E-044-role-change.png` | |
| E2E-045 | Theme persistence | | `E2E-045-themes.png` | |
| E2E-046 | Halo/migration | | `E2E-046-halo-migration.png` | |
| E2E-047 | Backend outage/resync | | `E2E-047-resync.png` | |
| E2E-048 | Invalid token | | `E2E-048-invalid-token.png` | |
| E2E-049 | Responsive breakpoints | | `E2E-049-responsive.png` | |
| E2E-050 | Keyboard/focus/targets | | `E2E-050-a11y.png` | |

## Acceptance rule

- **Validated:** 50/50 PASS, zero unexplained console errors, zero unexpected failed requests, all evidence files present.
- **Not validated:** any FAIL or missing evidence. Create one implementation issue per failed procedure using the procedure ID and attach screenshot, console messages, failed request details, and exact reproduction steps.

## Teardown

1. Save the completed results table and browser console/network evidence.
2. Stop Vite and FastAPI processes gracefully.
3. Keep `/tmp/spid-e2e` until failures are diagnosed; delete it only after the 50/50 gate passes.
