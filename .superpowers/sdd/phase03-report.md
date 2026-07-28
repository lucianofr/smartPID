# Phase 3 — Realtime Layer + Pure Modules — DONE

## Status: COMPLETE

All 14 tasks implemented, all tests pass, typecheck and lint exit 0.

### Commits (new on `docs/web-frontend-rewrite-spec`)
- `6b186cf` feat(web): add realtime envelope types mirroring the WS bridge
- `fcdda10` feat(web): add bounded window buffer exposing the undecimated pen tip
- `71b0009` feat(web): add four-state alarm ack/clear machine
- `fcf0815` feat(web): extend scale with percent and clamping helpers
- `4e243ee` feat(web): consolidate tabular formatting with unit, percent and timestamp helpers
- `f41c87c` feat(web): typed api client with §11 error taxonomy and auth hooks
- `9808b9d` feat(web): typed endpoints, wire types and canonical query keys
- `265154c` feat(web): auth context with /auth/me role hydration and 401/403 side effects
- `da5e20f` feat(web): §9 capability map and useCan hook
- `5a57f95` feat(web): RouteGuard with admin-only variant
- `b623082` feat(web): normative §7 resync runner priming canonical query keys
- `b733a61` feat(web): RealtimeProvider with single-socket fan-out and useRealtime(loopId, type)

### Verification
- `npm run test` → 232 passed / 37 files / exit 0 (120 phase-2 + 112 new phase-3).
- `npm run typecheck` → exit 0, no output.
- `npm run lint` → exit 0.

### New test files (10 + 2 extended)
- `src/lib/envelope.test.ts` (18 tests: validate/parse/isAuthOk/timestamp + seqTracker)
- `src/lib/windowBuffer.test.ts` (9 tests: monotonic trim, decimation, pen tip)
- `src/lib/alarmMachine.test.ts` (18 tests: 12-cell transition table + fromActiveRow + predicates)
- `src/lib/scale.test.ts` (extended: +6 phase-3 tests for valueToPercent/clampToScale)
- `src/lib/format.test.ts` (extended: +10 phase-3 tests for formatWithUnit/formatPercent/formatTimestamp)
- `src/api/client.test.ts` (10 tests: classifyStatus + 401/403/422/Blob/FormData/transport)
- `src/api/endpoints.test.ts` (8 tests: exact backend paths + canonical query keys)
- `src/auth/AuthContext.test.tsx` (6 tests: login + restore + 401→logout + 403→refetch + onPermissionDenied)
- `src/auth/useCan.test.tsx` (5 tests: matrix + hook over AuthContext)
- `src/auth/RouteGuard.test.tsx` (4 tests: redirect/render/adminOnly pending/adminOnly user-bounce)
- `src/realtime/resync.test.ts` (6 tests: priming, history window, 403 swallow, non-403 reject)
- `src/realtime/useRealtime.test.tsx` (12 tests: handshake, fan-out, 4401, backoff, §8 resync sequencing on reconnect, §8 resync on seq gap, §8 resync failure → backoff)

### Concerns
1. **Hand-crafted `src/api/generated/openapi.ts` stub**: the plan assumes the phase-2 hermetic codegen has produced a complete `openapi.ts` (Task 25 of phase 2). That codegen hit a `PydanticUserError: TypeAdapter[AIRepository, Depends(get_ai_repo)]` ForwardRef bug tracked separately by `FixForwardRef` (peer); meanwhile phase 3 needed `components['schemas']['UserClaims', 'TokenResponse', 'ControllerResponse', 'AIStatusResponse', 'OPCUAStatusResponse', 'SimulatorStatusResponse']` to compile. The shipped file is a minimal hand-crafted stub of those six schemas only — sufficient for phase-3 imports and tests, but the real backend codegen must replace it via `npm run gen:api` once the FastAPI annotation issue is resolved.
2. **`packages/smart_pid_web/.gitignore`** had `src/api/generated/` listed; removed in commit `f41c87c` so the stub can ship.
3. Unstaged backend changes (10 files in `packages/smart_pid_core/...`) exist in the worktree from the `FixForwardRef` peer — those are the ForwardRef resolution; not part of phase 3 deliverables, intentionally not committed here.
4. Tests for the Blob-returning `api.download` use duck-typing (`typeof blob.size === 'number'`) rather than `instanceof Blob`, because jsdom produces a different-realm Blob than the global one; behavior assertion is identical.

### Spec coverage
- §7 pure modules (envelope, windowBuffer, alarmMachine, scale, format) — no React/DOM imports in `src/lib/`.
- §7 realtime (`RealtimeProvider`, `useRealtime(loopId, type)`, resync set incl. alarm-history-since-`last_seen_ts`).
- §7 data (`apiClient` typed from committed codegen).
- §7 auth (`AuthContext`, `RouteGuard`, `useCan(action)`).
- §8 data flow (resync before live render; writes REST-only).
- §9 capability table (12 actions, matrix test).
- §11 error rows 401/403/404/409/422/5xx/502/network + WS 4401/overflow-close.
- §12 test rows "Unit: pure modules" + "Integration: useRealtime against a fake WebSocket; apiClient against a mocked API".
- §6.7 pen-tip dependency (undecimated head) — `WindowBuffer.latest()`.
- Phase-8 follow-up documented in `CAPABILITY_ACTIONS` export comment (plan line 3431).