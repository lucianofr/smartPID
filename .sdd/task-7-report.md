# Task 7 Report — Theme token contract + ThemeProvider + format helper

## Status
COMPLETE — committed `80e6486` on `feat/web-fatia01-foundation-dashboard`.

## Files created (all under `packages/smart_pid_web/`, verbatim from brief)
- `src/theme/tokens.css` — canonical stable token contract (type scale §3.2, spacing §4.1, transitions §6.2) + `.numeric` class. 34 lines.
- `src/theme/themes.css` — per-theme semantic VALUES for `[data-theme='dark-room']` (§2.1) and `[data-theme='isa101']` (§2.2). 35 lines.
- `src/theme/ThemeProvider.tsx` — context provider; sets `data-theme` on `document.documentElement`, persists to localStorage key `smart-pid-theme`, default `isa101`. Exports `ThemeProvider`, `useTheme`, `ThemeName`. 27 lines.
- `src/lib/format.ts` — `formatNumber(value, decimals)`: `value.toFixed(decimals)`, em-dash `'—'` (U+2014) for null/undefined/NaN. 7 lines.
- `src/lib/format.test.ts` — 3 vitest cases (fixed decimals, dash for null/NaN, always-fixed digits). 15 lines.

## TDD evidence
- Step 4 RED: `npm run test -- format` → `Error: Failed to resolve import "./format" from "src/lib/format.test.ts"` (1 failed suite, no tests). Confirmed before implementing `format.ts`.
- Step 7 GREEN: `npm run test -- format` → `Test Files 1 passed (1) / Tests 3 passed (3)`.

## Build
`npm run build` (tsc -b + vite build) → `✓ 30 modules transformed`, `✓ built in 888ms`. Strict type-check passes; new .tsx/.ts compile cleanly.

## Self-review
- Token NAMES copied verbatim — no renames/reorders (CANONICAL contract for downstream fatias).
- Hex VALUES copied verbatim for both themes — no normalization (WCAG-AA gates depend on exact hex).
- Em-dash verified programmatically: codepoint is U+2014 exactly, matching the test assertion.
- Not wired prematurely: `grep` of `src/main.tsx` and `src/App.tsx` for theme/ThemeProvider/tokens.css/themes.css returned nothing (exit 1). CSS files unimported — expected (imported in a later task); build still passes.
- Commit staged exactly the 5 source files (no node_modules/dist/tsbuildinfo). `git status` clean for those paths.

## Concerns
None. The two CSS files are intentionally not imported yet (per brief, a later task wires the app shell), so they currently have no runtime effect — this is by design, not a defect.
