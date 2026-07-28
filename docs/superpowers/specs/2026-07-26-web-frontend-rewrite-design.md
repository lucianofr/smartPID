# Design — Web Frontend Rewrite (Recorder/Phosphor identity)

**Documento:** Design / Spec (saída de brainstorming)
**Data:** 2026-07-26 (v2 — revised after 5-facet review)
**Autor:** Luciano França Rocha — LFR Automação
**Status:** Proposto (aguardando revisão)
**Companion:** [`PRD.md`](../../../PRD.md) — product requirements
**Branch:** `docs/web-frontend-rewrite-spec`
**Review reports:** `.claude/reports/arch/arch-rewrite-spec-20260726.md`, `review/review-rewrite-spec-{facts,python,a11y}-20260726.md`, `design/design-rewrite-spec-20260726.md`

> Written in English to match the companion PRD. Prior specs in this directory are in Portuguese;
> code, commits and identifiers remain English per `CLAUDE.md`. **UI copy stays pt-BR** and
> accessible names are preserved verbatim — the retained E2E suite binds to them
> (`Usuário`, `Senha`, `Entrar`, `Salvar`, `Fechar`).

---

## 1. Context

The Smart PID Edge Platform has completed its PySide6 to web migration. `packages/smart_pid_web`
on `main` contains a working React/Vite client: all 8 slices shipped, 241 files, ~7,900 LOC of
non-test source, 72 unit/component test files, 13 Playwright E2E specs, and 21 visual baselines
(5 themes × 4 breakpoints + 1 faceplate). The backend `RealtimeWS` bridge exists and works.

That client has been through one big-bang styling refactor (Tailwind v4 + shadcn + flat ISA-101),
executed behind a DOM-freeze contract (`packages/smart_pid_web/docs/freeze-inventory.md`) whose sole
purpose was to keep the existing Vitest suite green while primitives were swapped wholesale.

**The problem is not function — it is commercial presentation.** The flat ISA-101 result is
standards-correct and safe, but it does not sell. The product needs a visual identity with
commercial appeal for demos, the website, and buyer-facing evaluation, while remaining a credible
industrial HMI.

Secondarily, the persistence layer uses raw `aiosqlite`. The `fullstack-selector` guidance places
this application in **Archetype 3** (RBAC + time series + real-time + OPC-UA/ML) and recommends
SQLAlchemy 2.0 async as the idiomatic data-access layer.

**Authorization baseline (corrected in v2):** `main` is a **single-admin** deployment. The only
gate is `require_authenticated_admin` (63 call sites across 14 routers); there are no role tiers
and no role-based 403s. The earlier mono-user plan already landed. This work therefore *introduces*
a second role — it does not collapse three.

## 2. Goals

1. Replace the frontend source with a new implementation carrying a distinctive, commercially
   appealing visual identity.
2. No regression in behaviour covered by the retained E2E suite and the backend pytest suite
   (the verifiable form of "preserve every existing behavior").
3. Move backend data access from raw `aiosqlite` to SQLAlchemy 2.0 async, preserving the schema
   and the existing idempotent column back-fill for old `.spid` files.
4. Introduce a second role: `admin` (full) and `user` (operate + observe), with the product's
   first 403 semantics and a user-management surface.
5. Keep the `.spid` portable-project model intact.

## 3. Non-goals

- Rewriting the PID engine, fuzzy engine, RL engine, OPC-UA adapter, workers, EventBus or
  `RealtimeWS` bridge. These are untouched.
- Changing the database engine. SQLite with WAL stays. No Postgres, no TimescaleDB.
- Introducing Celery or Redis.
- Changing the SQL **schema** (tables/columns). The existing `_apply_migrations()` add-column
  back-fill for older `.spid` files is *preserved verbatim* — "no migrations" means **no new**
  schema changes, not deletion of the load-bearing bootstrap.
- Changing **existing** REST routes or the WebSocket envelope. Additive surface required by the
  two-role model is in scope and enumerated in §9: a `users` router, 403 responses on admin-only
  routes, and the role-value data migration.
- Export-history listing (`GET /export/list` does not exist). The rewrite does not promise an
  export-history UI; the PRD is aligned. Recorded as tech debt TD-008.
- Retiring the PySide6 client. Already frozen; removal is separate work.
- Multi-tenant, remote or LAN-exposed operation. Bind stays `127.0.0.1` (verified: it is the
  current default, with CORS + TrustedHost allow-lists wired).

## 4. Locked decisions

