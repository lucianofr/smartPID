# Test-Plan & Acceptance-Criteria Review — Web HMI React Migration

**Date:** 2026-06-18
**Reviewer:** test-runner agent
**Scope:** umbrella spec (`2026-06-18-web-hmi-react-migration-design.md` §5 Testes) + Fatias 0+1, 2, 3, 4, 5, 6, 7, 8
**Stack under test:** React+Vite+TS (Vitest unit), Playwright E2E; backend pytest + pytest-asyncio
**Status of code:** `packages/smart_pid_web/` and `adapters/inbound/api/ws/realtime.py` **do not exist yet** — these specs are proposals. Backend routers are already implemented and were inspected to ground the recommendations below.

---

## 0. Cross-cutting findings (apply to the whole migration)

These are the highest-leverage gaps; they recur across fatias and are not isolated to one slice.

### 0.1 WS contract / topic-name mismatch (BLOCKER for Fatia 0+1 and 3)

- Umbrella §2.3 and §3 say the WS subscribes to topics `TELEMETRY.{id}`, `STATUS.{id}`, `ACTION.CTRL.{id}`, `ACTION.AI.{id}`, `ALARM`, and emits `type: "alarm"`.
- The real `TelemetryPublisher` bridges `STATUS.`, `ACTION.CTRL.`, `ACTION.AI.`, **`EVENT.ALARM.`**, **`EVENT.SYSTEM`** — the alarm topic is `EVENT.ALARM.`, not `ALARM`, and there is a `EVENT.SYSTEM` stream (user-action live feed shown in the PySide6 alarm panel) the WS contract omits entirely.
- **Risk:** alarms and the system-event feed silently never reach the web client; no acceptance test as written would catch it because they only assert "alarm appears."
- **Required test:** a backend contract test that asserts the RealtimeWS subscribes to the *same* topic prefixes the `TelemetryPublisher` uses (parametrize over the topic list so the two bridges cannot drift). Plus an E2E that asserts a `EVENT.SYSTEM` user-action (e.g. another session changes a SP) surfaces in the web alarm/event feed if parity is intended.

### 0.2 "Last-value / no-persistence on reload" is asserted nowhere

Umbrella §2.3/§2.4 and Fatia 0+1 state the policy (only last value per topic, reload resets the window) but no acceptance criterion or test verifies it. This is a named risk in §6. Needs explicit tests (see Fatia 0+1).

### 0.3 RBAC thresholds are unspecified and untestable as written

The specs say "respeita RBAC" / "RBAC no backend" generically. The actual backend uses three concrete levels enforced per route:
- `require_operator` (level 0): SP/mode/CO/enable, alarm ack & ack-all, alarm view.
- `require_supervisor` (level 1): **apply-tuning**.
- `require_admin` (level 2): user CRUD.
- `/tuning` (direct Kp/Ti/Td write) is **operator**, while `/apply-tuning/{id}` (apply pending recommendation) is **supervisor** — two different gates the specs conflate.

No acceptance criterion names which role is required for which action, so "respeita RBAC" is not objectively verifiable. Every RBAC test must assert both the allowed role passes **and** the next-lower role gets `403` (negative path).

### 0.4 Auth is missing on project routes (SECURITY — affects Fatia 7)

`routers/project` (`/new`, `/open`, `/import`, `/download`, `/list`, `/current`, `DELETE /{name}`) has **no auth dependency** — any unauthenticated caller can list/create/delete/download `.spid` files. The Fatia 7 acceptance only covers "CRUD respeita RBAC" for *users*, not projects. Add explicit auth tests for project routes (expect they currently fail / reveal the gap).

### 0.5 Path-traversal on project import/open/delete (SECURITY — affects Fatia 7)

`import_project`/`open_project`/`delete_project` build `self._projects_dir / f"{name}.spid"` directly from a client-supplied `name` or uploaded filename, with no `..`/separator sanitization. The Fatia 7 risk claims "validação multipart no backend (já existente)" — that validation does **not** appear to exist. This acceptance claim is false and must become a failing security test (`name="../../etc/x"` must be rejected with 400, not write outside the projects dir).

### 0.6 Monitor vs control execution mode is never tested

