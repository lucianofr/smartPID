# Design — Web Frontend Rewrite (Recorder/Phosphor identity)

**Documento:** Design / Spec (saída de brainstorming)
**Data:** 2026-07-26
**Autor:** Luciano França Rocha — LFR Automação
**Status:** Proposto (aguardando revisão)
**Companion:** [`PRD.md`](../../../PRD.md) — product requirements
**Branch:** `docs/web-frontend-rewrite-spec`

> Written in English to match the companion PRD. Prior specs in this directory are in Portuguese;
> code, commits and identifiers remain English per `CLAUDE.md`.

---

## 1. Context

The Smart PID Edge Platform has completed its PySide6 to web migration. `packages/smart_pid_web`
on `main` contains a working React/Vite client: all 8 slices shipped, 241 files, ~7,900 LOC of
non-test source, 72 test files, 13 Playwright E2E specs, and visual baselines for 5 themes across
4 breakpoints. The backend `RealtimeWS` bridge exists and works.

That client has since been through one big-bang styling refactor (Tailwind v4 + shadcn + flat
ISA-101), executed behind a DOM-freeze contract (`packages/smart_pid_web/docs/freeze-inventory.md`)
whose sole purpose was to keep the existing Vitest suite green while primitives were swapped
wholesale.

**The problem is not function — it is commercial presentation.** The flat ISA-101 result is
standards-correct and safe, but it does not sell. The product needs a visual identity with
commercial appeal for demos, the website, and buyer-facing evaluation, while remaining a credible
industrial HMI.

Secondarily, the persistence layer uses raw `aiosqlite`. The `fullstack-selector` guidance places
this application in **Archetype 3** (RBAC + time series + real-time + OPC-UA/ML) and recommends
SQLAlchemy 2.0 async as the idiomatic data-access layer.

## 2. Goals

1. Replace the frontend source with a new implementation carrying a distinctive, commercially
   appealing visual identity.
2. Preserve every existing behavior. No feature regression across the 8 slices.
3. Move backend data access from raw `aiosqlite` to SQLAlchemy 2.0 async, without schema change.
4. Collapse RBAC to two roles: `admin` and `user`.
5. Keep the `.spid` portable-project model intact.

## 3. Non-goals

- Rewriting the PID engine, fuzzy engine, RL engine, OPC-UA adapter, workers, EventBus or
  `RealtimeWS` bridge. These are untouched.
- Changing the database engine. SQLite with WAL stays. No Postgres, no TimescaleDB.
- Introducing Celery or Redis. Continuous control loops correctly live in the asyncio loop;
  the only discrete job (export) is adequately served by the existing in-process worker.
- Changing the SQL schema, table names, or the `.spid` file format.
- Changing the REST contract or the WebSocket envelope.
- Retiring the PySide6 client as part of this work. It is already frozen; its removal is separate.
- Multi-tenant, remote or LAN-exposed operation. Bind stays `127.0.0.1`.

## 4. Locked decisions

| Decision | Value | Rationale |
|---|---|---|
| Backend scope | SQLAlchemy 2.0 async over SQLite | Idiomatic data layer per `fullstack-selector`; `.spid` portability outweighs a TimescaleDB migration |
| Frontend scope | Full rewrite of `src/` | New identity cannot be reached by patching DOM frozen to old tests |
| Roles | `admin`, `user` | Replaces the 3-tier RBAC and supersedes the earlier mono-user plan |
| Default theme | Recorder (light) | Differentiates from uniformly dark competitors; photographs well for sales |
| Dark theme | Phosphor | Control-room companion, shares one identity with Recorder |
| ISA-101 | Retained, demoted | Safety standard some buyers mandate; already built and contrast-tested |
| Test strategy | Keep E2E, rebuild unit | E2E asserts behavior and survives redesign; unit tests are welded to the old DOM |

### 4.1 Deliberate divergence from `fullstack-selector`

The skill's database rule states that an application with time-series data should consolidate on
Postgres + TimescaleDB rather than SQLite. This design **knowingly diverges**, because `.spid`
project files *are* SQLite databases. Project portability — list, new, open, import, download,
delete, and moving a plant configuration between machines — is a load-bearing product feature built
directly on that fact. Migrating to Postgres would require redesigning `.spid` as a dump/restore
format, invalidating the historian tests and the project service.

The divergence is accepted with these conditions:
- Recorded here explicitly rather than left implicit.
- Revisited if per-plant point counts or sampling rates grow to where SQLite's single-writer
  serialization becomes the bottleneck. The migration trigger is sustained historian write
  contention, not point count alone.
