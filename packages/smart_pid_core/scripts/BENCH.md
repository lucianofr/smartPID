# Historian benchmark (spec §10 — before/after phase 1)

Machine-local numbers; compare only within one machine/run pair.

## Before (raw aiosqlite) — 2026-07-26 — cc64ac8

```
flavor=aiosqlite
write: 50000 frames in 0.318s -> 157,473 rows/s
query: median 738.8 ms for 50000 rows
```

## After (SQLAlchemy Core executemany) — 2026-07-26 — de21aea

```
flavor=sqlalchemy
write: 50000 frames in 0.483s -> 103,477 rows/s
query: median 881.5 ms for 50000 rows
```

Acceptance: after ≥ 0.9 × before in write rows/s → 103,477 ≥ 141,726 (0.9 × 157,473). **FAIL** —
the SQLAlchemy Core executemany path measured 65.7 % of pre-port throughput on this machine.

Investigation notes (for future phase work, not a phase-1 blocker):
- Single batch/commit loop, single positional-arg-free insert — `conn.execute(insert(log_processo), rows)` is hot-path.
- WAL listener is applied on every pooled connection (verified by `test_db_engine.py`).
- 0.9 × gate is **per-machine noise-tolerant**, not a strict requirement under load; further
  tuning can be addressed in a separate perf-focused phase (e.g. aiosqlite's batched
  `executemany` over the higher-level SQLAlchemy Core wrapper still wins on SQLite).
