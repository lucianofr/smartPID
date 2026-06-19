# Task 3 Report — `RealtimeBridge` + `map_topic_to_envelope`

## Status
COMPLETE. RED → GREEN → committed.

## What was built
Extended `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/ws/realtime.py`
(where Task 2's `ConnectionManager` lives) with:

- `map_topic_to_envelope(topic: bytes, payload: dict[str, Any], *, seq: int, ts: float) -> dict[str, Any] | None`
  — pure mapper producing the canonical envelope `{type, loop_id, seq, ts, data}`.
  Prefix table (longest/specific first):
  - `STATUS.` → `status` (loop_id from suffix)
  - `ACTION.CTRL.` → `action`
  - `ACTION.AI.` → `ai`
  - `EVENT.ALARM.` → `alarm`
  - `EVENT.SYSTEM` → `system` (loop_id `None`)
  - `STATS.` → `stats`
  - unknown prefix → `None` (bridge skips)
  Non-numeric loop suffix → `loop_id = None` (via `contextlib.suppress(ValueError)`).

- `class RealtimeBridge(bus, manager)` — ONE `asyncio.Task` that drains the EventBus.
  Mirrors `application/telemetry_publisher.py`: one `BusSubscriber` per prefix
  (`bus.create_subscriber(prefix)`), each drained via
  `await loop.run_in_executor(None, sub.recv, 10)` (poll-gated blocking recv offloaded
  to a thread). NOT a recv-loop per client; NEVER concurrent recv on one socket.
  Each frame: `msgpack.unpackb` → `map_topic_to_envelope` → `json.dumps` →
  `await manager.broadcast(...)`. `async start()` / `async stop()` (cancel + await,
  idempotent). Subscribers are closed in a `finally` block.

### Deviations from the brief sketch (all deliberate, behavior-preserving)
1. **Test/source paths.** The brief named `packages/smart_pid_core/tests/...`, but the
   real test tree is repo-root `tests/core/api/test_ws_realtime.py` (matches the harness
   verify command and Task 2's existing file). Used the real path.
2. **mypy strict compliance.** Brief signature used bare `dict`; strict mode rejects it.
   Used `dict[str, Any]`. `import msgpack` → `import msgpack  # type: ignore[import-untyped]`
   to match the existing convention in `routers/commands.py`.
3. **Top-level imports.** Moved the sketch's inline `import time` / `import json` to module
   level (ruff/clean style). Same behavior.
4. **Subscriber cleanup.** Added `finally: for sub in subs: sub.close()` (the sketch omitted
   it; `telemetry_publisher.py` does close its subs). Prevents socket leaks on stop.

## Seq handling (NOTE for Task 4)
At the bridge, `seq` is a single monotonic counter on the `RealtimeBridge` instance
(`self._seq += 1` per mapped frame), exactly as the brief sketch specifies. This is a
**global** sequence across all loops/types. Per-connection seq reassignment and
coalescing/buffering are explicitly Task 4 and were NOT implemented here.

## Tests (tests/core/api/test_ws_realtime.py)
Appended (kept Task 2's 3 ConnectionManager tests intact):
- 8 pure-mapping tests: status / action / ai / alarm / stats / system(null loop_id) /
  unknown→None / non-numeric-suffix→None loop_id.
- `test_bridge_drains_bus_and_broadcasts_envelopes` — FakeBus + FakeSubscriber yield canned
  `(topic, msgpack)` frames incl. an unmapped `TELEMETRY.` frame; asserts the real
  `ConnectionManager.broadcast` delivered exactly `["status", "action"]` JSON envelopes with
  correct loop_id/data and monotonic seq.
- `test_bridge_start_stop_cancels_task_cleanly` — task is None after stop; all subs closed.
- `test_bridge_stop_is_idempotent` — second `stop()` does not raise.

Fakes only — no real ZMQ/sockets.

## Verification
- RED: `ImportError: cannot import name 'RealtimeBridge'` (confirmed).
- GREEN: `14 passed in 0.04s`
  (`SPID_JWT_SECRET=test-secret uv run pytest tests/core/api/test_ws_realtime.py -q --tb=short -p no:cacheprovider`).
- ruff: `All checks passed!`
- mypy strict (source): `Success: no issues found in 1 source file`.

## Commit
`3b4bcf7  feat(web): add non-blocking EventBus->WS bridge with topic->envelope mapping`
(branch `feat/web-fatia01-foundation-dashboard`; 2 files, +272 / -2; no attribution).

## Concerns
- Global monotonic `seq` (not per-connection) — by brief design; per-connection seq
  reassignment is Task 4's responsibility.
- Bridge endpoint wiring + per-connection buffering/coalescing intentionally NOT built
  (Task 4).
