# Task 9 Report — Canonical Realtime Layer (Fatia 0+1)

## Status
DONE. All 7 steps complete. TDD RED → GREEN, strict build clean, committed.

## Files created
- `packages/smart_pid_web/src/realtime/envelope.ts` — canonical contract §4 types: `RealtimeType` (6-value union incl. `'system'`), `RealtimeEnvelope<T>`, `StatusData`, `ActionData`, `AlarmData`, `AiData`, `StatsData`. Field names/types copied verbatim from the brief. `StatusData.timestamp` kept as `string` (ISO-8601) per binding fact — NOT changed to epoch.
- `packages/smart_pid_web/src/realtime/RealtimeProvider.tsx` — single WebSocket to `${proto}://${location.host}/ws/realtime`; first frame `{type:'auth', token}` on open; last-value maps for `status`/`stats` (forceRender); discrete subscriber dispatch for other types; exponential backoff (500ms → ×2 → cap 10_000ms); `onResync` fired only after a reconnect via `hadConnection` guard.
- `packages/smart_pid_web/src/realtime/useRealtime.ts` — canonical hook (contract §5) returning `{connected, lastStatus, lastStats, subscribe<T>, onResync}`; throws if used outside provider.
- `packages/smart_pid_web/src/realtime/useRealtime.test.ts` — 3 tests with MockWS via `vi.stubGlobal('WebSocket', ...)`.

## One deviation from verbatim brief (justified)
`RealtimeProvider` prop type changed from `children: ReactNode` to `children?: ReactNode` (one character: `?`). The brief's verbatim test calls `createElement(RealtimeProvider, { token: 'jwt-123' }, children)` — passing `children` as the THIRD positional arg, not inside the props object. Under strict TS, `tsc -b` (run by `npm run build`) type-checks the test and rejected the props object `{ token }` for missing required `children` (TS2769). React supplies positional children at runtime regardless, so making it optional is the idiomatic resolution. The test file is verbatim and untouched; only the component signature was relaxed. No runtime behavior change.

## TDD evidence

### RED (Step 3)
```
FAIL  src/realtime/useRealtime.test.ts
Error: Failed to resolve import "./RealtimeProvider" from "src/realtime/useRealtime.test.ts". Does the file exist?
```

### GREEN (Step 6, re-confirmed after the children? fix)
```
> vitest run useRealtime
 RUN  v2.1.9
 ✓ src/realtime/useRealtime.test.ts (3 tests) 35ms
 Test Files  1 passed (1)
      Tests  3 passed (3)
```

### Build (strict TS, noUnusedLocals/noUnusedParameters)
```
> tsc -b && vite build
vite v5.4.21 building for production...
✓ 30 modules transformed.
dist/assets/index-BPp-gYhQ.js  142.52 kB │ gzip: 45.77 kB
✓ built in 856ms
```
Clean. The `JSON.parse(e.data) as RealtimeEnvelope` cast is intentional and accepted under strict mode.

## How `auth_ok` is handled
The backend's first reply is a control frame `{"type":"auth_ok"}`. `onmessage` routes by `env.type`: `status`/`stats` → last-value maps; everything else → `subs.current.get(env.type)?.forEach(...)`. `'auth_ok'` is not a registered subscriber key, so `subs.current.get('auth_ok')` is `undefined` and optional chaining makes the dispatch a no-op. It is harmlessly ignored — no special-casing, no crash. Correct per the binding contract.

## Self-review (all PASS)
- Single WS: one `new WebSocket` per `connect()`, held in `wsRef`, closed in cleanup.
- First-frame auth exact: `ws.send(JSON.stringify({ type: 'auth', token }))`; test asserts `{type:'auth', token:'jwt-123'}`.
- Backoff caps at 10s: `Math.min(backoff.current * 2, MAX_BACKOFF)`, `MAX_BACKOFF = 10_000`, starts 500ms, reset to 500 on open.
- onResync only on reconnect (not first connect): `hadConnection` ref gates resync; set true after first open.
- Cleanup: effect return sets `cancelled = true`, `clearTimeout(reconnectTimer)`, `wsRef.current?.close()`. `onclose` checks `cancelled` to suppress reconnect after unmount.
- status/stats keyed by `loop_id` with `loop_id !== null` guard before `.set()`.
- Not wired into App/router (per scope) — modules only.
- Staged only the 4 realtime source/test files (not the pre-existing deleted pytest db files), then committed.

## Commit
`da84a60` feat(web): canonical realtime envelope, RealtimeProvider (single WS), useRealtime hook — 4 files, 212 insertions.

## Concerns
1. The `children?: ReactNode` relaxation (see deviation above) — single-char change forced by strict-build type-checking the verbatim test; behavior-neutral. The app-shell/dashboard task always passes children, so optionality is invisible in real usage.
2. None otherwise.

---

## Fix Pass — Reviewer Important Issue (stale render) + JSON.parse hardening

### What changed (only `src/realtime/RealtimeProvider.tsx`)
- **FIX 1 (Important — stale render):** The context `value` was `useMemo`'d on `[connected, subscribe, onResync]` while status/stats lived in `useRef` Maps mutated in place via `lastStatus.current.set(...)`. Map references and the context object never changed identity across live updates, so any consumer memoizing on `lastStatus`/`lastStats` identity silently missed updates. Applied the prescribed pattern:
  - Promoted the force-render state to a named version counter: `const [version, forceRender] = useState(0);`
  - Status frame: `lastStatus.current = new Map(lastStatus.current).set(env.loop_id, env.data as StatusData);` then `forceRender((n) => n + 1)` (clone-on-write — new Map identity per update).
  - Stats frame: same clone-on-write for `lastStats.current`.
  - Added `version` to the context memo deps: `useMemo(() => ({...}), [connected, version, subscribe, onResync])` — every update yields a new `value` object and new Map identity, so memoizing consumers update correctly. Refs stayed refs (not converted to state); only the assignment is now clone-on-write.
- **FIX 2 (cheap hardening):** Wrapped `JSON.parse(e.data)` in the `onmessage` handler in try/catch — a malformed frame now silently returns instead of throwing inside `onmessage`. No logging noise.

### Untouched (verified)
WS lifecycle, exponential backoff, `onResync` gating (`hadConnection`), `subscribe` disposer, first-frame auth send, and the `children?: ReactNode` signature — all unchanged. No new deps, no refactor.

### Verification
- `npm run test -- useRealtime` → `Test Files 1 passed (1)` / `Tests 3 passed (3)` (unchanged — 3 passed).
- `npm run build` → clean under strict TS (`tsc -b && vite build`): `30 modules transformed`, `built in 872ms`. `noUnusedLocals` satisfied — `version` is read in the memo deps.

### Self-review
Clone-on-write allocates a fresh Map per status/stats frame; at realtime cadence this is a small, bounded allocation (Map size = loop count) and is the standard React identity-change idiom — acceptable and intentional. try/catch is the minimal guard requested; a dropped frame is recoverable since `status`/`stats` are last-value coalesced and re-synced via REST on reconnect.

### Commit
`3a894fc` fix(web): rebuild realtime context value on update (clone-on-write maps + version) + guard JSON.parse — 1 file, +10/-5. Staged only `RealtimeProvider.tsx`.

### Fix-pass concerns
none.
