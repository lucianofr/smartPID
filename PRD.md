# PRD — Web Frontend Rewrite (commercial identity)

**Project:** Smart PID Edge Platform v2
**Scope:** Rewrite the existing React web client with a distinctive, commercially appealing visual
identity; move backend data access to SQLAlchemy 2.0 async; collapse RBAC to two roles.
**Status:** Proposed
**Companion spec:** [`docs/superpowers/specs/2026-07-26-web-frontend-rewrite-design.md`](docs/superpowers/specs/2026-07-26-web-frontend-rewrite-design.md)

**Supersedes:** the earlier revision of this document, which described the PySide6 → web migration
as unstarted. That migration is complete and shipped on `main`. This revision reflects the actual
starting state.

---

## Problem Statement

The Smart PID Edge Platform replaced its PySide6 desktop HMI with a React/Vite web client, and that
migration solved the problems that motivated it. The desktop client was hard to test automatically,
so defects survived in the field, and every operator workstation needed a Python and Qt runtime
installed and version-matched to the backend. The web client removed both problems: nothing is
installed on the operator's machine beyond a browser, and the interface is covered by unit,
component and end-to-end tests.

One problem remains, and it is commercial rather than technical.

The shipped client's visual direction is flat ISA-101 — a control-room safety standard that is
correct, restrained, and deliberately austere. Colour is reserved for abnormality, surfaces are
monochrome, and decoration is suppressed by design. That is exactly right for a night-shift operator
staring at a wall of screens, and exactly wrong for selling the product. In a demo, on the website,
or in front of a technical director evaluating vendors, the interface reads as utilitarian legacy
software rather than as a modern industrial-AI product. The engineering is strong; the presentation
undersells it.

Two secondary problems compound this:

- **The frontend cannot be restyled in place.** The client already went through one big-bang styling
  refactor (Tailwind v4 + shadcn + flat ISA-101). It survived only behind a DOM-freeze contract that
  pins `data-testid` values, asserted `className` strings, `role` attributes and dynamic inline
  styles, because the test suite binds to structure rather than behaviour. Any new visual identity
  fights that contract. The tests now constrain the design instead of protecting it.
- **The persistence layer is raw `aiosqlite`.** Hand-written SQL across seven repositories, with no
  ORM, makes the data layer the least idiomatic part of an otherwise clean backend.

Additionally, the deployed authorization model is single-admin — one seeded account, one gate on
every route, no role tiers and no 403s. The product needs a second, restricted role without
rebuilding authentication.

## Solution

Rewrite the frontend source with a new visual identity built for commercial appeal, while preserving
every behaviour the current client has. Replace the data-access layer with SQLAlchemy 2.0 async.
Introduce a second role: administrator and regular user.

**The identity ships as a coherent pair rather than a theme grab-bag:**

- **Recorder** (light, default) — references the continuous strip-chart recorder that predates every
  digital HMI: precision paper, engraved grid, ink-drawn traces, and a live pen tip at the leading
  edge of the trend. Every SCADA competitor is dark; a genuinely premium light interface is
  immediately differentiating and photographs far better for the website and sales deck.
- **Phosphor** (dark) — the control-room companion, sharing one type system and one trace-colour
  language with Recorder. Deep graphite surfaces, luminous PV trace, AI intervention marks on the
  time axis.
- **ISA-101** is retained unchanged for buyers who mandate the standard, but is no longer the
  default. Deleting it would be destructive; demoting it is sufficient.

The five unrelated themes on `main` (Dark Room, ISA-101, MD3 dark, MD3 light, Ocean) reduce to three
themes carrying one identity.

**Backend changes are strictly bounded.** The PID engine, fuzzy and RL engines, OPC-UA adapter,
workers, EventBus and the `RealtimeWS` bridge are untouched. Only the data-access layer and the
authorization dependencies change. The SQL schema, the `.spid` file format and the REST and
WebSocket contracts are unchanged.

## User Stories

### Commercial presentation

1. As a sales engineer, I want the default interface to look like a modern, premium product, so that
   the visual impression matches the sophistication of the control algorithms underneath.
2. As a sales engineer, I want screenshots that stand out from competitors' dark SCADA screens, so
   that our website and proposals are visually distinctive.
3. As a prospective buyer in a live demo, I want the trend chart to be immediately impressive, so
   that the product's core value — a loop being optimized in real time — is obvious at a glance.
4. As a technical director evaluating vendors, I want the interface to feel deliberate rather than
   templated, so that I trust the engineering behind it.