| Decision | Value | Rationale |
|---|---|---|
| Backend scope | SQLAlchemy 2.0 async over SQLite + two-role authorization | Idiomatic data layer per `fullstack-selector`; `.spid` portability outweighs TimescaleDB |
| Frontend scope | Full rewrite of `src/` | New identity cannot be reached by patching DOM frozen to old tests |
| Roles | `admin`, `user` | **Expands** the shipped single-admin model (not a collapse; v1 premise was wrong) |
| Default theme | Recorder (light) | Differentiates from uniformly dark competitors; photographs well for sales |
| Dark theme | Phosphor | Control-room companion, shares one identity with Recorder |
| ISA-101 | Retained, demoted, **retokenised** | Visual output unchanged; implementation re-expressed on the shared token contract (§6.4) |
| Styling engine | **Tailwind v4 + shadcn/Radix kept**, rethemed | Preserves primitive skeleton, bundle continuity, and the token-only lint guard; React pinned at 18 |
| Test strategy | Keep E2E specs, staged re-enable per phase; rebuild unit | §12–§13; `themes.spec.ts` is a rewrite, not a patch |

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
production and proxied from Vite in development (**dev port pinned to 5173** — the CORS/TrustedHost
allow-list is bound to `http://127.0.0.1:5173` / `http://localhost:5173`).

```
OPC-UA ──asyncua──> IO Worker ──> EventBus ──┬──> PID / AI / Alarm / Stats workers
                                              ├──> DB worker (own thread + loop, own engine)
                                              ├──> TelemetryPublisher ──> ZMQ 5555 (PySide6, legacy)
                                              └──> RealtimeWS ──> WS /ws/realtime ──┐
                    FastAPI REST /api/* ───────────────────────────────────────────┤
                    SQLAlchemy 2.0 async ──┬─> engine A: .spid (main loop)          │
                                           ├─> engine B: .spid (DB-worker loop)     │
                                           └─> engine C: users.db (main loop)       v
                                              smart_pid_web (React 18 + Vite + TS, rewritten)
```

Three engines is a consequence of two constraints: `AsyncEngine` is loop-affine (the DB worker runs
a private loop on its own thread), and credentials live in a separate `users.db` that must never
travel inside `.spid`. Details in §10.

## 6. Visual identity

### 6.1 Principle

The product is an instrument, and its most characteristic artifact is the closed loop rendered over
time. The identity is grounded in the physical heritage of process instrumentation — panel-mount
controllers and continuous strip-chart recorders — rather than in generic dashboard language.

Boldness is spent in exactly one place: the trend. Everything around it stays quiet.

### 6.2 Typography

Two families, self-hosted, no external CDN.

| Role | Face | Use |
|---|---|---|
| Display | **Archivo Variable**, `wdth` 125 ("Expanded"), weight 600–700 | Headings, wordmark, section labels — **never numerals** |
| Body / UI | Archivo Variable, `wdth` 100, weight 400–600 | Labels, controls, prose |
| Data | **Geist Mono**, weight 400/500 | **Every numeral in the product**, incl. KPI figures; tabular by construction |

Decisions (previously ambiguous or deferred, now fixed):
- **Numerals are always Geist Mono.** A KPI figure is a metric; Archivo Expanded never renders
  digits. This resolves the display-vs-data conflict on the product's most prominent glyph run and
  keeps decimal columns aligned across loops (`font-variant-numeric: tabular-nums` retained as
  belt-and-braces; slashed zero **kept** — `font-feature-settings: 'zero' 1`).
- **File strategy:** one Archivo Variable woff2 (wght + wdth axes, Latin subset) + two Geist Mono
  static woff2 (400, 500, Latin). `font-display: swap`; both families preloaded; fallback stacks
  are metric-compatible (`system-ui` / `ui-monospace`) accepting minor reflow on first paint.
- **Font budget:** combined font transfer ≤ 160 KB. `scripts/check-bundle.mjs` is **extended in
  phase 2** to sum `dist/assets/*.woff2` — today it measures only the entry JS chunk and its CSS,
  so fonts are invisible to the existing gate (§14 v1 over-claimed this).
- Token names: `--font-display`, `--font-ui`, `--font-data` (consumed today by `uplotTheme.ts`).

Inter and IBM Plex remain deliberately avoided.

### 6.3 Trace language (constant across Recorder and Phosphor)

| Series | Treatment |
|---|---|
| PV | Cool, highest contrast — the measured truth. Width `--trend-pv-width: 2px` |
| SP | Dashed graphite, low emphasis — a reference. Width `--trend-sp-width: 1.5px` |
| CO | Warm amber, right axis — valve output. Width `--trend-co-width: 1.5px` |

Alarm colors are never reused as trace colors, and trace colors never signal alarm state.
**ISA-101 keeps its own, stricter rules unchanged** (gray-until-abnormal PV, solid blue SP): this
section governs the two new themes only.

One sanctioned exception to "color = process meaning" carried over from the current app:
destructive actions (Delete project, Delete controller) use `--alarm-crit` on their confirm
affordance. No fourth red is invented.

### 6.4 Token contract (normative — all themes share these names)

