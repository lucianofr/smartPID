# Smart PID — E2E Validation for Modification Set 1

Companion runbook to [`TEST_E2E.md`](./TEST_E2E.md). That document validates the rewrite as shipped
at `34c445d`. **This one validates the changes on top of it**: the six UI corrections and the `neon`
theme specified in
[`docs/superpowers/specs/2026-07-27-ui-corrections-design.md`](./docs/superpowers/specs/2026-07-27-ui-corrections-design.md)
(commit `c594f09`).

Procedures are numbered `MOD1-NNN` so they never collide with `E2E-NNN`. Section H re-runs the six
original procedures this work invalidates; the other 44 in `TEST_E2E.md` are unaffected and are not
repeated here.

## Mandatory execution contract

Everything in `TEST_E2E.md` §"Mandatory execution contract" still applies. Four additions:

1. **Measure, do not eyeball.** Every procedure below that states a number must be verified by
   evaluating the given JavaScript in the page, not by looking at a screenshot. A screenshot is
   evidence that the measurement was taken, not the measurement itself.
2. **Assert on the wire where the wire is the contract.** MOD1-013 and MOD1-016 fail if you check
   only the DOM. A previous run in this project proved the point: a mutation that fired a write and
   left the dialog open passed every DOM assertion and was caught only by the network assertion.
3. **The omp `browser` tool does not deliver CDP mouse/keyboard input.** `page.keyboard.press()` and
   `page.mouse.click()` produce zero events with no error. Reading the DOM via `page.evaluate` is
   reliable; for input use synthetic in-page dispatch, or run the real thing:
   `cd packages/smart_pid_web && env -u CI npx playwright test`. This tool defect has already
   fabricated three false "dead control" bug reports in this repo — do not rediscover it.
4. **`tab.type` stops working silently after `page.reload()`.** Login then fails with
   `Usuário ou senha inválidos`, which looks like bad credentials and is not. Open a new tab instead
   of reloading.

## Environment boot

Identical to `TEST_E2E.md` §"Environment boot" — same `/tmp/spid-e2e` isolation, same
`SPID_EXECUTION_MODE=execute`, same four loops.

Two differences introduced by this change set:

- **A fresh browser profile now paints `neon`, not `recorder`.** Any procedure that says "fresh
  profile" means `localStorage.clear()` followed by a load, and the expected default is `neon`.
- Where a procedure needs a specific theme, set it explicitly through the `Configurações` menu
  rather than assuming the default.

Environment hazards carried over, both of which have broken this environment before:

- **Never create or import a project on the live daemon.** It switches the active project, persists
  the switch in `~/.smart-pid/daemon_state.json`, and empties `/controllers` for every session.
  `SPID_DB_PATH` does not override the stored value. Recovery:
  `echo '{}' > ~/.smart-pid/daemon_state.json`, then restart.
- The simulator binds OPC-UA port **4849**. It conflicts with exactly one backend test,
  `test_api_simulator.py::TestOPCUAEndpoints::test_opcua_start_stop`. It is not a ZeroMQ conflict —
  that claim circulated in this project and is false.

---

## Procedures

### A — Loops page: faceplate as a full-height left rail (spec §4)

#### MOD1-001 — Rail position and width
- **Steps:** Log in as `admin` at 1920×1080, open `/`. Evaluate:
  ```js
  const fp = document.querySelector('aside[aria-label^="Faceplate"]');
  const strip = document.querySelector('section[aria-label="Malhas"]');
  ({ fp: fp.getBoundingClientRect(), strip: strip.getBoundingClientRect() })
  ```
- **Expected:** `fp.left` is within 2 px of the viewport left edge (allowing a border);
  `fp.width` is 320 ± 4 px; `strip.left >= fp.right`. The faceplate is to the **left** of the card
  strip, not below or beside the trend on the right.
- **Evidence:** `test-evidence/MOD1-001-rail-position.png`
- **Result:** [ ] PASS [ ] FAIL

#### MOD1-002 — Rail never scrolls: 16-combination sweep
- **Steps:** For each viewport in `1920×1080`, `1600×900`, `1440×900`, `1024×768`, for each role in
  `admin`, `operador`, and with the simulator twin both running and stopped (the
  `SimulationModeBanner` costs ~40 px when shown), evaluate:
  ```js
  const fp = document.querySelector('aside[aria-label^="Faceplate"]');
  ({ scrollH: fp.scrollHeight, clientH: fp.clientHeight, over: fp.scrollHeight - fp.clientHeight })
  ```
- **Expected:** `over === 0` in **all 16 combinations**. Record the tightest margin observed; the
  spec predicts 1024×768 with the banner is worst at ~2 px of headroom. A single non-zero `over`
  fails this procedure — the whole point of the change is that the rail does not scroll.
- **Evidence:** `test-evidence/MOD1-002-rail-noscroll.png`
- **Result:** [ ] PASS [ ] FAIL

