# Fatia 8 — Themes + Faceplate — Orchestrator Digest (FINAL FATIA, closes parity)

Merged main **`814f902`** (parents `2a17c78` + `95d4806`), 2026-06-20. Frontend-only (empty `*.py` diff).
Branch `feat/web-fatia8-themes-faceplate` (deleted post-merge). This is the LAST fatia — total visual +
functional parity reached → **PySide6 HMI can be retired**.

## Gate evidence (final HEAD `95d4806`)
vitest 274/274 (65 files) · tsc -b 0 · vite build OK (119.9 kB gz) · Playwright e2e 21/21
(5 themes × {320,768,1024,1440} + faceplate) · eslint 0 err / 2 pre-existing warns.

## Commits (11)
13fcc9d registry · 1cc2488 ThemeSwitcher · 36fe4ae md3/ocean tokens · 71d037c contrast gate ·
882c4d6 scale helper · 87bc742 AnalogBar instrument · 0721482 uPlot theme · b5e72132 Faceplate ·
36dd9c4 mount+PV size · 8f58b8a visual baselines · 95d4806 pv_decimals fix.

## Key decisions (durable)
1. **Contrast gate = WCAG 1.4.11 3:1 for non-text alarm indicators** (NOT 4.5/5:1). Spec §8.4 demanded
   4.5/5:1 but identity reds (ISA-101 `#FF3333` 3.77:1, Dark Room `#D92525` 3.92:1 on dark surfaces)
   cannot meet it; alarm color renders as a 3px stripe + 10px shaped icon (non-text), colorblind safety
   via ISA-101 §8.2 SHAPE. Owner-approved; spec §8.4 reconciled (`c1a1230`). Text stays ≥4.5:1 (all pass).
   `themeContrast.ts` hand-rolls contrast (no `wcag-contrast` dep) — text 4.5 + alarm 3 + CRIT/WARN hue-OR-lum.
2. **Faceplate mounted** via ControllerCard "Open faceplate" (⤢) → DashboardPage `Dialog` (owner-approved;
   spec/plan were silent on the entry point). Without this the widget was dead code + unsnapshottable.
3. **Manual CO = validated numeric input** (not the brief's "slider") — a11y/precision; gated on MAN.
4. **pv_decimals per-loop precision preserved** — T6 had hardcoded `.toFixed(1)` (regression vs main);
   caught at final review, fixed `95d4806` (AnalogBar/Faceplate `decimals` prop; CO always %@1).

## STALE-brief corrections that recurred EVERY task (the brief is a sketch; real code wins)
- Hook/contract names: `useModeMutation/useSetpointMutation/useOutputMutation` `{id,...}` (NOT useSetMode/`{controller_id}`);
  modes from `loop-config/types` CONTROLLER_MODES; apply-tuning = mirror `AiPanel` (`applyTuning`+`ConfirmApplyTuningDialog`+`useTuningRecommendation`).
- Status frame: `pv/sp/co` are FFSignal → access `.value`; `lastStatus` is `ReadonlyMap<number,StatusData>`.
- Storage key `spid.theme` (Fatia 0+1 used `smart-pid-theme`; renamed — one-time theme reset, acceptable pre-GA).
- Tests COLOCATED (`src/**/*.test.tsx`), not `__tests__/`. Charts render BARE in tests → no `useTheme` in RealtimeTrend/MultiTrendChart (MutationObserver instead).
- Tokens: `--sp-N`, `--font-data` (NOT `--font-mono`), `--text-3xl/xl`; `--radius-*` default 0 in tokens.css, md3 overrides to 12/8/999.
- e2e: dir `e2e/`, cmd `npm run test:e2e`, no backend; StubWS seeds token **AND `spid.welcome-seen='1'`** + auto-push STATUS frames; mockRest doubles. Snapshots `-linux` tagged, committed (not gitignored).
- `npx tsc -b` is a HARD gate vitest/eslint miss — ran every UI/types task.

## Open follow-ups for the spec owner (none merge-blocking; full list in `.git/worktrees/main-web-hmi/sdd/fatia8-minor-findings.md`)
- **EU range + decimals on `ControllerResponse`:** AnalogBar/Faceplate scale hardcodes `{euMin:0,euMax:100}` (no
  per-loop EU range field on the DTO — bars mis-scaled for ranges ≠ 0–100). Same root gap as ControllerCard since Fatia 0+1.
  A future `pv_scale {eu_min,eu_max,unit,decimals}` on the DTO closes both the scale and the decimals plumbing cleanly.
- **`--alarm-diag-bg`** omitted from md3-dark/md3-light/ocean (advisory-row bg falls back to `transparent` there).
- **BYPASS 9th mode button** in Faceplate + CardControls — reconcile the "8 modes" spec wording or filter BYPASS.
- 2 pre-existing `react-hooks/exhaustive-deps` warns (RealtimeProvider, DashboardPage onResync) — Fatia 0+1, not this fatia.

## PySide6 retirement (next, separate work — NOT this fatia)
Parity is reached. Retiring `packages/smart_pid_hmi/` (remove from workspace, drop ZMQ tcp://5555 PySide6 publisher
path if web-only) is a distinct follow-up branch, to be planned + approved separately.