Commands (`setpoint`/`mode`/`output`) take two completely different code paths by `execution_mode`: in `monitor` they write via OPC-UA and return **409** if OPC is disconnected; in control mode they go through `LoopManager`. `mode` write can also return **502** ("Failed to write mode to DCS"). None of the Fatia 2 acceptance criteria mention these branches. The happy-path-only "altera SP → telemetria muda" hides the 409/502 behaviors operators will actually hit.

### 0.7 Generic test-plan verbs ("componentes de gráfico/cards", "fluxo principal")

Umbrella §5 lists test *areas* but no concrete cases; "por fatia, o fluxo principal" is happy-path only. Below, each fatia gets an explicit case list with negative/edge paths.

---

## Fatia 0+1 — Foundation + Live Dashboard

### Acceptance-criteria gaps

| Criterion (as written) | Problem | Rewritten (testable) |
|---|---|---|
| "Login → dashboard recebe telemetria ao vivo via WS" | "ao vivo" not bounded; no failure path | "After login, within 2 s of the backend emitting a `telemetry` envelope for loop N, the loop-N card shows the new PV/SP/CO and the trend appends a point." |
| "Reconexão automática após queda do WS" | No bound on backoff, no cap, no max attempts, no UI signal | "On WS close, the client retries with exponential backoff (assert increasing intervals, capped at a max); on reconnect it resumes receiving; a 'reconnecting' state is exposed while down." |
| "Status OPC visível por loop" | "visível" subjective; OPC status is global in backend (`GET /opcua/status`), not per-loop — criterion contradicts the REST it lists | "OPC connection status (connected/disconnected) is rendered and updates from `GET /opcua/status` (and/or `status` WS events); reconcile whether status is global or per-loop." |
| "WS rejeita token inválido/ausente (`4401`)" | Good and objective. Keep. Add expired + malformed cases. | Keep; expand cases below. |

### Missing test cases (not in spec)
- WS auth: **expired** token (not just invalid/absent) → `4401`. Backend `decode_access_token` raises on expiry; needs its own case.
- WS auth via **two channels**: §2.3 allows token via `?token=` *or* first message — both must be tested, plus the ambiguous case (token in neither) and (token in both, conflicting).
- Last-value policy (§0.2): connect a slow client, produce M frames for one topic faster than it drains, assert it receives only the **latest**, never a backlog, and the producer is never blocked.
- Broadcast to **multiple** clients: one socket failing/closing mid-broadcast must not drop the others (named in umbrella §5 but no acceptance criterion).
- Clean drop on disconnect: `ConnectionManager` removes the socket; no leak/zombie after N connect/disconnect cycles.
- Reload resets the trend window (§0.2): no IndexedDB/localStorage persistence of telemetry.
- Envelope parse robustness in `useRealtime`: malformed JSON, unknown `type`, `loop_id: null` (global event) — must not crash the hook.

### Prioritized test-case list
**Backend (pytest-asyncio)** — P0
1. WS handshake accepts valid token; rejects missing → `4401`.
2. WS handshake rejects invalid signature → `4401`.
3. WS handshake rejects **expired** token → `4401`.
4. Token accepted via `?token=` query param; token accepted via first message; rejected when in neither.
5. Broadcast reaches 3 concurrent clients; killing one mid-broadcast leaves the other 2 receiving.
6. Last-value-only: rapid produce → slow consumer receives latest, no backlog, producer not blocked.
7. Disconnect removes connection from `ConnectionManager` (no leak over 100 cycles).
8. Contract: WS topic prefixes == `TelemetryPublisher._BRIDGE_TOPICS` (guards §0.1 drift).

**Frontend (Vitest)** — P0/P1
9. `useRealtime` parses a valid envelope and exposes last state by `loop_id`/`type` (P0).
10. `useRealtime` reconnects with exponential backoff (fake timers, assert interval growth + cap) (P0).
11. `useRealtime` ignores malformed JSON / unknown `type` without throwing (P1).
12. `useRealtime` handles `loop_id: null` global events (P1).
13. Loop card renders PV/SP/CO/mode from last state; shows stale/disconnected indicator when WS down (P1).