#### MOD1-003 — Page gains no vertical scrollbar
- **Steps:** At each of the four viewports above, evaluate:
  ```js
  const d = document.documentElement;
  ({ v: d.scrollHeight - d.clientHeight, h: d.scrollWidth - d.clientWidth })
  ```
- **Expected:** `v === 0` and `h === 0` at all four. Moving overflow from the rail onto the page
  would satisfy MOD1-002 while making the result worse; this procedure exists to catch that.
- **Evidence:** `test-evidence/MOD1-003-page-noscroll.png`
- **Result:** [ ] PASS [ ] FAIL

#### MOD1-004 — The LOG.AI box is the element that flexes
- **Steps:** As `admin` at 1920×1080 then 1024×768, evaluate the height of
  `div[role="log"][aria-label="LOG.AI"]` at each.
- **Expected:** The height differs between the two viewports and is never below 32 px. Fixed content
  (bars, mode buttons, SP, CO, AI status/actions) keeps the same height at both. If the log box
  height is identical at both viewports, it is not flexing and MOD1-002 is passing for some other,
  unverified reason.
- **Evidence:** `test-evidence/MOD1-004-log-flex.png`
- **Result:** [ ] PASS [ ] FAIL

#### MOD1-005 — Below `lg` the layout stacks and the page scrolls
- **Steps:** Set viewport `768×900`, then `320×800`. Evaluate the faceplate and trend bounding boxes
  and the page horizontal overflow.
- **Expected:** Faceplate and trend are stacked (faceplate `top >= trend.bottom` or vice versa, not
  side by side); faceplate width is full-width, not 320 px; page `scrollWidth - clientWidth === 0`
  at 320 px. Vertical page scrolling **is** expected and correct here.
- **Evidence:** `test-evidence/MOD1-005-stacked.png`
- **Result:** [ ] PASS [ ] FAIL

#### MOD1-006 — Compaction did not shrink any touch target
- **Steps:** At 1440×900 and 320×800, measure the bounding box of every interactive element inside
  the faceplate: `AUTO`, `MAN`, the setpoint input and its `Set setpoint` button, the manual CO
  slider thumb, the output input and its `Set output` button, and the AI `Start` / `Pause` / `Stop`
  and `Apply tuning` buttons.
- **Expected:** Every one is ≥ 44 × 44 CSS px. The spec names four compaction levers and explicitly
  forbids any of them from breaching this floor; the log-box floor is the term that gives instead.
- **Evidence:** `test-evidence/MOD1-006-targets.png`
- **Result:** [ ] PASS [ ] FAIL

#### MOD1-007 — Card strip still a single non-wrapping row in the right column
- **Steps:** With four loops at 1440×900, evaluate the strip's `<li>` children and compare their
  `top` values; scroll the strip horizontally.
- **Expected:** All `<li>` share the same `top` (single row, no wrap); the strip scrolls
  horizontally; the edge fade is present; the trend sits below the strip inside the same right-hand
  column, not beside the faceplate on the left. This is the pre-existing E2E-010 contract, re-checked
  because the strip changed parent.
- **Evidence:** `test-evidence/MOD1-007-strip.png`
- **Result:** [ ] PASS [ ] FAIL

### B — AI configuration relocation (spec §5)

#### MOD1-008 — The config fields are gone from the faceplate
- **Steps:** As `admin`, on `/`, search the faceplate subtree for the labels `Motor`, `Objetivo`,
  `Velocidade do processo`, `Tempo morto L`, `Limite mín.`, `Limite máx.`
- **Expected:** None of the six is present anywhere inside `aside[aria-label^="Faceplate"]`.
- **Evidence:** `test-evidence/MOD1-008-faceplate-no-config.png`
- **Result:** [ ] PASS [ ] FAIL

#### MOD1-009 — The faceplate keeps AI *operation*
- **Steps:** Same view. Confirm the AI lifecycle badge (`RUN` / `PAUSE` / `STOP`), the
  `motor · Ki · γ` readout, the `Start` / `Pause` / `Stop` group, the `LOG.AI` box and the
  `Apply tuning` button are all still present. Press `Pause`, then `Start`.
- **Expected:** All present. The badge transitions `RUN → PAUSE → RUN` and the transition is driven
  by `GET /ai/status`, not by a stale `LOG.AI` frame. Moving configuration must not have moved
  operation.
- **Evidence:** `test-evidence/MOD1-009-faceplate-ai-ops.png`
- **Result:** [ ] PASS [ ] FAIL

#### MOD1-010 — The dialog has an `AI Optimization` section
- **Steps:** As `admin`, open a loop's config dialog from the card. Locate the section.
- **Expected:** A section labelled `AI Optimization` exists, sits after `Integral Type`, and carries
  all six moved controls with their pt-BR labels unchanged.
- **Evidence:** `test-evidence/MOD1-010-dialog-ai-section.png`
- **Result:** [ ] PASS [ ] FAIL

#### MOD1-011 — `Salvar IA` no longer exists
- **Steps:** Search the whole document for a button named `Salvar IA`, both with the dialog open and
  closed, as `admin`.
