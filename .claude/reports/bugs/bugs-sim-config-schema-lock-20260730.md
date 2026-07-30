# Simulator config: schema drift + write-lock contention

Branch `fix/simulator-registration-and-schema` (worktree `new-hmi-design`). No commits made.
Paths below are relative to `packages/smart_pid_core/src/smart_pid_core/`.

## Defect 1 — `Configuracao_Simulador has no column named pid_enabled`

**Root cause.** The table shipped in three generations (git archaeology on `sqlite_repo.py`):

| Gen | Commit | Columns | Back-filled by `_apply_migrations`? |
|---|---|---|---|
| gen1 | `3dec29c` and earlier | 6, no PID block | — |
| gen2 | `5421327^` | 11 (`+pid_enabled/kp/ti/td/mode`) | **No** |
| gen3 | `5421327` | 17 (`+auto_*`, `pid_sp`) | Yes, those 6 only |

Commit `5421327` added `auto_*`/`pid_sp` to `_DDL` *and* gave them a back-fill, but the `pid_*`
group introduced one generation earlier never got one. `CREATE TABLE IF NOT EXISTS` is a no-op on
an existing table, so a gen1 `.spid` kept its 6-column table forever and the 17-column
`INSERT OR REPLACE` failed. `pid_*` was the orphaned generation. Reproduced (RED) by building a
gen1 file from the historical DDL and opening it with current code:

```
MISSING pid_* : ['pid_enabled','pid_kp','pid_ti','pid_td','pid_mode']
RESULT: save_sim_config FAILED -> table Configuracao_Simulador has no column named pid_enabled
```

After the fix the same script prints all 17 columns and `save_sim_config SUCCEEDED`.

**Approach.** Kept the established pattern — additive `ALTER TABLE ADD COLUMN` in
`_apply_migrations`, run from `_bootstrap` on every open/reopen — with the lists lifted to module
constants beside `_DDL` so the "any column added to `_DDL` must be repeated here" contract sits
where `_DDL` is edited; defaults copied verbatim. Idempotency now comes from `PRAGMA table_info`
(`_add_missing_columns`) rather than `contextlib.suppress(Exception)` per `ALTER`, which also
swallowed real failures — the file already used the `table_info` idiom for `scan_rate_s`/`tss_s`,
so this is that pattern applied consistently. `scan_rate_ms → scan_rate_s` moved to
`_migrate_scan_rate`, ordered **before** the declarative pass, since a declarative `scan_rate_s`
add would otherwise satisfy the conversion's guard and skip the ms→s division.

## Defect 2 — `database is locked` (HTTP 500 on `/simulator/{id}/pid/mode`)

**Diagnosis.** Two connections write one `.spid` under WAL by design (documented in
`db_engine.py`): engine A on the main loop (REST, the 2 s sim flusher, retention) and engine B on
the DB-worker loop (telemetry batches every `flush_interval_s` = 5.0 s). WAL admits one writer;
the loser waits `busy_timeout` then raises. `busy_timeout` was **5000 ms — identical to the flush
interval**, so zero headroom. From the live log (`/tmp/spid-backend.log`, 20.2 h against the
1.08 GB `novoProjeto1.spid`): **300** `sim_persist_flush_failed` events, every one the sim
`INSERT OR REPLACE` on engine A, never the telemetry insert, and zero
checkpoint/export/history/reopen activity — so engine B is the only contender. Which mode it is
matters, since they need different fixes; two probes on a 121 MB WAL db:

| Mode | Mechanism | Measured |
|---|---|---|
| H1 | blocked by a competing write | fails after **2003 ms** at `busy_timeout=2000` — full budget consumed |
| H2 | `SQLITE_BUSY_SNAPSHOT` (read snapshot promoted to write) | fails after **0.0 ms** — busy handler bypassed |

Both print the same `database is locked`, but H2 is immune to a bigger timeout. The discriminator
is timing, and the real data settles it: across all 300 events the **minimum gap between
consecutive failures is exactly 5.0 s**, zero same-second pairs (median 130 s). The flusher
iterates dirty ids sequentially, so instant failures would cluster several ids into one second.
They never do — each failure consumed the entire 5000 ms budget. This is H1.

A larger `busy_timeout` is therefore the correct fix, not a workaround: the two-writer WAL design
is intentional and the transactions are already single-statement and minimal — only the *sizing*
of the budget, against the flush period it must outlast, was wrong. Engine B's batch is not the
long holder: 50-row `executemany` + commit on a 1.5 M-row / 121 MB table ran p50 **0.2 ms**, max
**0.4 ms**; the multi-second holds come from scale (real file ~9x larger, 4.8 MB WAL,
autocheckpointing), so headroom is the answer.

