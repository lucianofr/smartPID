# Task 2 Report — `ConnectionManager` (resilient async broadcast)

## Status
DONE_WITH_CONCERNS (functionality complete; two intentional deviations from the brief noted below)

## Scope
Built ONLY the `ConnectionManager` (Task 2). Did NOT build the `/ws/realtime` endpoint
(Task 4), the per-connection buffering/coalescing (Task 4), or the `RealtimeBridge`
bus→envelope consumer (Task 3). The module docstring mentions the bridge model for
forward context, but no bridge/endpoint code was added.

## TDD cycle
- RED: `tests/core/api/test_ws_realtime.py` failed with
  `ModuleNotFoundError: No module named 'smart_pid_core.adapters.inbound.api.ws'`.
- GREEN: after adding the package + impl, `3 passed in 0.02s`.
- Lint: `ruff check` on the new `ws/` package and the test file → `All checks passed!`.

## Files
- Created `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/ws/__init__.py`
  (package marker, verbatim from brief).
- Created `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/ws/realtime.py`
  (`_Sendable` Protocol + `ConnectionManager`, verbatim from brief).
- Created `tests/core/api/test_ws_realtime.py` (brief test code verbatim).

## Interface produced (matches brief)
`class ConnectionManager`:
- `async connect(ws)` — adds under async lock.
- `async disconnect(ws)` — `discard` under async lock.
- `async broadcast(message: str)` — snapshots the set under the lock, then sends
  outside the lock; any socket whose `send_text` raises is collected and removed
  afterward (one dead/slow socket cannot break delivery to the rest). Does not mutate
  the connection set while iterating it during broadcast.
- `count` property.

## Deviations from the brief (intentional, noted per task instructions)
1. **Test location.** Brief specified
   `packages/smart_pid_core/tests/adapters/inbound/api/test_ws_realtime.py`. The repo has
   NO per-package `tests/` dir; `pyproject.toml` sets `testpaths = ["tests"]`, so a test at
   that path would never be collected by `uv run pytest` (orphaned). Placed it at
   `tests/core/api/test_ws_realtime.py` (alongside the existing `test_opcua_endpoint.py`,
   in the already-`__init__`'d `tests/core/api/` package) so it is actually collected and
   runs. Test contents are byte-for-byte the brief's code (only the unused `asyncio` import
   from the brief snippet was omitted — it was never used and would have failed ruff F401).
2. **Commit prefix.** Brief Step 7 used `feat(api): ...`; the Task-2 constraints in my
   instructions require `feat(web): ...`. Followed the constraint → commit message is
   `feat(web): add resilient WebSocket ConnectionManager for realtime bridge`.
3. **Staging.** Brief Step 7 used `git add -A`. The worktree already had 30+ unrelated
   pre-existing modified/deleted files from this session. To keep the commit surgical I
   staged ONLY my two new paths explicitly instead of `-A`.

## Verification
`SPID_JWT_SECRET=test-secret uv run pytest tests/core/api/test_ws_realtime.py -q --tb=short -p no:cacheprovider`
→ `3 passed in 0.02s`. Did not run the full suite (Py3.14 aiosqlite SIGABRT, per task guidance).

## Commit
- `631519c` feat(web): add resilient WebSocket ConnectionManager for realtime bridge
  (3 files, +114).

## Concerns
- `asyncio.Lock()` is created in `__init__` without a running loop; this is fine in
  Python 3.10+ (no implicit loop binding at construction) and the tests confirm it works
  under the test event loop. The ConnectionManager must be instantiated/used within an
  asyncio context (it will be, since Task 4 owns it inside the FastAPI app loop).
- Broadcast sends sequentially (await per socket). Adequate for Task 2's contract; if
  fan-out latency becomes an issue with many clients, Task 4 could switch to
  `asyncio.gather(..., return_exceptions=True)`. Left as-is to stay minimal and exactly
  match the brief's impl.