- **Expected:** Zero matches anywhere in the application. The dialog has exactly one save control,
  named `Salvar`.
- **Evidence:** `test-evidence/MOD1-011-no-salvar-ia.png`
- **Result:** [ ] PASS [ ] FAIL

#### MOD1-012 — Invalid AI configuration blocks the dialog's single save
- **Steps:** In the dialog, set `Limite mín.` to a value greater than `Limite máx.` (e.g. `500` with
  max `100`).
- **Expected:** The message `Limite mínimo deve ser menor que o máximo` appears, and the `Salvar`
  button is disabled. Restoring a valid band re-enables it. AI validation must participate in the
  dialog's `blocked` computation alongside PID and limit validation, not sit beside it.
- **Evidence:** `test-evidence/MOD1-012-ai-validation.png`
- **Result:** [ ] PASS [ ] FAIL

#### MOD1-013 — One PATCH carries both AI keys (**wire assertion**)
- **Steps:** With the network log recording, open the dialog, change `Motor` and
  `Velocidade do processo`, and press `Salvar`. Capture every request to
  `PATCH /api/controllers/{id}`.
- **Expected:** **Exactly one** PATCH. Its JSON body contains both `ai_config` (with `engine`,
  `objective`, `dead_time_l`, `limit_min`, `limit_max`) and `process_speed`. Two PATCHes means the
  moved form kept its own mutation and the merge into the dialog's single save was not done — a
  defect the DOM cannot reveal.
- **Evidence:** `test-evidence/MOD1-013-single-patch.png`
- **Result:** [ ] PASS [ ] FAIL

#### MOD1-014 — Role matrix unchanged by the move
- **Steps:** Log in as `operador`. On `/`, inspect the faceplate. Then open a loop's config dialog
  and inspect the `AI Optimization` section.
- **Expected:** No AI panel at all on the faceplate (the whole panel is admin-gated and returns
  nothing for a `user`). The dialog opens and is read-only: AI fields are present but disabled, and
  there is no `Salvar` and no `Excluir`. This is the pre-existing contract — "you cannot see it" is
  not the same promise as "you cannot change it" — and the move must not alter it.
- **Evidence:** `test-evidence/MOD1-014-user-ai.png`
- **Result:** [ ] PASS [ ] FAIL

### C — Command palette removal (spec §6)

#### MOD1-015 — The `[k]` control is gone
- **Steps:** As `admin`, inspect the header. Search the document for a button with accessible name
  `Comandos` and for the literal text `[k]`.
- **Expected:** Zero matches for both.
- **Evidence:** `test-evidence/MOD1-015-no-k-button.png`
- **Result:** [ ] PASS [ ] FAIL

#### MOD1-016 — The `k` shortcut is dead, and `k` still types
- **Steps:** With focus on `document.body`, press `k` (real key event, not synthetic — use
  Playwright for this one). Then focus the setpoint input and type `k`.
- **Expected:** No dialog opens in either case; no element with `role="dialog"` appears. The
  setpoint input receives the character `k`. A partial removal that drops the button but leaves the
  listener would pass MOD1-015 and fail here.
- **Evidence:** `test-evidence/MOD1-016-k-dead.png`
- **Result:** [ ] PASS [ ] FAIL

#### MOD1-017 — `cmdk` is out of the bundle
- **Steps:** From `packages/smart_pid_web`, run `npm ls cmdk`; grep `src/` for `from 'cmdk'` and for
  `components/Command`; confirm `src/components/Command.tsx` and `Command.test.tsx` are deleted.
- **Expected:** `npm ls cmdk` reports the package absent, both greps return nothing, both files are
  gone. Removing the usage but leaving the dependency and the component is dead weight the spec
  explicitly deletes.
- **Evidence:** `test-evidence/MOD1-017-cmdk-gone.png`
- **Result:** [ ] PASS [ ] FAIL

### D — Icon affordances (spec §7)

#### MOD1-018 — Top-bar gear
- **Steps:** Inspect the configuration trigger in the header.
- **Expected:** It renders an SVG (lucide `Settings`), not the text `[cfg]`. Its accessible name is
  still exactly `Configurações`. The SVG is `aria-hidden="true"`. The button is ≥ 44 × 44 px.
  Clicking it still opens the theme + `Administração` menu.
- **Evidence:** `test-evidence/MOD1-018-gear.png`
- **Result:** [ ] PASS [ ] FAIL

#### MOD1-019 — Per-card sliders icon
- **Steps:** Inspect the config button on each loop card, as both `admin` and `operador`.
- **Expected:** It renders an SVG (lucide `SlidersHorizontal`), not `[cfg]`. Accessible name is still
  exactly `Configurar {tag}` for each loop. Present and functional for **both** roles — it opens a
  read-only dialog for `operador`, which is by design. Button ≥ 44 × 44 px.
- **Evidence:** `test-evidence/MOD1-019-sliders.png`
- **Result:** [ ] PASS [ ] FAIL