- SQLAlchemy 2.0 async is adopted now specifically so that a future engine change is a dialect
  change rather than a rewrite.

Alignment with the rest of Archetype 3 is already satisfied: React + Vite (not Next.js, correct
given a mandatory Python backend), shadcn/ui, FastAPI, native WebSocket, uPlot for high-frequency
trends, and continuous loops in asyncio rather than Celery.

## 5. Architecture

Unchanged in shape. The daemon remains a single asyncio process hosting the engine, workers,
EventBus, REST API and the WebSocket bridge. The SPA is served single-origin by the backend in
production and proxied from Vite in development.

```
OPC-UA ──asyncua──> IO Worker ──> EventBus ──┬──> PID / AI / Alarm / Stats / DB workers
                                              ├──> TelemetryPublisher ──> ZMQ 5555 (PySide6, legacy)
                                              └──> RealtimeWS ──> WS /ws/realtime ──┐
                    FastAPI REST /api/* ───────────────────────────────────────────┤
                    SQLAlchemy 2.0 async ──> SQLite WAL (.spid)                     │
                                                                                    v
                                              smart_pid_web (React + Vite + TS, rewritten)
```

The only structural change is the data-access layer beneath the repositories.

## 6. Visual identity

### 6.1 Principle

The product is an instrument, and its most characteristic artifact is the closed loop rendered over
time. The identity is grounded in the physical heritage of process instrumentation — panel-mount
controllers and continuous strip-chart recorders — rather than in generic dashboard language.

Boldness is spent in exactly one place: the trend. Everything around it stays quiet.

### 6.2 Typography

Three roles, two families, all self-hosted. No external CDN, consistent with browser-only localhost
delivery.

| Role | Face | Use |
|---|---|---|
| Display | Archivo Expanded (variable width, weight ≥ 600) | Headings, KPI figures |
| Body / UI | Archivo (normal width) | Labels, controls, prose |
| Data | Geist Mono | Every process value and metric, tabular numerals |

Archivo is chosen for industrial signage character with an open license and a variable width axis.
Inter and IBM Plex are deliberately avoided: the former is the current AI default, the latter is the
existing generic-industrial choice being replaced.

All process values use `font-variant-numeric: tabular-nums`. Decimal columns align across loops.

### 6.3 Trace language (constant across all themes)

| Series | Treatment |
|---|---|
| PV | Cool, highest contrast — the measured truth |
| SP | Dashed graphite, low emphasis — a reference, not a measurement |
| CO | Warm amber, right axis — valve output, industrial convention |

Alarm colors are never reused as trace colors, and trace colors never signal alarm state.

### 6.4 Recorder — light, default

```css
[data-theme="recorder"] {
  --paper:        #F7F8FA;  /* cool paper base */
  --surface:      #FFFFFF;  /* cards */
  --surface-sunk: #EEF1F5;  /* chart wells, inputs */
  --rule:         #DCE2EA;  /* hairlines, engraved grid */
  --ink:          #16202B;  /* primary text */
  --ink-soft:     #5A6875;  /* secondary text */
  --accent:       #0E6B6B;  /* deep teal — interactive chrome only */
  --trace-pv:     #1B4F87;
  --trace-sp:     #7C8894;
  --trace-co:     #C77A16;
  --alarm-crit:   #C02026;
  --alarm-warn:   #B26A00;
  --alarm-adv:    #6B4FA8;
}
```

The base is a cool paper neutral, deliberately not the warm cream that characterizes one of the
common AI-generated design defaults.

### 6.5 Phosphor — dark companion

```css
[data-theme="phosphor"] {
  --void:         #0A0E14;
  --panel:        #131A24;
  --panel-hi:     #1C2530;
  --rule:         #253040;
  --text:         #D6DEE8;
  --text-soft:    #7E8B9A;
  --accent:       #23A6A6;
  --trace-pv:     #9FC8F0;
  --trace-sp:     #6E7B8A;
  --trace-co:     #E39B3D;
  --alarm-crit:   #FF4D4D;
  --alarm-warn:   #FFA51F;
  --alarm-adv:    #A98BFF;
}
```

Phosphor uses a duotone data language (cool PV, warm CO) drawn from instrument convention rather
than a single saturated accent on near-black, which is another recognized AI-design default.

The teal accent in both themes is chosen to sit apart from PV blue, CO amber and alarm red, so
interactive chrome never collides with process meaning.

### 6.6 Signature element

The trend, rendered per theme:

- **Recorder** — a continuous strip chart. Engraved grid, ink traces, and a live pen tip at the
  leading edge, so the current value is visibly being drawn.