**Fix.** `SQLITE_BUSY_TIMEOUT_MS = 15_000` — 3x the flush interval, deliberately **below**
SQLAlchemy's 30 s pool checkout timeout so one request can't burn the pool wait and the busy wait
back to back. A test pins `busy_timeout >= 3x DBWorker.flush_interval_s`, reading the default off
the constructor signature, so shortening the flush interval later fails loudly. No blanket retry
loop: retrying after the budget is exhausted only adds latency, since sustained contention won't
clear in 100 ms. `persist_sim_config` retries only when the failure returned *fast* (the H2 shape)
and gives up at once when the budget was consumed — worst case ~one `busy_timeout`, not three.

## Defect 3 — the 500 was dishonest (requirement 4)

A simulator mutation applies to the in-memory adapter **first**; this helper only writes it
through, so raising turned "your change is live but won't survive a restart" into "the request
failed" (REST path only — the background flusher already caught everything). `persist_sim_config`
now returns `bool` and logs structured `sim_persist_failed` (`waited_ms`, `busy_budget_exhausted`,
`reason`) instead of propagating; routers ignore the return value, so they stop 500ing unchanged.
**Follow-up for the Backend specialist:** `/simulator/*` responses should carry `persisted: false`
so the operator sees "applied, not saved" — a router/DTO change I left alone per the scope split.

## Audit of the other tables (requirement 2)

Parsed the live `_DDL` (10 tables) and diffed expected vs actual columns against real files,
cross-referencing each gap with migration coverage. `testeInicial.spid` (6 Apr, oldest surviving,
read from a copy): `Controladores` missing 8 (`scan_rate_s`, `tss_s`, `node_id_bkcal_in/out`,
`node_id_kp/ti/td`, `optimization_enabled`) — all covered; `Log_System_Events` absent — created by
`CREATE TABLE IF NOT EXISTS`; `Configuracao_Simulador` missing the 6 `auto_*`/`pid_sp` — all
covered (gen2 file, `pid_*` already present). `novoProjeto1.spid` (active, 1.08 GB): **no drift**.
So **`pid_*` was the only genuine gap** — `Configuracao_Alarmes`, `Log_Processo`,
`Log_Sintonia_IA`, `Log_Auditoria`, `Modelos_IA`, `Log_Alarmes` and `Projeto_Meta` all match on
both files and were left alone. `scan_rate_s`/`tss_s` added declaratively as a safety net.
**Your live files were not modified** — work ran on copies, the active file only opened `mode=ro`.
Neither needs manual migration: `novoProjeto1.spid` is current and `testeInicial.spid`'s gaps are
all covered, so they apply on next open. Older `.spid` files elsewhere now self-heal.

## Adjacent issues found, not fixed (outside scope)

1. **`Log_Processo` retention never runs in practice** — `_retention_cleanup` (`main.py:224`)
   sleeps 24 h *before* its first pass, so a daemon restarted more often never prunes. This is why
   the file reached 1.08 GB, the scale that made writes slow enough to exhaust the budget. That
   `DELETE` held the write lock **2.87 s** for 1.18 M rows on a 121 MB table (~25-30 s at 1 GB,
   past even the new 15 s). Prune on startup, batch with `LIMIT`.
2. **`historian.cleanup_older_than` is dead code** — no production caller.
3. **Retention compares mismatched formats** — `isoformat()` rows vs `datetime('now','-7 days')`:
   right on the date prefix, wrong at the boundary.
4. **A lock error in `DBWorker._flush()` kills the worker thread** — `_run_async`'s `try` wraps
   only `recv` and catches `zmq.ZMQError`, so an `OperationalError` escapes and telemetry stops.
5. **4 raw `aiosqlite.connect()` sites bypass the PRAGMA listener**, so get no `busy_timeout`
   (`main.py:136`, `project_service.py:99,203`, `user_repo.py:52`); none causes this bug, but
   `_migrate_users_if_needed` writes the active `.spid` without a busy budget.

## Files changed

| File | Change |
|---|---|
| `adapters/outbound/sqlite_repo.py` | `_SIM_ADDED_COLUMNS` (+5 `pid_*`), `_CONTROLADORES_ADDED_COLUMNS`, `_add_missing_columns`/`_table_columns`/`_migrate_scan_rate`, typed `driver` params, dropped `contextlib` |
| `adapters/outbound/db_engine.py` | `SQLITE_BUSY_TIMEOUT_MS = 15_000` (was inline `5000`) + rationale |
| `adapters/inbound/sim_persistence.py` | returns `bool`, conditional retry, structured log, no longer raises |
| `tests/core/unit/test_sqlite_repo_sim_migration.py` | **new** — 15 tests |
| `tests/core/unit/test_db_engine.py` | assert the constant, not a literal `5000` |

