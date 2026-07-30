# Frontend defects: trend x-axis label clip + dead Tabs declaration

Branch `fix/simulator-registration-and-schema`, worktree `new-hmi-design`. No commits made. The
`vite.config.ts` / `smart_pid_core` entries in the diff are a parallel agent's work, not mine.

## Bug A — root cause: the well overflowed its plot box (candidate 3)

`MIN_PLOT_HEIGHT` (140) floors the **canvas**, but the well's height is content-driven —
`TREND_WELL_INSET_PX` (28) + canvas. When the floor outbid the flex remainder, `Trend` rendered a
168px well inside a 114px box. That 54px of overflow left the card's content box, painted
`bg-surface-sunk` over the card's own bottom border, and was cut by the right column's
`lg:overflow-hidden` — taking the ruler's last 3px. Live `page.evaluate` geometry (temporary probe
spec, since deleted), before the fix:

| viewport | plot box | well | overflow | ruler bottom | clipper bottom |
|---|---|---|---|---|---|
| 1920×1080 | 331 | 331 | **0** | 972 | 1023 ok |
| 1600×900 | 151 | 168 | 17 | 809 | 843 ok |
| 1440×900 | 114 | 168 | **54** | **846** | **843 clipped** |
| 1024×768 | 17 | 168 | **151** | **811** | **711 clipped** |

**Ruling out the other two candidates:**
- *Annotation overflowing the ring:* no. It measured 10px tall with its bottom 4px above the well's
  edge — 836–846 inside a 14px band running 836–850, so 4px of clearance. The glyphs were cut
  because the whole **well** was displaced 54px down.
- *Card losing its border to `overflow`:* no. Pixel-scanning the baseline at x=378 (card padding,
  left of the well) found the border at y=814 = `rgb(31,58,92)`; at x=1000 (inside the well) y=814
  = `rgb(10,21,38)` = `--surface-sunk`. It rendered and was merely **occluded** — a descendant
  background paints after an ancestor's border.
- *Decisive:* at 1920×1080 the floor does not bind (331−28 = 303 > 140), overflow is exactly 0 and
  nothing clips — the defect appears iff the floor binds.

### Fix — two coupled changes, because it is two invariants

1. `Trend.tsx`: `max-h-full` on the well — structural guarantee it can never exceed the box it was
   given, so the padding ring and every label anchored in it stay inside the card. The pre-existing
   `overflow-hidden` absorbs the squeeze.
2. `TrendPanel.tsx`: `MIN_PLOT_HEIGHT` 140 → 72, re-documented as a *paint guard* (uPlot must not
   get a 0-height canvas or `trendCanvasPainted` hangs), **not** a design minimum. 72+28 = 100 fits
   the ~114px the tightest supported layout affords.

Change 1 alone is insufficient: at floor 140 the well is contained but the **canvas** is clipped,
silently eating uPlot's x-axis tick labels — a quieter regression than the reported one. I found
this by running my new guard against floor 140 and watching it pass, falsifying a claim I had
already written into the comment. Both halves are now pinned separately in `e2e/responsive.spec.ts`.
The y-bound manual-scale-only rule and in-ring annotation placement are untouched; context7
(`/leeoniya/uplot`) confirms `height` is total chart height with axis chrome allocated *within* it,
so a shorter canvas re-lays out rather than breaking.

Two consequences I did **not** absorb into scope. (a) 1440/1024×900 is now visibly compressed
(canvas 140 → 86): nothing clipped, but uPlot drops y-ticks and the traces sit in a ~36px band —
the honest rendering of a ~413px loop strip plus a 245px card whose header wraps to two lines
(81px), previously masked by the overflow. Reclaiming it means header/spacing work I was told not
to do. (b) 1024×768 is degenerate and pre-existing: plot box 17px < the 28px ring, so the well
bottoms out at 28px and containment is geometrically impossible — `max-height` is a border-box
limit and cannot shrink an element below its own padding. Hence the bound is `max(box, ring)`.

## Bug B — dead declaration removed

Confirmed in a real browser before touching anything: the active tab computes `borderBottomColor:
rgb(255,140,66)` = `--brand-accent` `#FF8C42`, while `borderTopColor: rgb(43,107,174)` = `--accent`
with `borderTopWidth: 0px`. The shorthand can only repaint the three zero-width edges → paints nothing.

- `Tabs.tsx`: dropped `data-[state=active]:border-accent`, kept `border-b-brand-accent`, and rewrote
  the comment to say why a shorthand must not be paired back in.
- `Tabs.test.tsx`: asserts the brand-amber longhand **and** `.not.toContain` the dead shorthand so
  it cannot creep back; title updated. The test was the stale artefact, as briefed.
  `border-b-brand-accent` is token-backed and token-guard's `named-palette` pattern needs a trailing
  digit, so that guard still passes.

## Files touched, baselines regenerated

All under `packages/smart_pid_web/`: `src/components/Trend.tsx`, `src/components/Tabs.tsx`,
`src/features/dashboard/TrendPanel.tsx`, `src/components/Tabs.test.tsx`, `e2e/responsive.spec.ts`
(new two-part guard, +105). 12 of 25 baselines in `e2e/themes.spec.ts-snapshots/`:
`dashboard-{optimizer,optimizer-dark,recorder,phosphor,isa101,neon}-{1024,1440}-linux.png`. 320/768
are byte-identical and the faceplate PNG untouched — predicted, then confirmed: below `lg` the panel
is content-height so the canvas holds its 280px fixed point (probed 768/320: well 308, canvas 280).
Pixel-verified regenerated `dashboard-optimizer-dark-1440-linux.png`: well now 682–795 (h=114, was
168 ending at 850), card bottom border at y=814 at **both** x=378 and x=1000 — `−30 min → agora` is
whole, eyeballed.

## Verification
```
# from packages/smart_pid_web, pinned binaries, explicit port on every Playwright run
$ ./node_modules/.bin/tsc -b                        -> exit 0, no output
$ ./node_modules/.bin/eslint src                    -> exit 0, no output
$ ./node_modules/.bin/eslint e2e/responsive.spec.ts -> exit 0, no output
$ ./node_modules/.bin/vitest run   -> Test Files 90 passed (90) | Tests 847 passed (847)
$ SPID_WEB_PORT=5210 playwright test -g "responsive|target size|renders identically"
    -> 36 passed (33.8s)   [the re-run AFTER --update-snapshots, i.e. baselines are stable]
$ SPID_WEB_PORT=5210 playwright test          -> 101 passed (1.7m)   [whole suite]
```

Guard proven both directions: floor 140 -> `canvas outgrows its well at 1600x900, Expected <= 0,
Received 17` (1 failed); floor 72 -> 1 passed. Pre-fix probe data (well 168 vs box 114) also fails
the containment half, so removing `max-h-full` is caught too. Contracts green in the full run:
`role=img "Tendência FIC-101"` with `data-glow` + `<canvas>`, `Exportar CSV` / `Unidade da janela`
>=44x44, trend >=65% of 1440, faceplate rail not scrolling at 1920/1600/1440/1024 for both roles.
Probe spec deleted; `git status` clean of it.