**E2E (Playwright)** — P0/P1
14. Login → dashboard shows live telemetry within bound (P0).
15. Kill WS (block route) → UI shows reconnecting → restore → telemetry resumes (P0).
16. Reload page → trend window resets (no persisted history) (P1).
17. Invalid credentials → no dashboard, no WS opened (P1).

---

## Fatia 2 — Comandos + Configuração por Loop

### Acceptance-criteria gaps

| Criterion | Problem | Rewritten |
|---|---|---|
| "Alterar SP/modo/params reflete no backend e na telemetria ao vivo" | Happy path only; ignores monitor-mode 409, mode 502, validation 422 | "Valid SP/mode/params POST returns 2xx and the change appears in the next telemetry frame; in monitor mode with OPC disconnected the command returns 409 and the UI surfaces it; out-of-range params return 422 and the form blocks submit." |
| "apply-tuning só escreve após confirmação; resultado visível" | "confirmação" untestable (where? what dismisses it?); ignores 404 (no pending rec), 409 (external PID not Auto), guardrail clamping, and supervisor-only gate | "Clicking apply-tuning opens a confirm dialog; cancel issues no POST; confirm issues POST `/apply-tuning/{id}`. UI shows the applied Kp/Ti/Td and a 'clamped' indicator when the response `clamped=true`. 404→'no pending recommendation' shown; 409→'external PID must be in Auto' shown; operator role sees the action disabled/hidden (supervisor required)." |
| "IA start/stop/pause altera estado reportado" | "estado reportado" source unspecified (REST status vs `ai` WS) | "After start/stop/pause, `GET ai/status` reflects the new state AND an `ai` WS event updates the panel without manual refresh." |

### Missing test cases
- **RBAC negative**: operator attempting apply-tuning → backend 403 and UI gates the control (§0.3). Supervisor allowed.
- Client-side param validation parity with backend (Kp/Ti/Td ranges, ARW, filter, structure enums) — invalid client values blocked; valid-client-but-rejected-by-backend (422) shows the server error (named in Fatia 2 risks, no test).
- apply-tuning **guardrail clamp**: recommendation beyond `max_tuning_change_pct` → response `clamped=true`, applied values are the clamped ones; UI shows clamp.
- apply-tuning when **no pending recommendation** → 404 handled.
- apply-tuning when **external PID not in Auto** → 409 handled.
- The two distinct write paths: `/tuning` (direct write, operator, requires OPC connected → 409 if not) vs `/apply-tuning/{id}` (supervisor) — both, separately. Spec text says `apply-tuning/{id}` but lists it where the `/tuning` semantics live; resolve the conflation.
- Mode write failure in monitor mode → 502 surfaced to UI.
- Confirmation guard idempotency: double-click confirm issues exactly one POST.

### Prioritized test-case list
**Vitest** — P0
1. apply-tuning confirm-dialog: cancel → no network call; confirm → exactly one POST (P0).
2. Param form blocks submit on out-of-range Kp/Ti/Td and enum mismatches; valid values enabled (P0).
3. apply-tuning button hidden/disabled for operator role, enabled for supervisor (P0, §0.3).
4. UI renders `clamped` indicator when response `clamped=true` (P1).
5. Server 422 on params maps to inline form error, not a crash (P1).

**E2E (Playwright)** — P0/P1
6. Change SP (control mode) → next telemetry frame shows new SP (P0).
7. Change mode → telemetry mode field updates (P0).
8. apply-tuning happy path: confirm → applied Kp/Ti/Td visible (P0).
9. apply-tuning with no pending rec → 404 message (P1).
10. Monitor mode + OPC disconnected: SP change → 409 surfaced (P1).
11. Operator blocked from apply-tuning end-to-end (403) (P1, §0.3).

---

## Fatia 3 — Alarmes

### Acceptance-criteria gaps