5. As a plant operator, I want a dark theme available for control-room use, so that the commercial
   default does not force me to stare at a light screen on a night shift.
6. As a buyer subject to ISA-101, I want the standard-compliant theme still available, so that the
   product satisfies my site's HMI policy.
7. As a process operator, I want my theme choice to persist across sessions, so that I set it once.

### Access and deployment

8. As a process operator, I want to open the HMI in any modern browser at `localhost`, so that
   nothing has to be installed or version-matched on my workstation.
9. As a maintenance engineer, I want no Python or Qt runtime on operator machines, so that upgrading
   the backend never breaks a client install.
10. As a process operator, I want to log in before reaching any feature, so that unauthenticated
    users cannot operate the plant.
11. As a process operator, I want protected routes to redirect to login when my session is missing
    or expired, so that direct-URL access cannot bypass authentication.
12. As a process operator, I want to log out explicitly and have my token cleared, so that a shared
    workstation is safe after I leave.
13. As a process operator, I want the client to reconnect automatically when the WebSocket drops, so
    that transient network glitches do not cost me visibility.
14. As a process operator, I want state to resynchronize over REST after a reconnect, so that events
    missed during the gap are recovered rather than silently stale.

### Roles

15. As a plant owner, I want exactly two roles — administrator and regular user — so that access
    control is simple enough to administer correctly.
16. As an administrator, I want full access to loop configuration, tuning, AI control, OPC-UA
    settings, projects and users, so that I can commission and maintain the system.
17. As a regular user, I want to operate loops (setpoint, mode, manual output) and acknowledge
    alarms, so that I can run the process day to day.
18. As a regular user, I want configuration controls hidden rather than shown-and-rejected, so that
    the interface reflects what I can actually do.
19. As a plant owner, I want the backend to enforce permissions on every route, so that hiding a
    control in the UI is never the security boundary.
20. As an administrator, I want user credentials stored outside `.spid` project files, so that
    importing a project never leaks or overwrites accounts.

### Live dashboard

21. As a process operator, I want a card per loop showing PV, SP, CO, mode and alarm state, so that
    I can scan plant health in one view.
22. As a process operator, I want cards to update in real time over WebSocket, so that the numbers
    reflect the actual process within milliseconds.
23. As a process operator, I want to select a loop and see its trend update at a high frame rate, so
    that I can judge process dynamics visually.
24. As a process operator, I want the trend to keep a bounded sliding window, so that the chart never
    degrades from unbounded data growth.
25. As a process operator, I want OPC-UA connection status visible per loop, so that I know when
    telemetry is stale because the PLC link is down.
26. As a control engineer, I want PV, SP and CO visually distinguishable by a consistent rule across
    every theme, so that I never misread which series is which.
27. As a process operator, I want a backgrounded tab to drop stale frames rather than replay a
    backlog, so that returning to it shows current state.
28. As a process operator, I want process values rendered in tabular numerals with aligned decimals,
    so that digits do not jump while I read them.

### Commands and loop configuration

29. As a regular user, I want to change a loop's setpoint, so that I can drive the process to a new
    target.
30. As a regular user, I want to switch a loop between Manual and Auto, so that I can take or release
    control.
31. As a regular user, I want to drive the control output manually while in Manual, so that I can
    move the actuator directly.
32. As an administrator, I want a per-loop configuration dialog for PID parameters (Kp, Ti, Td,
    structure, anti-reset-windup, filters), so that I can tune the controller.
33. As an administrator, I want to choose the AI strategy per loop (NONE, FUZZY, RL) and configure
    it, so that each loop uses the appropriate method.
34. As an administrator, I want tuning applied only after explicit confirmation, so that I never push
    bad gains to a live process by accident.
35. As an administrator, I want tuning parameters clamped to guardrails server-side, so that a typo
    cannot destabilize a loop.
36. As an administrator, I want to start, pause and stop the AI worker per loop, so that I control
    when optimization runs.
37. As an administrator, I want AI worker state reflected in real time, so that I am never unsure
    whether optimization is active.
38. As an administrator, I want to enable or disable PID optimization independently of Man/Auto, so
    that I can isolate the optimizer.
39. As a process operator, I want writes forbidden by loop state to fail with a clear reason, so that
    I get feedback instead of silence.
40. As an administrator, I want to create, edit and delete controllers, so that I can manage the loop
    inventory without touching the database.
41. As an administrator, I want backend-generated tuning recommendations surfaced per loop, so that I
    can act on data-driven suggestions.

### Alarms

42. As a process operator, I want alarms to appear in real time, so that I am alerted the moment a
    limit is crossed.
