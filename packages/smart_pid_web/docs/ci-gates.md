# CI Gate Order (§12 — Perf budget + quality gates)

This package has **no in-repo CI workflow** (`.github/workflows/` is absent). Per Task 9.3,
the §12 gate order is documented here as the authority; when a CI workflow is added it MUST
run these steps in this order, failing fast on the first non-zero exit.

## Gate order (run from `packages/smart_pid_web/`)

| # | Gate | Command | Fails when |
|---|------|---------|-----------|
| 1 | **Lint** | `npm run lint` | ESLint error (incl. flat-config rules + `no-raw-color` token guard) |
| 2 | **Typecheck** | `npm run typecheck` | `tsc -b` reports any type error |
| 3 | **Vitest** | `npm run test` | Any unit/contract test fails — includes contrast, target-size, token-resolve, missing-states, and the ISA-101 guard suite |
| 4 | **Build + bundle budget** | `npm run build:budget` | `vite build` fails, OR app-page JS > 300 KB gzip, OR CSS > 50 KB gzip, OR a regression beyond tolerance vs `bundle-baseline.json` |
| 5 | **Playwright snapshots** | `npm run test:e2e` | Any visual/E2E snapshot diff |

`build:budget` runs `npm run build` then `npm run check:bundle` (`scripts/check-bundle.mjs`).

## Bundle budgets (gzip)

- **app-page JS entry chunk: ≤ 300 KB gzip**
- **CSS: ≤ 50 KB gzip**
- Regression guard: > 10 KB growth over the committed `bundle-baseline.json` fails the gate.
  Run `npm run check:bundle -- --update-baseline` to record an intentional change.

The check resolves the entry chunk + its CSS from `dist/.vite/manifest.json`
(`build.manifest: true` in `vite.config.ts`); it falls back to the largest hashed JS/CSS
asset if the manifest is absent.

## How the budget is kept

Heavy/rare routes (Executive Dashboard, MultiTrend, Simulator, Projects) are code-split via
`React.lazy` + `Suspense` in `src/App.tsx`, keeping the dashboard entry lean. Tailwind v4
purges unused CSS via its default content scan; Radix is tree-shaken by Vite/Rollup.

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
  - run: npx playwright install --with-deps
  - run: npm run test:e2e
```
