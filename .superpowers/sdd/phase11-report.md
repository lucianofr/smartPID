# Phase 11 — ISA-101 Retokenisation, Visual Baselines, and Budget — Completion Report

**Status:** COMPLETE — all 4 tasks shipped, phase gate green. Terminal feature phase.
**Plan:** `docs/superpowers/plans/2026-07-26-phase11-isa101-baselines-budget.md`
**Worktree:** `.worktrees/web-frontend-rewrite` · branch `docs/web-frontend-rewrite-spec`

## Commits

| SHA | Subject |
|---|---|
| `f0d9736` | `feat(web): finalize ISA-101 shared token mapping` |
| `2ff767b` | `test(web): replace visual baselines for three themes` |
| `688cadf` | `chore(web): close rewrite quality gates` |

`47e5bb8 fix(core): repair daemon bootstrap after the SQLAlchemy migration`
landed on the branch from another worker mid-phase; it is backend-only and was
neither staged nor reverted here.

## Gate results

| Gate | Result |
|---|---|
| `npm run test -- --run` | **681 passed / 82 files** (592 / 81 at phase 10; +89 — 87 in `isa101Mapping.test.ts`, 2 in `uplotTheme.test.ts`) |
| `npm run typecheck` | exit 0 |
| `npm run lint` | exit 0 |
| `npm run build` | exit 0 |
| `npm run check:bundle` | exit 0 — JS **184.0 KB** gzip (budget 300), CSS **7.8 KB** (budget 50), fonts **109.6 KB** raw / 3 woff2 (budget 160); delta vs baseline +0.0 / +0.0 / +0.0 |
| `npx playwright test` | **66 passed / 0 failed** — the 53 retained specs plus the 13 new visual baselines |

The 53 pre-existing specs all still pass; nothing was weakened. The full suite
was run twice back-to-back after baseline generation and reproduced the PNG set
byte for byte both times.

## Task 1 — 5→3 surface mapping (shipped)

`packages/smart_pid_web/docs/isa101-token-mapping.md` is the durable artifact.
Every hex is read from the pre-rewrite `[data-theme='isa101']` block at
`ca0a6f6` — the parent of `38005e9`, the phase-2 commit that deleted legacy
`src/`. Nothing is inferred. `src/theme/isa101Mapping.test.ts` holds the same
palette, the same old→new edges and the same final values and asserts them
through `getComputedStyle`, so the document and the CSS cannot drift.

**Shared-vocabulary invariant re-verified** (the #1 blocking defect of the
original architecture review): `recorder`, `phosphor` and `isa101` each declare
the *identical* 41 custom properties, `CONTRACT_TOKENS` covers those 41 plus the
three `:root` type tokens, and no theme declares a token outside the contract.
Pinned by `isa101Mapping.test.ts` → *"all three themes declare the identical
token vocabulary"*. A component styled `var(--surface)` renders under all three.

Three interim values were **wrong** and are corrected:

- `--rule` `#3A3A3D` → **`#454548`**. Old `--border` (65 class uses) and
  `--divider` (10) both collapse into `--rule`; the interim picked the minority
  hex, so 60 boundaries rendered a step too dark. `--divider`'s hex survives on
  `--trend-grid`.
- `--selection` `#3A3A3D` → **`#333337`**, the old `--surface-container-high`,
  which is literally the hover/selected/open-menu raise that `bg-selection`
  now serves (`NavRail.LINK_ACTIVE`, `dropdown-menu` items).
- `--accent-*`, `--scrim`, `--alarm-log` lose their `/* interim */` marks —
  each was already an old-palette value, now traced instead of guessed.
  `--alarm-log: #ABABAB` is the old `.sev-icon--dot` (LOG glyph) colour.

**§6.3 solid ISA SP, closed.** `buildUplotTheme` hard-coded `dash: [6, 4]` for
every theme — in v1 and in the phase-2 rewrite alike — so ISA-101 has never
rendered the solid blue SP its own rules require. The dash is now the
`--trend-sp-dash` token (`6 4` for Recorder/Phosphor, `none` for ISA-101),
added to `CONTRACT_TOKENS` so the single shared vocabulary still holds. This is
the one place phase 11 changes ISA-101 pixels, and it *restores* the documented
rule rather than preserving the bug.

Legacy contrast failures are documented, not silently fixed: `--rule-strong` on
`--surface` is 1.91:1 and `--on-alarm` on the warn/log fills is 2.39 / 2.30:1.
Both are inherited verbatim and are why `themeContrast.ts` gates Recorder and
Phosphor only.