| Criterion | Problem | Rewritten |
|---|---|---|
| "Alarmes aparecem em tempo real via WS" | Depends on §0.1 topic fix; otherwise untestable-but-passing | "When the backend emits an `EVENT.ALARM.*` event, it arrives on the WS as `type:"alarm"` and appears in the panel within 2 s with correct severity/state/timestamp." |
| "Ack (individual e all) reflete estado no backend e na UI" | "reflete estado" ignores that ack ≠ clear; an acked-but-still-active alarm stays visible | "POST `/{id}/ack` marks `reconhecido`; the row shows ACK state but remains listed while the alarm is still active (not cleared). ack-all acks all currently-active; count returned matches rows acked. UI revalidates via `GET /active` after ack (backend is source of truth)." |
| "Config de alarme persiste e altera o disparo" | "altera o disparo" not observable from UI alone; needs a trigger scenario | "PUT `/{id}/alarm-config` persists (GET returns new limits); with new limits, a PV crossing the new threshold raises an alarm and a PV within the old-but-not-new band does not." |

### Missing test cases
- Alarm **state machine**: ACTIVE_UNACK → ACK (still active) → CLEARED_UNACK → CLEARED+ACK (removed from `/active`). The backend computes `state` as ACTIVE/CLEARED_UNACK and only hides `cleared AND reconhecido`. The single criterion "ack limpa estado" is wrong; replace with the 4-state assertions.
- ack-all returns `acknowledged_count`; UI reflects exact count (named no test).
- Alarm **flood / virtualization & dedupe by `alarm_id`** (named in Fatia 3 risks, no test): inject 500 alarms → list virtualizes, no duplicate rows for same `alarm_id`, UI stays responsive.
- ack desync recovery (named risk): optimistic ack then backend rejects → UI reverts to backend truth after `GET /active` revalidation.
- Alarm bar severity counts match panel; blink/ack-needed indicator clears after ack.
- RBAC: ack/ack-all require operator (negative test: sub-operator → 403, though operator is the floor — confirm anonymous/expired → 401).
- Filter/sort by severity, controller, state.

### Prioritized test-case list
**Vitest** — P0/P1
1. Panel renders rows grouped/colored by severity; state badge per the 4 states (P0).
2. ack action: optimistic update then reconcile with `GET /active`; revert on failure (P0).
3. ack-all updates count and badges; bar count syncs (P1).
4. Virtualized list with 500 items renders without dup `alarm_id` rows (P1).

**E2E (Playwright)** — P0/P1
5. Backend raises alarm → appears in panel + bar with correct severity (P0).
6. Ack a still-active alarm → row shows ACK but stays listed; clear it → row leaves `/active` (P0, encodes the corrected state machine).
7. ack-all clears badges; returned count matches (P1).
8. Alarm-config change raises/suppresses an alarm at the new threshold (P1).

---

## Fatia 4 — Multi-trend + Stats + Export

### Acceptance-criteria gaps

| Criterion | Problem | Rewritten |
|---|---|---|
| "Multi-trend plota múltiplos sinais ao vivo sem travar (~60 fps)" | "~60 fps" / "sem travar" not objectively measured in CI | "With K loops × 3 vars streaming at the telemetry rate over a sliding window of N points, frame time stays under a threshold (assert via performance.now sampling) and decimation keeps rendered points ≤ window cap; main thread not blocked >X ms." |
| "Stats por loop exibidos e coerentes com o backend" | "coerentes" untestable without a reference | "Each metric (IAE, ITAE, ISE, MSE, σ, TV, 2σ/RANGE, 2σ/SP) rendered equals the `GET /{id}/stats` value, formatted to spec precision." |
| "History consultável; export baixa arquivo válido" | "válido" undefined; no pagination/limit/empty-range cases | "History query with start/end returns rows respecting limit/offset; export creates an export id, `GET /{id}/download` returns a non-empty file with expected content-type; empty range returns empty set, not an error." |

### Missing test cases
- **Perf / high point volume** (the key risky behavior + named Fatia 4 risk): N-point window enforced (oldest dropped), frontend decimation active, no unbounded memory growth over a long session.
- Multi-series correctness: each series maps to the right loop/var; toggling a series add/removes it; axis/scale per series.
- History pagination edges: limit, offset, start>end, invalid ISO date (backend `fromisoformat` → 422/500?), empty result.
- Export lifecycle: create → list shows it → download → content-type `application/octet-stream` and non-empty; download of unknown export id → 404.
- Stats for a loop with no data yet → graceful empty/zero, not crash.

