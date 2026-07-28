# CI Gate Order (§12 — quality gates, rewrite era)

This package has **no in-repo CI workflow** (`.github/workflows/` is absent). This
document is the authority for the gate order; when a CI workflow is added it MUST
run these steps in this order, failing fast on the first non-zero exit.

## Gate order (run from `packages/smart_pid_web/`)

| # | Gate | Command | Fails when |
|---|------|---------|-----------|
| 1 | **Lint** | `npm run lint` | ESLint error |
| 2 | **Typecheck** | `npm run typecheck` | `tsc -b` reports any type error |
| 3 | **Vitest** | `npm run test` | Any unit/component/gate test fails — includes the §6.4 token-resolution gate, the Recorder/Phosphor contrast gate, the no-raw-color source guard (`src/__tests__/token-guard.test.ts`), the fonts gate, and every primitive component test |
| 4 | **Build + bundle budget** | `npm run build:budget` | `vite build` fails, OR app-page JS > 300 KB gzip, OR CSS > 50 KB gzip, OR fonts > 160 KB raw (§6.2), OR a regression > 10 KB vs `bundle-baseline.json` |
| 5 | **OpenAPI drift** | `npm run gen:api:check` | The committed `openapi.json` / `src/api/generated/openapi.ts` differ from a fresh hermetic regeneration (requires `uv sync` at the repo root) |
| 6 | **Playwright E2E** | `npm run test:e2e` | **SUSPENDED — E2E IS DARK in phases 2–3** (spec §13/§14: the foundation has no routes). Do NOT run as a gate. Re-greening is per phase from 4 on: `login-dashboard`, `faceplate`, `responsive`, `target-size`, `fatia7-auth-negative`, `themes` (rewritten) in phase 4; see the §13 table for the rest. The specs and old visual baselines stay on disk untouched until their phase (baselines are deleted in phase 11). |

`build:budget` runs `npm run build` then `npm run check:bundle` (`scripts/check-bundle.mjs`).

## Bundle budgets

- **app-page JS entry chunk: ≤ 300 KB gzip**
- **CSS: ≤ 50 KB gzip**
- **Fonts: ≤ 160 KB raw woff2 sum (§6.2)** — 1 Archivo Variable + 2 Geist Mono files
- Regression guard: > 10 KB growth over the committed `bundle-baseline.json`
  (fields `appPageJsGzipKb`, `cssGzipKb`, `fontsRawKb`) fails the gate.
  Run `npm run check:bundle -- --update-baseline` to record an intentional change.

The check resolves the entry chunk + its CSS from `dist/.vite/manifest.json`
(`build.manifest: true` in `vite.config.ts`); it falls back to the largest hashed
JS/CSS asset if the manifest is absent. Fonts are summed from `dist/assets/*.woff2`.

## Example workflow (reference — not committed)

```yaml
# .github/workflows/web-ci.yml — add when CI infra lands. Order is load-bearing.
defaults:
  run:
    working-directory: packages/smart_pid_web
steps:
  - run: npm ci
  - run: npm run lint
  - run: npm run typecheck
  - run: npm run test
  - run: npm run build:budget
  - run: uv sync            # repo root — gen:api:check shells into the backend
  - run: npm run gen:api:check
  # npm run test:e2e — DARK until phase 4 (§13); re-enable per phase
```