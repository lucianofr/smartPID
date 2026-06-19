# Task 10 Report — AnalogBar, ControllerCard, RealtimeTrend, app shell, live DashboardPage

Branch: `feat/web-fatia01-foundation-dashboard` (worktree `.worktrees/main-web-hmi`)
Scope: `packages/smart_pid_web/` only.

## Files

Created:
- `packages/smart_pid_web/src/components/AnalogBar.tsx` — meter bar (track + scaleX fill + value), `role="meter"`, design-system §5.1 tokens.
- `packages/smart_pid_web/src/components/ControllerCard.tsx` — 280px card, alarm strip, header, 3 AnalogBars (PV/SP/CO), mode footer. Exports `ControllerSummary`.
- `packages/smart_pid_web/src/components/RealtimeTrend.tsx` — uPlot themed from tokens (PV/SP/CO), jsdom-safe (`try/catch` around `new uPlot`, `destroy()` cleanup).
- `packages/smart_pid_web/src/components/shell/StatusIndicator.tsx`
- `packages/smart_pid_web/src/components/shell/NavRail.tsx`
- `packages/smart_pid_web/src/components/shell/TopBar.tsx`
- `packages/smart_pid_web/src/components/shell/AppShell.tsx`
- `packages/smart_pid_web/src/pages/DashboardPage.tsx` — controllers via Query `['controllers']`, OPC via Query `['opcua-status']` `refetchInterval:5000`, live PV via `useRealtime().lastStatus.get(c.id)`, `onResync` effect refetches both queries on WS reconnect.
- `packages/smart_pid_web/src/components/ControllerCard.test.tsx` (2 tests)
- `packages/smart_pid_web/src/components/RealtimeTrend.test.tsx` (1 test)

Modified:
- `packages/smart_pid_web/src/App.tsx` — REPLACED. Provider nesting Theme → Query → Auth → BrowserRouter → RealtimeProvider(token) → Routes (`/login`, `/` (RequireAuth→DashboardPage), `*` → `/`). Imports `./theme/tokens.css` + `./theme/themes.css`.
- `packages/smart_pid_web/src/test/setup.ts` — added a jsdom no-op canvas 2D context stub (test-infra only; see Deviations).

## CONTRACT CHECK — ControllerResponse (brief `ControllerSummary` vs real backend)

Read `_to_response` in `packages/smart_pid_core/.../api/routers/controllers.py` and the DTO
`ControllerResponse` in `packages/smart_pid_domain/.../dtos/controllers.py`.

Brief `ControllerSummary = { id, name, description, pv_decimals, pv_unit }`.

Real `ControllerResponse` fields: `id`, `name`, `description` EXIST. But:
- `pv_decimals` — DOES NOT EXIST on the backend. No decimals field at all.
- `pv_unit` — DOES NOT EXIST as a flat field. Unit lives nested: `pv_scale.unit` (`ScaleConfigDTO { eu_min, eu_max, unit }`).
- Per-loop range also lives in `pv_scale.eu_min / eu_max` (relevant to the hardcoded AnalogBar 0..100).

Per the brief, KEPT the brief's `ControllerSummary` shape (tests + e2e mock it). REPORTING the
mismatch as a T12 contract item:
  T12 must either (a) add `pv_decimals` + `pv_unit` flat fields to `ControllerResponse`, or
  (b) adapt the frontend to map `pv_scale.unit` → `pv_unit` and pick a decimals convention.

SECOND mismatch (OPC status): brief's DashboardPage computes
`opcDown = opcua.data.state !== 'CONNECTED'`, but the real `/opcua/status` returns
`state: ConnectionState` whose connected value is `"ONLINE"` (enum: OFFLINE/CONNECTING/ONLINE/RECONNECTING).
So against the live backend a healthy OPC would render as DOWN. Kept brief's code verbatim
(authoritative); flagging for T12: compare against `'ONLINE'`, not `'CONNECTED'`.

Route paths confirmed correct: `/controllers` (list), `/opcua/status` (mounted at `/opcua` prefix).

## TESTS / BUILD

`npm run test` — 5 files, 11 passed:
```
 ✓ src/lib/format.test.ts (3 tests)
 ✓ src/realtime/useRealtime.test.ts (3 tests)
 ✓ src/auth/AuthContext.test.tsx (2 tests)
 ✓ src/components/ControllerCard.test.tsx (2 tests)
 ✓ src/components/RealtimeTrend.test.tsx (1 test)
 Test Files  5 passed (5)
      Tests  11 passed (11)
```
TDD: ControllerCard RED (unresolved import) → GREEN (2 passed); RealtimeTrend RED → GREEN (1 passed). PV test asserts `/150\.2/`.

`npm run build` — exit 0:
```
tsc -b  (clean, strict: noUnusedLocals/noUnusedParameters)
vite build → 98 modules
dist/index.html                 0.41 kB
dist/assets/index-*.css         2.67 kB gzip 1.08 kB   (incl. uPlot CSS)
dist/assets/index-*.js        209.40 kB gzip 67.11 kB
```
`dist/`, `node_modules/`, `tsconfig.tsbuildinfo` all git-ignored → only source/test staged.

## Deviations from the brief (both minimal, justified)

1. RealtimeTrend.test.tsx: dropped the brief's `import { ..., vi }` — `vi` was unused and would
   trip `noUnusedLocals` in `tsc -b`. Component + test behavior unchanged.
2. test/setup.ts canvas stub: the brief's `try/catch` only guards uPlot's SYNCHRONOUS constructor.
   uPlot schedules a deferred draw (microtask) that calls `ctx.clearRect` on jsdom's stub canvas,
   throwing an Unhandled Error AFTER the try/catch returns → `vitest run` exited 1 even though the
   test "passed". Added a no-op 2D context to the shared test setup (test-infra, not component
   code). RealtimeTrend.tsx kept verbatim per the brief. Result: exit 0, no unhandled errors.

## Self-review

- Provider nesting matches brief: Theme → Query → Auth → BrowserRouter → RealtimeProvider(token) → Routes. OK.
- RequireAuth guards `/`; `*` → `/`; `/login` public. OK.
- Live status keyed by controller id (`lastStatus.get(c.id)`). OK.
- OPC polled via REST `refetchInterval:5000` (not WS). OK.
- onResync effect refetches controllers + opcua on WS reconnect. OK.
- uPlot jsdom-safe (try/catch + destroy + setup stub). OK.
- App imports tokens.css + themes.css → CSS shipped in dist. OK.
- Strict build clean; imports limited to what's used; `type ReactNode` imported, no bare `React.X`. OK.
- Nothing out of scope; only `packages/smart_pid_web/` touched.

## Concerns (for T12)

1. `ControllerResponse` lacks `pv_decimals`/`pv_unit` (unit is `pv_scale.unit`) — frontend/backend contract gap.
2. OPC `opcDown` compares `'CONNECTED'` but backend emits `'ONLINE'` → false "OPC down" against live backend.
3. AnalogBar PV/SP range hardcoded 0..100 (accepted Fatia-0+1 simplification); real range is `pv_scale.eu_min/eu_max`.