43. As a process operator, I want a persistent alarm bar with counts by severity, so that alarms are
    visible from any page.
44. As a regular user, I want to acknowledge an alarm individually, so that I can record that I have
    seen it.
45. As a regular user, I want to acknowledge all active alarms at once, so that I can handle a flood.
46. As a process operator, I want acknowledgement not to clear an alarm, so that it disappears only
    when the process condition actually returns to normal.
47. As a process operator, I want the four alarm states distinguished — active, acknowledged,
    cleared-unacknowledged, cleared-acknowledged — so that I never lose track of an alarm that
    normalized before I saw it.
48. As a process operator, I want alarm floods deduplicated and the list virtualized, so that
    hundreds of alarms do not freeze the browser.
49. As an administrator, I want to configure per-loop alarm limits and severities, so that thresholds
    match process safety requirements.
50. As a process operator, I want alarm state revalidated against the backend after each
    acknowledgement, so that the UI never diverges from server truth.
51. As a process operator, I want alarm transitions delivered without coalescing, so that no
    transition is dropped under load.

### Trends, statistics, history, export

52. As a control engineer, I want a multi-trend page plotting several loops and signals at once, so
    that I can correlate interactions.
53. As a control engineer, I want zoom or pan on one trend to time-sync the others, so that I inspect
    the same window across signals.
54. As a control engineer, I want to query history for any window, so that I can investigate past
    incidents.
55. As a control engineer, I want per-loop statistics (IAE, ITAE, ISE, MSE, sigma, TV, variability)
    computed server-side, so that numbers are consistent.
56. As a regular user, I want to export displayed trend data to CSV, so that I can analyze it offline.
57. As a plant manager, I want a formatted PDF report with charts, statistics and the AI log, so that
    I can present performance to stakeholders.
58. As a control engineer, I want export scoped per loop or plant-wide, so that it matches my
    analysis.
59. As a control engineer, I want large exports to run in the background, so that the UI stays
    responsive.

### Simulator

60. As a control engineer, I want to run a digital twin against a process preset, so that I can
    validate strategies before commissioning.
61. As a control engineer, I want to adjust dynamics (gain, time constants, dead time) live, so that
    I can explore scenarios.
62. As a control engineer, I want to inject disturbances and measurement noise, so that I can test
    the AI's robustness.
63. As a control engineer, I want to control the twin's output and mode, so that I drive it like a
    real loop.
64. As a control engineer, I want auto-disturbance and auto-setpoint toggles, so that I can run
    unattended stress tests.
65. As a control engineer, I want simulation context visually unmistakable, so that I never confuse
    it with live operation.

### Executive dashboard

66. As a plant manager, I want plant-wide KPIs (percentage in AUTO, AI coverage, bad actors), so that
    I can assess health at a glance.
67. As a plant manager, I want the worst-performing loops ranked, so that I can prioritize effort.
68. As a plant manager, I want before/after AI comparison, so that I can quantify return on the
    optimizer.
69. As a plant manager, I want KPI aggregation done server-side, so that the view stays fast with
    many loops.

### Settings, connection, projects

70. As an administrator, I want a settings page for application preferences, so that I configure the
    system without editing files.
71. As an administrator, I want to configure the OPC-UA endpoint, so that I can point the backend at
    the right PLC.
72. As an administrator, I want to connect and disconnect the OPC-UA session explicitly, so that I
    control when the backend talks to the PLC.
73. As an administrator, I want a searchable OPC-UA tag browser, so that I can map PV, SP, CO and Ti
    to NodeIDs without memorizing them.
74. As an administrator, I want to manage `.spid` projects — list, new, open, import, download,
    delete — so that I can move plant configurations between machines.
75. As an administrator, I want a welcome screen after login listing projects, so that I can resume
    where I left off.
76. As an administrator, I want malicious `.spid` uploads rejected by size cap and path sanitization,
    so that importing cannot compromise the backend.

### Quality and accessibility

77. As a visually impaired operator, I want every theme to meet WCAG AA contrast, so that the
    interface is readable regardless of theme.
78. As a keyboard-only operator, I want visible focus rings and full keyboard operability, so that I
    can work without a mouse.
79. As an operator sensitive to motion, I want animation suppressed when I request reduced motion, so
    that the interface does not cause discomfort.
80. As a process operator, I want loading and empty states designed rather than blank, so that I can
    tell the difference between "no data" and "broken".

### Engineering

81. As a developer, I want the frontend test suite to query by role and accessible name rather than
    by DOM structure, so that a future restyle does not require another freeze contract.