### Prioritized test-case list
**Vitest** — P0/P1
1. Series selection add/remove updates plotted set; metric formatting matches precision (P0).
2. Sliding-window cap drops oldest points; decimation reduces rendered count under high volume (P0, perf).
3. Stats panel maps each metric to its API field (P1).

**E2E (Playwright)** — P0/P1
4. Multi-trend with ≥3 live series renders all; frame budget sampled stays under threshold (P0, perf).
5. Export create → download yields non-empty file (P0).
6. History query with limit/offset returns paged rows; empty range returns empty list (P1).
7. Invalid date range → handled error, no crash (P1).

---

## Fatia 5 — Simulador

### Acceptance-criteria gaps

| Criterion | Problem | Rewritten |
|---|---|---|
| "Preset aplicado altera a dinâmica visível na telemetria" | "altera a dinâmica" not observable deterministically | "After POST `/preset`, telemetry PV response to a fixed SP step changes vs the prior preset (e.g., settling/overshoot differs measurably) within a bounded time." |
| "Distúrbio injetado reflete no trend; remoção volta ao normal" | "reflete"/"volta ao normal" vague | "POST `/disturbance` produces a visible PV step/offset on the trend within T s; DELETE `/disturbance/{id}` returns PV toward the pre-disturbance baseline within T s." |
| "Output/modo do simulador controláveis; auto-toggles funcionam" | "funcionam" untestable | "PUT auto-disturbance / auto-sp toggles persist (GET reflects) and, when on, periodic disturbance/SP changes appear in telemetry; when off, they stop." |

### Missing test cases
- Sim-vs-real **mode labeling** (named risk): UI shows an unambiguous "SIMULATION" indicator; controls target the sim, not the real loop.
- Simulator not enabled → backend 404 (`get_simulator_adapter`) surfaced as a disabled/explanatory UI, not a crash.
- start/stop simulator: telemetry stops/starts; controls disabled when stopped.
- Slider bounds: param sliders clamp to valid ranges; out-of-range rejected.
- Disturbance idempotency: re-injecting / double-remove handled.

### Prioritized test-case list
**Vitest** — P1
1. Preset selector / sliders / disturbance controls emit correct payloads; sliders clamp to range.
2. "SIMULATION" mode indicator present; controls disabled when sim stopped.
3. Simulator-disabled (404) → explanatory UI state.

**E2E (Playwright)** — P0/P1
4. Apply preset → trend response to a SP step differs from previous preset (P0).
5. Inject disturbance → visible PV step; remove → returns to baseline (P0).
6. auto-disturbance toggle on → periodic disturbances appear; off → stop (P1).

---

## Fatia 6 — Executive Dashboard

### Acceptance-criteria gaps

| Criterion | Problem | Rewritten |
|---|---|---|
| "Cards refletem dados ao vivo e agregações de período" | "refletem"/"ao vivo" vague; period window untested | "Each KPI card value equals the corresponding `GET /stats` (or per-loop) field for the selected period; changing the period window re-queries and updates values; a live telemetry frame updates the live portion within 2 s." |
| "Recomendações de sintonia exibidas por loop" | No empty-state / source attribution | "`GET /tuning-recommendations/{id}` results render per loop with recommended vs current Kp/Ti/Td and source; loops with no recommendation show an explicit empty state (404 handled)." |
| "Paridade visual com a versão PySide6" | Not objectively verifiable — subjective | "Replace with concrete checks: required KPI fields present; loop health states (running/stopped/error/OPC) mapped to defined visuals; defer pure visual parity to Fatia 8 snapshots." |

### Missing test cases
- Loop health mapping: running/stopped/error/OPC-disconnected each render distinctly; error state from `status` events.
- Period-window selection re-queries stats (not stale).
- No-data / no-recommendation empty states.
- Aggregation source: assert client uses backend aggregation (Fatia 6 risk: avoid heavy client aggregation) — KPIs sourced from `GET /stats`, not recomputed client-side from raw telemetry.
- RBAC: read-only view available to operator; no write actions exposed here.