Components consume **only** these custom properties. Poetic names ("paper", "void") are comments in
the CSS, never selectors. A token-resolution test asserts every name below resolves non-empty under
every `[data-theme]` (successor of `tokenResolve.test.ts`), and the token-only source guard
(successor of `isa101-guard.test.ts` + the `no-raw-color` lint fixtures) is re-established in
phase 2 — deleting `src/` deletes the current enforcement, so the guard ships *with* the tokens.

```
Surfaces:  --bg  --surface  --surface-sunk
Lines:     --rule  --rule-strong
Text:      --text  --text-soft  --text-disabled
Focus:     --focus-ring          Selection: --selection      Overlay: --scrim
Accent:    --accent  --accent-hover  --accent-sunk  --accent-soft  --on-accent
Alarm:     --alarm-crit  --alarm-crit-bg  --alarm-warn  --alarm-warn-bg
           --alarm-adv   --alarm-adv-bg   --alarm-log   --on-alarm
State:     --state-running  --state-stopped  --state-error  --state-oos
Trend:     --trace-pv  --trace-sp  --trace-co
           --trend-grid  --trend-axis  --trend-bg
           --trend-pv-width  --trend-sp-width  --trend-co-width
Bar:       --bar-track  --bar-fill  --bar-marker
Type:      --font-display  --font-ui  --font-data
```

Notes:
- The old 5-step surface ladder (`surface-container`, `-high`, `field-bg`…) collapses to 3 steps
  **deliberately**; ISA-101's retokenisation maps its 5 values onto these 3 names (visual output
  unchanged — the mapping table lands with phase 11).
- `--alarm-log` exists because the domain has **four** severities (`CRITICAL/WARNING/ADVISORY/LOG`,
  `severity.ts`); v1 supplied three and `sev-log` resolved to nothing.
- Alarm severity is never color-only: severity keeps its icon + text label channel (octagon /
  triangle / circle glyphs as today), and unacked state keeps a non-color channel (weight + icon),
  with blink subject to §11's reduced-motion policy.
- All state tokens are gray in normal operation. **Green never means "ok"** — inherited rule.

### 6.5 Recorder — light, default (values)

All values below verified: text ≥ 4.5:1, UI components/graphics ≥ 3:1 against their assigned
surfaces (computed 2026-07-26; two v1 values corrected: `--alarm-warn` was 3.99:1, `--trace-co`
was 2.98:1).

```css
[data-theme="recorder"] {
  --bg: #F7F8FA;            /* cool paper */         --surface: #FFFFFF;
  --surface-sunk: #EEF1F5;  /* chart wells, inputs */
  --rule: #DCE2EA;          /* hairlines, engraved grid — decorative only */
  --rule-strong: #7C8894;   /* control boundaries — 3.62:1 on surface */
  --text: #16202B;  --text-soft: #5A6875;  --text-disabled: #8B95A0;
  --focus-ring: #16202B;  --selection: #DCEBEB;  --scrim: rgba(10, 14, 20, 0.5);
  --accent: #0E6B6B;  --accent-hover: #0B5757;  --accent-sunk: #083F3F;
  --accent-soft: #E1EEEE;  --on-accent: #FFFFFF;                /* 6.30:1 */
  --alarm-crit: #C02026;  --alarm-crit-bg: #F7DCDC;
  --alarm-warn: #9E5E00;  --alarm-warn-bg: #F5E3CC;             /* 4.87:1 on bg */
  --alarm-adv:  #6B4FA8;  --alarm-adv-bg:  #E8E1F4;
  --alarm-log:  #5A6875;  --on-alarm: #FFFFFF;                  /* ≥5.18:1 on all fills */
  --state-running: #7C8894;  --state-stopped: #5A6875;          /* gray, never green */
  --state-error: #C02026;    --state-oos: #B0B8C0;
  --trace-pv: #1B4F87;  --trace-sp: #7C8894;  --trace-co: #BC7211;  /* 3.34:1 on sunk */
  --trend-grid: #E4E9EF;  --trend-axis: #9DA9B5;  --trend-bg: #EEF1F5;
  --trend-pv-width: 2px;  --trend-sp-width: 1.5px;  --trend-co-width: 1.5px;
  --bar-track: #EEF1F5;  --bar-fill: #5A6875;  --bar-marker: #16202B;
}
```

### 6.6 Phosphor — dark companion (values)