82. As a developer, I want the existing end-to-end suite re-greened phase by phase as each surface
    lands, so that the rewrite converges on proven behaviour instead of a big-bang validation.
83. As a developer, I want frontend types generated from the backend OpenAPI schema, so that contract
    drift is a compile error.
84. As a developer, I want data access through SQLAlchemy 2.0 async rather than hand-written SQL, so
    that the data layer is idiomatic and a future engine change is a dialect change.
85. As a developer, I want the SQL schema and `.spid` format unchanged, so that existing projects and
    historians keep working and backend tests stay valid.
86. As a developer, I want the control engine, AI engines, OPC-UA adapter and WebSocket bridge
    untouched, so that the rewrite cannot destabilize process control.
87. As a developer, I want the WebSocket bridge to never block the daemon event loop, so that PID
    scan timing stays deterministic.
88. As a developer, I want one slow client not to affect others, so that a frozen browser does not
    degrade the control room.
89. As a developer, I want the backend bound to `127.0.0.1` by default, so that the HMI is not
    unintentionally exposed to the LAN.
90. As a developer, I want each rewrite phase to leave the tree green, so that work is reviewable and
    revertible per phase.

## Implementation Decisions

### Stack alignment with `fullstack-selector`

The application is Archetype 3 (RBAC, time series, real time, OPC-UA and ML). Current alignment:

| Prescribed | Status |
|---|---|
| React + Vite + shadcn/ui, explicitly not Next.js when a Python backend is mandatory | Already satisfied |
| FastAPI with native WebSocket, not Django Channels | Already satisfied |
| Continuous loops (PID, OPC-UA, AI) in the asyncio event loop, not Celery | Already satisfied |
| uPlot for high-frequency trends | Already satisfied |
| SQLAlchemy 2.0 async | **Adopted by this work** |
| Custom RBAC | Two-tier model **introduced** by this work (deployed baseline is single-admin) |
| Postgres + TimescaleDB | **Deliberate divergence** — see below |
| Celery + Redis for discrete jobs | Not adopted — the only discrete job (export) is served by the existing in-process worker |

**Divergence on the database.** The guidance says an application with time-series data should
consolidate on Postgres + TimescaleDB. This project keeps SQLite because `.spid` project files *are*
SQLite databases, and project portability is a load-bearing product feature. Migrating would require
redesigning `.spid` as a dump/restore format and invalidating the historian and project-service
tests. The divergence is accepted, recorded, and revisited if sustained historian write contention
appears. SQLAlchemy 2.0 is adopted now so that a future engine change is a dialect change rather
than a rewrite.

### Frontend

- `packages/smart_pid_web/src` is replaced. Tooling is kept: Vite, TypeScript, React 18 (pinned),
  Tailwind v4 + shadcn/Radix (rethemed, not replaced), Vitest, Playwright, the OpenAPI codegen
  script (rebuilt hermetic and committed), and the CI gates for bundle budget, lint and typecheck.
- Logic is separated from React into pure modules that test without a DOM: envelope parsing and
  sequence-gap detection, the bounded sliding window with decimation, the alarm state machine, the
  analog-bar scale and tick maths, and numeric formatting.
- A realtime layer provides one WebSocket per session with reconnect backoff and fan-out, plus a
  resync path triggered by gaps or reconnects.
- Data access is TanStack Query over the typed REST client. Writes are REST only, never over the
  WebSocket; after a write the affected query is invalidated and the server confirms.
- Pages compose features and hold no business logic.

### Visual identity

- Three themes: `recorder` (default), `phosphor`, `isa101`.
- Type: Archivo Expanded for display, Archivo for UI, Geist Mono for all process data. Self-hosted,
  Latin subset, no external CDN. Inter and IBM Plex are deliberately avoided as defaults.
- Trace language constant across themes: PV cool and high contrast, SP dashed graphite as a
  reference, CO warm amber on the right axis. Alarm colours are never reused as trace colours.
- The signature element is the trend: a strip-chart with a live pen tip in Recorder, the same
  geometry with a luminous PV trace and AI intervention ticks in Phosphor.
- Components consume semantic tokens only, never raw colour values, so theme switching requires no
  component change.

### Backend

- Declarative SQLAlchemy models mapped to the existing tables. No new schema changes; the existing
  idempotent add-column back-fill for older `.spid` files is preserved verbatim.