### Prioritized test-case list
**Vitest** — P1
1. KPI cards map each value to its `/stats` field for selected period.
2. Loop health badge per state; error from `status` event.
3. Tuning recommendation empty state (404) handled.
4. Period-window change triggers re-query (mock query layer).

**E2E (Playwright)** — P1
5. Executive dashboard loads and a live frame updates the live portion.
6. Switch period window → values change accordingly.

---

## Fatia 7 — Settings + Users (RBAC) + Conexão + Projetos `.spid`

### Acceptance-criteria gaps

| Criterion | Problem | Rewritten |
|---|---|---|
| "CRUD de usuários respeita RBAC (permissões do backend)" | Doesn't name the threshold (user CRUD = **admin**); UI-gating vs server-gating not separated | "User create/update/delete require ADMIN: admin succeeds; supervisor and operator receive 403 AND the UI hides/disables the controls. Both UI gate and server gate are asserted independently." |
| "Conexão OPC configurável; tag browse/search funcional" | "funcional" vague; connect/disconnect/start/stop state transitions untested | "PUT `/endpoint` persists; POST `/connect` → status becomes connected (GET reflects); `/disconnect` → disconnected; browse/{node}/search return tag lists; failed connect surfaces an error, not a crash." |
| "Projetos `.spid` gerenciáveis (incl. upload/download); welcome lista projetos" | No auth assertion (routes are currently UNAUTHENTICATED — §0.4); no path-traversal guard (§0.5); no conflict/not-found cases | "All project routes require auth (401 when absent). new with existing name → 409; open missing → 404; delete active project → 409; delete missing → 404. import with `name`/filename containing `..` or path separators is rejected (400) and writes nothing outside the projects dir. download returns the active `.spid` with octet-stream type." |
| "Auth/usuários fora dos metadados do projeto" | Good intent but no test | "Create a user, export/download the active `.spid`, assert no user/credential data is present in the project file (only `users.db` holds it)." |

### Missing test cases
- **SECURITY (P0)**: project routes reject unauthenticated requests (§0.4) — currently they don't; this test should fail and expose the gap.
- **SECURITY (P0)**: path traversal on import/open/delete (`name="../../x"`, filename with separators) rejected (§0.5); the spec's "validação já existente" is false.
- Malicious / non-`.spid` upload: wrong extension, oversized, non-DB content → rejected with a clear error (Fatia 7 risk, no test).
- User CRUD RBAC matrix: admin allowed; supervisor/operator 403 (server) and gated (UI).
- Register vs update password handling; duplicate username → conflict.
- OPC connect failure (bad endpoint) → error surfaced; reconnect after disconnect.
- Welcome dialog: lists projects from `GET /list`; opening one sets active (`/current` reflects); empty list state.
- Credential-leak assertion (rewritten criterion above).

### Prioritized test-case list
**Backend (pytest)** — P0 (security)
1. Each project route returns 401 without a valid token (exposes §0.4).
2. import/open/delete with traversal `name` rejected, no file written outside dir (exposes §0.5).
3. import of non-`.spid` / oversized payload rejected.
4. User CRUD: admin 2xx; supervisor/operator 403.
5. new(existing)→409, open(missing)→404, delete(active)→409, delete(missing)→404.
6. Exported `.spid` contains no user/credential data.

**Vitest** — P1
7. User-management controls hidden/disabled for non-admin.
8. OPC connection form: connect/disconnect toggles state; error shown on failure.
9. Project import form rejects non-`.spid` client-side.

**E2E (Playwright)** — P1
10. Admin creates/edits/deletes a user; operator cannot see those controls.
11. Configure OPC endpoint → connect → status connected; disconnect.
12. Import a `.spid` → appears in welcome list → open → becomes current.

---

## Fatia 8 — Temas + Faceplate

### Acceptance-criteria gaps