## Tests added — `tests/core/unit/test_sqlite_repo_sim_migration.py` (15)

**Migration (6):** gen1/gen2 fixtures from verbatim historical DDL — all INSERT columns present
after `initialize()`; `save_sim_config` succeeds (the exact failing call); legacy rows survive with
DDL defaults; re-open of a migrated file is a no-op. **Concurrency (3):** the `busy_timeout >= 3x`
flush-interval invariant; a writer blocked by a competing `BEGIN IMMEDIATE` **waits then succeeds**
instead of raising; 25 rounds of interleaved engine-A sim writes and engine-B 50-row batches yield
zero `database is locked`. **Failure policy (6):** returns `False` instead of raising; recovers
from a transient lock; exhausted budget not retried; schema error not retried; unknown controller
writes nothing.

## Verification

```
$ uv run pytest tests/core -q                       -> 1 failed, 1339 passed in 183.61s
$ uv run pytest test_sqlite_repo_sim_migration.py test_db_engine.py \
      test_sqlite_repo_new_tables.py -q             -> 32 passed in 1.96s
$ uv run --with ruff ruff check <5 changed files>   -> All checks passed!
$ uv run --with mypy mypy db_engine.py sim_persistence.py
Success: no issues found in 2 source files
```

The single failure is **environmental, not mine**: `test_api_simulator.py::TestOPCUAEndpoints::
test_opcua_start_stop` dies at `OSError: [Errno 98] address already in use` binding
`0.0.0.0:4849`, a port held by the live daemon (`pid=3898314`) another agent started — it fails at
socket bind, before any DB access. Repo-wide `ruff check .` (49 errors) and `mypy packages/` (562
in 64 files) are the pre-existing baseline in other agents' files; the two pre-existing
`sqlite_repo.py` findings (`I001`, `SIM118`) were confirmed at `HEAD` and cleared, since I own it.

---

## Follow-up: retention first pass and DBWorker survival

Both previously-deferred items are now fixed. They were the root enabler of the lock
contention, so a 15 s budget alone was a deferral: a ~25-30 s unbounded `DELETE` blows
straight through it.

### D1 — `_retention_cleanup` never ran on a restarted daemon

**Root cause.** `await asyncio.sleep(interval_hours * 3600)` was the *first* statement in the
loop, so a daemon restarted more often than daily pruned nothing, ever. `Log_Processo` grew
without bound — that is the 1.08 GB file.

**Fix (`main.py`).** Pass first, sleep after. Three parts:

- **Chunked deletes.** `_prune_table()` issues
  `DELETE ... WHERE rowid IN (SELECT rowid ... WHERE timestamp <= :cutoff LIMIT :batch)`,
  committing per batch and pausing `_RETENTION_BATCH_PAUSE_S` (50 ms) between them so the WAL
  write lock is actually released rather than held for the whole backlog.
- **Batch size from measurement**, not a guess. On a 1.5 M-row / 142 MB `Log_Processo`:
  5 000 rows = **72 ms** lock hold, 20 000 = **279 ms**, 50 000 = **361 ms**. Chose
  **5 000** — an order of magnitude below the 2 s simulator-flush cadence even on a
  multi-hundred-MB file. Total work is unchanged; it is simply no longer one long hold.
- **Timestamp comparison fixed** (issue 3 from the original report, same function). All four
  tables store `datetime.isoformat()`; cutoffs are now built the same way instead of via
  `datetime('now', ...)`, whose space separator sorts below the stored `T` and left rows just
  past the cutoff unprunable forever.

**Readiness: background, not gating — deliberate.** The task is already
`asyncio.create_task(...)` before `daemon_ready`, and I kept it that way. On a large backlog
the first pass is minutes of wall clock; blocking the API on it would trade an oversized file
for an operator staring at a dead UI, which is the worse bug. Chunking is what makes the
non-gating choice safe — each statement's lock hold is tens of milliseconds, so the pass is
invisible to the PID and telemetry paths while it runs. Measured below.

### D2 — a failed flush killed the DBWorker thread

**Root cause.** `_run_async`'s inner `try` wrapped only the `recv` block and caught
`zmq.ZMQError`. An `OperationalError` from `await self._flush()` escaped the `while`, unwound
the thread, and telemetry persistence stopped with no signal. The RED run reproduced exactly
that (`db_worker.py:96 in _run_async` → thread death). The `finally` was also unsafe: it
re-called the raising `_flush()`, so `engine.dispose()` could be skipped and engine B leaked.

**Fix (`db_worker.py`).** New `_safe_flush()` wraps both buffers, never raises, increments a
public `flush_failures` counter and emits a structured `historian_flush_failed`
(`buffer`, `dropped_rows`, `total_failures`, `reason`). Because it cannot raise,
`engine.dispose()` in the `finally` now always runs.