```css
[data-theme="phosphor"] {
  --bg: #0A0E14;            /* void */               --surface: #131A24;  /* panel */
  --surface-sunk: #0E141C;  /* chart wells — new in v2; traces ≥ 3:1 on it */
  --rule: #253040;
  --rule-strong: #54697F;   /* 3.08:1 on surface */
  --text: #D6DEE8;  --text-soft: #8894A3;  /* 5.67:1 on surface (v1 value was 4.46 on raised) */
  --text-disabled: #55616E;
  --focus-ring: #D6DEE8;  --selection: #16304A;  --scrim: rgba(0, 0, 0, 0.6);
  --accent: #23A6A6;  --accent-hover: #2FBDBD;  --accent-sunk: #1A7F7F;
  --accent-soft: #10302F;  --on-accent: #0A0E14;                /* 6.52:1 — white FAILS here */
  --alarm-crit: #FF4D4D;  --alarm-crit-bg: #3A0E0E;
  --alarm-warn: #FFA51F;  --alarm-warn-bg: #3A2A00;
  --alarm-adv:  #A98BFF;  --alarm-adv-bg:  #241A3E;
  --alarm-log:  #8894A3;  --on-alarm: #0A0E14;                  /* ≥5.91:1 on all fills */
  --state-running: #5E7080;  --state-stopped: #8894A3;
  --state-error: #FF4D4D;    --state-oos: #3E4A57;
  --trace-pv: #9FC8F0;  --trace-sp: #6E7B8A;  --trace-co: #E39B3D;
  --trend-grid: #16202E;  --trend-axis: #3E4E63;  --trend-bg: #0A0E14;
  --trend-pv-width: 2px;  --trend-sp-width: 1.5px;  --trend-co-width: 1.5px;
  --bar-track: #0E141C;  --bar-fill: #5E7080;  --bar-marker: #8FB6D6;
}
```

Phosphor uses a duotone data language (cool PV, warm CO) from instrument convention rather than a
single saturated accent on near-black. The teal accent sits apart from PV blue, CO amber and alarm
red in both themes, so interactive chrome never collides with process meaning.

### 6.7 Signature element — the trend

Both themes share geometry; the treatment differs:

- **Recorder** — continuous strip chart: engraved grid (`--trend-grid`), ink traces, live **pen
  tip** at the leading edge. Implemented as a uPlot `hooks.draw` plugin marking `valToPos()` of the
  **true latest sample — not the tail of the decimated series** (the `windowBuffer` decimation
  policy must expose the undecimated head, or the pen visibly jumps at high rates).
- **Phosphor** — PV trace carries a glow rendered as a **halo pass**: re-stroke the PV path 1–2×
  with wider `lineWidth` at low `globalAlpha` before the crisp stroke. **`ctx.shadowBlur` is
  banned from the per-frame path** (phase-4 acceptance criterion) — its cost scales with path
  length × radius at 60 fps and collapses on multitrend pages. AI-intervention ticks on the time
  axis take their timestamps from the `ai` envelope events (`ACTION.AI.{id}`), buffered alongside
  the trend window.

Under `prefers-reduced-motion`: the pen tip freezes to a static marker at the leading edge (no
trailing animation), the halo remains (static, not animated), and ticks render without transition.

### 6.8 Theme inventory, default and persistence

Three themes ship: `recorder` (default), `phosphor`, `isa101`. MD3 dark/light and Ocean are
dropped; Dark Room is superseded by Phosphor.

- `DEFAULT_THEME` changes to `recorder` (today `isa101`).
- Persistence is **per browser**: `localStorage` key `spid.theme` (kept). Resolution order:
  stored value → `recorder`. No `prefers-color-scheme` auto-switch — an operator's theme is an
  explicit choice.
- **Stored-value migration:** `dark-room → phosphor`; `md3-dark`, `md3-light`, `ocean` →
  `recorder`; unknown → `recorder`. Without this rule a returning user with `spid.theme='ocean'`
  silently falls to the default constant.
- ISA-101 is **retokenised** onto §6.4's contract with **unchanged visual output** (its current
  values re-expressed under the new names, 5→3 surface mapping documented in phase 11). "Retained
  unchanged" in v1 was ambiguous; the visual result is unchanged, the CSS is not.

### 6.9 Layout — operational dashboard

```
+---------------------------------------------------------+
| SMART PID   Loops Trends Alarms Sim      [k] [cfg] [sair]|
+---------------------------------------------------------+
| [FIC-101] [TIC-202] [LIC-303] [PIC-404] ->   loop cards  |
+-----------------------------------+---------------------+
| TREND  strip chart, pen tip       | FACEPLATE  (~320px) |
| .................grid............ | PV #####-  150.2    |
|    /~~\___ PV                 (o) | SP ####--  148.0    |
| --------- SP dashed               | CO ##----   42.1    |
|  /~~\ CO, right axis              | [AUTO][MAN]  IAE 12.4|
|                                   | [Apply tuning]*     |
+-----------------------------------+---------------------+
| alarms: 2 CRITICAL 1 WARNING      (quiet when none)     |
+---------------------------------------------------------+
```

Rules that phase 4 must not improvise:

- **Navigation:** top bar with `Loops · Trends · Alarms · Sim`; `[cfg]` menu hosts Projects,
  Settings, Connection, Users. This replaces the current NavRail — a deliberate IA change.