| Criterion | Problem | Rewritten |
|---|---|---|
| "Troca de tema aplica tokens em toda a app; persiste entre sessões" | "em toda a app" needs a concrete probe; persistence channel unspecified | "Selecting a theme sets the documented CSS custom-property tokens on the root; a sampled set of components reads the new token values; the choice persists across reload (localStorage) and is reapplied on next session." |
| "Faceplate com paridade visual/funcional vs PySide6" | Visual parity subjective | "Faceplate renders PV/SP/CO, mode, analog bar, and actions; state-driven rendering verified per mode/alarm state; live telemetry updates the bar. Visual parity covered by snapshot tests at key breakpoints (objective baseline), not by reviewer opinion." |
| "ISA-101 atende padrão industrial (contraste/semântica de cor)" | Not objectively verifiable as prose | "ISA-101 theme passes an automated contrast check (≥ WCAG AA / ISA-101 thresholds) for text and alarm-state colors; color semantics (alarm severity → color) match the identity docs token map." |

### Missing test cases
- Theme token application probe (not just "looks themed"): assert computed CSS variable values per theme.
- Persistence across reload + default theme on first run.
- Faceplate state matrix: each of the 8 modes + alarm/normal renders correctly; analog bar reflects PV within range and clamps out-of-range.
- Faceplate commands reuse Fatia 2 paths (SP/mode/CO) with the same RBAC/confirmation gates — regression that gating still applies inside the faceplate.
- Contrast/accessibility check per theme (named Fatia 8 risk).
- Visual regression snapshots at 320/768/1024/1440 per theme (only "snapshots por tema" mentioned; pin breakpoints).

### Prioritized test-case list
**Vitest** — P1
1. Theme switch sets expected root CSS variables; persists across reload.
2. Faceplate renders correctly for each mode and for alarm vs normal state.
3. Faceplate analog bar maps PV to fill and clamps out-of-range.
4. Faceplate command actions still enforce RBAC/confirmation (reuse Fatia 2).

**Playwright / visual** — P1
5. Snapshot each theme at 320/768/1024/1440.
6. Automated contrast check passes for ISA-101 (and other themes).

---

## Summary

### Biggest coverage gaps (highest impact first)
1. **Project routes are unauthenticated + path-traversal-capable (Fatia 7).** The spec asserts validation "já existente" — it isn't. No acceptance test covers it. Security P0.
2. **WS topic-name / contract mismatch (Fatia 0+1 & 3).** Spec says `ALARM`; backend bridges `EVENT.ALARM.` and also `EVENT.SYSTEM`. Alarms and the user-action feed could silently never reach the web client, and no test as written catches it.
3. **RBAC thresholds unspecified and only happy-path-tested everywhere.** Concrete gates exist (operator/supervisor/admin; apply-tuning=supervisor, user CRUD=admin) but no acceptance criterion names them and no negative (403) tests are required.
4. **Last-value/no-persistence-on-reload policy asserted nowhere** despite being a named architectural risk.
5. **Monitor-mode 409 / mode 502 command branches untested (Fatia 2)** — operators will hit these; specs are happy-path only.
6. **Alarm ack ≠ clear (Fatia 3).** "ack limpa estado" is incorrect; the real 4-state machine (ACTIVE/ACK/CLEARED_UNACK/cleared+acked) is untested.
7. **Multi-trend high-volume perf (Fatia 4) is asserted as "~60 fps / sem travar"** — not objectively measurable as written; needs a frame-budget + window-cap + decimation test.
8. **Several acceptance criteria are non-verifiable prose** ("paridade visual", "funciona", "coerentes", "atende padrão industrial") — each rewritten above into an objective assertion.

### Proposed test-case count per fatia
| Fatia | Backend (pytest) | Vitest | E2E/Visual | Total |
|---|---|---|---|---|
| 0+1 | 8 | 5 | 4 | 17 |
| 2 | (reuse) | 5 | 6 | 11 |
| 3 | (reuse) | 4 | 4 | 8 |
| 4 | (reuse) | 3 | 4 | 7 |
| 5 | (reuse) | 3 | 3 | 6 |
| 6 | (reuse) | 4 | 2 | 6 |
| 7 | 6 | 3 | 3 | 12 |
| 8 | — | 4 | 2 | 6 |
| **Total** | **14** | **31** | **28** | **73** |

Note: "reuse" = relies on existing backend pytest suite for those routers; the new behaviors needing fresh backend tests concentrate in Fatia 0+1 (WS) and Fatia 7 (project auth/traversal).