#### MOD1-020 — No bracketed abbreviation survives anywhere
- **Steps:** Evaluate `document.body.innerText.includes('[cfg]')` and `.includes('[k]')` on `/`,
  `/multitrend`, `/alarms`, `/simulator`, `/executive`, and with the loop config dialog and the
  "Nova malha" dialog both open.
- **Expected:** `false` in every case. The `NewLoopDialog` description that read
  "O restante da configuração fica disponível no [cfg] da malha criada" must no longer name a
  control that does not exist.
- **Evidence:** `test-evidence/MOD1-020-no-brackets.png`
- **Result:** [ ] PASS [ ] FAIL

### E — Executive navigation (spec §8)

#### MOD1-021 — `Executivo` in the top bar for both roles
- **Steps:** As `admin`, then as `operador`, inspect the main nav and click `Executivo`.
- **Expected:** The nav reads `Loops · Trends · Alarms · Sim · Executivo` for both roles; the link
  `href` is `/executive`; clicking it lands on the executive dashboard with real KPI values.
- **Evidence:** `test-evidence/MOD1-021-exec-nav.png`
- **Result:** [ ] PASS [ ] FAIL

#### MOD1-022 — The wordmark points at `/`
- **Steps:** From `/multitrend`, click the `Smart PID` wordmark.
- **Expected:** `href` is `/` and it navigates to the Loops dashboard, not to `/executive`.
- **Evidence:** `test-evidence/MOD1-022-wordmark.png`
- **Result:** [ ] PASS [ ] FAIL

#### MOD1-023 — The fifth nav item costs no page overflow at 320 px
- **Steps:** At `320×800`, evaluate:
  ```js
  const nav = document.querySelector('nav[aria-label="Navegação principal"]');
  const d = document.documentElement;
  ({ navClient: nav.clientWidth, navScroll: nav.scrollWidth,
     headerOver: document.querySelector('header').scrollWidth - document.querySelector('header').clientWidth,
     pageOver: d.scrollWidth - d.clientWidth })
  ```
- **Expected:** `pageOver === 0` and `headerOver === 0`. `navScroll` should read ~236 px (five links
  at 44 px plus four 4 px gaps) against an unchanged `navClient` of ~61 px — the nav absorbs the
  growth in its existing horizontal scroller. Baseline before the change was `navScroll` 188 px.
  A non-zero `pageOver` reopens the `bab300a` header-overflow regression.
- **Evidence:** `test-evidence/MOD1-023-320-overflow.png`
- **Result:** [ ] PASS [ ] FAIL

### F — Trends: persistence and titles (spec §9)

#### MOD1-024 — Selection survives navigation
- **Steps:** On `/multitrend`, select `Loop 1 · PV`, `Loop 1 · SP` and `Loop 2 · CO`. Navigate to
  `/alarms`, then back to `/multitrend`.
- **Expected:** The same three checkboxes are checked and the same cells are rendered. This is the
  reported defect: the selection was "forgotten" on leaving the page.
- **Evidence:** `test-evidence/MOD1-024-survives-nav.png`
- **Result:** [ ] PASS [ ] FAIL

#### MOD1-025 — Selection survives reload and a new session
- **Steps:** With the same selection, reload the page. Then close the tab, open a new one, log in
  again and return to `/multitrend`.
- **Expected:** The selection is restored in both cases. Also confirm on the wire of storage:
  `localStorage.getItem('spid.multitrend')` parses to four slot entries of shape
  `{ controllerId, series: { pv, sp, co } }`.
- **Evidence:** `test-evidence/MOD1-025-survives-reload.png`
- **Result:** [ ] PASS [ ] FAIL

#### MOD1-026 — A stale loop id is discarded, not rendered
- **Steps:** Set `localStorage['spid.multitrend']` to a payload whose first slot references a
  controller id that does not exist (e.g. `9999`) and whose second slot references a real loop.
  Reload `/multitrend`.
- **Expected:** The real loop renders; the phantom id produces **no** chart cell and no empty cell.
  The page does not throw. Restoring a chart for a deleted loop would leave a permanently empty
  panel — this is the failure reconciliation exists to prevent.
- **Evidence:** `test-evidence/MOD1-026-stale-id.png`
- **Result:** [ ] PASS [ ] FAIL

#### MOD1-027 — Corrupt storage degrades to empty, never to a crash
- **Steps:** Set `localStorage['spid.multitrend']` to `'{not json'`, reload. Then set it to
  `'{"slots":"wrong-shape"}'`, reload. Then to `'[]'`, reload.
- **Expected:** In all three cases the page loads, shows the empty state
  `Nenhuma série selecionada.`, logs no uncaught error, and selecting a series still works. Partial
  trust in a malformed payload is worse than discarding it.
- **Evidence:** `test-evidence/MOD1-027-corrupt-storage.png`
- **Result:** [ ] PASS [ ] FAIL