- Async engines over `aiosqlite`, WAL retained — three of them: the `.spid` engine on the main
  loop, a dedicated `.spid` engine on the DB-worker's private loop, and the separate `users.db`
  engine. The real coupling surface is the shared raw connection (`repo.db`), which is replaced by
  injected session factories; the call sites that borrow it are in scope, enumerated in the spec.
- The historian batch insert is preserved; it is the write-hot path and must not regress.
- Authorization gains a second tier: `require_user` (any authenticated principal) and
  `require_admin` (403 otherwise) replace the single `require_authenticated_admin` gate at all its
  call sites; a `users` management router is added; existing role values are migrated one-time
  (`ADMIN`/`SUPERVISOR` to `admin`, `OPERATOR` to `user`) and legacy JWTs are rejected with 401.

### Contracts

- Existing REST routes, request and response models are unchanged. Additive only: the `users`
  router and 403 responses on admin-only routes.
- The WebSocket envelope `{ type, loop_id, seq, ts, data }` is unchanged.
- Types are generated from the served OpenAPI document.

## Testing Decisions

Tests assert observable behaviour, not internal structure. The previous suite bound so tightly to
`data-testid`, asserted `className` values and inline styles that a DOM-freeze contract was required
to survive a restyle; the new suite must not recreate that.

- **Unit** — pure modules with no DOM: envelope, window buffer, alarm state machine, scale, format.
- **Component** — every primitive and feature under Vitest and Testing Library, queried by role and
  accessible name wherever a role exists; `data-testid` only where no semantic query is available.
- **Integration** — the realtime hook against a fake WebSocket; the API client against a mocked API.
- **End-to-end** — the existing thirteen Playwright specs are re-greened per phase as each surface
  lands (the theme spec is rewritten — it hardcodes the five dropped themes), plus one new spec
  covering regular-user role gating. E2E specs stub the API and WebSocket, so they verify frontend
  behaviour; backend behaviour is covered by pytest plus a 403-per-route contract test.
- **Visual** — regenerated baselines: three themes across four breakpoints plus the faceplate
  (13 total); the 21 old baselines are deleted.
- **Contrast and accessibility** — automated gates per theme: WCAG AA 4.5:1 for text, 3:1 for
  non-text (traces, alarm fills, focus ring, control boundaries), focus ring at least 2px, target
  size at least 44 by 44, token resolution in every theme, reduced-motion compliance.
- **Backend** — behaviour-level pytest stays green through the SQLAlchemy swap. The shared test
  fixture layer and the tests that touch the raw connection directly are adapted in the same
  phase; fixture code that authors `.spid` files with raw SQLite stays raw (that is the file
  format, not the data layer). The historian is benchmarked before and after.

Prior art: `tests/core/integration/test_telemetry_publisher.py` for bridge-style integration tests,
and the existing alarm-engine tests as the reference for the frontend alarm state machine.

## Out of Scope

- Rewriting the PID engine, fuzzy engine, RL engine, OPC-UA adapter, workers, EventBus or the
  `RealtimeWS` bridge.
- Migrating to Postgres or TimescaleDB, and any change to the `.spid` file format.
- Introducing Celery or Redis.
- Any SQL schema change, table rename or migration.
- Changing existing REST routes or the WebSocket envelope (the `users` router and 403 responses
  are the only additive surface).
- Retiring the PySide6 client. It is already frozen; removal is separate work.
- Multi-tenant, remote or LAN-exposed operation. The bind stays `127.0.0.1`.
- Roles beyond `admin` and `user`.
- The MD3 dark, MD3 light, Ocean and Dark Room themes, which are dropped rather than ported.
- Offline or installed-PWA operation.

## Further Notes

**Authority.** The companion design spec at
`docs/superpowers/specs/2026-07-26-web-frontend-rewrite-design.md` governs architecture, tokens,
module structure and sequencing. Where this PRD and that spec disagree, the spec wins on
implementation detail and this PRD wins on product intent.

**Sequencing.** Twelve phases. The two backend phases land first: the two-role model on the current
data layer, then the SQLAlchemy port against the final role model. Frontend foundation (tokens,
themes, primitives) and the realtime layer follow, then feature surfaces one at a time — each
re-greening its own end-to-end specs — then ISA-101 retokenisation and visual baselines.

**Theme reduction.** Going from five themes to three is a deliberate reduction in maintenance
surface. Five unrelated themes each needed their own contrast validation and visual baselines;
three themes carrying one identity need less and communicate more.

**Risk to watch.** The largest risk is that the rewrite silently drops a behaviour present in the
current client. The retained end-to-end suite is the primary control, which is why patching its
selectors is treated as required work rather than cleanup.