**"Degrade" here means drop the batch**, chosen over retry or backpressure because:

- `_buffer` is already a bounded `deque(maxlen=10_000)` that sheds oldest frames under
  pressure — shedding on a failed write honours the contract the buffer already has.
- Re-queueing would head-of-line block behind a persistently locked file and evict *newer*
  frames to preserve *older* ones — a worse historian than the gap it avoids.
- There is no backpressure path to the publisher (ZMQ SUB drops subscriber-side), so the only
  real alternatives are drop or unbounded memory growth.

The live HMI telemetry path (ZMQ PUB) is untouched; only the historian record has a hole, and
the counter plus the log make that hole observable instead of silent.

### Answering the question about the 1.08 GB file

Measured on a purpose-built **1.06 GB / 11 M-row** `.spid` (same shape as `novoProjeto1.spid`,
all rows older than the 7-day window — the worst case), with a writer on a 2 s cadence standing
in for the simulator flusher:

| | Result |
|---|---|
| `initialize()` (DDL + migrations) on 1.06 GB | **373 ms** |
| First retention pass, 11 M rows | **155 s**, fully in background |
| Concurrent 2 s writer during the pass | **78 ok, 0 failed**, max wait **184 ms**, median **1 ms** |
| File size after pruning 11 M rows | **1.06 GB** — unchanged |

**Confirmed: no stall an operator would read as a hang.** Opening costs 373 ms because the
migration is metadata-only — `CREATE TABLE IF NOT EXISTS` and `PRAGMA table_info` do not scan
data, and `novoProjeto1.spid` has no drift so zero `ALTER`s run. During the 155 s background
pass the worst a concurrent write ever waited was 184 ms, with a median of 1 ms and **zero**
lock failures.

**One documented one-time cost, stated plainly:** the file does **not** shrink. SQLite returns
the freed pages to its internal freelist, not to the OS, so `novoProjeto1.spid` will stay at
~1.08 GB and then grow much more slowly as the freelist is reused. Reclaiming the space needs
`VACUUM`, which rewrites the whole database under an exclusive lock — minutes of hard stall on
a 1 GB file — so I did **not** wire it in. If you want the space back, it should be an explicit
operator action on a stopped daemon, not something the daemon does at startup.

### Verification

```
$ uv run pytest tests/core/integration/test_retention_and_worker_survival.py -q
   before fix: 5 failed in 47.32s     after fix: 5 passed in 1.64s
$ uv run pytest tests/core/integration -q --deselect <opcua_start_stop>
   544 passed, 1 deselected in 144.80s      # includes every DBWorker test
$ uv run pytest tests/core/unit/test_db_engine.py test_sqlite_repo_sim_migration.py \
      test_sqlite_repo_new_tables.py test_db_models.py test_config.py \
      test_loop_manager_commands.py -q
   52 passed in 2.77s                       # full blast radius of these changes
$ uv run --with ruff ruff check <8 files owned this session>   -> All checks passed!
$ uv run --with mypy mypy packages/   -> 560 errors (baseline 562; 2 fewer, none new)
```

All 5 new tests were confirmed failing on pristine code first. `test_opcua_start_stop` remains
**deselected**: it fails environmentally on `0.0.0.0:4849`, held by the live daemon another
agent started, and is unrelated to these changes.

**Full backend suite is green**, run in slices because the host was contended (other agents:
an 8 GB process plus several `bun` workers, load average 4-6) and a single-process run kept
being killed mid-way. Slices sum exactly to the 1352 tests `--collect-only` reports:

| Slice | Result |
|---|---|
| `tests/core/unit` | **773 passed** in 40.60s |
| `tests/core/integration` | **544 passed, 1 deselected** in 144.80s |
| `tests/core/api` | **34 passed** in 0.69s |
| **Total** | **1351 passed + 1 deselected = 1352 collected** |

For the record: mid-session I saw the unit slice abort in an EventBus fixture teardown and
reported it as an unverified risk. It was host contention, not a regression — the same slice
passes cleanly (773/773) once the machine freed up, and nothing in D1/D2 touches `EventBus` or
`LoopManager`.

### Files changed in this follow-up

| File | Change |
|---|---|
| `main.py` | `_prune_table()`, `_RETENTION_BATCH_ROWS`/`_PAUSE_S`/`_POLICY`, `_retention_cleanup` inverted to pass-then-sleep with ISO cutoffs, typed `session_factory` |
| `application/workers/db_worker.py` | `_safe_flush()`, `flush_failures` counter, structlog logger, non-raising `finally` |
| `tests/core/integration/test_retention_and_worker_survival.py` | **new** — 5 tests |