#### MOD1-028 — `paused` is deliberately not restored
- **Steps:** Select a series, press `Pausar`, confirm the button reads `Retomar`, then reload.
- **Expected:** After reload the button reads `Pausar` — the chart is live, not frozen. A restored
  pause would render stale data with no indication it is stale, which is the same failure class as
  the E2E-047 defect this project already fixed once.
- **Evidence:** `test-evidence/MOD1-028-paused-not-restored.png`
- **Result:** [ ] PASS [ ] FAIL

#### MOD1-029 — Every trend cell names its loop
- **Steps:** Select signals from two different loops. Inspect each chart cell's visible header and
  its `aria-label`.
- **Expected:** Each cell shows `#{id} · {tag}` (e.g. `#1 · TIC-E2E`) and its region `aria-label` is
  `Tendência #{id} · {tag}`. The two cells show different loops and are attributable at a glance,
  which is the reported defect.
- **Evidence:** `test-evidence/MOD1-029-chart-titles.png`
- **Result:** [ ] PASS [ ] FAIL

#### MOD1-030 — The selector uses the same label, and the frozen name is untouched
- **Steps:** Inspect the `Séries` selector rows and the checkbox accessible names.
- **Expected:** Each row is labelled `#{id} · {tag}`, matching the chart header exactly. Each
  checkbox's accessible name is still **exactly** `Loop {id} · {SIGNAL}` — e.g. `Loop 1 · PV`. That
  name is pinned by `SeriesSelector.test.tsx` and `e2e/multitrend.spec.ts:150,151,214`; changing it
  breaks tests that have nothing to do with this feature.
- **Evidence:** `test-evidence/MOD1-030-selector-labels.png`
- **Result:** [ ] PASS [ ] FAIL

#### MOD1-031 — Name fallback never renders blank
- **Steps:** Throttle or block `GET /api/controllers` so the roster query is slow, then load
  `/multitrend` with a stored selection.
- **Expected:** Cells and selector rows read `Loop {id}` until names arrive, then upgrade to
  `#{id} · {tag}`. At no point is the title empty, `undefined`, or `#{id} · `.
- **Evidence:** `test-evidence/MOD1-031-name-fallback.png`
- **Result:** [ ] PASS [ ] FAIL

### G — The `neon` theme (spec §10)

#### MOD1-032 — Four themes offered
- **Steps:** Open the `Configurações` menu as `operador` and as `admin`.
- **Expected:** Exactly four theme radio items: `Recorder`, `Phosphor`, `ISA-101`, `Neon`. Both
  roles see all four; only `admin` additionally sees the `Administração` block.
- **Evidence:** `test-evidence/MOD1-032-four-themes.png`
- **Result:** [ ] PASS [ ] FAIL

#### MOD1-033 — `neon` is the fresh-profile default, painted before React mounts
- **Steps:** Clear `localStorage`, load `/`. Read `document.documentElement.dataset.theme`
  immediately. Then capture a filmstrip or trace of first paint.
- **Expected:** `neon`. No flash of `recorder` or of an unthemed page — the pre-paint script in
  `index.html` must apply the attribute before the bundle executes, and the static
  `<html data-theme>` fallback must also read `neon`.
- **Evidence:** `test-evidence/MOD1-033-neon-default.png`
- **Result:** [ ] PASS [ ] FAIL

#### MOD1-034 — All four themes switch and persist
- **Steps:** For each of the four, select it, confirm `<html data-theme>`, reload, confirm it
  survived, and confirm `localStorage['spid.theme']`.
- **Expected:** Attribute and stored value match the selection in all four cases and survive reload.
  This is E2E-045 widened from three themes to four.
- **Evidence:** `test-evidence/MOD1-034-theme-persistence.png`
- **Result:** [ ] PASS [ ] FAIL

#### MOD1-035 — The legacy migration still works
- **Steps:** Set `localStorage['spid.theme'] = 'ocean'` and reload.
- **Expected:** It migrates to `recorder` (the existing `LEGACY_THEME_MAP` target — introducing
  `neon` must **not** silently re-point legacy values), the attribute reads `recorder`, and storage
  is rewritten once to `recorder`.
- **Evidence:** `test-evidence/MOD1-035-legacy-migration.png`
- **Result:** [ ] PASS [ ] FAIL

#### MOD1-036 — Palette values match the spec exactly
- **Steps:** Under `data-theme="neon"`, evaluate `getComputedStyle(document.documentElement)` for
  each of the 41 non-type contract tokens and diff against the table in spec §10.3.
- **Expected:** Every token resolves non-empty and equals the specified value. Spot-check anchors:
  `--bg` = `#07070E`, `--accent` = `#00E5FF`, `--alarm-crit` = `#FF2D6F`,
  `--state-running` = `#39FF88`, `--on-accent` = `#04040A`.
- **Evidence:** `test-evidence/MOD1-036-palette.png`
- **Result:** [ ] PASS [ ] FAIL

#### MOD1-037 — Measured contrast in the live page
- **Steps:** Under `neon`, compute the WCAG ratio for: `--text` on `--bg`, `--surface` and
  `--surface-sunk`; `--text-soft` on the same three; `--on-accent` on `--accent`; `--on-alarm` on
  each of the four severity fills; each severity as text on `--bg` and `--surface`.
