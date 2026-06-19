# Task 4 Report — `/ws/realtime` endpoint (first-message auth, Origin validation, ConnectionBuffer)

> Note: the brief requested this report at `sdd/task-4-report.md`, but that `sdd/` dir is git-internal
> (`.git/worktrees/main-web-hmi/sdd/`, read-only to the file-writer guard). Prior task reports
> (task-1/2/3) live in the worktree's `.sdd/`, so this report follows that established convention.

**Status:** DONE_WITH_CONCERNS (functional & tested; concerns are brief path drift + deferred wiring, not regressions)
**Branch:** `feat/web-fatia01-foundation-dashboard` (worktree `.worktrees/main-web-hmi`)
**Commit:** `d891a87` — `feat(api): /ws/realtime first-message auth, Origin check, coalescing+lossless buffer`

## Files changed
- `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/ws/realtime.py` (+79): added `ConnectionBuffer`, `register_realtime_ws`, `_origin_allowed`, top-level constants `_ALLOWED_ORIGIN_DEFAULT`/`_WS_CLOSE_AUTH`/`_LOSSLESS_QUEUE_MAX`, and imports (`FastAPI`, `WebSocket`, `WebSocketDisconnect`, `WebSocketState`, `decode_access_token`).
- `tests/core/api/test_ws_realtime.py` (+115): appended 4 auth/Origin endpoint tests + 3 ConnectionBuffer tests; consolidated new imports into the existing import block.

## What I did (TDD per the brief's 10 steps)
1. Read brief + existing `realtime.py` (T2/T3 code: `ConnectionManager`, `RealtimeBridge`, `map_topic_to_envelope` already present) + `auth.py`.
2. RED: appended tests → `ImportError: cannot import name 'ConnectionBuffer'` (collection error). Matches the brief's expected RED (missing-symbol import error). `ConnectionBuffer` is alphabetically first in the import tuple so it trips first; `register_realtime_ws` was equally missing.
3. GREEN: implemented endpoint + buffer. `21 passed`.
4. Lint: 1 E501 in a test line copied verbatim from the brief (101>100); wrapped the `buf.offer({...})` call. Re-lint `All checks passed!`, tests still `21 passed`.
5. Commit `d891a87` with only the two task files.

## Signature verification (the brief's stated assumptions held)
- `create_access_token(*, user_id: int, username: str, role: str, secret: str, expiry_hours: int = 8) -> str` — matches brief's keyword usage exactly.
- `decode_access_token(token: str, *, secret: str) -> dict` (raises `jwt.PyJWTError`) — matches. No test or endpoint adaptation needed for signatures.
- Env: starlette 1.0.0, fastapi 0.135.3. `WebSocketState.CONNECTED` and `websocket.application_state` both valid → brief endpoint code correct against installed versions.

## Deviations from the brief (binding-resolution & repo-reality driven)
1. **Test file path.** Brief says `packages/smart_pid_core/tests/adapters/inbound/api/test_ws_realtime.py`. That path/dir does NOT exist. The real, already-existing T2/T3 test file is `tests/core/api/test_ws_realtime.py` (repo `testpaths = ["tests"]`). I appended there, as the brief intends ("Append to test_ws_realtime.py" + it references `ConnectionManager()`/`map` unqualified, which only works in the file that already imports them).
2. **Imports/constants hoisted, not duplicated.** Brief Step 3 re-imports `FastAPI, WebSocket` + starlette names and redefines `_WS_CLOSE_AUTH`/`_LOSSLESS_QUEUE_MAX` at the append point. Duplicating would trigger ruff F811/F401. I placed them once at the top with existing imports; behavior identical.
3. **Test imports consolidated** into the existing single import block (existing file already imports `pytest`); did not re-`import pytest`. Added `ConnectionBuffer`/`register_realtime_ws` to the existing `...realtime import (...)` tuple.
4. **One test line wrapped** for line-length=100 (brief's verbatim line was 101 chars). Test-only formatting; assertions unchanged.
5. **Commit scope.** Brief's `git add -A` would have swept 7 pre-existing untracked `.sdd/*` report files from prior tasks into my commit. I amended (soft reset + unstage `.sdd/`) so the commit contains ONLY my two task files — surgical/traceable. `.sdd/*` files remain untracked, untouched.

## Test output (verbatim, final run)
```
.....................                                                    [100%]
... InsecureKeyLengthWarning (HMAC key 11 bytes < 32 recommended) x3 ...
21 passed, 3 warnings in 0.07s
```
(13 pre-existing T2/T3 + 4 auth/Origin + 3 ConnectionBuffer + 1 valid-token/auth_ok = 21.) Ran ONLY the targeted file per the VERIFICATION CONSTRAINT (full suite SIGABRTs on Py3.14+aiosqlite — environmental, not touched). All commands prefixed with `SPID_JWT_SECRET=test-secret`.

Lint (verbatim): `All checks passed!` for both the production file and the test file.

## Self-review notes
- Close-code 4401 fires on: missing token, malformed first frame (`WebSocketDisconnect`/`ValueError`), `type != "auth"`, missing/disallowed Origin, and any JWT decode error (expired included via broad `except Exception` with documented `# noqa: BLE001`). Matches the security spec.
- CSWSH defense: Origin must be present AND in the allowlist (`_origin_allowed` rejects `None`).
- No scope creep: `ConnectionBuffer` is unit-tested only and NOT wired into the live send/broadcast path — per the binding ambiguity resolution (integration deferred). Endpoint receive loop is exactly the brief's (watches client close; bridge drives outbound via `manager.broadcast`).
- No magic numbers: 4401 / 256 / default origin are named constants.
- mypy: not runnable in this worktree env (`mypy` not installed / not declared); brief's 10 steps include no mypy gate and the VERIFICATION CONSTRAINT limits me to the targeted test path. Production code is fully annotated and ruff-clean.

## Concerns
- The endpoint reads `app.state.settings.allowed_ws_origins` and `.jwt_secret`. Production `CoreSettings` must expose `allowed_ws_origins` for real Origin enforcement; that wiring (lifespan + `register_realtime_ws(app)` registration) is Task 5, not this task. A `getattr(..., default)` fallback keeps the endpoint safe if absent, but real CoreSettings should define it.
- Brief test-path/import drift (deviations 1-3): a reviewer comparing literally against the brief will see differences; they are repo-reality adaptations, behavior-equivalent.