- **Phosphor** — identical geometry; the PV trace carries a faint bloom, and AI intervention points
  appear as precise ticks on the time axis.

### 6.7 Theme inventory

Three themes ship: `recorder` (default), `phosphor`, `isa101`. The five-theme set on `main`
(dark-room, isa101, md3-dark, md3-light, ocean) is reduced. Three themes with one coherent identity
replaces five unrelated ones. MD3 and Ocean are dropped; Dark Room is superseded by Phosphor.

### 6.8 Layout — operational dashboard

```
+---------------------------------------------------------+
| SMART PID      Loops Trends Alarms Sim        [k]  [cfg] |
+---------------------------------------------------------+
| [FIC-101 ] [TIC-202 ] [LIC-303 ] [PIC-404 ]   loop cards |
| [####-- ] [#####- ] [##---- ] [###--- ]                  |
| [ AUTO   ] [ AUTO   ] [ MAN    ] [ ALARM  ]              |
+-----------------------------------+---------------------+
| TREND  recorder chart, pen tip    | FACEPLATE           |
| .................grid............ | PV #####-  150.2    |
|    /~~\___ PV                 (o) | SP ####--  148.0    |
| --------- SP dashed               | CO ##----   42.1    |
|  /~~\ CO, right axis              | [AUTO][MAN]         |
|                                   | IAE 12.4            |
|                                   | [Apply tuning]      |
+-----------------------------------+---------------------+
| 2 CRITICAL   1 WARNING          alarm bar, fixed footer  |
+---------------------------------------------------------+
```

## 7. Frontend module structure

Layered so that logic is testable without a DOM.

**Pure modules — no React, no DOM:**

| Module | Responsibility |
|---|---|
| `envelope` | Parse and validate the WS envelope; detect `seq` gaps |
| `windowBuffer` | Bounded sliding window with an explicit decimation policy |
| `alarmMachine` | Four-state ack/clear transitions |
| `scale` | Value-to-percent, clamping, tick generation for AnalogBar |
| `format` | Tabular numeric formatting, units, decimal places |

**Realtime:** `RealtimeProvider` (single socket, reconnect with backoff, fan-out),
`useRealtime(loopId, type)`, and `resync` (refetch controllers, active alarms and AI status on gap
or reconnect).

**Data:** `apiClient` typed from the OpenAPI codegen, plus per-resource query hooks for controllers,
alarms, stats, history, export, simulator, projects and opcua.

**Auth:** `AuthContext`, `RouteGuard`, and `useCan(action)` for capability checks.

**Design system:** `ThemeProvider` writing `data-theme` on the root element; `tokens.css` and
`themes.css`; primitives `AnalogBar`, `Trend`, `Readout`, `Dialog`, `Field`, `Button`, `Badge`.

**Features:** alarms, loop-config, multitrend, simulator, projects, connection, settings.

**Pages:** thin composition only, no business logic.

## 8. Data flow

- Reads go through TanStack Query over REST, cached and invalidated on mutation.
- Live data arrives on a single WebSocket per session, fanned out by the provider.
- Writes are REST only, never over the WebSocket.
- After any write, the affected query is invalidated and REST confirms. Optimistic state is never
  trusted for process values.
- On reconnect or a detected `seq` gap, a full REST resync precedes resuming live render.

## 9. Roles and permissions

Two roles. The backend enforces on every route; the frontend hides controls for presentation only.
A hidden control is never the security boundary.

| Capability | `admin` | `user` |
|---|---|---|
| View dashboards, trends, alarms, stats | yes | yes |
| Acknowledge alarms | yes | yes |
| Set SP, mode, manual CO | yes | yes |
| Export data | yes | yes |
| Edit PID / fuzzy / RL parameters, apply tuning | yes | no |
| Start, pause, stop AI workers | yes | no |
| Create, edit, delete controllers | yes | no |
| Configure alarm limits | yes | no |
| OPC-UA connection and tag mapping | yes | no |
| `.spid` project management | yes | no |
| Manage users | yes | no |
| Change application settings | yes | no |

Implementation replaces `require_operator` / `require_supervisor` / `require_admin` with
`require_user` (any authenticated principal) and `require_admin`. Credentials remain in the separate
store, never inside `.spid`.

## 10. Backend change — SQLAlchemy 2.0 async

Scope is the data-access layer only.

- Declarative models mapped to the **existing** tables. No renames, no migrations, no new columns.
- Async engine over `aiosqlite`, WAL retained.
- Repositories (`sqlite_repo`, `historian`, `alarm_repo`, `ai_repo`, `audit_repo`, `user_repo`,
  `system_event_repo`) reimplemented against `AsyncSession`, keeping their current public methods so
  callers are unaffected.