- **Expected:** ≥ 4.5:1 for every pair above. Then the non-text set — `--rule-strong` on surfaces,
  `--focus-ring` on `--bg` and `--surface`, traces on `--trend-bg` and `--surface-sunk`, bar fill and
  marker on `--bar-track`, state dots on `--bg` and `--surface` — at ≥ 3:1. This duplicates the CI
  gate on purpose: the gate reads a mirrored table in `themeContrast.ts`, this reads what the browser
  actually resolved, and the two drifting apart is exactly the bug worth catching.
- **Evidence:** `test-evidence/MOD1-037-contrast.png`
- **Result:** [ ] PASS [ ] FAIL

#### MOD1-038 — Glow is present exactly where it is specified
- **Steps:** Under `neon`, with at least one active unacknowledged alarm, read the computed
  `box-shadow` of: an active alarm row, a severity badge, the focused element after tabbing to a
  button, and a primary button under hover. Read the PV trace halo via the trend's `data-glow`
  attribute and the resolved `--glow-trace`.
- **Expected:** Non-`none` `box-shadow` on all four; `--glow-trace` resolves to `8px` and the trend
  reports glow on.
- **Evidence:** `test-evidence/MOD1-038-glow-present.png`
- **Result:** [ ] PASS [ ] FAIL

#### MOD1-039 — Glow is absent everywhere else
- **Steps:** Under `neon`, read computed `box-shadow` and `text-shadow` of: a state dot, a loop card
  border, the header, a page `<h1>`, body paragraph text, and a normal (non-alarm, non-focused,
  non-hovered) secondary button.
- **Expected:** `none` for all. Glow that decorates instead of signalling defeats its purpose here:
  the whole reason glow was chosen is that the neon palette pushed `--state-running` chroma (0.221)
  above two of the three alarm severities, and glow is the channel that keeps an alarm findable.
- **Evidence:** `test-evidence/MOD1-039-glow-absent.png`
- **Result:** [ ] PASS [ ] FAIL

#### MOD1-040 — Reduced motion suppresses the alarm pulse
- **Steps:** Emulate `prefers-reduced-motion: reduce`. With an unacknowledged alarm active, inspect
  its computed `animation-name` / `animation-duration`.
- **Expected:** No running animation. The static glow may remain — it carries the signal; the motion
  is what must stop.
- **Evidence:** `test-evidence/MOD1-040-reduced-motion.png`
- **Result:** [ ] PASS [ ] FAIL

#### MOD1-041 — Halo follows the token, not a theme name
- **Steps:** In each of the four themes, read the trend's `data-glow` attribute and the resolved
  `--glow-trace`.
- **Expected:** `neon` → `8px`, glow on. `phosphor` → `4px`, glow on. `recorder` and `isa101` →
  `0px`, glow off. Then grep `src/` for `=== 'phosphor'`: zero matches. This is E2E-046 restated —
  the halo is no longer "Phosphor only", it is "wherever the token is non-zero", and no component
  hardcodes a theme id.
- **Evidence:** `test-evidence/MOD1-041-halo-token.png`
- **Result:** [ ] PASS [ ] FAIL

#### MOD1-042 — Orbitron on display text, Geist Mono on numerals
- **Steps:** Under `neon`, read the computed `font-family` of: the wordmark, a `DialogTitle`, a page
  `<h1>`, a PV numeric readout, an `AnalogBar` value, and body paragraph text. Repeat under
  `recorder`.
- **Expected:** Under `neon` the first three resolve to Orbitron; the numerics resolve to Geist Mono
  and the body to Archivo — identical to `recorder`. Under `recorder` all display text is Archivo.
  Numerals must never change face between themes: an operator reading a process value is the one
  thing this theme may not make exotic.
- **Evidence:** `test-evidence/MOD1-042-fonts.png`
- **Result:** [ ] PASS [ ] FAIL

#### MOD1-043 — No external font request, on any route
- **Steps:** With the network log recording, visit `/`, `/multitrend`, `/alarms`, `/simulator`,
  `/executive`, `/settings`, and `/login`. Filter for `fonts.googleapis.com` and `fonts.gstatic.com`.
- **Expected:** Zero requests. Fonts are self-hosted `woff2` under `src/assets/fonts/`. Also confirm
  the Orbitron file is preloaded from `index.html` and that the OFL licence file is committed beside
  it. A CDN dependency here is a runtime failure on an isolated plant network, not a style choice.
- **Evidence:** `test-evidence/MOD1-043-no-cdn.png`
- **Result:** [ ] PASS [ ] FAIL

#### MOD1-044 — The neon theme renders every route without regression
- **Steps:** Under `neon`, visit all seven routes above at 1440×900. Check the console after each.
- **Expected:** Every route renders with readable text and visible controls; no unstyled or
  invisible element; zero unexpected console errors; no HTTP 4xx/5xx beyond the by-design
  `GET /controllers/{id}/ai/status` 404 for loops with optimization off.