- **Card overflow:** loop cards render in a **single row with horizontal scroll and edge fade**;
  wrapping is forbidden (it pushes the trend below the fold — the demo's money shot).
- **Faceplate:** fixed content width ~320 px; the trend takes all remaining width (≥ 65% at 1440).
  The `user`-role faceplate **omits** `[Apply tuning]` (admin-only, §9) — the shorter variant is a
  designed state, not a hole.
- **Alarm bar quiet state:** with zero unacked alarms the bar renders monochrome (counts in
  `--text-soft`); alarm colors appear only while unacked alarms exist. A permanently red footer
  would compete with the trend and violate §6.1.
- **Responsive (baselines exist at 320/768/1024/1440):** below 1024 the faceplate stacks under the
  trend; below 768 cards become a horizontal scroller above a full-width trend, and the alarm bar
  collapses to a count chip. 320 is a degraded-but-usable floor (monitoring, ack, SP entry), not a
  design target.

## 7. Frontend module structure

Layered so that logic is testable without a DOM.

**Stack pins:** React **18** (Radix/shadcn pins depend on it), Tailwind **v4** CSS-first with the
`@theme inline` token bridge over `[data-theme]` custom properties, shadcn primitives over Radix.
The rewrite reuses this engine — restyled, not replaced.

**Pure modules — no React, no DOM:**

| Module | Responsibility |
|---|---|
| `envelope` | Parse/validate the WS envelope; detect `seq` gaps; track `last_seen_ts` per topic class |
| `windowBuffer` | Bounded sliding window with explicit decimation; exposes the undecimated latest sample (pen tip) |
| `alarmMachine` | Four-state ack/clear transitions |
| `scale` | Value-to-percent, clamping, tick generation for AnalogBar |
| `format` | Tabular numeric formatting, units, decimal places (single module — today's `format` is duplicated in `lib/` and `multitrend/`) |

**Realtime:** `RealtimeProvider` (single socket, reconnect with backoff, fan-out),
`useRealtime(loopId, type)`, and `resync`. **Resync set (normative):** controllers · active alarms ·
**alarm history since `last_seen_ts`** (`GET /alarms/history?start=…` — active-only misses alarms
that fired *and cleared* during the gap, breaking the cleared-unacknowledged promise) · AI status ·
OPC-UA status · simulator status.

**Data:** `apiClient` typed from the OpenAPI schema. The codegen chain is **rebuilt** (today the
output is gitignored, produced against a live server, and imported by nothing):
- the generated file is **committed** (drop the `.gitignore` entry);
- generation is **hermetic** — a script dumps `app.openapi()` to a static JSON and
  `openapi-typescript` consumes the dump, no listening daemon required;
- a CI-listed gate regenerates and fails on diff;
- regeneration is sequenced **immediately after phase 0** (the role change alters the schema:
  403 responses, role field, users router).

**Auth:** `AuthContext`, `RouteGuard`, `useCan(action)` — all new surface (no role logic exists in
the current client).

**Design system:** `ThemeProvider` (`data-theme` on root, `spid.theme` persistence + legacy value
migration per §6.8); `tokens.css` / `themes.css`; the **uPlot token bridge is retained** —
`readTrendTokens(getComputedStyle(…))` → `buildUplotTheme(…)`, plus the `themeKey` re-instantiation
pattern (uPlot bakes stroke colors at construction; theme switch must rebuild the plot).

**Primitives (phase 2 scope — v1 listed 7 of 17):** `AnalogBar`, `Trend`, `Readout`, `Dialog`,
`Field`, `Button`, `Badge`, `Select`, `Slider`, `Switch`, `Tabs`, `Toast`/`Toaster`, `Tooltip`,
`DropdownMenu`, `Command` (the `[k]` palette, `cmdk`), `VirtualList` (`@tanstack/react-virtual` —
alarm flood), `MissingState` (loading / empty / error-disconnect).

**Features:** **dashboard**, **executive**, alarms, loop-config, multitrend, simulator, projects,
connection, settings, **users** (new).

**Pages:** thin composition only, no business logic.

## 8. Data flow

- Reads go through TanStack Query over REST, cached and invalidated on mutation.
- Live data arrives on a single WebSocket per session, fanned out by the provider.
- Writes are REST only, never over the WebSocket.
- After any write, the affected query is invalidated and REST confirms. Optimistic state is never
  trusted for process values.
- On reconnect or a detected `seq` gap, the §7 resync set runs before live render resumes.

## 9. Roles and permissions

**Baseline (v2 correction):** the deployed model is single-admin — one seeded account,
`require_authenticated_admin` on every protected route, no 403s anywhere. Phase 0 therefore
**builds** the two-tier model: it does not simplify an existing one.

Two roles. The backend enforces on every route; the frontend hides controls for presentation only.

| Capability | `admin` | `user` |
|---|---|---|
| View dashboards, trends, alarms, stats | yes | yes |
| Acknowledge alarms | yes | yes |
| Set SP, mode, manual CO | yes | yes |
| Export data (create + download) | yes | yes |
| Edit PID / fuzzy / RL parameters, apply tuning | yes | no |
| Start, pause, stop AI workers; optimization toggle | yes | no |
| Create, edit, delete controllers | yes | no |
| Configure alarm limits | yes | no |
| OPC-UA connection and tag mapping | yes | no |
| `.spid` project management | yes | no |
| Manage users | yes | no |
| Change application settings | yes | no |

Phase-0 deliverables (the real work, previously understated):

1. **Dependencies:** `require_user` (any authenticated principal) + `require_admin` (403
   otherwise) replace the single gate at all 63 call sites.
2. **Route classification appendix:** every gated route mapped to `user` or `admin` per the table
   above, written into the phase-0 plan and enforced by a **parametrised backend contract test**
   (one pytest over the admin-only route list asserting 403 for `user`, 2xx/409 for `admin`).
   Simulator's 17 endpoints are admin-only except twin SP/mode/CO (mirroring real-loop operation).
3. **Users API (new surface, §3 amended):** a `users` router — list / create / update role /
   deactivate / change password — admin-gated. `RegisterRequest` (currently dead code) is reworked
   to the new role enum. The settings UI gains the matching admin-only management panel (phase 10);
   the current client asserts the *absence* of such a panel, so its test is superseded.
4. **Role-value data migration (mandatory):** existing `users.db` rows hold `'ADMIN'`,
   `'SUPERVISOR'`, `'OPERATOR'` (uppercase; legacy `.spid` imports copy them verbatim). A one-time
   startup `UPDATE` maps `ADMIN → admin`, `SUPERVISOR → admin` (they held tuning/config powers),
   `OPERATOR → user`; the DDL default changes from `'OPERATOR'` to `'user'`. Without this, the
   enum change turns every legacy non-admin login into an unhandled 500 (pydantic `ValidationError`
   in `get_current_user`) — permanent lockout.
5. **JWT transition:** tokens carry the old role string for up to 8 h. Legacy role claims are
   **rejected with 401** (single forced re-login), not mapped — simplest rule, no dual-vocabulary
   window.

Credentials remain in the separate `users.db`, never inside `.spid`.

## 10. Backend change — SQLAlchemy 2.0 async

Scope corrected: the coupling surface is **not** a set of repository methods — it is a **shared
connection object**. `SQLiteRepository.db` is declared public ("exposed for shared use by
historian") and is borrowed by `historian`, `alarm_repo`, `audit_repo`, `ai_repo` (lazy
re-reading properties), consumed directly by `main.py` (`_load_alarm_configs(repo.db)`,
`SystemEventRepository(repo.db)`, `_retention_cleanup(repo.db)`, user-migration
`user_repo.db.execute`), captured **eagerly** by `SystemEventRepository.__init__` (typed
`aiosqlite.Connection`), and read as `_repo._db_path` by `project_service`. The v1 sentence
"callers are unaffected" is deleted; those call sites are **in scope**.

**Topology (the central phase-1 decision, previously unstated):**

- **Engine A** — `.spid`, main asyncio loop. All repositories + API. `StaticPool` is not viable
  across loops, so: `NullPool` is rejected too (per-query connect cost on the hot API path);
  **`AsyncAdaptedQueuePool` with `pool_size=1, max_overflow=0`** — exactly one connection,
  preserving today's single-connection serialization on the main loop.
- **Engine B** — `.spid`, DB-worker loop. `AsyncEngine` is **loop-affine**; the DB worker keeps its
  own thread + private loop (an architecture §3 protects), so it owns a dedicated single-connection
  engine. Two writers under WAL ⇒ **`busy_timeout=5000`** PRAGMA on both engines (absent today
  because today there is literally one connection).
- **Engine C** — `users.db`, main loop, single-connection. Never touched by project switching.
- **PRAGMAs** move to a sync `connect` event listener per engine: `journal_mode=WAL`,
  `busy_timeout=5000`, and **`foreign_keys` stays OFF explicitly** — SQLite defaults OFF, so every
  `ON DELETE CASCADE` in the DDL is inert today; enabling FKs (the canonical SQLAlchemy recipe)
  would activate cascades and new FK violations, a behavior change this spec forbids.

**Data-access rules:**

- Declarative models map the **existing** tables; DDL bootstrap (`CREATE TABLE IF NOT EXISTS`) and
  the idempotent `_apply_migrations()` add-column back-fill run on every open/reopen exactly as
  today (old field `.spid` files depend on them).
- **Historian hot path pinned to Core:** `conn.execute(insert(log_processo), rows)` — the
  executemany fast path — one commit per batch. `session.add_all()` (per-object flush) is
  forbidden here. Benchmark before/after phase 1.
- **Session-per-method with immediate commit** — the behavior-preserving transaction scope (today
  every repo method commits on the shared connection). Session-per-request would change commit
  timing observed by the workers.
- Row access migrates `aiosqlite.Row` name-indexing to `.mappings()`; `lastrowid`/`rowcount`
  usages stay on Core `CursorResult`.
- `SystemEventRepository`'s constructor signature **changes** (session factory instead of a raw
  connection). Its latent stale-connection bug (eager capture, never sees `reopen()`) is **fixed by
  the port** — after a project switch it currently writes to a closed connection; the fix is a
  deliberate, documented behavior change.

**`.spid` lifecycle across `reopen()` (highest-risk path):**

1. `PRAGMA wal_checkpoint(TRUNCATE)` on engine A;
2. dispose engines A and B (drain — no pooled handle may survive, or `delete_project` fails on a
   held file and `-wal`/`-shm` siblings corrupt the download);
3. re-create both engines against the new path; re-run bootstrap + back-fill.

`GET /project/download` runs `wal_checkpoint(TRUNCATE)` **before** streaming the live file, so a
downloaded `.spid` cannot silently miss recent writes. `list_projects` keeps its raw per-file
`aiosqlite.connect` probe (read-only, out of engine scope).

**Acceptance (replaces v1's "suite passes unmodified"):** behavior-level backend tests pass; the
shared `tests/conftest.py` fixture layer and the ~15 test files that touch `repo.db` /
`aiosqlite` directly (incl. `test_sqlite_repo` journal/table helpers, `test_system_event_repo`'s
constructor, `test_ai_repo`, `test_db_worker_ai_log`) are adapted **in the same phase**. Fixture
authoring that builds `.spid` files with raw `aiosqlite` stays raw — that is the file format, not
the data layer. New tests: `open → download → delete` leaves no open handle; WAL checkpoint before
download; busy-timeout under concurrent engine A/B writes.

## 11. Error handling and motion policy

| Condition | Behavior |
|---|---|
| Transport failure / offline | Typed error from `apiClient`; offline banner; queries pause, WS reconnects with backoff |
| 401 | Clear session, redirect to login |
| 403 | **New in this work.** Control was wrongly shown or role changed mid-session: toast "sem permissão", refetch `me`/capabilities |
| 404 | Deleted controller / expired export id: remove stale entity from cache, MissingState |
| 409 | Loop-state conflict (mode, OPC): show reason, preserve form state |
| 422 | Validation from typed bodies: field-level messages, form stays editable |
| 5xx | Generic failure state with retry; never blank |
| 502 | OPC-UA down: loop-level banner, writes disabled, reads continue |
| WS close 4401 | Token invalid: force re-login |
| WS overflow close | Reconnect + full §7 resync (alarm history closes the fired-and-cleared gap) |

Every destructive write sits behind an explicit confirmation dialog. Loading and empty are designed
states (`MissingState`), not spinners over blank space.

**Reduced-motion policy (global, not per-feature):** all animation is suppressed or replaced with
static equivalents under `prefers-reduced-motion: reduce` — alarm blink becomes a static
highlighted state (the current `useReducedMotion` behavior is the floor), the pen tip freezes
(§6.7), transitions drop to none. This is a §12 gate, not an aspiration.

## 12. Testing

| Layer | Scope |
|---|---|
| Unit | Pure modules with no DOM: `envelope`, `windowBuffer`, `alarmMachine`, `scale`, `format` |
| Component | Every primitive and feature, Vitest + Testing Library, queried by role and accessible name |
| Integration | `useRealtime` against a fake WebSocket; `apiClient` against a mocked API |
| Backend contract | **403-per-route parametrised test** over the admin-only list (phase 0); OpenAPI **drift gate** (regenerate + fail on diff) |
| E2E | 13 existing Playwright specs re-greened **per phase** (§13 table); `themes.spec.ts` **rewritten** (hardcodes the 5 old themes); one new spec: `user`-role gating (login as `user`, assert hidden admin controls + 403 handling) |
| Visual | **13 baselines**: 3 themes × 4 breakpoints + 1 faceplate. The 21 old baselines are deleted in phase 11 |
| Contrast & a11y gates | AA 4.5:1 text per theme; **3:1 non-text** (traces, alarm fills, focus ring, control boundaries, state dots, bar fill); focus ring ≥ 3:1 **and** ≥ 2px; target size ≥ 44×44; token-resolution (every §6.4 name, every theme); reduced-motion gate |
| Source guard | Token-only colors (`no-raw-color`) re-established in phase 2 with the lint fixtures |
| Backend | Pytest suite green per §10's acceptance; historian before/after benchmark |

E2E specs stub the API and WebSocket (`page.route` + `addInitScript`) — they verify **frontend**
behavior only; §14 no longer claims them as backend coverage. Component tests query by role and
accessible name wherever a role exists; `data-testid` only where no semantic query is available.
`freeze-inventory.md` is retired with the old source; a new, much smaller contract is derived from
the new primitives once they stabilize.

## 13. Sequencing

12 phases. Order justification (v2): **roles land before the ORM swap** — the role-value migration
is a data change best authored against the known-good raw layer, and it changes the OpenAPI schema
that phase 2's committed codegen consumes; the ORM port then proceeds against the final role model.

**Cutover (staged re-enable, decided):** the old `src/` is deleted at phase 2. E2E is dark during
phases 2–3 (foundation, no routes) and re-greens per phase from 4 on — the documented residual
risk in §14. No parallel mount.

| Phase | Content | E2E re-greened |
|---|---|---|
| 0 | Backend: two-role model — deps split, route classification, users router, role-value migration, 403 contract test. On raw aiosqlite. | — (pytest) |
| 1 | Backend: SQLAlchemy 2.0 async per §10 — three engines, PRAGMA listeners, Core historian, lifecycle tests, benchmark. | — (pytest) |
| 2 | Frontend: scaffold, tokens (§6.4 contract + both value sets), ThemeProvider + persistence migration, all 17 primitives, source guard, contrast/token gates, **bundle gate incl. fonts**, committed hermetic codegen. | — (dark) |
| 3 | Frontend: realtime layer + pure modules, fully unit-tested. | — (dark) |
| 4 | Frontend: shell + login + dashboard, loop cards, Trend signature (pen tip; no-shadowBlur gate), Faceplate (+`user` variant). | `login-dashboard`, `faceplate`, `responsive`, `target-size`, `fatia7-auth-negative`, `themes` (rewritten) |
| 5 | Frontend: loop config, commands, AI panel. | `fatia2-commands`, new `user-role` spec |
| 6 | Frontend: alarms (VirtualList, quiet bar, 4 severities). | `alarms` |
| 7 | Frontend: multitrend, stats, history, export (create/download only). | `multitrend` |
| 8 | Frontend: simulator. | `simulator` |
| 9 | Frontend: executive dashboard. | `executive-dashboard` |
| 10 | Frontend: settings, connection, projects, **users management UI**. | `fatia7-connection`, `fatia7-projects` |
| 11 | (a) ISA-101 retokenisation (mapping table, unchanged visual output) · (b) 13 new visual baselines, delete 21 old + orphans, budget re-verify. | full suite green |

## 14. Risks

| Risk | Mitigation |
|---|---|
| **E2E dark window, phases 2–3** (largest project risk) | Scope of dark phases limited to foundation; per-phase re-green table in §13 is the exit criterion of every feature phase |
| Rewrite loses behavior the E2E suite never covered | Component tests rebuilt per feature; backend pytest unaffected; §2 goal is scoped to covered behavior — honest, not aspirational |
| Two token vocabularies resurface | §6.4 contract is normative; token-resolution test fails any theme missing any name |
| Light-theme contrast regressions | All Recorder/Phosphor values pre-verified (this doc); §12 gates text AND non-text AND focus |
| `.spid` reopen under engines leaks handles, breaks delete/download | §10 lifecycle: checkpoint → dispose → recreate; dedicated tests |
| DB-worker loop affinity breaks the shared engine | Engine B is dedicated to that loop; busy-timeout on both `.spid` engines |
| Role migration locks out legacy users | §9.4 startup UPDATE + DDL default + 401-on-legacy-JWT rule; migration test with a 3-role fixture DB |
| Historian throughput regresses | Core executemany pinned; before/after benchmark in phase 1 |
| OpenAPI drift between backend and client | Committed hermetic codegen + CI diff gate; regen sequenced after phase 0 |
| Fonts blow the budget invisibly | check-bundle extended to woff2 assets; ≤ 160 KB font budget; single variable Archivo file |
| Phase-2 under-scoping | Primitive list enumerated (17); phase 2 is the largest frontend phase by design |
| Recorder rejected by night-shift operators | Phosphor ships in the same release; theme persists **per browser** |
| Theme-switch chart artifacts | uPlot `themeKey` re-instantiation pattern retained |
| Scope creep into the control engine | §3 non-goals; phases 0–1 are the only backend phases; §9's additive surface is enumerated and closed |

## 15. Resolved and open items

Resolved in v2 (were open in v1):
- Fonts: one Archivo Variable + Geist Mono 400/500, woff2, Latin subset, ≤ 160 KB, swap + preload.
- Pen tip under reduced motion: freezes to a static marker (§6.7).
- KPI numerals: always Geist Mono (§6.2).
- Styling engine: Tailwind v4 + shadcn/Radix retained; React 18 pinned (§7).
- UI locale: pt-BR copy and accessible names preserved (§ preamble).

Still open (deliberately):
- Whether the executive dashboard warrants a layout distinct from the operational shell — decided
  in phase 9 against the Recorder direction.
- ISA-101 5→3 surface mapping table — produced with phase 11a (mechanical, low risk).
- TD-008 (`GET /export/list`) — product decision deferred; not part of this rewrite.