- Historian batch insert preserved; it is the write-hot path and must not regress.
- `.spid` open/new/import/download continues to operate on SQLite files directly.

Acceptance: the existing backend pytest suite passes unmodified except where a test reaches into
raw-`aiosqlite` internals rather than a repository's public method.

## 11. Error handling

| Condition | Behavior |
|---|---|
| Transport failure | Typed error from `apiClient`, mapped to a user-facing message |
| 401 | Clear session, redirect to login |
| 403 | Control was wrongly shown; log and surface "not permitted" |
| 409 | Loop-state conflict; show the reason and preserve form state |
| 502 | OPC-UA down; loop-level banner, writes disabled, reads continue |
| WS close 4401 | Token invalid; force re-login |
| WS overflow close | Reconnect and resync; alarm transitions are never lost |

Every destructive write sits behind an explicit confirmation dialog. Loading and empty are designed
states, not spinners over blank space.

## 12. Testing

| Layer | Scope |
|---|---|
| Unit | Pure modules with no DOM: `envelope`, `windowBuffer`, `alarmMachine`, `scale`, `format` |
| Component | Every primitive and feature, Vitest + Testing Library, queried by role and accessible name |
| Integration | `useRealtime` against a fake WebSocket; `apiClient` against a mocked API |
| E2E | The existing 13 Playwright specs, selectors patched — the regression net for the rewrite |
| Visual | Regenerated baselines, 3 themes × 4 breakpoints (320 / 768 / 1024 / 1440) |
| Contrast | Automated WCAG AA per theme; Recorder and Phosphor must both pass 4.5:1 for body text |
| Backend | Existing pytest suite green through the SQLAlchemy swap |

Component tests query by role and accessible name wherever a role exists, and resort to `data-testid`
only where no semantic query is available. This is a deliberate correction: the previous suite bound
so tightly to `data-testid`, asserted `className` and inline styles that it required a DOM-freeze
contract to survive a restyle. The new suite must not recreate that trap.

`packages/smart_pid_web/docs/freeze-inventory.md` is retired with the old source. A new, much
smaller contract is derived from the new primitives once they stabilize.

## 13. Sequencing

Each phase is independently reviewable and leaves the tree green.

| Phase | Content |
|---|---|
| 0 | Backend: SQLAlchemy 2.0 async layer. Backend tests green. No frontend change. |
| 1 | Backend: collapse RBAC to `admin` / `user`. Update auth tests. |
| 2 | Frontend: scaffold, tokens, ThemeProvider, Recorder + Phosphor, primitives, contrast tests. |
| 3 | Frontend: realtime layer and pure modules, fully unit-tested. |
| 4 | Frontend: dashboard, loop cards, Trend signature, Faceplate. |
| 5 | Frontend: loop config, commands, AI panel. |
| 6 | Frontend: alarms. |
| 7 | Frontend: multitrend, stats, history, export. |
| 8 | Frontend: simulator. |
| 9 | Frontend: executive dashboard. |
| 10 | Frontend: settings, connection, projects. |
| 11 | ISA-101 theme port, E2E selector patch, visual baselines, bundle budget. |

Phases 0 and 1 are backend-only and can land before any frontend work begins. Phases 2 and 3 are
the foundation for everything after.

## 14. Risks

| Risk | Mitigation |
|---|---|
| Rewrite loses a behavior present in the old client | E2E suite is kept and must pass; it encodes behavior, not structure |
| New identity fails a contrast or ISA-101 expectation | Automated contrast gate per theme; ISA-101 retained unchanged for buyers who require it |
| SQLAlchemy swap regresses historian write throughput | Batch insert preserved; benchmark the historian before and after phase 0 |
| Scope creep into the control engine | Non-goals are explicit; phases 0–1 are the only backend phases |
| Recorder light theme rejected by operators in a real control room | Phosphor ships alongside as the dark companion; theme choice persists per user |
| Bundle grows past budget with new fonts | Fonts subset to Latin, only required weights preloaded; existing `check-bundle` gate enforces |

## 15. Open items

- Exact Archivo and Geist Mono weights and subsets to bundle, decided during phase 2.
- Whether the executive dashboard warrants a layout distinct from the operational shell, decided in
  phase 9 against the Recorder direction.
- Whether the pen-tip animation respects `prefers-reduced-motion` by freezing the tip or by removing
  it; decided in phase 4 with an accessibility check.