- **Evidence:** `test-evidence/MOD1-044-neon-routes.png`
- **Result:** [ ] PASS [ ] FAIL

### H — Regression of the seven touched original procedures

#### MOD1-045 — Re-run the seven `TEST_E2E.md` procedures this change set touches
- **Steps:** Execute, from the updated `TEST_E2E.md`:
  - **E2E-006** — repurposed: executive dashboard reachable from the top bar
  - **E2E-036** — executive KPIs, now opened from the top bar rather than the palette
  - **E2E-049** — responsive breakpoints, now including the rail no-scroll assertion
  - **E2E-045** — theme switch and persistence, now four themes with `Neon` as default
  - **E2E-046** — halo and legacy migration, now token-driven across two themes
  - **E2E-015** and **E2E-043** — faceplate consistency and user-forbidden capabilities: assertions
    unchanged, evidence PNGs re-captured against the new layout and default theme
- **Expected:** All pass, with fresh evidence images. No assertion was weakened to achieve this; if
  any procedure can only pass by relaxing what it claims, stop and report instead.
- **Evidence:** `test-evidence/MOD1-045-regression.png`
- **Result:** [ ] PASS [ ] FAIL

#### MOD1-046 — The other 43 original procedures still pass
- **Steps:** Run the remainder of `TEST_E2E.md` — everything except the seven named above.
- **Expected:** 43/43 pass. This change set is layout, chrome and colour; any behavioural regression
  it produces will surface here.
- **Evidence:** `test-evidence/MOD1-046-full-regression.png`
- **Result:** [ ] PASS [ ] FAIL

### I — Automated gates

#### MOD1-047 — Static analysis and unit suite
- **Steps:**
  ```bash
  cd packages/smart_pid_web
  npm run typecheck
  npm run lint
  npm run test
  ```
- **Expected:** All three green. The unit count rises from the 746 baseline: new cases cover
  trend-selection persistence and roster reconciliation, and the theme registry, contrast gate and
  token resolution gain a fourth theme.
- **Evidence:** `test-evidence/MOD1-047-unit.png`
- **Result:** [ ] PASS [ ] FAIL

#### MOD1-048 — Contrast and token gates specifically
- **Steps:**
  ```bash
  cd packages/smart_pid_web
  npx vitest run src/theme/themeContrast.test.ts src/theme/tokenResolve.test.ts src/theme/isa101Mapping.test.ts src/theme/fonts.test.ts
  ```
- **Expected:** Green with `neon` in `GateThemeId`. Confirm by reading the diff that **no floor was
  lowered** and no assertion was deleted to achieve it — `TEXT_FLOOR` stays `4.5` and
  `NONTEXT_FLOOR` stays `3.0`. All 48 contract tokens resolve non-empty under all four themes.
- **Evidence:** `test-evidence/MOD1-048-gates.png`
- **Result:** [ ] PASS [ ] FAIL

#### MOD1-049 — Playwright, including new baselines
- **Steps:**
  ```bash
  cd packages/smart_pid_web
  env -u CI npx playwright test
  ```
- **Expected:** Green. New `dashboard-neon-<width>.png` baselines exist at all four breakpoints and
  were reviewed by eye before being accepted — an auto-generated baseline of a broken layout is a
  test that locks in the bug.
- **Evidence:** `test-evidence/MOD1-049-playwright.png`
- **Result:** [ ] PASS [ ] FAIL

#### MOD1-050 — Backend untouched
- **Steps:** `git diff --stat <base>..HEAD -- packages/smart_pid_core`
- **Expected:** Empty. This change set is frontend-only; any Python in the diff is out of scope and
  needs justification before merge. The backend suite is deliberately **not** re-run.
- **Evidence:** `test-evidence/MOD1-050-no-backend.png`
- **Result:** [ ] PASS [ ] FAIL

---

## Results

