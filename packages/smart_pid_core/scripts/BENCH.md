# Historian benchmark (spec §10 — before/after phase 1)

Machine-local numbers; compare only within one machine/run pair.

## Before (raw aiosqlite) — 2026-07-26 — cc64ac8

```
flavor=aiosqlite
write: 50000 frames in 0.318s -> 157,473 rows/s
query: median 738.8 ms for 50000 rows
```

## After (SQLAlchemy Core executemany) — filled by Task 12