## Task 2 — delete the 21 obsolete baselines (already satisfied)

No work was needed and none was invented. Commit `7603b80 test(web): re-enable
dashboard e2e coverage` deleted **exactly** the 21 files the plan enumerates
(4 ocean + 4 md3-dark + 4 md3-light + 4 dark-room + 4 isa101 + 1 faceplate);
`git show --diff-filter=D --name-only 7603b80` lists them one for one. Step 2's
grep over `e2e/**/*.spec.ts` returns only the `LEGACY` migration table in
`themes.spec.ts:67-73` — the explicit exception the plan allows.

## Task 3 — the 13 final baselines (shipped)

Exactly the 13 names the plan specifies, viewport-sized at `{width}x900` to
match the pre-rewrite geometry, plus the element-scoped faceplate.

Freezing the nondeterminism took more than disabling animations. The socket
stub's open-time burst races React's mount and the realtime fan-out only
reaches live subscribers, so a shot could catch 0, 1 or 2 samples in the trend
window depending on scheduling. The visual specs now pass `samples: 0` and
drive frames themselves via `emitFrames`, which probes with frame 0 until the
faceplate reports a value — idempotent, since the probe carries the same
timestamp every try and `windowBuffer` rejects a non-increasing `t` — then
sends the whole burst at a fixed base 2048 frames out, past the 30-minute
window so `trim()` discards the probe residue. Verified through the panel's own
CSV export ("exactly the plotted rows"): 24 rows, fixed timestamps, fixed
values, every run. `settleForShot` additionally kills animations, transitions
and the caret, awaits `document.fonts.ready`, waits for uPlot to commit a
frame, and the specs pin `timezoneId: 'UTC'` because the uPlot time axis
formats ticks in the browser's local zone.

## Task 4 — budget (shipped)

`bundle-baseline.json` retightened to the measured feature-complete app: JS
**174.9 → 184.0 KB** gzip, CSS **7.3 → 7.8 KB**, fonts unchanged at 109.6 KB.
This is not a regression being hidden — 184.0 KB is the size the app actually
is. The old number was captured at `12a8c76` for the phase-6 alarm workspace,
before phases 7–10 added multitrend, the simulator twin, the executive
dashboard, settings, projects and user management. Left at 174.9 the gate had
0.9 KB of its 10 KB tolerance remaining, so the next honest kilobyte would have
failed CI for the wrong reason.

**Budget constants are untouched** — JS 300 KB, CSS 50 KB, fonts 160 KB. The
entry chunk sits at 61% of its budget and fonts at 69%.

## Concerns for the terminal Chrome E2E gate

1. **The trend well paints no trace.** This is the significant finding of the
   phase and it is a product defect, not a harness artifact. With 24 rows
   confirmed present in the plotted data (via the panel's own CSV export), a
   patched `CanvasRenderingContext2D.prototype.stroke` shows uPlot issuing the
   PV/SP/CO strokes with the correct colours and widths — `#1b4f87 w=2`,
   `#7c8894 w=1.5`, `#bc7211 w=1.5` — and yet the canvas ends up holding only
   `--trend-grid` and `--trend-axis` pixels. The pen tip's filled circle does
   not land either, which points at a degenerate series path rather than a
   colour problem. The signature element of the product (§6.7) therefore
   renders empty under the mocked socket. `TEST_E2E.md` against a real backend
   is the right place to confirm whether this reproduces with live telemetry;
   if it does, it needs its own fix phase. Nothing here was papered over: the
   baseline readiness gate is honestly a *paint* gate, and the harness comment
   at `e2e/helpers/harness.ts` records exactly why a content gate could not be
   used.
2. **Visual baselines are Linux/Chromium-specific.** The 13 PNGs carry the
   `-linux` suffix and were recorded on this machine's Chromium. A different
   platform or a Playwright browser bump will need `--update-snapshots`.
3. **ISA-101 stays outside the WCAG gate by design.** Preserving its appearance
   and passing WCAG are mutually exclusive for two token pairs (see Task 1).
   Recorder is the default; operators needing a compliant dark theme use
   Phosphor.
4. **Bundle headroom.** 184.0 KB of 300 KB. Comfortable, but the entry chunk is
   577 KB raw and Vite still warns about it; further route splitting beyond
   phase 9's would be the lever if that changes.