| Procedure | Title | Result | Evidence | Notes |
|---|---|---|---|---|
| MOD1-001 | Rail position and width | | `MOD1-001-rail-position.png` | |
| MOD1-002 | Rail never scrolls (16 combos) | | `MOD1-002-rail-noscroll.png` | |
| MOD1-003 | Page gains no vertical scrollbar | | `MOD1-003-page-noscroll.png` | |
| MOD1-004 | LOG.AI box is the flexing element | | `MOD1-004-log-flex.png` | |
| MOD1-005 | Stacks below `lg` | | `MOD1-005-stacked.png` | |
| MOD1-006 | Touch targets survive compaction | | `MOD1-006-targets.png` | |
| MOD1-007 | Card strip still single row | | `MOD1-007-strip.png` | |
| MOD1-008 | Config fields gone from faceplate | | `MOD1-008-faceplate-no-config.png` | |
| MOD1-009 | Faceplate keeps AI operation | | `MOD1-009-faceplate-ai-ops.png` | |
| MOD1-010 | Dialog has `AI Optimization` | | `MOD1-010-dialog-ai-section.png` | |
| MOD1-011 | `Salvar IA` no longer exists | | `MOD1-011-no-salvar-ia.png` | |
| MOD1-012 | Invalid AI config blocks `Salvar` | | `MOD1-012-ai-validation.png` | |
| MOD1-013 | One PATCH, both AI keys (wire) | | `MOD1-013-single-patch.png` | |
| MOD1-014 | Role matrix unchanged | | `MOD1-014-user-ai.png` | |
| MOD1-015 | `[k]` control gone | | `MOD1-015-no-k-button.png` | |
| MOD1-016 | `k` shortcut dead, `k` still types | | `MOD1-016-k-dead.png` | |
| MOD1-017 | `cmdk` out of the bundle | | `MOD1-017-cmdk-gone.png` | |
| MOD1-018 | Top-bar gear | | `MOD1-018-gear.png` | |
| MOD1-019 | Per-card sliders icon | | `MOD1-019-sliders.png` | |
| MOD1-020 | No bracketed abbreviation anywhere | | `MOD1-020-no-brackets.png` | |
| MOD1-021 | `Executivo` in nav, both roles | | `MOD1-021-exec-nav.png` | |
| MOD1-022 | Wordmark points at `/` | | `MOD1-022-wordmark.png` | |
| MOD1-023 | No 320 px overflow with 5 items | | `MOD1-023-320-overflow.png` | |
| MOD1-024 | Selection survives navigation | | `MOD1-024-survives-nav.png` | |
| MOD1-025 | Selection survives reload/session | | `MOD1-025-survives-reload.png` | |
| MOD1-026 | Stale loop id discarded | | `MOD1-026-stale-id.png` | |
| MOD1-027 | Corrupt storage degrades safely | | `MOD1-027-corrupt-storage.png` | |
| MOD1-028 | `paused` not restored | | `MOD1-028-paused-not-restored.png` | |
| MOD1-029 | Trend cells name their loop | | `MOD1-029-chart-titles.png` | |
| MOD1-030 | Selector label + frozen aria-label | | `MOD1-030-selector-labels.png` | |
| MOD1-031 | Name fallback never blank | | `MOD1-031-name-fallback.png` | |
| MOD1-032 | Four themes offered | | `MOD1-032-four-themes.png` | |
| MOD1-033 | `neon` default, no flash | | `MOD1-033-neon-default.png` | |
| MOD1-034 | All four persist | | `MOD1-034-theme-persistence.png` | |
| MOD1-035 | Legacy `ocean` migration intact | | `MOD1-035-legacy-migration.png` | |
| MOD1-036 | Palette matches spec §10.3 | | `MOD1-036-palette.png` | |
| MOD1-037 | Measured contrast in-page | | `MOD1-037-contrast.png` | |
| MOD1-038 | Glow present where specified | | `MOD1-038-glow-present.png` | |
| MOD1-039 | Glow absent everywhere else | | `MOD1-039-glow-absent.png` | |
| MOD1-040 | Reduced motion kills the pulse | | `MOD1-040-reduced-motion.png` | |
| MOD1-041 | Halo follows the token | | `MOD1-041-halo-token.png` | |
| MOD1-042 | Orbitron display, Geist numerals | | `MOD1-042-fonts.png` | |
| MOD1-043 | No external font request | | `MOD1-043-no-cdn.png` | |
| MOD1-044 | Every route renders under neon | | `MOD1-044-neon-routes.png` | |
| MOD1-045 | Seven touched procedures re-run | | `MOD1-045-regression.png` | |
| MOD1-046 | Other 43 procedures still pass | | `MOD1-046-full-regression.png` | |
| MOD1-047 | Typecheck, lint, unit suite | | `MOD1-047-unit.png` | |
| MOD1-048 | Contrast and token gates | | `MOD1-048-gates.png` | |
| MOD1-049 | Playwright + new baselines | | `MOD1-049-playwright.png` | |
| MOD1-050 | Backend untouched | | `MOD1-050-no-backend.png` | |

## What this runbook does not cover

Stated so the gaps are chosen rather than accidental:

- **Aesthetic judgement.** No procedure asserts the neon theme looks good. MOD1-036 through
  MOD1-044 verify it is correct, legible, accessible and consistent; whether it is *appealing* is
  the operator's call on seeing it, and a screenshot review is the right instrument, not a checkbox.
- **Long-run visual drift.** Playwright baselines catch pixel regressions per commit. They do not
  catch a slow accumulation of small accepted diffs. Re-review baselines by eye when accepting them.
- **Real PLC hardware.** Everything here runs against the internal simulator twins. Behaviour
  against a physical DCS in `monitor` mode is out of scope for a frontend change set.
- **Performance budgets.** The added `woff2` and the glow shadows have a cost. MOD1-043 confirms the
  font is local and preloaded, but no procedure sets an LCP or CLS budget. If first paint matters
  commercially, add a Lighthouse run — the `--glow-*` box-shadows and the extra font are the two
  things worth measuring.
