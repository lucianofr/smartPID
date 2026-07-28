# Phase 1 — SQLAlchemy 2.0 Async Data Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Port every backend data-access path from raw `aiosqlite` to SQLAlchemy 2.0 async (spec §10) — three single-connection engines, PRAGMA listeners, session-per-method repositories, Core-executemany historian, and a checkpoint-dispose-recreate `.spid` reopen lifecycle — with zero schema change and zero REST/WS surface change.

**Architecture:** A new engine factory (`adapters/outbound/db_engine.py`) builds identical single-connection async engines; three instances exist at runtime: **A** (active `.spid`, main loop, owned by `SQLiteRepository`), **B** (same `.spid`, DB-worker private loop, owned by `DBWorker._run_async`), **C** (`users.db`, main loop, owned by `UserRepository`). Repositories stop borrowing a shared connection (`repo.db`) and instead receive an injected `async_sessionmaker` whose identity is stable across `reopen()` (it is re-bound in place via `configure(bind=...)`), which also fixes `SystemEventRepository`'s latent stale-connection bug. The DDL bootstrap and `_apply_migrations()` add-column back-fill keep running verbatim on every open/reopen through the raw driver connection.

**Tech Stack:** Python 3.13 · uv workspace · SQLAlchemy 2.0 async (`sqlite+aiosqlite` dialect) · aiosqlite ≥ 0.20 (stays: it is the SQLAlchemy SQLite async driver AND remains for `.spid` fixture authoring / the `list_projects` probe) · pytest + pytest-asyncio (`asyncio_mode = "auto"`).

## Global Constraints

- Working directory for ALL commands: the worktree root (the directory containing `packages/` and `tests/`). Backend tests: `uv run pytest tests/core/... -q`. All file paths below are worktree-root-relative.
- **No schema change.** Tables, columns, DDL text, and the idempotent `_apply_migrations()` add-column back-fill are preserved verbatim (spec §3, §10).
- **PRAGMAs per engine** via a sync `connect` event listener: `journal_mode=WAL`, `busy_timeout=5000`, `foreign_keys` **explicitly OFF** — SQLite defaults OFF, every `ON DELETE CASCADE` in the DDL is deliberately inert; enabling FKs is a forbidden behavior change (spec §10).
- **Pooling:** every engine `AsyncAdaptedQueuePool` with `pool_size=1, max_overflow=0` — exactly one connection per engine, preserving today's single-connection serialization per scope (spec §10). `NullPool` and `StaticPool` are rejected (spec §10).
- **Historian hot path pinned to Core:** `conn.execute(insert(log_processo), rows)` — the executemany fast path — one commit per batch. `session.add_all()` is **forbidden** on this path (spec §10).
- **Session-per-method with immediate commit** for every write (behavior-preserving transaction scope). Row access via `.mappings()`; `lastrowid`/`rowcount` stay on Core `CursorResult` (spec §10).
- **Phase 0 already landed** when this plan executes: dependencies are `require_user`/`require_admin`, roles are lowercase `admin`|`user`, `main.py` contains `_migrate_user_roles(user_repo)` (role-value UPDATE on the raw connection) and seeds `admin` via `user_repo.create("admin", admin_hash, UserRole.ADMIN.value)`, `_USERS_DDL` default is `'user'`, and a `routers/users.py` exists. **Line numbers for `main.py` cited below are anchors from the pre-phase-0 tree — always re-locate by the quoted code, not the number.**
- **No frontend change. No role-logic change.** This phase touches only `packages/smart_pid_core` (src + pyproject) and `tests/`.
- Commits: conventional style matching repo history — `feat(core): ...`, `refactor(core): ...`, `test: ...`, `chore(core): ...`.
- Python: `from __future__ import annotations` at top of every module (existing convention), ruff line length 100.

---

## File structure

| File | Responsibility |
|---|---|
| `packages/smart_pid_core/src/smart_pid_core/adapters/outbound/db_engine.py` | **New.** Engine factory + PRAGMA listener. Documents the A/B/C topology. |
| `packages/smart_pid_core/src/smart_pid_core/adapters/outbound/db_models.py` | **New.** Declarative models mapping the EXISTING tables verbatim (two metadata scopes: `.spid` vs `users.db`). Never emits DDL. |
| `packages/smart_pid_core/src/smart_pid_core/adapters/outbound/sqlite_repo.py` | Owns engine A + the `.spid` session factory + bootstrap/back-fill + `checkpoint()`/`reopen()`/`close()`. CRUD via sessions. `_DDL` string stays here unchanged. |
| `packages/smart_pid_core/src/smart_pid_core/adapters/outbound/historian.py` | Session-factory injected; Core executemany hot path. |
| `packages/smart_pid_core/src/smart_pid_core/adapters/outbound/{alarm_repo,audit_repo,ai_repo,system_event_repo,user_repo}.py` | Session-factory injected (user_repo owns engine C). |
| `packages/smart_pid_core/src/smart_pid_core/application/workers/db_worker.py` | Creates/disposes engine B on its private loop. |
| `packages/smart_pid_core/src/smart_pid_core/application/project_service.py` | Drains the DB worker around `reopen()`; `prepare_download()` checkpoints before streaming. |
| `packages/smart_pid_core/src/smart_pid_core/main.py` | All eight `repo.db`-borrow call sites replaced (table below). |
| `packages/smart_pid_core/scripts/bench_historian.py` + `BENCH.md` | **New.** Before/after historian throughput benchmark. |
| `tests/core/unit/test_db_engine.py`, `tests/core/unit/test_db_models.py`, `tests/core/integration/test_engine_lifecycle.py` | **New** test files. |

### The eight `repo.db` borrow sites and their replacements (normative for this plan)

| # | Site (current anchor) | Replacement |
|---|---|---|
| 1 | `historian = SQLiteHistorian(repo)` — `main.py:239` (lazy `_db` property borrow) | `SQLiteHistorian(repo.session_factory)` (Task 6) |
| 2 | `ai_repo = AIRepository(repo)` — `main.py:351` | `AIRepository(repo.session_factory)` (Task 7) |
| 3 | `alarm_repo = AlarmRepository(repo)` — `main.py:358` | `AlarmRepository(repo.session_factory)` (Task 7) |
| 4 | `audit_repo = AuditRepository(repo)` — `main.py:359` | `AuditRepository(repo.session_factory)` (Task 7) |
| 5 | `alarm_configs = await _load_alarm_configs(repo.db)` — `main.py:362` | `await _load_alarm_configs(repo.session_factory)` + ported body (Task 8) |
| 6 | `system_event_repo = SystemEventRepository(repo.db)` — `main.py:385` (eager capture — the stale-connection bug) | `SystemEventRepository(repo.session_factory)`; constructor signature changes (Task 5) |
| 7 | `cleanup_task = asyncio.create_task(_retention_cleanup(repo.db))` — `main.py:504` | `_retention_cleanup(repo.session_factory)` + ported body (Task 8) |
| 8 | `await user_repo.db.execute(...)` / `await user_repo.db.commit()` — `main.py:148–153` inside `_migrate_users_if_needed` (plus phase-0's `_migrate_user_roles`, same pattern) | engine-C sessions via `user_repo.session_factory` (Task 9); `UserRepository.db` property deleted |

Related wiring changes that are not `.db` borrows: `DBWorker(bus=bus, historian=historian)` → `DBWorker(bus=bus, repo=repo)` (`main.py:396`, Task 6) and `ProjectService(...)` gains `db_worker=db_worker` (`main.py:445–452`, Task 11).

### Transition strategy (why the tasks stay green)

`SQLiteRepository.db` is the single coupling point for six modules and ~18 test files; porting everything in one commit is unreviewable. Tasks 4–9 therefore run **dual-stack**: Task 4 gives `SQLiteRepository` its engine + session factory while *temporarily keeping* the legacy `aiosqlite` connection alive for not-yet-ported borrowers. Each subsequent task moves one borrower onto sessions. **Task 10 deletes the legacy connection entirely** — no shim survives the phase. Every task leaves `uv run pytest tests/core -q` green.

---

### Task 1: Historian throughput baseline (pre-port benchmark)

**Files:**
- Create: `packages/smart_pid_core/scripts/bench_historian.py`
- Create: `packages/smart_pid_core/scripts/BENCH.md`

**Interfaces:**
- Consumes: current (raw-aiosqlite) `SQLiteRepository`, `SQLiteHistorian`.
- Produces: `bench_historian.py` runnable at ANY point of the phase (it feature-detects the historian constructor), and `BENCH.md` holding the "before" numbers that Task 12 compares against.

- [ ] **Step 1: Write the benchmark script**

```python
"""Historian write-throughput benchmark — spec §10 "benchmark before/after phase 1".

Run from the worktree root:
    uv run python packages/smart_pid_core/scripts/bench_historian.py

Works both before the SQLAlchemy port (SQLiteHistorian(repo)) and after
(SQLiteHistorian(repo.session_factory)) so the same script produces the
before/after pair recorded in BENCH.md.
"""
from __future__ import annotations

import asyncio
import statistics
import tempfile
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

from smart_pid_core.adapters.outbound.historian import SQLiteHistorian
from smart_pid_core.adapters.outbound.sqlite_repo import SQLiteRepository
from smart_pid_domain.models.signal import FFSignal
from smart_pid_domain.models.telemetry import TelemetryFrame

N_FRAMES = 50_000
BATCH_SIZE = 500  # matches DBWorker default batch_size
QUERY_RUNS = 5


def _make_frames(n: int) -> list[TelemetryFrame]:
    base = datetime.now(tz=UTC)
    return [
        TelemetryFrame(
            controller_id=1,
            pv=FFSignal.good(50.0 + (i % 100) * 0.1, base),
            sp=FFSignal.good(50.0, base),
            co=FFSignal.good(25.0, base),
            bkcal_in=FFSignal.good(0.0, base),
            integral_val=1.0,
            timestamp=base + timedelta(milliseconds=i),
        )
        for i in range(n)
    ]


async def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "bench.spid"
        repo = SQLiteRepository(db_path)
        await repo.initialize()
        session_factory = getattr(repo, "session_factory", None)
        if session_factory is not None:
            historian = SQLiteHistorian(session_factory)
            flavor = "sqlalchemy"
        else:
            historian = SQLiteHistorian(repo)  # pre-port constructor
            flavor = "aiosqlite"

        frames = _make_frames(N_FRAMES)
        t0 = time.perf_counter()
        for i in range(0, N_FRAMES, BATCH_SIZE):
            await historian.write_batch(frames[i : i + BATCH_SIZE])
        write_s = time.perf_counter() - t0

        start = frames[0].timestamp - timedelta(seconds=1)
        end = frames[-1].timestamp + timedelta(seconds=1)
        query_times: list[float] = []
        for _ in range(QUERY_RUNS):
            t0 = time.perf_counter()
            rows = await historian.query(1, start, end)
            query_times.append(time.perf_counter() - t0)
        assert len(rows) == N_FRAMES, f"expected {N_FRAMES} rows, got {len(rows)}"

        await repo.close()
        print(f"flavor={flavor}")
        print(f"write: {N_FRAMES} frames in {write_s:.3f}s -> {N_FRAMES / write_s:,.0f} rows/s")
        print(f"query: median {statistics.median(query_times) * 1000:.1f} ms for {N_FRAMES} rows")


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: Run the baseline**

Run: `uv run python packages/smart_pid_core/scripts/bench_historian.py`
Expected: three lines starting `flavor=aiosqlite`, then `write: 50000 frames in ...s -> ... rows/s`, then `query: median ... ms for 50000 rows`. (`flavor=aiosqlite` proves the pre-port path is being measured.)

- [ ] **Step 3: Record the baseline in BENCH.md**

Create `packages/smart_pid_core/scripts/BENCH.md` with (paste your real output):

```markdown
# Historian benchmark (spec §10 — before/after phase 1)

Machine-local numbers; compare only within one machine/run pair.

## Before (raw aiosqlite) — <date> — <git rev>

<paste the three output lines here>

## After (SQLAlchemy Core executemany) — filled by Task 12
```

- [ ] **Step 4: Commit**

```bash
git add packages/smart_pid_core/scripts/bench_historian.py packages/smart_pid_core/scripts/BENCH.md
git commit -m "chore(core): historian throughput benchmark + pre-port baseline"
```

---

### Task 2: Dependency + engine factory `db_engine.py`

**Files:**
- Modify: `packages/smart_pid_core/pyproject.toml` (dependencies list, currently lines 10–25)
- Create: `packages/smart_pid_core/src/smart_pid_core/adapters/outbound/db_engine.py`
- Test: `tests/core/unit/test_db_engine.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `create_sqlite_engine(db_path: Path) -> AsyncEngine` — THE factory used for all three engines (A: `SQLiteRepository.initialize`, B: `DBWorker._run_async`, C: `UserRepository.initialize`). Also `_apply_sqlite_pragmas(dbapi_connection, connection_record) -> None` (module-private listener, tested through the engine).

- [ ] **Step 1: Add the dependency**

In `packages/smart_pid_core/pyproject.toml`, inside `dependencies = [...]`, add one line after `"aiosqlite>=0.20",`:

```toml
    "sqlalchemy[asyncio]>=2.0",
```

(`[asyncio]` guarantees greenlet. `aiosqlite` stays — it is the async driver and remains for fixture authoring / the `list_projects` probe.)

Run: `uv sync`
Expected: resolves and installs `sqlalchemy` ≥ 2.0 with no conflicts.

- [ ] **Step 2: Write the failing test**

Create `tests/core/unit/test_db_engine.py`:

```python
"""Tests for the spec §10 engine factory: pool shape + PRAGMA listener."""
from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.pool import AsyncAdaptedQueuePool

from smart_pid_core.adapters.outbound.db_engine import create_sqlite_engine


class TestCreateSqliteEngine:
    @pytest.mark.asyncio
    async def test_pragmas_applied_on_connect(self, tmp_path) -> None:
        engine = create_sqlite_engine(tmp_path / "t.spid")
        async with engine.connect() as conn:
            journal = (await conn.execute(text("PRAGMA journal_mode"))).scalar()
            busy = (await conn.execute(text("PRAGMA busy_timeout"))).scalar()
            fks = (await conn.execute(text("PRAGMA foreign_keys"))).scalar()
        assert journal == "wal"
        assert busy == 5000
        assert fks == 0  # explicitly OFF — ON DELETE CASCADE must stay inert
        await engine.dispose()

    @pytest.mark.asyncio
    async def test_single_connection_pool(self, tmp_path) -> None:
        engine = create_sqlite_engine(tmp_path / "t.spid")
        assert isinstance(engine.pool, AsyncAdaptedQueuePool)
        assert engine.pool.size() == 1
        # pool_size=1/max_overflow=0 => sequential checkouts reuse ONE driver connection
        async with engine.connect() as c1:
            raw1 = (await c1.get_raw_connection()).driver_connection
        async with engine.connect() as c2:
            raw2 = (await c2.get_raw_connection()).driver_connection
        assert raw1 is raw2
        await engine.dispose()
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/core/unit/test_db_engine.py -q`
Expected: FAIL/ERROR with `ModuleNotFoundError: No module named 'smart_pid_core.adapters.outbound.db_engine'`

- [ ] **Step 4: Write the engine factory**

Create `packages/smart_pid_core/src/smart_pid_core/adapters/outbound/db_engine.py`:

```python
"""SQLAlchemy async engine factory — spec §10 three-engine topology.

Engine instances built by this factory (who creates which, on which loop):

- **Engine A** — active ``.spid`` file, MAIN asyncio loop. Created (and
  re-created on ``reopen()``) by ``SQLiteRepository.initialize()``. Serves
  every repository and the REST API.
- **Engine B** — same ``.spid`` file, DB-WORKER private loop. Created inside
  ``DBWorker._run_async()`` on the worker's own thread + event loop and
  disposed there. ``AsyncEngine`` is loop-affine: its pooled connections are
  bound to the loop that created them, so the worker cannot share engine A.
- **Engine C** — ``users.db``, main loop. Created by
  ``UserRepository.initialize()``. Never touched by project switching.

Every engine holds exactly one pooled connection (``AsyncAdaptedQueuePool``,
``pool_size=1, max_overflow=0``), preserving the pre-port single-connection
serialization per scope. A sync ``connect`` listener applies the spec-pinned
PRAGMAs: ``journal_mode=WAL``, ``busy_timeout=5000`` (two ``.spid`` writers
now exist under WAL), and ``foreign_keys`` explicitly OFF — the DDL's
``ON DELETE CASCADE`` clauses are deliberately inert today; enabling FKs
would activate cascades and new FK violations, a forbidden behavior change.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import AsyncAdaptedQueuePool

if TYPE_CHECKING:
    from pathlib import Path


def _apply_sqlite_pragmas(dbapi_connection: Any, connection_record: Any) -> None:  # noqa: ARG001
    """Sync ``connect`` listener run for every new pooled connection.

    ``dbapi_connection`` is SQLAlchemy's pep-249 adapter over the aiosqlite
    connection; sync-style cursor calls here drive the async driver
    internally (the documented recipe for asyncio dialects).
    """
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.execute("PRAGMA foreign_keys=OFF")
    cursor.close()


def create_sqlite_engine(db_path: Path) -> AsyncEngine:
    """Create a single-connection async engine for one SQLite file."""
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{db_path}",
        poolclass=AsyncAdaptedQueuePool,
        pool_size=1,
        max_overflow=0,
    )
    event.listen(engine.sync_engine, "connect", _apply_sqlite_pragmas)
    return engine
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/core/unit/test_db_engine.py -q`
Expected: `2 passed`

- [ ] **Step 6: Commit**

```bash
git add packages/smart_pid_core/pyproject.toml uv.lock packages/smart_pid_core/src/smart_pid_core/adapters/outbound/db_engine.py tests/core/unit/test_db_engine.py
git commit -m "feat(core): sqlalchemy dep + single-connection engine factory with PRAGMA listener"
```

---

### Task 3: Declarative models `db_models.py` (verbatim table map)

**Files:**
- Create: `packages/smart_pid_core/src/smart_pid_core/adapters/outbound/db_models.py`
- Test: `tests/core/unit/test_db_models.py`

**Interfaces:**
- Consumes: `SQLiteRepository`/`UserRepository` bootstrap (only in the parity test, to build a reference schema).
- Produces: `SpidBase`, `UsersBase` (separate `DeclarativeBase` per database file), mapped classes `Controladores`, `ConfiguracaoAlarmes`, `LogProcesso`, `LogSintoniaIA`, `LogAuditoria`, `ModelosIA`, `LogAlarmes`, `ProjetoMeta`, `LogSystemEvents`, `ConfiguracaoSimulador`, `Usuarios`, and Core table aliases `controladores`, `configuracao_alarmes`, `log_processo`, `log_sintonia_ia`, `log_auditoria`, `modelos_ia`, `log_alarmes`, `projeto_meta`, `log_system_events`, `configuracao_simulador`, `usuarios` (each `= <Class>.__table__`). Later tasks import `controladores`, `log_processo`.

- [ ] **Step 1: Write the failing parity test**

The test bootstraps real files through the EXISTING raw DDL + back-fill, then asserts every model's column set equals `PRAGMA table_info` exactly. It is the guard that keeps `db_models.py` verbatim forever (it keeps passing after the port, since bootstrap still runs the same DDL).

Create `tests/core/unit/test_db_models.py`:

```python
"""db_models must mirror the bootstrapped schema column-for-column."""
from __future__ import annotations

import aiosqlite  # raw probe — fixture/probing use stays raw per spec §10
import pytest

from smart_pid_core.adapters.outbound.db_models import SpidBase, UsersBase
from smart_pid_core.adapters.outbound.sqlite_repo import SQLiteRepository
from smart_pid_core.adapters.outbound.user_repo import UserRepository


class TestModelSchemaParity:
    @pytest.mark.asyncio
    async def test_spid_models_match_bootstrapped_schema(self, tmp_path) -> None:
        db_path = tmp_path / "t.spid"
        repo = SQLiteRepository(db_path)
        await repo.initialize()  # runs _DDL + _apply_migrations
        await repo.close()
        async with aiosqlite.connect(db_path) as db:
            for table in SpidBase.metadata.sorted_tables:
                async with db.execute(f"PRAGMA table_info({table.name})") as cur:
                    db_cols = {r[1] for r in await cur.fetchall()}
                model_cols = {c.name for c in table.columns}
                assert db_cols, f"table {table.name} missing from bootstrap"
                assert model_cols == db_cols, (
                    f"{table.name} drift: only-in-model={model_cols - db_cols} "
                    f"only-in-db={db_cols - model_cols}"
                )

    @pytest.mark.asyncio
    async def test_users_model_matches_bootstrapped_schema(self, tmp_path) -> None:
        db_path = tmp_path / "users.db"
        urepo = UserRepository(db_path)
        await urepo.initialize()
        await urepo.close()
        async with aiosqlite.connect(db_path) as db:
            async with db.execute("PRAGMA table_info(Usuarios)") as cur:
                db_cols = {r[1] for r in await cur.fetchall()}
        table = UsersBase.metadata.tables["Usuarios"]
        assert {c.name for c in table.columns} == db_cols

    def test_expected_table_names(self) -> None:
        assert set(SpidBase.metadata.tables) == {
            "Controladores", "Configuracao_Alarmes", "Log_Processo",
            "Log_Sintonia_IA", "Log_Auditoria", "Modelos_IA", "Log_Alarmes",
            "Projeto_Meta", "Log_System_Events", "Configuracao_Simulador",
        }
        assert set(UsersBase.metadata.tables) == {"Usuarios"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/unit/test_db_models.py -q`
Expected: FAIL/ERROR with `ModuleNotFoundError: No module named 'smart_pid_core.adapters.outbound.db_models'`

- [ ] **Step 3: Write the models**

Create `packages/smart_pid_core/src/smart_pid_core/adapters/outbound/db_models.py`. Rules encoded here: attribute name == column name (no aliasing); DDL `NOT NULL` → non-Optional `Mapped[...]`, nullable → `| None`; `INTEGER`→`int`, `REAL`→`float`, `TEXT`→`str`; **no** `ForeignKey`/`relationship()`/`server_default` — these models NEVER emit DDL (bootstrap owns DDL; the parity test enforces the mapping) and FK behavior is governed solely by the `foreign_keys=OFF` PRAGMA. Migration-added columns (`rl_*`) are included because `_apply_migrations()` guarantees them post-bootstrap.

```python
"""Declarative models mapping the EXISTING SQLite tables verbatim — spec §10.

Two metadata scopes, one per database file:
- ``SpidBase``  — tables inside a ``.spid`` project file (engines A and B).
- ``UsersBase`` — the standalone ``users.db`` (engine C).

These models NEVER create tables. The DDL bootstrap (``_DDL`` +
``_apply_migrations()`` in ``sqlite_repo.py``, ``_USERS_DDL`` in
``user_repo.py``) remains the only source of schema, running on every
open/reopen exactly as before the port. ``tests/core/unit/test_db_models.py``
asserts column-set parity between these models and a bootstrapped file.

No ForeignKey objects and no server defaults on purpose: FK enforcement is
OFF by PRAGMA (cascades stay inert), and INSERT paths either supply values
explicitly or rely on the SQLite-side DDL defaults.
"""
from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class SpidBase(DeclarativeBase):
    """Tables that live inside a .spid project file."""


class UsersBase(DeclarativeBase):
    """Tables that live in the standalone users.db."""


class Controladores(SpidBase):
    __tablename__ = "Controladores"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str]
    descricao: Mapped[str]
    modo_execucao: Mapped[str]
    scan_rate_s: Mapped[float]
    tss_s: Mapped[float]
    # PID params
    kp_manual: Mapped[float]
    ki_inicial: Mapped[float]
    kd_manual: Mapped[float]
    alpha: Mapped[float]
    deadband: Mapped[float]
    # PID structure
    pid_structure: Mapped[str]
    integral_type: Mapped[str]
    # Scale
    pv_min: Mapped[float]
    pv_max: Mapped[float]
    pv_unit: Mapped[str]
    co_min: Mapped[float]
    co_max: Mapped[float]
    co_unit: Mapped[str]
    # Tag bindings
    node_id_pv: Mapped[str]
    node_id_sp: Mapped[str]
    node_id_co: Mapped[str]
    node_id_integral: Mapped[str]
    node_id_bkcal_in: Mapped[str]
    node_id_bkcal_out: Mapped[str]
    node_id_kp: Mapped[str]
    node_id_ti: Mapped[str]
    node_id_td: Mapped[str]
    node_id_mode_target: Mapped[str]
    node_id_mode_actual: Mapped[str]
    mode_int_map: Mapped[str]
    # SP limits
    sp_hi_lim: Mapped[float]
    sp_lo_lim: Mapped[float]
    sp_rate_up: Mapped[float]
    sp_rate_dn: Mapped[float]
    # Output limits
    out_hi_lim: Mapped[float]
    out_lo_lim: Mapped[float]
    # ARW limits
    arw_hi_lim: Mapped[float]
    arw_lo_lim: Mapped[float]
    # Filter
    pv_ftime: Mapped[float]
    sp_ftime: Mapped[float]
    low_cut: Mapped[float]
    # Shed
    shed_opt: Mapped[str]
    shed_time_s: Mapped[float]
    # Modes
    permitted_modes: Mapped[str]
    mode_normal: Mapped[str]
    # Control opts (boolean flags as integers)
    no_out_limits_in_manual: Mapped[int]
    obey_sp_limits_if_cas: Mapped[int]
    track_in_manual: Mapped[int]
    track_enable: Mapped[int]
    direct_acting: Mapped[int]
    sp_track_retained_target: Mapped[int]
    ctrl_sp_pv_track_in_lo_or_iman: Mapped[int]
    sp_pv_track_in_rout: Mapped[int]
    ctrl_sp_pv_track_in_man: Mapped[int]
    use_pv_for_bkcal_out: Mapped[int]
    bypass_enable: Mapped[int]
    # IO opts
    low_cutoff: Mapped[int]
    target_to_man_if_fault: Mapped[int]
    fault_state_to_value: Mapped[int]
    increase_to_close: Mapped[int]
    io_sp_pv_track_in_lo_or_iman: Mapped[int]
    io_sp_pv_track_in_man: Mapped[int]
    # Status opts
    bad_if_limited: Mapped[int]
    use_uncertain_as_good: Mapped[int]
    # Track opt / process type
    track_opt: Mapped[str]
    process_type: Mapped[str]
    # AI config
    ai_engine: Mapped[str]
    objetivo_controle: Mapped[str]
    process_speed: Mapped[str]
    tempo_morto_l: Mapped[float]
    ai_limit_min: Mapped[float]
    ai_limit_max: Mapped[float]
    optimization_enabled: Mapped[int]
    # Timestamps (TEXT, SQLite-side datetime('now') defaults)
    criado_em: Mapped[str]
    atualizado_em: Mapped[str]
    # Columns guaranteed by _apply_migrations() (absent from _DDL on purpose)
    rl_fallback_kp: Mapped[float]
    rl_fallback_kd: Mapped[float]
    rl_learning_rate: Mapped[float]
    rl_train_interval: Mapped[int]


class ConfiguracaoAlarmes(SpidBase):
    __tablename__ = "Configuracao_Alarmes"

    id: Mapped[int] = mapped_column(primary_key=True)
    controlador_id: Mapped[int]
    tipo_alarme: Mapped[str]
    prioridade: Mapped[str]
    limite: Mapped[float]
    habilitado: Mapped[int]
    histerese: Mapped[float]
    delay_on_s: Mapped[float]
    delay_off_s: Mapped[float]
    mensagem: Mapped[str]
    criado_em: Mapped[str]


class LogProcesso(SpidBase):
    __tablename__ = "Log_Processo"

    id: Mapped[int] = mapped_column(primary_key=True)
    controlador_id: Mapped[int]
    timestamp: Mapped[str]
    pv: Mapped[float]
    sp: Mapped[float]
    co: Mapped[float]
    integral_val: Mapped[float]


class LogSintoniaIA(SpidBase):
    __tablename__ = "Log_Sintonia_IA"

    id: Mapped[int] = mapped_column(primary_key=True)
    controlador_id: Mapped[int]
    timestamp: Mapped[str]
    motor: Mapped[str]
    kp_antes: Mapped[float | None]
    ki_antes: Mapped[float | None]
    kd_antes: Mapped[float | None]
    kp_depois: Mapped[float | None]
    ki_depois: Mapped[float | None]
    kd_depois: Mapped[float | None]
    objetivo: Mapped[str | None]
    metrica: Mapped[float | None]
    aprovado: Mapped[int]


class LogAuditoria(SpidBase):
    __tablename__ = "Log_Auditoria"

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int | None]
    username: Mapped[str]
    timestamp: Mapped[str]
    acao: Mapped[str]
    entidade: Mapped[str]
    entidade_id: Mapped[int | None]
    detalhe: Mapped[str]
    ip_origem: Mapped[str]


class ModelosIA(SpidBase):
    __tablename__ = "Modelos_IA"

    id: Mapped[int] = mapped_column(primary_key=True)
    controlador_id: Mapped[int]
    algoritmo: Mapped[str]
    episodios: Mapped[int]
    reward_medio: Mapped[float]
    caminho_modelo: Mapped[str]
    criado_em: Mapped[str]


class LogAlarmes(SpidBase):
    __tablename__ = "Log_Alarmes"

    id: Mapped[int] = mapped_column(primary_key=True)
    controlador_id: Mapped[int]
    timestamp: Mapped[str]
    tipo_alarme: Mapped[str]
    prioridade: Mapped[str]
    valor: Mapped[float | None]
    limite: Mapped[float | None]
    cleared_at: Mapped[str | None]
    reconhecido: Mapped[int]
    reconhecido_por: Mapped[str | None]
    reconhecido_em: Mapped[str | None]


class ProjetoMeta(SpidBase):
    __tablename__ = "Projeto_Meta"

    chave: Mapped[str] = mapped_column(primary_key=True)
    valor: Mapped[str]


class LogSystemEvents(SpidBase):
    __tablename__ = "Log_System_Events"

    id: Mapped[int] = mapped_column(primary_key=True)
    timestamp: Mapped[str]
    source: Mapped[str]
    severity: Mapped[str]
    message: Mapped[str]


class ConfiguracaoSimulador(SpidBase):
    __tablename__ = "Configuracao_Simulador"

    controlador_id: Mapped[int] = mapped_column(primary_key=True)
    preset: Mapped[str]
    gain: Mapped[float]
    tau1: Mapped[float]
    tau2: Mapped[float]
    dead_time: Mapped[float]
    pid_enabled: Mapped[int]
    pid_kp: Mapped[float]
    pid_ti: Mapped[float]
    pid_td: Mapped[float]
    pid_mode: Mapped[int]
    auto_sp_enabled: Mapped[int]
    auto_sp_min_pct: Mapped[float]
    auto_sp_max_pct: Mapped[float]
    auto_dist_enabled: Mapped[int]
    auto_dist_max_pct: Mapped[float]
    pid_sp: Mapped[float]


class Usuarios(UsersBase):
    __tablename__ = "Usuarios"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str]
    senha_hash: Mapped[str]
    perfil: Mapped[str]
    ativo: Mapped[int]
    criado_em: Mapped[str]


# Core table handles for Core-statement call sites (spec §10 pins
# ``insert(log_processo)`` for the historian hot path).
controladores = Controladores.__table__
configuracao_alarmes = ConfiguracaoAlarmes.__table__
log_processo = LogProcesso.__table__
log_sintonia_ia = LogSintoniaIA.__table__
log_auditoria = LogAuditoria.__table__
modelos_ia = ModelosIA.__table__
log_alarmes = LogAlarmes.__table__
projeto_meta = ProjetoMeta.__table__
log_system_events = LogSystemEvents.__table__
configuracao_simulador = ConfiguracaoSimulador.__table__
usuarios = Usuarios.__table__
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/core/unit/test_db_models.py -q`
Expected: `3 passed` (if a parity assertion fails, the diff in the message names the exact drifted column — fix `db_models.py`, never the DDL)

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/adapters/outbound/db_models.py tests/core/unit/test_db_models.py
git commit -m "feat(core): declarative models mapping existing tables verbatim + parity test"
```

---

### Task 4: `SQLiteRepository` → engine A (dual-stack transition)

**Files:**
- Modify: `packages/smart_pid_core/src/smart_pid_core/adapters/outbound/sqlite_repo.py` (whole class body; `_DDL` string lines 32–244 untouched)
- Test (add): `tests/core/integration/test_sqlite_repo.py` (FK-inertness regression tests appended)
- Verify green, no edits expected: `tests/core/integration/test_sqlite_repo.py` existing tests, `tests/core/unit/test_sqlite_repo_new_tables.py`, `tests/core/unit/test_projects_dir_setting.py`

**Interfaces:**
- Consumes: `create_sqlite_engine` (Task 2), `controladores` table (Task 3).
- Produces (used by every later task):
  - `SQLiteRepository.engine: AsyncEngine` (engine A; re-created on reopen)
  - `SQLiteRepository.session_factory: async_sessionmaker[AsyncSession]` — **stable object identity across `reopen()`** (re-bound via `configure(bind=...)`); this is the injectable handed to all repositories
  - `SQLiteRepository.db_path -> Path` (read-only property)
  - `SQLiteRepository.close() -> None` (disposes engine A; during Tasks 4–9 also closes the transitional legacy connection)
  - CRUD/meta/sim-config method signatures **unchanged**: `save`, `get`, `list_all`, `delete`, `set_meta`, `get_meta`, `save_sim_config`, `get_sim_config`, `list_sim_configs`, `reopen`, `_get_table_names`, `_get_journal_mode`
  - TRANSITIONAL, deleted in Task 10: `SQLiteRepository.db` (legacy `aiosqlite.Connection`) still exists so not-yet-ported borrowers keep working.

- [ ] **Step 1: Write the failing FK-inertness regression tests**

Append to `tests/core/integration/test_sqlite_repo.py` (these pin the "cascades stay inert" behavior the PRAGMA protects; they FAIL right now only because `session_factory` does not exist yet — and pass after the port):

```python
class TestForeignKeysStayInert:
    """spec §10: foreign_keys OFF — ON DELETE CASCADE in the DDL must not fire."""

    @pytest.mark.asyncio
    async def test_orphan_child_insert_allowed(self, repo) -> None:
        from sqlalchemy import text

        async with repo.session_factory() as session:
            await session.execute(
                text(
                    "INSERT INTO Configuracao_Alarmes"
                    " (controlador_id, tipo_alarme, prioridade, limite)"
                    " VALUES (:cid, 'HI', 'WARNING', 90.0)"
                ),
                {"cid": 424242},  # no such controller — must NOT raise
            )
            await session.commit()

    @pytest.mark.asyncio
    async def test_delete_controller_does_not_cascade(self, repo) -> None:
        from sqlalchemy import text

        saved = await repo.save(Controller(id=0, name="TIC-900"))
        async with repo.session_factory() as session:
            await session.execute(
                text(
                    "INSERT INTO Configuracao_Alarmes"
                    " (controlador_id, tipo_alarme, prioridade, limite)"
                    " VALUES (:cid, 'HI', 'WARNING', 90.0)"
                ),
                {"cid": saved.id},
            )
            await session.commit()
        await repo.delete(saved.id)
        async with repo.session_factory() as session:
            count = (
                await session.execute(
                    text("SELECT COUNT(*) FROM Configuracao_Alarmes WHERE controlador_id = :cid"),
                    {"cid": saved.id},
                )
            ).scalar()
        assert count == 1  # child row survived — cascade inert, as before the port
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/core/integration/test_sqlite_repo.py -q`
Expected: the two new tests FAIL with `AttributeError: 'SQLiteRepository' object has no attribute 'session_factory'`; all pre-existing tests still pass.

- [ ] **Step 3: Port the class (dual-stack)**

In `sqlite_repo.py`, replace the module header and the class implementation as follows. **Keep byte-identical:** the `_DDL` string, the domain imports (`smart_pid_domain.enums`, `smart_pid_domain.models.controller`), `_controller_to_params()` (body unchanged), `_row_to_controller()` (body unchanged except the parameter type hint), `_sim_row_to_dict()` (body unchanged except hint), and the `save()` dispatcher.

Module header — replace lines 1–8 (docstring through `import aiosqlite`) with:

```python
"""SQLite-backed Controller repository adapter (SQLAlchemy 2.0 async, engine A)."""
from __future__ import annotations

import contextlib
import json
from collections.abc import Mapping  # noqa: TC003
from pathlib import Path

import aiosqlite
from sqlalchemy import func, insert, text, update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from smart_pid_core.adapters.outbound.db_engine import create_sqlite_engine
from smart_pid_core.adapters.outbound.db_models import controladores
```

(the `aiosqlite` import remains while the transitional connection exists; Task 10 removes it.)

Class head + lifecycle (replaces current `__init__`/`initialize`/`_apply_migrations`, lines 250–322):

```python
class SQLiteRepository:
    """SQLite-backed implementation of ControllerRepository.

    Owns engine A (active .spid, main loop) and the .spid session factory.
    The session factory's OBJECT IDENTITY is stable across reopen(): it is
    re-bound in place, so injected copies held by other repositories never
    go stale (this is what fixes the SystemEventRepository bug).
    """

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self.engine: AsyncEngine  # created by initialize()
        self.session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
            expire_on_commit=False,
        )
        # TRANSITIONAL (deleted in Task 10): legacy shared connection still
        # feeds historian/alarm/audit/ai/system-event borrowers until their
        # port tasks land.
        self.db: aiosqlite.Connection

    @property
    def db_path(self) -> Path:
        """Filesystem path of the active .spid file."""
        return self._db_path

    async def initialize(self) -> None:
        """Create engine A, run DDL bootstrap + back-fill (every open/reopen)."""
        self.engine = create_sqlite_engine(self._db_path)
        self.session_factory.configure(bind=self.engine)
        await self._bootstrap()
        # TRANSITIONAL (deleted in Task 10):
        self.db = await aiosqlite.connect(self._db_path)
        self.db.row_factory = aiosqlite.Row
        await self.db.execute("PRAGMA journal_mode=WAL")

    async def _bootstrap(self) -> None:
        """Run CREATE TABLE IF NOT EXISTS + idempotent add-column back-fill.

        Executed through the raw aiosqlite driver connection (executescript
        needs script support), exactly as before the port. Old .spid files
        depend on this running on every open/reopen.
        """
        async with self.engine.connect() as conn:
            raw = await conn.get_raw_connection()
            driver = raw.driver_connection  # the real aiosqlite.Connection
            await driver.executescript(_DDL)
            await self._apply_migrations(driver)
            await driver.commit()

    async def _apply_migrations(self, driver) -> None:  # noqa: ANN001
        """Add columns that may be missing from older databases."""
        new_columns = [
            ("node_id_bkcal_in", "TEXT NOT NULL DEFAULT ''"),
            ("node_id_bkcal_out", "TEXT NOT NULL DEFAULT ''"),
            ("node_id_kp", "TEXT NOT NULL DEFAULT ''"),
            ("node_id_ti", "TEXT NOT NULL DEFAULT ''"),
            ("node_id_td", "TEXT NOT NULL DEFAULT ''"),
        ]
        for col_name, col_def in new_columns:
            with contextlib.suppress(Exception):
                await driver.execute(
                    f"ALTER TABLE Controladores ADD COLUMN {col_name} {col_def}",
                )
        # Configuracao_Simulador: auto SP / auto disturbance columns + pid_sp
        sim_new_columns = [
            ("auto_sp_enabled", "INTEGER NOT NULL DEFAULT 0"),
            ("auto_sp_min_pct", "REAL NOT NULL DEFAULT 30.0"),
            ("auto_sp_max_pct", "REAL NOT NULL DEFAULT 70.0"),
            ("auto_dist_enabled", "INTEGER NOT NULL DEFAULT 0"),
            ("auto_dist_max_pct", "REAL NOT NULL DEFAULT 10.0"),
            ("pid_sp", "REAL NOT NULL DEFAULT 50.0"),
        ]
        for col_name, col_def in sim_new_columns:
            with contextlib.suppress(Exception):
                await driver.execute(
                    f"ALTER TABLE Configuracao_Simulador ADD COLUMN {col_name} {col_def}",
                )

        # AIConfig RL-specific columns + ENABLE_OPTIMIZER master flag
        ai_new_columns = [
            ("rl_fallback_kp", "REAL NOT NULL DEFAULT 0.6"),
            ("rl_fallback_kd", "REAL NOT NULL DEFAULT 0.2"),
            ("rl_learning_rate", "REAL NOT NULL DEFAULT 0.0003"),
            ("rl_train_interval", "INTEGER NOT NULL DEFAULT 32"),
            ("optimization_enabled", "INTEGER NOT NULL DEFAULT 1"),
        ]
        for col_name, col_def in ai_new_columns:
            with contextlib.suppress(Exception):
                await driver.execute(
                    f"ALTER TABLE Controladores ADD COLUMN {col_name} {col_def}",
                )

        # Rename scan_rate_ms → scan_rate_s (convert ms to seconds)
        cursor = await driver.execute("PRAGMA table_info(Controladores)")
        col_names = {r[1] for r in await cursor.fetchall()}
        if "scan_rate_ms" in col_names and "scan_rate_s" not in col_names:
            await driver.execute(
                "ALTER TABLE Controladores ADD COLUMN scan_rate_s REAL NOT NULL DEFAULT 1.0"
            )
            await driver.execute(
                "UPDATE Controladores SET scan_rate_s = scan_rate_ms / 1000.0"
            )

        # Add tss_s column
        if "tss_s" not in col_names:
            with contextlib.suppress(Exception):
                await driver.execute(
                    "ALTER TABLE Controladores ADD COLUMN tss_s REAL NOT NULL DEFAULT 60.0"
                )
```

CRUD (replaces current `save`/`get`/`list_all`/`delete`/`_insert`/`_update`, lines 328–392):

```python
    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    async def save(self, controller: Controller) -> Controller:
        """INSERT (id==0) or UPDATE (id>0). Returns Controller with assigned id."""
        if controller.id == 0:
            return await self._insert(controller)
        await self._update(controller)
        return controller

    async def get(self, controller_id: int) -> Controller:
        """Return Controller or raise KeyError."""
        async with self.session_factory() as session:
            result = await session.execute(
                text("SELECT * FROM Controladores WHERE id = :cid"),
                {"cid": controller_id},
            )
            row = result.mappings().first()
        if row is None:
            raise KeyError(controller_id)
        return self._row_to_controller(row)

    async def list_all(self) -> list[Controller]:
        """Return all controllers."""
        async with self.session_factory() as session:
            result = await session.execute(
                text("SELECT * FROM Controladores ORDER BY id"),
            )
            rows = result.mappings().all()
        return [self._row_to_controller(r) for r in rows]

    async def delete(self, controller_id: int) -> None:
        """Delete controller or raise KeyError."""
        async with self.session_factory() as session:
            found = (
                await session.execute(
                    text("SELECT id FROM Controladores WHERE id = :cid"),
                    {"cid": controller_id},
                )
            ).first()
            if found is None:
                raise KeyError(controller_id)
            await session.execute(
                text("DELETE FROM Controladores WHERE id = :cid"),
                {"cid": controller_id},
            )
            await session.commit()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _insert(self, c: Controller) -> Controller:
        params = self._controller_to_params(c)
        async with self.session_factory() as session:
            result = await session.execute(insert(controladores).values(**params))
            new_id = result.lastrowid
            await session.commit()
        from dataclasses import replace
        return replace(c, id=new_id or 0)

    async def _update(self, c: Controller) -> None:
        params = self._controller_to_params(c)
        async with self.session_factory() as session:
            await session.execute(
                update(controladores)
                .where(controladores.c.id == c.id)
                .values(**params, atualizado_em=func.datetime("now"))
            )
            await session.commit()
```

`_controller_to_params()` — **keep the body exactly as in the current file** (pure dict builder, no DB access). `_row_to_controller()` — keep the body exactly as in the current file, changing only the signature to `def _row_to_controller(self, row: Mapping) -> Controller:` (`RowMapping` supports the same `row["name"]` access as `aiosqlite.Row`).

Projeto_Meta + simulator config (replaces current lines 631–727):

```python
    # ------------------------------------------------------------------
    # Projeto_Meta
    # ------------------------------------------------------------------

    async def set_meta(self, key: str, value: str) -> None:
        """Insert or replace a project metadata key-value pair."""
        async with self.session_factory() as session:
            await session.execute(
                text("INSERT OR REPLACE INTO Projeto_Meta (chave, valor) VALUES (:k, :v)"),
                {"k": key, "v": value},
            )
            await session.commit()

    async def get_meta(self, key: str) -> str | None:
        """Return the value for *key* or ``None`` if missing."""
        async with self.session_factory() as session:
            result = await session.execute(
                text("SELECT valor FROM Projeto_Meta WHERE chave = :k"),
                {"k": key},
            )
            row = result.mappings().first()
        return str(row["valor"]) if row else None

    # ------------------------------------------------------------------
    # Configuracao_Simulador
    # ------------------------------------------------------------------

    async def save_sim_config(
        self,
        controller_id: int,
        preset: str,
        gain: float,
        tau1: float,
        tau2: float,
        dead_time: float,
        pid_enabled: bool = False,
        pid_kp: float = 1.0,
        pid_ti: float = 10.0,
        pid_td: float = 0.0,
        pid_mode: int = 0,
        auto_sp_enabled: bool = False,
        auto_sp_min_pct: float = 30.0,
        auto_sp_max_pct: float = 70.0,
        auto_dist_enabled: bool = False,
        auto_dist_max_pct: float = 10.0,
        pid_sp: float = 50.0,
    ) -> None:
        """Insert or replace a simulator configuration for *controller_id*."""
        async with self.session_factory() as session:
            await session.execute(
                text(
                    "INSERT OR REPLACE INTO Configuracao_Simulador"
                    " (controlador_id, preset, gain, tau1, tau2, dead_time,"
                    "  pid_enabled, pid_kp, pid_ti, pid_td, pid_mode,"
                    "  auto_sp_enabled, auto_sp_min_pct, auto_sp_max_pct,"
                    "  auto_dist_enabled, auto_dist_max_pct, pid_sp)"
                    " VALUES (:cid, :preset, :gain, :tau1, :tau2, :dead_time,"
                    "  :pid_enabled, :pid_kp, :pid_ti, :pid_td, :pid_mode,"
                    "  :auto_sp_enabled, :auto_sp_min_pct, :auto_sp_max_pct,"
                    "  :auto_dist_enabled, :auto_dist_max_pct, :pid_sp)"
                ),
                {
                    "cid": controller_id, "preset": preset, "gain": gain,
                    "tau1": tau1, "tau2": tau2, "dead_time": dead_time,
                    "pid_enabled": int(pid_enabled), "pid_kp": pid_kp,
                    "pid_ti": pid_ti, "pid_td": pid_td, "pid_mode": pid_mode,
                    "auto_sp_enabled": int(auto_sp_enabled),
                    "auto_sp_min_pct": auto_sp_min_pct,
                    "auto_sp_max_pct": auto_sp_max_pct,
                    "auto_dist_enabled": int(auto_dist_enabled),
                    "auto_dist_max_pct": auto_dist_max_pct,
                    "pid_sp": pid_sp,
                },
            )
            await session.commit()

    async def get_sim_config(self, controller_id: int) -> dict | None:
        """Return sim config dict or ``None``."""
        async with self.session_factory() as session:
            result = await session.execute(
                text("SELECT * FROM Configuracao_Simulador WHERE controlador_id = :cid"),
                {"cid": controller_id},
            )
            row = result.mappings().first()
        if row is None:
            return None
        return self._sim_row_to_dict(row)

    async def list_sim_configs(self) -> list[dict]:
        """Return all simulator configurations."""
        async with self.session_factory() as session:
            result = await session.execute(
                text("SELECT * FROM Configuracao_Simulador ORDER BY controlador_id"),
            )
            rows = result.mappings().all()
        return [self._sim_row_to_dict(r) for r in rows]
```

`_sim_row_to_dict` — keep the body exactly as in the current file, changing only the signature to `def _sim_row_to_dict(row: Mapping) -> dict:` (`RowMapping.keys()` supports the existing `"pid_sp" in row.keys()` guard).

Lifecycle + test helpers (replaces current lines 733–758; `checkpoint()` is added in Task 11 — do NOT add it yet):

```python
    # ------------------------------------------------------------------
    # Project lifecycle
    # ------------------------------------------------------------------

    async def reopen(self, db_path: Path) -> None:
        """Close the current DB and open a new one at *db_path*."""
        await self.db.close()  # TRANSITIONAL (deleted in Task 10)
        await self.engine.dispose()
        self._db_path = db_path
        await self.initialize()

    # ------------------------------------------------------------------
    # Test helpers
    # ------------------------------------------------------------------

    async def _get_table_names(self) -> list[str]:
        async with self.session_factory() as session:
            result = await session.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"),
            )
            rows = result.mappings().all()
        return [r["name"] for r in rows]

    async def _get_journal_mode(self) -> str:
        async with self.session_factory() as session:
            row = (await session.execute(text("PRAGMA journal_mode"))).first()
        return str(row[0]) if row else ""

    async def close(self) -> None:
        """Dispose engine A (finalizes WAL on the pooled connection)."""
        await self.db.close()  # TRANSITIONAL (deleted in Task 10)
        await self.engine.dispose()
```

- [ ] **Step 4: Run the repository suites**

Run: `uv run pytest tests/core/integration/test_sqlite_repo.py tests/core/unit/test_sqlite_repo_new_tables.py tests/core/unit/test_db_models.py -q`
Expected: all pass, including the two new FK-inertness tests (`sqlite_master` also contains `sqlite_sequence`; the existing `test_initialize_creates_tables` asserts membership, not set equality, so it stays green).

- [ ] **Step 5: Run the full backend suite (dual-stack must not break borrowers)**

Run: `uv run pytest tests/core -q`
Expected: same pass count as before this task (legacy `repo.db` still feeds historian/alarm/audit/ai/system-event).

- [ ] **Step 6: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/adapters/outbound/sqlite_repo.py tests/core/integration/test_sqlite_repo.py
git commit -m "feat(core): SQLiteRepository on engine A with session-per-method (transitional dual-stack)"
```

---

### Task 5: `SystemEventRepository` → session factory (stale-connection bug fixed)

**Files:**
- Modify: `packages/smart_pid_core/src/smart_pid_core/adapters/outbound/system_event_repo.py` (whole file)
- Modify: `packages/smart_pid_core/src/smart_pid_core/main.py` — site #6 (`SystemEventRepository(repo.db)`, anchor line 385)
- Modify: `tests/conftest.py:41` (`system_event_repo = SystemEventRepository(repo.db)`)
- Modify: `tests/core/integration/test_security_middleware.py:44` (same pattern)
- Modify: `tests/core/unit/test_system_event_repo.py` (fixtures, lines 13–34)

**Interfaces:**
- Consumes: `SQLiteRepository.session_factory` (Task 4), `create_sqlite_engine` (Task 2, test fixture only).
- Produces: `SystemEventRepository.__init__(self, session_factory: async_sessionmaker[AsyncSession])` — **changed constructor** (documented behavior change: the repository now survives `reopen()`, because the injected sessionmaker is re-bound in place; previously it captured a raw connection eagerly and wrote to a closed handle after a project switch). Methods `insert_event`, `get_history` keep their signatures.

- [ ] **Step 1: Rewrite the unit-test fixtures (failing first)**

Replace lines 1–34 of `tests/core/unit/test_system_event_repo.py` (imports + `db`/`repo` fixtures; every test function below stays untouched) with:

```python
"""Tests for SystemEventRepository."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker

from smart_pid_core.adapters.outbound.db_engine import create_sqlite_engine
from smart_pid_core.adapters.outbound.system_event_repo import SystemEventRepository


@pytest_asyncio.fixture
async def session_factory(tmp_path):
    engine = create_sqlite_engine(tmp_path / "events.spid")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.connect() as conn:
        raw = await conn.get_raw_connection()
        await raw.driver_connection.executescript("""
        CREATE TABLE Log_System_Events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL DEFAULT (datetime('now')),
            source TEXT NOT NULL,
            severity TEXT NOT NULL CHECK(severity IN ('CRITICAL','WARNING','INFO')),
            message TEXT NOT NULL
        );
        CREATE INDEX idx_sysevents_timestamp ON Log_System_Events(timestamp);
        CREATE INDEX idx_sysevents_severity ON Log_System_Events(severity);
        """)
        await raw.driver_connection.commit()
    yield factory
    await engine.dispose()


@pytest_asyncio.fixture
async def repo(session_factory):
    return SystemEventRepository(session_factory)
```

(Scan the rest of the file: as of the current tree only the two fixtures touch the raw connection — the test bodies use `repo.insert_event`/`repo.get_history` and need no edits. If a body references the old `db` fixture, rewire it through `session_factory` the same way.)

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/core/unit/test_system_event_repo.py -q`
Expected: FAIL — `insert_event` crashes with `AttributeError` (the repository still calls `self._db.execute` on what is now a sessionmaker).

- [ ] **Step 3: Rewrite the repository**

Replace the whole `packages/smart_pid_core/src/smart_pid_core/adapters/outbound/system_event_repo.py`:

```python
"""SystemEventRepository — CRUD for Log_System_Events table."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import text

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


class SystemEventRepository:
    """Persistence layer for system events (write-once, read-many).

    Takes the .spid ``async_sessionmaker`` (engine A). The sessionmaker is
    re-bound in place on ``reopen()``, so — unlike the pre-port eager
    ``aiosqlite.Connection`` capture — this repository keeps working after a
    project switch (deliberate, documented behavior change: the stale-
    connection bug is fixed by the port).
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def insert_event(
        self, source: str, severity: str, message: str,
    ) -> int:
        """Insert a system event. Returns the event ID."""
        now = datetime.now(tz=UTC).isoformat()
        async with self._session_factory() as session:
            result = await session.execute(
                text(
                    "INSERT INTO Log_System_Events (timestamp, source, severity, message)"
                    " VALUES (:ts, :source, :severity, :message)"
                ),
                {"ts": now, "source": source, "severity": severity, "message": message},
            )
            event_id = result.lastrowid
            await session.commit()
        return event_id or 0

    async def get_history(
        self,
        start: datetime,
        end: datetime,
        source: str | None = None,
        severity: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict]:
        """Return system events in a time range with optional filters."""
        sql = """SELECT id, timestamp, source, severity, message
                 FROM Log_System_Events
                 WHERE timestamp BETWEEN :start AND :end"""
        params: dict = {"start": start.isoformat(), "end": end.isoformat()}
        if source is not None:
            sql += " AND source = :source"
            params["source"] = source
        if severity is not None:
            sql += " AND severity = :severity"
            params["severity"] = severity
        sql += " ORDER BY timestamp DESC LIMIT :limit OFFSET :offset"
        params["limit"] = limit
        params["offset"] = offset

        async with self._session_factory() as session:
            result = await session.execute(text(sql), params)
            rows = result.mappings().all()
        return [dict(r) for r in rows]
```

- [ ] **Step 4: Update the three construction sites**

1. `main.py` — replace `system_event_repo = SystemEventRepository(repo.db)` (anchor 385) with:
   ```python
   system_event_repo = SystemEventRepository(repo.session_factory)
   ```
2. `tests/conftest.py:41` — replace `system_event_repo = SystemEventRepository(repo.db)` with:
   ```python
   system_event_repo = SystemEventRepository(repo.session_factory)
   ```
3. `tests/core/integration/test_security_middleware.py:44` — same one-line replacement as (2).

- [ ] **Step 5: Run to verify green**

Run: `uv run pytest tests/core/unit/test_system_event_repo.py tests/core/integration/test_security_middleware.py tests/core/integration/test_system_events_api.py tests/core/unit/test_system_event_worker.py -q`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/adapters/outbound/system_event_repo.py packages/smart_pid_core/src/smart_pid_core/main.py tests/conftest.py tests/core/integration/test_security_middleware.py tests/core/unit/test_system_event_repo.py
git commit -m "feat(core): SystemEventRepository on session factory (fixes stale-connection bug on reopen)"
```

---

### Task 6: Historian Core hot path + `DBWorker` on engine B

**Files:**
- Modify: `packages/smart_pid_core/src/smart_pid_core/adapters/outbound/historian.py` (whole file)
- Modify: `packages/smart_pid_core/src/smart_pid_core/application/workers/db_worker.py` (imports + constructor + `_run_async`)
- Modify: `packages/smart_pid_core/src/smart_pid_core/main.py` — site #1 (`SQLiteHistorian(repo)`, anchor 239) and `DBWorker(bus=bus, historian=historian)` (anchor 396)
- Modify test fixtures constructing `SQLiteHistorian(repo)` / `DBWorker(..., historian=...)`:
  - `tests/conftest.py:35` and `:156`
  - `tests/core/integration/test_historian.py:13–18`
  - `tests/core/integration/test_db_worker.py:15–24, 31, 54`
  - `tests/core/integration/test_db_worker_ai_log.py:9, 21, 26, 54–58, 70, 79, 84, 91–94, 98`
  - `tests/core/api/test_ws_realtime.py:363`
  - `tests/core/integration/test_api_opcua.py:41`
  - `tests/core/integration/test_api_stats.py:36`
  - `tests/core/integration/test_audit_api.py:26`
  - `tests/core/unit/test_commands_monitor_mode.py:46, 159`
  - `tests/core/unit/test_get_tuning_recommendations.py:47`

**Interfaces:**
- Consumes: `SQLiteRepository.session_factory`, `SQLiteRepository.db_path` (Task 4), `create_sqlite_engine` (Task 2), `log_processo` (Task 3).
- Produces:
  - `SQLiteHistorian.__init__(self, session_factory: async_sessionmaker[AsyncSession])` — **changed constructor**; methods `write_batch`, `query`, `write_ai_log`, `cleanup_older_than` keep signatures (`ExportWorker` and the history/stats routers consume the instance unchanged).
  - `DBWorker.__init__(self, bus: EventBus, repo: SQLiteRepository, flush_interval_s: float = 5.0, batch_size: int = 500)` — **changed constructor**; engine B + its sessionmaker + a private `SQLiteHistorian` are created inside `_run_async()` on the worker loop and disposed there.

- [ ] **Step 1: Adapt the historian tests (failing first)**

In `tests/core/integration/test_historian.py`, replace the fixture (lines 13–18) with:

```python
@pytest.fixture
async def historian(tmp_path):
    db_path = tmp_path / "test.spid"
    repo = SQLiteRepository(db_path)
    await repo.initialize()
    return SQLiteHistorian(repo.session_factory)
```

Run: `uv run pytest tests/core/integration/test_historian.py -q`
Expected: FAIL — `SQLiteHistorian` still expects a repo and dereferences `.db` (`AttributeError: 'async_sessionmaker' object has no attribute 'db'`).

- [ ] **Step 2: Rewrite `historian.py`**

Replace the whole file:

```python
"""SQLite-backed historian adapter for telemetry data (SQLAlchemy async)."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import insert, text

from smart_pid_core.adapters.outbound.db_models import log_processo
from smart_pid_domain.models.signal import FFSignal
from smart_pid_domain.models.telemetry import TelemetryFrame

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


class SQLiteHistorian:
    """Writes and queries process telemetry in Log_Processo.

    Bound to an injected async_sessionmaker: the main-loop instance receives
    engine A's factory (API reads, export); the DB worker builds its own
    instance over engine B on its private loop. The main-loop factory is
    re-bound in place across reopen(), so this class never goes stale.
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def write_batch(self, frames: list[TelemetryFrame]) -> None:
        """Batch-insert telemetry frames. No-op for empty list.

        HOT PATH (spec §10): Core executemany — ``conn.execute(insert(...),
        rows)`` with a list of parameter dicts — one commit per batch.
        ``session.add_all()`` (per-object flush) is forbidden here.
        """
        if not frames:
            return
        rows = [
            {
                "controlador_id": f.controller_id,
                "timestamp": f.timestamp.isoformat(),
                "pv": f.pv.value,
                "sp": f.sp.value,
                "co": f.co.value,
                "integral_val": f.integral_val,
            }
            for f in frames
        ]
        async with self._session_factory() as session:
            conn = await session.connection()
            await conn.execute(insert(log_processo), rows)
            await session.commit()

    async def query(
        self,
        controller_id: int,
        start: datetime,
        end: datetime,
    ) -> list[TelemetryFrame]:
        """Return frames for a controller within [start, end] inclusive."""
        async with self._session_factory() as session:
            result = await session.execute(
                text(
                    "SELECT controlador_id, timestamp, pv, sp, co, integral_val "
                    "FROM Log_Processo "
                    "WHERE controlador_id = :cid AND timestamp >= :start AND timestamp <= :end "
                    "ORDER BY timestamp"
                ),
                {"cid": controller_id, "start": start.isoformat(), "end": end.isoformat()},
            )
            rows = result.all()

        results: list[TelemetryFrame] = []
        for row in rows:
            ts = datetime.fromisoformat(row[1])
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=UTC)
            results.append(
                TelemetryFrame(
                    controller_id=row[0],
                    pv=FFSignal.good(row[2], ts),
                    sp=FFSignal.good(row[3], ts),
                    co=FFSignal.good(row[4], ts),
                    bkcal_in=FFSignal.good(0.0, ts),
                    integral_val=row[5],
                    timestamp=ts,
                )
            )
        return results

    async def write_ai_log(self, entry: dict) -> None:
        """Insert a single AI tuning log entry into Log_Sintonia_IA."""
        async with self._session_factory() as session:
            await session.execute(
                text(
                    "INSERT INTO Log_Sintonia_IA "
                    "(controlador_id, timestamp, motor, ki_antes, ki_depois,"
                    " objetivo, metrica, aprovado)"
                    " VALUES (:cid, :ts, :motor, :ki_antes, :ki_depois, :objetivo, :metrica, 1)"
                ),
                {
                    "cid": entry["controller_id"],
                    "ts": entry.get("timestamp", ""),
                    "motor": entry.get("engine", "NONE"),
                    "ki_antes": entry.get("old_ki"),
                    "ki_depois": entry.get("new_ki"),
                    "objetivo": entry.get("objective", ""),
                    "metrica": entry.get("gamma"),
                },
            )
            await session.commit()

    async def cleanup_older_than(self, days: int) -> int:
        """Delete frames older than `days` days. Returns count deleted."""
        async with self._session_factory() as session:
            result = await session.execute(
                text("DELETE FROM Log_Processo WHERE timestamp <= datetime('now', :offset)"),
                {"offset": f"-{days} days"},
            )
            await session.commit()
        return result.rowcount
```

Run: `uv run pytest tests/core/integration/test_historian.py -q`
Expected: `5 passed`

- [ ] **Step 3: Port `DBWorker` to engine B (failing test first)**

In `tests/core/integration/test_db_worker.py`, change the fixture and both constructor calls:

```python
@pytest.fixture
async def setup(tmp_path):
    db_path = tmp_path / "test.spid"
    repo = SQLiteRepository(db_path)
    await repo.initialize()
    historian = SQLiteHistorian(repo.session_factory)  # engine A — used by the TEST to query
    bus = EventBus()
    bus.start()
    yield bus, historian, repo
    bus.stop()
    await repo.close()
```

and in both tests: `worker = DBWorker(bus=bus, repo=repo, flush_interval_s=0.1)`.

Run: `uv run pytest tests/core/integration/test_db_worker.py -q`
Expected: FAIL with `TypeError: DBWorker.__init__() got an unexpected keyword argument 'repo'`

- [ ] **Step 4: Implement the `DBWorker` port**

In `db_worker.py`:

Add imports after the existing third-party block:

```python
from sqlalchemy.ext.asyncio import async_sessionmaker

from smart_pid_core.adapters.outbound.db_engine import create_sqlite_engine
from smart_pid_core.adapters.outbound.historian import SQLiteHistorian
```

and change the `TYPE_CHECKING` block to import the repo instead of the historian:

```python
if TYPE_CHECKING:
    from smart_pid_core.adapters.outbound.sqlite_repo import SQLiteRepository
    from smart_pid_core.application.event_bus import EventBus
```

Replace `__init__` (lines 26–40):

```python
    def __init__(
        self,
        bus: EventBus,
        repo: SQLiteRepository,
        flush_interval_s: float = 5.0,
        batch_size: int = 500,
    ) -> None:
        self._bus = bus
        self._repo = repo
        self._historian: SQLiteHistorian | None = None  # built per-run on the worker loop
        self._flush_interval_s = flush_interval_s
        self._batch_size = batch_size
        self._buffer: deque[TelemetryFrame] = deque(maxlen=10_000)
        self._ai_log_buffer: deque[dict] = deque(maxlen=1_000)
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
```

Replace `_run_async` (lines 60–88) — the polling body is unchanged; engine B is created on THIS loop and disposed here (spec §10: engine B lives and dies with the worker thread, which is how `reopen()` gets its drain guarantee — ProjectService stops the worker before switching, Task 11):

```python
    async def _run_async(self) -> None:
        # Engine B — same .spid file, THIS thread's private loop (AsyncEngine
        # is loop-affine). Created at thread start against the repo's current
        # path; disposed in the finally block, so a stopped worker never holds
        # a pooled handle on the file.
        engine = create_sqlite_engine(self._repo.db_path)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        self._historian = SQLiteHistorian(session_factory)
        telem_sub = self._bus.create_subscriber(b"TELEMETRY")
        ai_sub = self._bus.create_subscriber(b"LOG.AI.")
        try:
            while not self._stop_event.is_set():
                try:
                    # Wait for telemetry messages up to flush interval
                    msg = telem_sub.recv(timeout_ms=int(self._flush_interval_s * 1000))
                    if msg is not None:
                        self._process_message(msg)
                    # Drain remaining telemetry without blocking
                    while True:
                        msg = telem_sub.recv(timeout_ms=0)
                        if msg is None:
                            break
                        self._process_message(msg)
                    # Drain AI log messages without blocking
                    while True:
                        msg = ai_sub.recv(timeout_ms=0)
                        if msg is None:
                            break
                        self._process_ai_log(msg)
                except zmq.ZMQError:
                    break
                # Flush both buffers
                await self._flush()
                await self._flush_ai_logs()
        finally:
            # Final flush on shutdown, then release engine B completely.
            await self._flush()
            await self._flush_ai_logs()
            await engine.dispose()
```

(`_flush`/`_flush_ai_logs`/`_process_message`/`_process_ai_log` bodies stay unchanged — they use `self._historian`, which is set before the subscribers are created.)

- [ ] **Step 5: Adapt `test_db_worker_ai_log.py`**

- Line 9 (`from smart_pid_core.adapters.outbound.historian import SQLiteHistorian`): delete — unused after this step.
- Lines 21 and 79: delete `historian = SQLiteHistorian(repo)`.
- Lines 26 and 84: `worker = DBWorker(bus=bus, repo=repo, flush_interval_s=0.1)`.
- Verification block (lines 54–58) becomes:

```python
    from sqlalchemy import text
    async with repo.session_factory() as session:
        result = await session.execute(text(
            "SELECT controlador_id, motor, ki_antes, ki_depois, objetivo, metrica "
            "FROM Log_Sintonia_IA WHERE controlador_id = 42"
        ))
        rows = result.all()
```

- Count block (lines 91–94) becomes:

```python
    from sqlalchemy import text
    async with repo.session_factory() as session:
        row = (await session.execute(text("SELECT COUNT(*) FROM Log_Sintonia_IA"))).first()
```

- Teardown lines 70 and 98: `await repo.close()` (instead of `await repo.db.close()`).

- [ ] **Step 6: Update remaining `SQLiteHistorian(repo)` construction sites**

One-line change `SQLiteHistorian(repo)` → `SQLiteHistorian(repo.session_factory)` at each of:
`tests/conftest.py:35`, `tests/conftest.py:156`, `tests/core/api/test_ws_realtime.py:363`, `tests/core/integration/test_api_opcua.py:41`, `tests/core/integration/test_api_stats.py:36`, `tests/core/integration/test_audit_api.py:26`, `tests/core/unit/test_commands_monitor_mode.py:46` and `:159`, `tests/core/unit/test_get_tuning_recommendations.py:47`.

Then `main.py`: anchor 239 `historian = SQLiteHistorian(repo)` → `historian = SQLiteHistorian(repo.session_factory)`; anchor 396 `db_worker = DBWorker(bus=bus, historian=historian)` → `db_worker = DBWorker(bus=bus, repo=repo)`.

Gate: `grep -rn "SQLiteHistorian(repo)" packages tests` must return nothing.

- [ ] **Step 7: Run the affected suites**

Run: `uv run pytest tests/core/integration/test_db_worker.py tests/core/integration/test_db_worker_ai_log.py tests/core/integration/test_historian.py tests/core/integration/test_api_history.py tests/core/integration/test_export_worker.py tests/core/unit/test_export_router.py -q`
Expected: all pass (the DB-worker tests now exercise the true cross-loop topology: worker writes via engine B on its private loop, test reads via engine A).

- [ ] **Step 8: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/adapters/outbound/historian.py packages/smart_pid_core/src/smart_pid_core/application/workers/db_worker.py packages/smart_pid_core/src/smart_pid_core/main.py tests/conftest.py tests/core
git commit -m "feat(core): historian on Core executemany; DBWorker owns engine B on its private loop"
```

---

### Task 7: `AlarmRepository`, `AuditRepository`, `AIRepository` → session factory

**Files:**
- Modify: `packages/smart_pid_core/src/smart_pid_core/adapters/outbound/alarm_repo.py` (whole file)
- Modify: `packages/smart_pid_core/src/smart_pid_core/adapters/outbound/audit_repo.py` (whole file)
- Modify: `packages/smart_pid_core/src/smart_pid_core/adapters/outbound/ai_repo.py` (whole file)
- Modify: `packages/smart_pid_core/src/smart_pid_core/main.py` — sites #2/#3/#4 (anchors 351, 358, 359)
- Modify construction sites in tests: `tests/conftest.py:39–40`, `tests/core/unit/test_alarm_repo.py:19`, `tests/core/unit/test_audit_repo.py:18`, `tests/core/integration/test_ai_repo.py:9–17` (+ every `AIRepository(repo)` inside that file, e.g. line 26), `tests/core/integration/test_audit_api.py:30–31`, `tests/core/unit/test_commands_monitor_mode.py:50–51` and `:163–164`, `tests/core/unit/test_get_tuning_recommendations.py:51–52`, `tests/core/integration/test_security_middleware.py:43`, plus any `AlarmRepository(repo)`/`AuditRepository(repo)` hits inside `tests/core/api/test_ws_realtime.py` and `tests/core/integration/test_api_opcua.py` local fixtures (grep in Step 5 catches them)

**Interfaces:**
- Consumes: `SQLiteRepository.session_factory` (Task 4).
- Produces — **changed constructors**, all methods keep signatures:
  - `AlarmRepository.__init__(self, session_factory: async_sessionmaker[AsyncSession])`
  - `AuditRepository.__init__(self, session_factory: async_sessionmaker[AsyncSession])`
  - `AIRepository.__init__(self, session_factory: async_sessionmaker[AsyncSession])`

- [ ] **Step 1: Flip the unit-test fixtures (failing first)**

`tests/core/unit/test_alarm_repo.py:19`: `alarm_repo = AlarmRepository(repo.session_factory)`
`tests/core/unit/test_audit_repo.py:18`: `audit_repo = AuditRepository(repo.session_factory)`
`tests/core/integration/test_ai_repo.py` fixture (lines 9–18) becomes:

```python
@pytest.fixture
async def repo(tmp_path):
    from sqlalchemy import text

    r = SQLiteRepository(tmp_path / "test.spid")
    await r.initialize()
    # Need a controller row for FK reference
    async with r.session_factory() as session:
        await session.execute(text("INSERT INTO Controladores (id, nome) VALUES (1, 'Test')"))
        await session.commit()
    yield r
```

and every `AIRepository(repo)` in that file → `AIRepository(repo.session_factory)`.

Run: `uv run pytest tests/core/unit/test_alarm_repo.py tests/core/unit/test_audit_repo.py tests/core/integration/test_ai_repo.py -q`
Expected: FAIL — the repositories still expect a `SQLiteRepository` and dereference `._repo.db` (`AttributeError: 'async_sessionmaker' object has no attribute 'db'`).

- [ ] **Step 2: Rewrite `alarm_repo.py`**

This is the template port for a borrow-pattern repository — the same mechanical rules apply to audit/ai: constructor takes the sessionmaker; every method opens ONE session; writes commit immediately; `?` positional binds become `:name` binds; `dict(row)` moves onto `.mappings()`; `lastrowid`/`rowcount` read off the `CursorResult`.

```python
# packages/smart_pid_core/src/smart_pid_core/adapters/outbound/alarm_repo.py
"""Alarm repository — CRUD operations on Log_Alarmes table."""
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import text

if TYPE_CHECKING:
    from datetime import datetime

    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from smart_pid_domain.enums import AlarmPriority, AlarmType


class AlarmRepository:
    """Persistence layer for alarm events (injected .spid session factory)."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def insert_alarm(
        self,
        controller_id: int,
        alarm_type: AlarmType,
        priority: AlarmPriority,
        value: float,
        limit_value: float,
        triggered_at: datetime,
    ) -> int:
        """Insert a new alarm record. Returns the alarm ID."""
        async with self._session_factory() as session:
            result = await session.execute(
                text(
                    """INSERT INTO Log_Alarmes
                       (controlador_id, tipo_alarme, prioridade, valor, limite, timestamp)
                       VALUES (:cid, :atype, :prio, :value, :limit, :ts)"""
                ),
                {
                    "cid": controller_id,
                    "atype": str(alarm_type),
                    "prio": str(priority),
                    "value": value,
                    "limit": limit_value,
                    "ts": triggered_at.isoformat(),
                },
            )
            alarm_id = result.lastrowid
            await session.commit()
        return alarm_id or 0

    async def mark_cleared(
        self,
        controller_id: int,
        alarm_type: AlarmType,
        cleared_at: datetime,
    ) -> None:
        """Mark the most recent active alarm of this type as cleared."""
        async with self._session_factory() as session:
            await session.execute(
                text(
                    """UPDATE Log_Alarmes SET cleared_at = :cleared
                       WHERE controlador_id = :cid AND tipo_alarme = :atype
                         AND cleared_at IS NULL"""
                ),
                {"cleared": cleared_at.isoformat(), "cid": controller_id,
                 "atype": str(alarm_type)},
            )
            await session.commit()

    async def acknowledge(
        self,
        alarm_id: int,
        username: str,
        ack_at: datetime,
    ) -> dict:
        """Acknowledge a specific alarm. Returns alarm details for HMI update."""
        async with self._session_factory() as session:
            await session.execute(
                text(
                    """UPDATE Log_Alarmes
                       SET reconhecido = 1, reconhecido_por = :user, reconhecido_em = :ts
                       WHERE id = :aid"""
                ),
                {"user": username, "ts": ack_at.isoformat(), "aid": alarm_id},
            )
            await session.commit()
            result = await session.execute(
                text(
                    """SELECT id, controlador_id as controller_id, tipo_alarme as alarm_type,
                              prioridade as priority
                       FROM Log_Alarmes WHERE id = :aid"""
                ),
                {"aid": alarm_id},
            )
            row = result.mappings().first()
        if row is None:
            return {"id": alarm_id, "acknowledged": True}
        return {
            "id": row["id"],
            "controller_id": row["controller_id"],
            "alarm_type": row["alarm_type"],
            "priority": row["priority"],
            "acknowledged": True,
        }

    async def acknowledge_all(self, username: str, ack_at: datetime) -> dict:
        """Acknowledge all unacknowledged alarms. Returns count and controller_ids."""
        async with self._session_factory() as session:
            # First, get affected controller_ids before updating
            result = await session.execute(
                text("SELECT DISTINCT controlador_id FROM Log_Alarmes WHERE reconhecido = 0"),
            )
            controller_ids = [row["controlador_id"] for row in result.mappings().all()]

            result = await session.execute(
                text(
                    """UPDATE Log_Alarmes
                       SET reconhecido = 1, reconhecido_por = :user, reconhecido_em = :ts
                       WHERE reconhecido = 0"""
                ),
                {"user": username, "ts": ack_at.isoformat()},
            )
            count = result.rowcount
            await session.commit()
        return {"acknowledged_count": count, "controller_ids": controller_ids}

    async def get_active(
        self,
        controller_id: int | None = None,
        priority: str | None = None,
    ) -> list[dict]:
        """Return alarms that are still visible (not cleared+acked)."""
        sql = """SELECT a.id, a.controlador_id as controller_id,
                        c.nome as controller_name,
                        a.tipo_alarme as alarm_type,
                        a.prioridade as priority, a.valor as value,
                        a.limite as "limit",
                        a.timestamp, a.cleared_at,
                        a.reconhecido as acknowledged,
                        a.reconhecido_por as ack_by_user, a.reconhecido_em as ack_at,
                        CASE
                            WHEN a.reconhecido = 1 THEN 'ACKNOWLEDGED'
                            WHEN a.cleared_at IS NOT NULL THEN 'CLEARED_UNACK'
                            ELSE 'UNACKNOWLEDGED'
                        END as status
                 FROM Log_Alarmes a
                 LEFT JOIN Controladores c ON c.id = a.controlador_id
                 WHERE NOT (a.cleared_at IS NOT NULL AND a.reconhecido = 1)"""
        params: dict = {}
        if controller_id is not None:
            sql += " AND a.controlador_id = :cid"
            params["cid"] = controller_id
        if priority is not None:
            sql += " AND a.prioridade = :prio"
            params["prio"] = priority
        sql += " ORDER BY a.timestamp DESC"

        async with self._session_factory() as session:
            result = await session.execute(text(sql), params)
            rows = result.mappings().all()
        return [dict(r) for r in rows]

    async def get_alarm_config(self, controller_id: int) -> list[dict]:
        """Return all alarm threshold configs for a controller."""
        async with self._session_factory() as session:
            result = await session.execute(
                text(
                    """SELECT id, controlador_id as controller_id, tipo_alarme as alarm_type,
                              prioridade as priority, limite as "limit", habilitado as enabled,
                              histerese as deadband, delay_on_s, delay_off_s
                       FROM Configuracao_Alarmes WHERE controlador_id = :cid
                       ORDER BY tipo_alarme"""
                ),
                {"cid": controller_id},
            )
            rows = result.mappings().all()
        return [dict(r) for r in rows]

    async def save_alarm_config(
        self,
        controller_id: int,
        thresholds: list[dict],
    ) -> None:
        """Replace all alarm thresholds for a controller (delete + insert)."""
        async with self._session_factory() as session:
            await session.execute(
                text("DELETE FROM Configuracao_Alarmes WHERE controlador_id = :cid"),
                {"cid": controller_id},
            )
            for t in thresholds:
                await session.execute(
                    text(
                        """INSERT INTO Configuracao_Alarmes
                           (controlador_id, tipo_alarme, prioridade, limite, habilitado,
                            histerese, delay_on_s, delay_off_s)
                           VALUES (:cid, :atype, :prio, :limit, :enabled,
                                   :deadband, :don, :doff)"""
                    ),
                    {
                        "cid": controller_id,
                        "atype": t["alarm_type"],
                        "prio": t["priority"],
                        "limit": t["limit"],
                        "enabled": 1 if t.get("enabled", True) else 0,
                        "deadband": t.get("deadband", 0.0),
                        "don": t.get("delay_on_s", 0.0),
                        "doff": t.get("delay_off_s", 0.0),
                    },
                )
            await session.commit()

    async def get_history(
        self,
        start: datetime,
        end: datetime,
        controller_id: int | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict]:
        """Return alarm history in a time range."""
        sql = """SELECT a.id, a.controlador_id as controller_id,
                        c.nome as controller_name,
                        a.tipo_alarme as alarm_type,
                        a.prioridade as priority, a.valor as value,
                        a.limite as "limit",
                        a.timestamp, a.cleared_at,
                        a.reconhecido as acknowledged,
                        a.reconhecido_por as ack_by_user, a.reconhecido_em as ack_at,
                        CASE
                            WHEN a.reconhecido = 1 THEN 'ACKNOWLEDGED'
                            WHEN a.cleared_at IS NOT NULL THEN 'CLEARED_UNACK'
                            ELSE 'UNACKNOWLEDGED'
                        END as status
                 FROM Log_Alarmes a
                 LEFT JOIN Controladores c ON c.id = a.controlador_id
                 WHERE a.timestamp BETWEEN :start AND :end"""
        params: dict = {"start": start.isoformat(), "end": end.isoformat()}
        if controller_id is not None:
            sql += " AND a.controlador_id = :cid"
            params["cid"] = controller_id
        sql += " ORDER BY a.timestamp DESC LIMIT :limit OFFSET :offset"
        params["limit"] = limit
        params["offset"] = offset

        async with self._session_factory() as session:
            result = await session.execute(text(sql), params)
            rows = result.mappings().all()
        return [dict(r) for r in rows]
```

- [ ] **Step 3: Rewrite `audit_repo.py`**

```python
"""Audit repository — CRUD operations on Log_Auditoria table."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import text

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from smart_pid_domain.enums import AuditAction


class AuditRepository:
    """Persistence layer for audit trail entries (injected .spid session factory)."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def record(
        self,
        user_id: int,
        username: str,
        action: AuditAction,
        resource: str | None,
        detail: str | None,
    ) -> None:
        """Insert an audit trail entry."""
        async with self._session_factory() as session:
            await session.execute(
                text(
                    """INSERT INTO Log_Auditoria
                       (usuario_id, username, timestamp, acao, entidade, detalhe)
                       VALUES (:uid, :user, :ts, :acao, :entidade, :detalhe)"""
                ),
                {
                    "uid": user_id,
                    "user": username,
                    "ts": datetime.now(tz=UTC).isoformat(),
                    "acao": str(action),
                    "entidade": resource or "",
                    "detalhe": detail or "",
                },
            )
            await session.commit()

    async def get_history(
        self,
        start: datetime,
        end: datetime,
        user_id: int | None = None,
        action: AuditAction | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict]:
        """Return audit entries in a time range."""
        sql = """SELECT id, usuario_id as user_id, username, timestamp,
                        acao as action, entidade as resource, detalhe as detail
                 FROM Log_Auditoria WHERE timestamp BETWEEN :start AND :end"""
        params: dict = {"start": start.isoformat(), "end": end.isoformat()}
        if user_id is not None:
            sql += " AND usuario_id = :uid"
            params["uid"] = user_id
        if action is not None:
            sql += " AND acao = :acao"
            params["acao"] = str(action)
        sql += " ORDER BY timestamp DESC LIMIT :limit OFFSET :offset"
        params["limit"] = limit
        params["offset"] = offset

        async with self._session_factory() as session:
            result = await session.execute(text(sql), params)
            rows = result.mappings().all()
        return [dict(r) for r in rows]
```

- [ ] **Step 4: Rewrite `ai_repo.py`**

```python
"""SQLite-backed repository for AI model metadata and tuning logs."""
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import text

if TYPE_CHECKING:
    from datetime import datetime

    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


class AIRepository:
    """Persistence for AI model metadata and tuning action logs.

    Bound to the injected .spid session factory (engine A).
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def save_model_metadata(
        self,
        controller_id: int,
        algorithm: str,
        episodes: int,
        avg_reward: float,
        model_path: str,
    ) -> int:
        """Save RL model metadata. Returns the row ID."""
        async with self._session_factory() as session:
            result = await session.execute(
                text(
                    "INSERT INTO Modelos_IA "
                    "(controlador_id, algoritmo, episodios, reward_medio, caminho_modelo) "
                    "VALUES (:cid, :algo, :eps, :reward, :path)"
                ),
                {"cid": controller_id, "algo": algorithm, "eps": episodes,
                 "reward": avg_reward, "path": model_path},
            )
            row_id = result.lastrowid
            await session.commit()
        return row_id or 0

    async def get_latest_model(self, controller_id: int) -> dict | None:
        """Return the most recent model metadata for a controller."""
        async with self._session_factory() as session:
            result = await session.execute(
                text(
                    "SELECT id, controlador_id, algoritmo, episodios, reward_medio, "
                    "caminho_modelo, criado_em "
                    "FROM Modelos_IA WHERE controlador_id = :cid "
                    "ORDER BY criado_em DESC LIMIT 1"
                ),
                {"cid": controller_id},
            )
            row = result.first()
        if row is None:
            return None
        return {
            "id": row[0],
            "controller_id": row[1],
            "algorithm": row[2],
            "episodes": row[3],
            "avg_reward": row[4],
            "model_path": row[5],
            "created_at": row[6],
        }

    async def log_tuning_action(
        self,
        controller_id: int,
        engine: str,
        old_ki: float,
        new_ki: float,
        objective: str,
        metric: float = 0.0,
    ) -> None:
        """Log a Ki adjustment in Log_Sintonia_IA.

        Args:
            controller_id: Controller ID (FK to Controladores).
            engine: AI engine name (e.g. "FUZZY", "RL").
            old_ki: Ki value before adjustment.
            new_ki: Ki value after adjustment.
            objective: Control objective name.
            metric: Computed metric value (e.g. gamma).
        """
        async with self._session_factory() as session:
            await session.execute(
                text(
                    "INSERT INTO Log_Sintonia_IA "
                    "(controlador_id, motor, ki_antes, ki_depois, objetivo, metrica, aprovado) "
                    "VALUES (:cid, :motor, :old, :new, :obj, :metric, 1)"
                ),
                {"cid": controller_id, "motor": engine, "old": old_ki,
                 "new": new_ki, "obj": objective, "metric": metric},
            )
            await session.commit()

    async def get_last_ki(self, controller_id: int) -> float | None:
        """Return the most recent Ki/Ti value computed by AI for a controller."""
        async with self._session_factory() as session:
            result = await session.execute(
                text(
                    "SELECT ki_depois FROM Log_Sintonia_IA "
                    "WHERE controlador_id = :cid ORDER BY timestamp DESC LIMIT 1"
                ),
                {"cid": controller_id},
            )
            row = result.first()
        if row is None:
            return None
        return float(row[0])

    async def get_tuning_history(
        self,
        controller_id: int,
        limit: int = 50,
    ) -> list[dict]:
        """Return recent tuning log entries."""
        async with self._session_factory() as session:
            result = await session.execute(
                text(
                    "SELECT id, controlador_id, timestamp, motor, ki_antes, ki_depois, "
                    "objetivo, metrica, aprovado "
                    "FROM Log_Sintonia_IA WHERE controlador_id = :cid "
                    "ORDER BY timestamp DESC LIMIT :limit"
                ),
                {"cid": controller_id, "limit": limit},
            )
            rows = result.all()
        return [
            {
                "id": r[0],
                "controller_id": r[1],
                "timestamp": r[2],
                "engine": r[3],
                "ki_before": r[4],
                "ki_after": r[5],
                "objective": r[6],
                "metric": r[7],
                "approved": bool(r[8]),
            }
            for r in rows
        ]

    async def get_tuning_history_range(
        self,
        start: datetime,
        end: datetime,
        controller_id: int | None = None,
        limit: int = 500,
    ) -> list[dict]:
        """Return AI tuning log entries in a time range (all controllers)."""
        sql = (
            "SELECT a.id, a.controlador_id as controller_id, "
            "c.nome as controller_name, "
            "a.timestamp, a.motor as engine, "
            "a.ki_antes as ki_before, a.ki_depois as ki_after, "
            "a.objetivo as objective, a.metrica as metric "
            "FROM Log_Sintonia_IA a "
            "LEFT JOIN Controladores c ON c.id = a.controlador_id "
            "WHERE a.timestamp BETWEEN :start AND :end"
        )
        params: dict = {"start": start.isoformat(), "end": end.isoformat()}
        if controller_id is not None:
            sql += " AND a.controlador_id = :cid"
            params["cid"] = controller_id
        sql += " ORDER BY a.timestamp DESC LIMIT :limit"
        params["limit"] = limit
        async with self._session_factory() as session:
            result = await session.execute(text(sql), params)
            rows = result.mappings().all()
        return [dict(r) for r in rows]
```

- [ ] **Step 5: Update all remaining construction sites**

One-line changes:
- `main.py` anchor 351: `ai_repo = AIRepository(repo.session_factory)`
- `main.py` anchor 358: `alarm_repo = AlarmRepository(repo.session_factory)`
- `main.py` anchor 359: `audit_repo = AuditRepository(repo.session_factory)`
- `tests/conftest.py:39–40`: `alarm_repo = AlarmRepository(repo.session_factory)` / `audit_repo = AuditRepository(repo.session_factory)`
- `tests/core/integration/test_audit_api.py:30–31`, `tests/core/unit/test_commands_monitor_mode.py:50–51` and `:163–164`, `tests/core/unit/test_get_tuning_recommendations.py:51–52`, `tests/core/integration/test_security_middleware.py:43`: same substitution, plus any hits from the gate grep.

Gate: `grep -rnE "AlarmRepository\(repo\)|AuditRepository\(repo\)|AIRepository\(repo\)" packages tests` must return nothing.

- [ ] **Step 6: Run the affected suites**

Run: `uv run pytest tests/core/unit/test_alarm_repo.py tests/core/unit/test_audit_repo.py tests/core/integration/test_ai_repo.py tests/core/integration/test_alarm_api.py tests/core/integration/test_alarm_config_crud.py tests/core/integration/test_audit_api.py tests/core/unit/test_alarm_worker.py tests/core/unit/test_commands_monitor_mode.py tests/core/unit/test_get_tuning_recommendations.py -q`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/adapters/outbound/alarm_repo.py packages/smart_pid_core/src/smart_pid_core/adapters/outbound/audit_repo.py packages/smart_pid_core/src/smart_pid_core/adapters/outbound/ai_repo.py packages/smart_pid_core/src/smart_pid_core/main.py tests/conftest.py tests/core
git commit -m "feat(core): alarm/audit/ai repositories on injected session factory"
```

---

### Task 8: `main.py` helpers — `_load_alarm_configs` + `_retention_cleanup`

**Files:**
- Modify: `packages/smart_pid_core/src/smart_pid_core/main.py` — function bodies at anchors 32–117 and 183–204, call sites #5 (anchor 362) and #7 (anchor 504)

**Interfaces:**
- Consumes: `SQLiteRepository.session_factory` (Task 4).
- Produces: `_load_alarm_configs(session_factory) -> dict[int, AlarmConfig]` and `_retention_cleanup(session_factory, interval_hours: int = 24) -> None` (module-private; parameter renamed from `db`/`repo_db` to `session_factory`).

- [ ] **Step 1: Port `_load_alarm_configs`**

Replace the signature and the fetch block (anchors 32–43); everything from `by_controller: dict[int, dict] = {}` onward is **byte-identical to the current file** (`RowMapping` supports `row["..."]` and `row.keys()` exactly like `aiosqlite.Row`, so the `"delay_on_s" in row.keys()` guards keep working):

```python
async def _load_alarm_configs(session_factory) -> dict[int, AlarmConfig]:  # noqa: ANN001
    """Load alarm configurations from Configuracao_Alarmes table."""
    from sqlalchemy import text

    from smart_pid_domain.enums import AlarmPriority
    from smart_pid_domain.models.alarm_config import AlarmConfig as _AC

    configs: dict[int, _AC] = {}
    try:
        async with session_factory() as session:
            result = await session.execute(
                text("SELECT * FROM Configuracao_Alarmes ORDER BY controlador_id"),
            )
            rows = result.mappings().all()
    except Exception:
        logger.debug("alarm_configs_not_loaded", exc_info=True)
        return configs

    by_controller: dict[int, dict] = {}
    # ... KEEP the rest of the function body exactly as it stands in the
    # current file (the per-row dict build, the _get closure, the _AC
    # construction, `return configs`) — no changes below this line ...
```

Call site #5 (anchor 362): `alarm_configs = await _load_alarm_configs(repo.session_factory)`.

- [ ] **Step 2: Port `_retention_cleanup`**

Replace the whole function (anchors 183–204):

```python
async def _retention_cleanup(session_factory, interval_hours: int = 24) -> None:  # noqa: ANN001
    """Daily cleanup of old alarm logs and system events."""
    from sqlalchemy import text

    _log = structlog.get_logger()
    while True:
        await asyncio.sleep(interval_hours * 3600)
        try:
            async with session_factory() as session:
                await session.execute(text(
                    "DELETE FROM Log_Alarmes WHERE timestamp <= datetime('now', '-30 days')"
                ))
                await session.execute(text(
                    "DELETE FROM Log_System_Events"
                    " WHERE timestamp <= datetime('now', '-30 days')"
                ))
                await session.execute(text(
                    "DELETE FROM Log_Sintonia_IA WHERE timestamp <= datetime('now', '-7 days')"
                ))
                await session.execute(text(
                    "DELETE FROM Log_Processo WHERE timestamp <= datetime('now', '-7 days')"
                ))
                await session.commit()
            _log.info("retention_cleanup_complete")
        except Exception:
            _log.exception("retention_cleanup_error")
```

Call site #7 (anchor 504): `cleanup_task = asyncio.create_task(_retention_cleanup(repo.session_factory))`.

- [ ] **Step 3: Verify**

Run: `uv run pytest tests/core -q`
Expected: same pass count as after Task 7 (these helpers have no dedicated unit tests; the API/worker suites cover the wiring).
Gate: `grep -n "repo\.db" packages/smart_pid_core/src/smart_pid_core/main.py` returns **nothing** (sites #5, #6, #7 all gone; site #8 is `user_repo.db`, next task).

- [ ] **Step 4: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/main.py
git commit -m "refactor(core): _load_alarm_configs/_retention_cleanup on session factory"
```

---

### Task 9: `UserRepository` → engine C + user migrations re-expressed

**Files:**
- Modify: `packages/smart_pid_core/src/smart_pid_core/adapters/outbound/user_repo.py` (whole file)
- Modify: `packages/smart_pid_core/src/smart_pid_core/main.py` — site #8: `_migrate_users_if_needed` (anchors 120–157) and phase-0's `_migrate_user_roles`
- Modify: `tests/core/integration/test_user_role_migration.py` — ONLY `TestDDLDefault::test_fresh_db_defaults_perfil_to_user` (phase 0 confirmed it is the single test in that file using `user_repo.db`)
- Verify green, no edits expected: `tests/core/integration/test_user_repo.py`, `tests/core/unit/test_user_repo_standalone.py`, `tests/core/integration/test_user_migration.py`, `tests/core/integration/test_api_auth.py`, the remaining 6 tests of `test_user_role_migration.py`, phase-0's users-router tests

**Interfaces:**
- Consumes: `create_sqlite_engine` (Task 2).
- Produces: `UserRepository` with **unchanged** `__init__(db_path: Path)`, `initialize()`, `close()`, `create()`, `get_by_username()`, `list_all()`, `get_by_id()`, `update()`, `deactivate()` (plus any method phase 0 added — port it with the same mechanical rules). **Removed:** the `db` property (consumers: `main.py`'s two migration helpers + one phase-0 test, all re-expressed here). **Added:** public `session_factory: async_sessionmaker[AsyncSession]` (engine C). Phase-0 names `_migrate_user_roles`, `_seed_default_admin`, `_ROLE_VALUE_MAP` stay importable from `smart_pid_core.main`.

- [ ] **Step 1: Rewrite `user_repo.py`**

Keep the `User` dataclass and `_USERS_DDL` exactly as they exist post-phase-0 (DDL default is `'user'` — do not touch the string). Replace the module imports: drop `import aiosqlite`, add

```python
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from smart_pid_core.adapters.outbound.db_engine import create_sqlite_engine
```

Replace the class:

```python
class UserRepository:
    """CRUD operations on the Usuarios table using its own SQLite database.

    Owns engine C (users.db, main loop, single connection). Credentials
    never travel inside .spid; this engine is never touched by project
    switching.
    """

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._engine: AsyncEngine | None = None
        self.session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
            expire_on_commit=False,
        )

    async def initialize(self) -> None:
        """Open the database, apply PRAGMAs, create the Usuarios table."""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._engine = create_sqlite_engine(self._db_path)
        self.session_factory.configure(bind=self._engine)
        async with self._engine.connect() as conn:
            raw = await conn.get_raw_connection()
            await raw.driver_connection.executescript(_USERS_DDL)
            await raw.driver_connection.commit()

    async def close(self) -> None:
        """Dispose engine C."""
        if self._engine is not None:
            await self._engine.dispose()
            self._engine = None

    async def create(self, username: str, password_hash: str, role: str) -> User:
        """Insert a new user. Raises on duplicate username."""
        async with self.session_factory() as session:
            result = await session.execute(
                text("INSERT INTO Usuarios (nome, senha_hash, perfil) VALUES (:n, :h, :p)"),
                {"n": username, "h": password_hash, "p": role},
            )
            new_id = result.lastrowid
            await session.commit()
        return User(
            id=new_id or 0,
            username=username,
            password_hash=password_hash,
            role=role,
            created_at="",
        )

    async def get_by_username(self, username: str) -> User | None:
        """Return active user or None if not found."""
        async with self.session_factory() as session:
            result = await session.execute(
                text(
                    "SELECT id, nome, senha_hash, perfil, criado_em, ativo"
                    " FROM Usuarios WHERE nome = :n AND ativo = 1"
                ),
                {"n": username},
            )
            row = result.first()
        if row is None:
            return None
        return User(
            id=row[0],
            username=row[1],
            password_hash=row[2],
            role=row[3],
            created_at=row[4],
            active=bool(row[5]),
        )

    async def list_all(self) -> list[User]:
        """Return all users."""
        async with self.session_factory() as session:
            result = await session.execute(
                text(
                    "SELECT id, nome, senha_hash, perfil, criado_em, ativo"
                    " FROM Usuarios ORDER BY id"
                ),
            )
            rows = result.all()
        return [
            User(
                id=r[0], username=r[1], password_hash=r[2],
                role=r[3], created_at=r[4], active=bool(r[5]),
            )
            for r in rows
        ]

    async def get_by_id(self, user_id: int) -> User | None:
        """Return user by id or None if not found."""
        async with self.session_factory() as session:
            result = await session.execute(
                text(
                    "SELECT id, nome, senha_hash, perfil, criado_em, ativo"
                    " FROM Usuarios WHERE id = :uid"
                ),
                {"uid": user_id},
            )
            row = result.first()
        if row is None:
            return None
        return User(
            id=row[0], username=row[1], password_hash=row[2],
            role=row[3], created_at=row[4], active=bool(row[5]),
        )

    async def update(
        self,
        user_id: int,
        role: str | None = None,
        password_hash: str | None = None,
        active: bool | None = None,
    ) -> User | None:
        """Update user fields. Returns updated user or None if not found."""
        updates: list[str] = []
        params: dict = {"uid": user_id}
        if role is not None:
            updates.append("perfil = :role")
            params["role"] = role
        if password_hash is not None:
            updates.append("senha_hash = :hash")
            params["hash"] = password_hash
        if active is not None:
            updates.append("ativo = :active")
            params["active"] = 1 if active else 0
        if not updates:
            return await self.get_by_id(user_id)
        async with self.session_factory() as session:
            await session.execute(
                text(f"UPDATE Usuarios SET {', '.join(updates)} WHERE id = :uid"),  # noqa: S608
                params,
            )
            await session.commit()
        return await self.get_by_id(user_id)

    async def deactivate(self, user_id: int) -> User | None:
        """Soft-delete a user by setting ativo=0."""
        async with self.session_factory() as session:
            await session.execute(
                text("UPDATE Usuarios SET ativo = 0 WHERE id = :uid"),
                {"uid": user_id},
            )
            await session.commit()
        return await self.get_by_id(user_id)
```

(If phase 0 added extra methods — e.g. a password-change helper for the users router — port each with the same pattern: one session, named binds, immediate commit. Do not drop any public method phase 0 introduced.)

- [ ] **Step 2: Re-express the two migration helpers in `main.py`**

Add `from sqlalchemy import text` to `main.py`'s imports.

`_migrate_users_if_needed` (anchors 120–157): the **read side stays raw aiosqlite** (it reads a legacy `.spid` — file-format work, spec §10). Replace only the write block (anchors 144–154):

```python
    user_repo = UserRepository(users_db_path)
    await user_repo.initialize()
    for row in rows:
        with contextlib.suppress(Exception):
            async with user_repo.session_factory() as session:
                await session.execute(
                    text(
                        "INSERT INTO Usuarios (nome, senha_hash, perfil, ativo, criado_em)"
                        " VALUES (:n, :h, :p, :a, :c)"
                    ),
                    {"n": row[0], "h": row[1], "p": row[2], "a": row[3], "c": row[4]},
                )
                await session.commit()
    await user_repo.close()
```

(One session+commit per row so a duplicate-name failure skips only that row — same end state as the old per-statement `suppress` with one trailing commit.)

`_migrate_user_roles` (added by phase 0; runs right after `await user_repo.initialize()` and before `_seed_default_admin`): keep the function name and keep `_ROLE_VALUE_MAP` as the single source of the mapping — only the execution mechanism changes, from `user_repo.db.execute` to engine-C sessions:

```python
async def _migrate_user_roles(user_repo: UserRepository) -> None:
    """One-time role-value migration (spec §9.4): legacy uppercase → new enum."""
    async with user_repo.session_factory() as session:
        for legacy, new in _ROLE_VALUE_MAP:
            await session.execute(
                text("UPDATE Usuarios SET perfil = :new WHERE perfil = :legacy"),
                {"new": new, "legacy": legacy},
            )
        await session.commit()
```

(`_ROLE_VALUE_MAP = (("ADMIN", "admin"), ("SUPERVISOR", "admin"), ("OPERATOR", "user"))` stays module-level and untouched. `_seed_default_admin(user_repo)` is untouched — it only calls `list_all()`/`create()`, whose signatures are stable. All three names remain importable from `smart_pid_core.main` — phase-0 tests import them.)

- [ ] **Step 3: Adapt the ONE phase-0 test that used `user_repo.db`**

In `tests/core/integration/test_user_role_migration.py`, rewrite `TestDDLDefault::test_fresh_db_defaults_perfil_to_user` to exercise the DDL default through an independent raw handle (fixture-style access — stays raw per spec §10) instead of the deleted `db` property:

```python
    @pytest.mark.asyncio
    async def test_fresh_db_defaults_perfil_to_user(self, tmp_path) -> None:
        import aiosqlite

        db_path = tmp_path / "users.db"
        repo = UserRepository(db_path)
        await repo.initialize()
        await repo.close()
        # No public API inserts omitting perfil (by design) — use an
        # independent raw handle to exercise the DDL DEFAULT.
        async with aiosqlite.connect(db_path) as db:
            await db.execute(
                "INSERT INTO Usuarios (nome, senha_hash) VALUES ('nodefault', 'h')"
            )
            await db.commit()
        repo2 = UserRepository(db_path)
        await repo2.initialize()
        users = await repo2.list_all()
        await repo2.close()
        assert [u.role for u in users if u.username == "nodefault"] == ["user"]
```

(Keep the class/test names — the file's other 6 tests are untouched.)

- [ ] **Step 4: Verify**

Run: `uv run pytest tests/core/integration/test_user_repo.py tests/core/unit/test_user_repo_standalone.py tests/core/integration/test_user_migration.py tests/core/integration/test_user_role_migration.py tests/core/integration/test_api_auth.py tests/core/unit/test_rbac.py -q`
Expected: all pass (public API is signature-stable). Also run phase-0's users-router test file — it must stay green.
Gate: `grep -rn "user_repo\.db\|\.db\.execute\|\.db\.commit" packages/smart_pid_core/src` returns nothing.

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/adapters/outbound/user_repo.py packages/smart_pid_core/src/smart_pid_core/main.py tests/core/integration/test_user_role_migration.py
git commit -m "feat(core): UserRepository on engine C; user migrations re-expressed on sessions"
```

---

### Task 10: Delete the legacy connection — `SQLiteRepository.db` is gone

**Files:**
- Modify: `packages/smart_pid_core/src/smart_pid_core/adapters/outbound/sqlite_repo.py` (remove transitional lines)
- Modify (teardown/fixture sweep — every remaining `repo.db` reference in tests):
  - `tests/conftest.py:78` and `:189` (`await repo.db.close()` → `await repo.close()`)
  - `tests/core/api/test_ws_realtime.py:392`
  - `tests/core/integration/test_api_opcua.py:70`
  - `tests/core/integration/test_security_middleware.py:76`
  - `tests/core/unit/test_alarm_worker.py:194`
  - `tests/core/unit/test_commands_monitor_mode.py:76` and `:189`
  - `tests/core/unit/test_get_tuning_recommendations.py:77`
  - plus any further hits the gate grep finds (check `tests/core/integration/test_api_stats.py` and `tests/core/integration/test_audit_api.py` teardowns)

**Interfaces:**
- Consumes: everything from Tasks 4–9 (all borrowers are off `repo.db`).
- Produces: final `SQLiteRepository` shape — no `db` attribute, no `aiosqlite` import in `sqlite_repo.py`; `close()` = `await self.engine.dispose()` only.

- [ ] **Step 1: Remove the transitional connection**

In `sqlite_repo.py`:
- Delete `import aiosqlite` from the imports.
- In `__init__`: delete the `self.db: aiosqlite.Connection` declaration and its TRANSITIONAL comment block.
- In `initialize()`: delete the three legacy lines (`self.db = await aiosqlite.connect(...)`, `self.db.row_factory = aiosqlite.Row`, `await self.db.execute("PRAGMA journal_mode=WAL")`) and the TRANSITIONAL comment.
- In `reopen()`: delete `await self.db.close()`.
- In `close()`: delete `await self.db.close()` — final body:

```python
    async def close(self) -> None:
        """Dispose engine A (finalizes WAL on the pooled connection)."""
        await self.engine.dispose()
```

- [ ] **Step 2: Sweep the test teardowns**

Apply `await repo.db.close()` → `await repo.close()` at every file listed above.

- [ ] **Step 3: Gate greps (all three must print nothing)**

```bash
grep -rn "repo\.db\b" packages/smart_pid_core/src tests
grep -n "self\.db\b" packages/smart_pid_core/src/smart_pid_core/adapters/outbound/sqlite_repo.py
grep -n "aiosqlite" packages/smart_pid_core/src/smart_pid_core/adapters/outbound/sqlite_repo.py
```

Expected: no output. (Remaining `aiosqlite` usage in the tree after this task, all legitimate per spec §10: `project_service.py`'s `list_projects` probe, `main.py`'s legacy-`.spid` read in `_migrate_users_if_needed`, and raw fixture authoring in tests — that is the file format, not the data layer.)

- [ ] **Step 4: Full backend suite**

Run: `uv run pytest tests/core tests/domain -q`
Expected: everything passes. This is the phase's "no shim survives" checkpoint.

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/adapters/outbound/sqlite_repo.py tests
git commit -m "refactor(core): remove legacy aiosqlite connection — SQLAlchemy is the only data layer"
```

---

### Task 11: `.spid` lifecycle — checkpoint, ordered reopen, DB-worker drain, download checkpoint

**Files:**
- Modify: `packages/smart_pid_core/src/smart_pid_core/adapters/outbound/sqlite_repo.py` (add `checkpoint()`, finalize `reopen()`)
- Modify: `packages/smart_pid_core/src/smart_pid_core/application/project_service.py` (constructor `db_worker` param, worker drain around reopen, `prepare_download()` replaces `download_path()`)
- Modify: `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/project.py` (download handler, anchors 131–143)
- Modify: `packages/smart_pid_core/src/smart_pid_core/main.py` (pass `db_worker=db_worker` to `ProjectService`, anchors 445–452)
- Test: `tests/core/integration/test_engine_lifecycle.py` (new)
- Verify green: `tests/core/unit/test_project_service.py`, `tests/core/integration/test_api_project.py`, `tests/core/integration/test_project_auth_required.py`, `tests/core/integration/test_project_export_no_credentials.py`, `tests/core/unit/test_sqlite_repo_new_tables.py`, `tests/core/api/test_opcua_endpoint.py`

**Interfaces:**
- Consumes: `SQLiteRepository.engine/session_factory/db_path` (Task 4), `DBWorker(bus, repo, ...)` (Task 6), `create_sqlite_engine` (Task 2).
- Produces:
  - `SQLiteRepository.checkpoint() -> None` — `PRAGMA wal_checkpoint(TRUNCATE)` on engine A
  - `SQLiteRepository.reopen(db_path: Path)` — final order: checkpoint(A) → dispose(A) → recreate + bootstrap/back-fill
  - `ProjectService.__init__(..., db_worker: DBWorker | None = None)` — new optional kwarg (all existing constructions stay valid)
  - `ProjectService.prepare_download() -> Path` (async; checkpoints then returns the live path). `download_path()` is **deleted** — the router is its only caller.

- [ ] **Step 1: Write the failing lifecycle tests**

Create `tests/core/integration/test_engine_lifecycle.py`:

```python
"""spec §10 .spid lifecycle guarantees: reopen drain, download checkpoint, busy-timeout."""
from __future__ import annotations

import asyncio
import time
import uuid
from pathlib import Path
from unittest.mock import MagicMock

import aiosqlite  # raw probes on bare files/copies — file format, not data layer
import msgpack
import pytest
from sqlalchemy import text

from smart_pid_core.adapters.outbound.db_engine import create_sqlite_engine
from smart_pid_core.adapters.outbound.sqlite_repo import SQLiteRepository
from smart_pid_core.application.event_bus import EventBus
from smart_pid_core.application.project_service import ProjectService
from smart_pid_core.application.workers.db_worker import DBWorker
from smart_pid_domain.models.controller import Controller


@pytest.fixture
async def projects_dir(tmp_path):
    d = tmp_path / "projects"
    d.mkdir()
    return d


@pytest.fixture
async def repo(tmp_path):
    r = SQLiteRepository(tmp_path / "active.spid")
    await r.initialize()
    yield r
    await r.close()


@pytest.fixture
def loop_manager():
    lm = MagicMock()
    lm.stop_all = MagicMock()
    return lm


@pytest.fixture
def service(repo, loop_manager, projects_dir):
    return ProjectService(repo=repo, loop_manager=loop_manager, projects_dir=projects_dir)


class TestReopenDrain:
    @pytest.mark.asyncio
    async def test_switch_away_releases_all_handles_then_delete(
        self, service, projects_dir,
    ) -> None:
        """open → write → switch away: no -wal/-shm sibling survives; delete works."""
        await service.new_project("alpha")
        alpha = projects_dir / "alpha.spid"
        # generate WAL traffic on engine A
        await service._repo.save(Controller(id=0, name="TIC-101"))
        await service.new_project("beta")  # checkpoint + dispose alpha engines
        assert not Path(str(alpha) + "-wal").exists()
        assert not Path(str(alpha) + "-shm").exists()
        await service.delete_project("alpha")
        assert not alpha.exists()

    @pytest.mark.asyncio
    async def test_reopened_file_contains_pre_switch_writes(
        self, service, projects_dir,
    ) -> None:
        """Nothing written before the switch may be stranded in a discarded WAL."""
        await service.new_project("gamma")
        saved = await service._repo.save(Controller(id=0, name="FIC-201"))
        await service.new_project("delta")
        gamma = projects_dir / "gamma.spid"
        async with aiosqlite.connect(gamma) as db:  # the bare file, no live engine
            async with db.execute(
                "SELECT nome FROM Controladores WHERE id = ?", (saved.id,)
            ) as cur:
                row = await cur.fetchone()
        assert row is not None and row[0] == "FIC-201"


class TestDownloadCheckpoint:
    @pytest.mark.asyncio
    async def test_prepare_download_truncates_wal(self, service, repo) -> None:
        for i in range(50):
            await repo.save(Controller(id=0, name=f"LIC-{i:03d}"))
        wal = Path(str(repo.db_path) + "-wal")
        assert wal.exists() and wal.stat().st_size > 0  # WAL has content pre-checkpoint
        path = await service.prepare_download()
        assert path == repo.db_path
        assert wal.stat().st_size == 0  # TRUNCATE folded the WAL into the main file

    @pytest.mark.asyncio
    async def test_downloaded_copy_is_complete_without_wal(
        self, service, repo, tmp_path,
    ) -> None:
        for i in range(20):
            await repo.save(Controller(id=0, name=f"PIC-{i:03d}"))
        path = await service.prepare_download()
        copy = tmp_path / "downloaded.spid"
        copy.write_bytes(path.read_bytes())  # what FileResponse streams: the file ALONE
        async with aiosqlite.connect(copy) as db:
            async with db.execute("SELECT COUNT(*) FROM Controladores") as cur:
                row = await cur.fetchone()
        assert row[0] == 20


class TestBusyTimeout:
    @pytest.mark.asyncio
    async def test_second_writer_waits_instead_of_failing(self, repo) -> None:
        """Two engines on one .spid (the A/B shape): busy_timeout absorbs contention."""
        engine_b = create_sqlite_engine(repo.db_path)

        async def hold_write_lock() -> None:
            async with repo.engine.begin() as conn:
                await conn.execute(
                    text("INSERT INTO Projeto_Meta (chave, valor) VALUES ('locka', '1')"),
                )
                await asyncio.sleep(0.3)  # keep the write txn open

        holder = asyncio.create_task(hold_write_lock())
        await asyncio.sleep(0.05)  # lock is now held by engine A
        # would raise 'database is locked' with busy_timeout=0
        async with engine_b.begin() as conn:
            await conn.execute(
                text("INSERT INTO Projeto_Meta (chave, valor) VALUES ('lockb', '2')"),
            )
        await holder
        async with engine_b.connect() as conn:
            n = (
                await conn.execute(
                    text("SELECT COUNT(*) FROM Projeto_Meta WHERE chave IN ('locka','lockb')"),
                )
            ).scalar()
        assert n == 2
        await engine_b.dispose()


class TestDBWorkerAcrossSwitch:
    @pytest.mark.asyncio
    async def test_project_switch_restarts_worker_onto_new_file(
        self, repo, loop_manager, projects_dir,
    ) -> None:
        """Frames published after a switch land in the NEW project via a fresh engine B."""
        bus = EventBus(url_prefix=f"inproc://test_{uuid.uuid4().hex[:8]}")
        bus.start()
        worker = DBWorker(bus=bus, repo=repo, flush_interval_s=0.1)
        worker.start()
        service = ProjectService(
            repo=repo, loop_manager=loop_manager,
            projects_dir=projects_dir, db_worker=worker,
        )
        try:
            await service.new_project("fresh")  # drains worker, reopens, restarts worker
            pub = bus.create_publisher()
            time.sleep(0.05)
            frame = {
                "controller_id": 7, "pv": 61.0, "sp": 60.0, "co": 31.0,
                "integral_val": 0.5, "timestamp": "2026-07-26T12:00:00+00:00",
                "status": "GOOD",
            }
            pub.send(b"TELEMETRY.7", msgpack.packb(frame))
            time.sleep(0.3)  # worker flush interval + margin
            async with repo.session_factory() as session:
                n = (
                    await session.execute(
                        text("SELECT COUNT(*) FROM Log_Processo WHERE controlador_id = 7"),
                    )
                ).scalar()
            assert n == 1
        finally:
            worker.stop()
            bus.stop()
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/core/integration/test_engine_lifecycle.py -q`
Expected: FAIL — `AttributeError: 'ProjectService' object has no attribute 'prepare_download'`, `TypeError: ProjectService.__init__() got an unexpected keyword argument 'db_worker'`, and the drain test fails on a surviving `-wal` (checkpoint not yet wired).

- [ ] **Step 3: Add `checkpoint()` and finalize `reopen()` in `sqlite_repo.py`**

Insert immediately above `reopen()`:

```python
    async def checkpoint(self) -> None:
        """PRAGMA wal_checkpoint(TRUNCATE) on engine A.

        Folds the WAL into the main file and truncates it to zero bytes, so
        the bare .spid can be streamed (download) or the file abandoned
        (reopen) without losing tail writes. Runs on the raw driver
        connection: PRAGMA must not sit inside an autobegun transaction.
        """
        async with self.engine.connect() as conn:
            raw = await conn.get_raw_connection()
            await raw.driver_connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
```

and replace `reopen()` with the final ordered form:

```python
    async def reopen(self, db_path: Path) -> None:
        """Switch the active .spid — spec §10 lifecycle, engine-A half.

        Order: (1) wal_checkpoint(TRUNCATE) on A, (2) dispose A — no pooled
        handle survives and SQLite removes the -wal/-shm siblings on the last
        close, (3) re-create the engine against the new path and re-run
        bootstrap + back-fill. Engine B's half is handled by ProjectService,
        which stops the DB worker (drain + dispose on its own loop) BEFORE
        calling this and restarts it after.
        """
        await self.checkpoint()
        await self.engine.dispose()
        self._db_path = db_path
        await self.initialize()
```

- [ ] **Step 4: Port `ProjectService`**

In `project_service.py`:

Add `import asyncio` after `import re` at the top of the file.

Constructor (anchors 28–42) — add the optional worker:

```python
    def __init__(
        self,
        repo: SQLiteRepository,
        loop_manager: LoopManager,
        projects_dir: Path,
        simulator_adapter: object | None = None,
        daemon_state: DaemonState | None = None,
        opcua_adapter: object | None = None,
        db_worker: DBWorker | None = None,
    ) -> None:
        self._repo = repo
        self._loop_manager = loop_manager
        self._projects_dir = projects_dir
        self._simulator_adapter = simulator_adapter
        self._daemon_state = daemon_state
        self._opcua_adapter = opcua_adapter
        self._db_worker = db_worker
```

with the `TYPE_CHECKING` import block extended:

```python
if TYPE_CHECKING:
    from smart_pid_core.adapters.outbound.sqlite_repo import SQLiteRepository
    from smart_pid_core.application.daemon_state import DaemonState
    from smart_pid_core.application.loop_manager import LoopManager
    from smart_pid_core.application.workers.db_worker import DBWorker
```

Drain helpers (place next to `_stop_simulator`):

```python
    async def _stop_db_worker(self) -> None:
        """Drain engine B before a project switch.

        stop() joins the worker thread; its finally block flushed pending
        frames into the OLD file and disposed engine B, so no pooled handle
        survives on the old path. Run in a thread so the join never blocks
        the event loop.
        """
        if self._db_worker is not None:
            await asyncio.to_thread(self._db_worker.stop)

    def _start_db_worker(self) -> None:
        """Restart the worker: new thread, new loop, new engine B on the CURRENT path."""
        if self._db_worker is not None:
            self._db_worker.start()
```

Wire the drain into the three switch paths (spec §10 lifecycle — B drained first, then the engine-A half inside `repo.reopen()`, then B recreated on the new path):

- `new_project`: insert `await self._stop_db_worker()` immediately after `self._stop_opcua()` (before `await self._repo.reopen(dest)`); insert `self._start_db_worker()` immediately after the `if self._daemon_state:` block (before `return ProjectResponse(...)`).
- `open_project`: insert `await self._stop_db_worker()` immediately after `self._stop_simulator()` (before `await self._repo.reopen(path)`); insert `self._start_db_worker()` immediately after the `if self._daemon_state:` block (before `return await self.get_current()`).
- `import_project`: insert `await self._stop_db_worker()` immediately after `self._stop_simulator()` (before `await self._repo.reopen(dest)`); insert `self._start_db_worker()` immediately after the `if self._daemon_state:` block (before `return await self.get_current()`).

Replace `download_path()` (anchors 147–149) with:

```python
    async def prepare_download(self) -> Path:
        """Checkpoint engine A, then return the live .spid path for streaming.

        GET /project/download must never stream a file whose recent writes
        still sit in the -wal sibling (spec §10).
        """
        await self._repo.checkpoint()
        return self._repo.db_path
```

(The `_repo._db_path` reads elsewhere in this file — `get_current`, `delete_project`, `is_managed_project_active` — are internal to the service and stay as they are. `list_projects` keeps its raw per-file `aiosqlite.connect` probe verbatim — spec §10.)

- [ ] **Step 5: Update the download route and `main.py` wiring**

`routers/project.py` (anchors 131–143) — keep whatever auth dependency phase 0 left on the route (`require_admin`); change only the handler body:

```python
@router.get("/download")
async def download_project(
    request: Request,
    user: Annotated[UserClaims, Depends(require_admin)],
) -> FileResponse:
    """Download the active project as a .spid file (WAL checkpointed first)."""
    svc = request.app.state.project_service
    path = await svc.prepare_download()
    return FileResponse(
        path=str(path),
        filename=path.name,
        media_type="application/octet-stream",
    )
```

Gate: `grep -rn "download_path" packages tests` must return nothing (the router was the only caller; the route path/response shape is unchanged, so the OpenAPI schema is untouched).

`main.py` (anchors 445–452) — add the worker to the service:

```python
    project_service = ProjectService(
        repo=repo,
        loop_manager=loop_manager,
        projects_dir=settings.projects_dir,
        simulator_adapter=simulator_adapter,
        daemon_state=daemon_state,
        opcua_adapter=opcua_adapter,
        db_worker=db_worker,
    )
```

(`db_worker` is created earlier at anchor 396, so it is in scope.)

- [ ] **Step 6: Run to verify green**

Run: `uv run pytest tests/core/integration/test_engine_lifecycle.py tests/core/unit/test_project_service.py tests/core/integration/test_api_project.py tests/core/integration/test_project_auth_required.py tests/core/integration/test_project_export_no_credentials.py tests/core/unit/test_sqlite_repo_new_tables.py tests/core/api/test_opcua_endpoint.py -q`
Expected: all pass (existing project tests construct `ProjectService` without `db_worker` — the kwarg is optional; `test_opcua_endpoint`'s `MagicMock` repo is unaffected).

- [ ] **Step 7: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/adapters/outbound/sqlite_repo.py packages/smart_pid_core/src/smart_pid_core/application/project_service.py packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/project.py packages/smart_pid_core/src/smart_pid_core/main.py tests/core/integration/test_engine_lifecycle.py
git commit -m "feat(core): .spid lifecycle — WAL checkpoint, ordered reopen, DB-worker drain, download checkpoint"
```

---

### Task 12: Post-port benchmark (before/after comparison)

**Files:**
- Modify: `packages/smart_pid_core/scripts/BENCH.md`

**Interfaces:**
- Consumes: `bench_historian.py` (Task 1) — its feature-detect now selects the SQLAlchemy path.
- Produces: the recorded before/after pair (spec §10 acceptance evidence).

- [ ] **Step 1: Run the benchmark on the ported stack**

Run: `uv run python packages/smart_pid_core/scripts/bench_historian.py`
Expected: first line `flavor=sqlalchemy` (proves the script picked up `repo.session_factory` — the Core executemany path is being measured), then the write/query lines.

- [ ] **Step 2: Record and compare**

Paste the three output lines under the `## After` heading in `packages/smart_pid_core/scripts/BENCH.md`, with date + output of `git rev-parse --short HEAD`.

Acceptance: **after ≥ 0.9 × before in write rows/s.** If lower, the executemany fast path is not engaged — verify `write_batch` passes the whole list of dicts to a single `conn.execute(insert(log_processo), rows)` (per-row execution and `session.add_all()` are the two known ways to lose 10×) and that the PRAGMA listener runs (WAL accidentally off would also tank it). Fix and re-measure; do not close the phase with a regression.

- [ ] **Step 3: Commit**

```bash
git add packages/smart_pid_core/scripts/BENCH.md
git commit -m "chore(core): record post-port historian benchmark (spec §10 before/after)"
```

---

### Task 13: Phase acceptance sweep

**Files:** none (verification only; fix-forward anything it finds, amending the responsible commit style `fix(core): ...`)

**Interfaces:**
- Consumes: the entire phase.
- Produces: the spec §10 acceptance evidence: behavior-level backend tests green, adapted fixture layer, lifecycle tests green, benchmark recorded.

- [ ] **Step 1: Full backend suite**

Run: `uv run pytest tests/core tests/domain -q`
Expected: 0 failures, 0 errors.

- [ ] **Step 2: Lint**

Run: `uv run ruff check packages/smart_pid_core tests/core`
Expected: `All checks passed!` (fix any import-order/unused-import fallout from the port; `uv run ruff check --fix` is fine for mechanical findings).

- [ ] **Step 3: Final coupling greps (all must print nothing)**

```bash
grep -rn "repo\.db\b" packages/smart_pid_core/src tests
grep -rnE "AlarmRepository\(repo\)|AuditRepository\(repo\)|AIRepository\(repo\)|SQLiteHistorian\(repo\)" packages tests
grep -rn "session.add_all" packages/smart_pid_core/src
grep -rn "download_path" packages tests
```

- [ ] **Step 4: Spec §10 acceptance checklist (tick each against the tree)**

- [ ] Three engines: A (`SQLiteRepository.initialize`), B (`DBWorker._run_async`), C (`UserRepository.initialize`) — all via `create_sqlite_engine`.
- [ ] PRAGMA listener applies WAL + busy_timeout=5000 + foreign_keys OFF on every engine (`test_db_engine.py`, FK-inertness tests).
- [ ] DDL bootstrap + `_apply_migrations()` run on every open/reopen (`test_sqlite_repo.py`, `test_db_models.py` parity).
- [ ] Historian hot path is Core executemany, one commit per batch; benchmark before/after recorded in `BENCH.md`.
- [ ] Session-per-method with immediate commit in every repository; `.mappings()` row access; `lastrowid`/`rowcount` on `CursorResult`.
- [ ] `SystemEventRepository` constructor changed; stale-connection bug gone (survives reopen by construction — sessionmaker re-bound in place).
- [ ] Reopen lifecycle checkpoint → dispose (A and B drained) → recreate + bootstrap (`test_engine_lifecycle.py::TestReopenDrain`, `TestDBWorkerAcrossSwitch`).
- [ ] `GET /project/download` checkpoints before streaming (`TestDownloadCheckpoint`).
- [ ] `list_projects` raw aiosqlite probe untouched.
- [ ] Busy-timeout under concurrent A/B writers (`TestBusyTimeout`).
- [ ] No REST route, response model, or WS envelope changed (phase 2's committed codegen sees an identical schema).

- [ ] **Step 5: No commit needed if clean**

If Steps 1–4 found nothing to fix, the phase is complete — nothing to commit.

---

## Interfaces exported (for later phases)

Everything later phases (2–11) may rely on from phase 1. REST routes, response models, and the WS envelope are **unchanged** by this phase — the OpenAPI document phase 2's hermetic codegen consumes is identical before and after phase 1.

### Engine factory — `smart_pid_core.adapters.outbound.db_engine`

```python
def create_sqlite_engine(db_path: Path) -> AsyncEngine
    # AsyncAdaptedQueuePool, pool_size=1, max_overflow=0;
    # connect-listener PRAGMAs: journal_mode=WAL, busy_timeout=5000, foreign_keys=OFF.
    # Used for engines A, B and C. Any future maintenance task needing a
    # read-only engine over a .spid file uses this same factory.
```

### Models — `smart_pid_core.adapters.outbound.db_models`

```python
class SpidBase(DeclarativeBase): ...   # .spid metadata scope
class UsersBase(DeclarativeBase): ...  # users.db metadata scope
# Mapped classes (attribute name == column name, verbatim):
Controladores, ConfiguracaoAlarmes, LogProcesso, LogSintoniaIA, LogAuditoria,
ModelosIA, LogAlarmes, ProjetoMeta, LogSystemEvents, ConfiguracaoSimulador   # SpidBase
Usuarios                                                                     # UsersBase
# Core Table handles:
controladores, configuracao_alarmes, log_processo, log_sintonia_ia,
log_auditoria, modelos_ia, log_alarmes, projeto_meta, log_system_events,
configuracao_simulador, usuarios
# Guard: tests/core/unit/test_db_models.py fails on any model↔DDL column drift.
```

### `SQLiteRepository` — `smart_pid_core.adapters.outbound.sqlite_repo`

```python
class SQLiteRepository:
    def __init__(self, db_path: Path) -> None
    engine: AsyncEngine                                   # engine A; NEW object after each reopen()
    session_factory: async_sessionmaker[AsyncSession]     # STABLE identity; re-bound on reopen()
    @property
    def db_path(self) -> Path                             # active .spid path
    async def initialize(self) -> None                    # engine + DDL bootstrap + back-fill
    async def checkpoint(self) -> None                    # PRAGMA wal_checkpoint(TRUNCATE)
    async def reopen(self, db_path: Path) -> None         # checkpoint → dispose → recreate
    async def close(self) -> None                         # engine.dispose()
    # CRUD (signatures identical to pre-port):
    async def save(self, controller: Controller) -> Controller
    async def get(self, controller_id: int) -> Controller             # raises KeyError
    async def list_all(self) -> list[Controller]
    async def delete(self, controller_id: int) -> None                # raises KeyError
    async def set_meta(self, key: str, value: str) -> None
    async def get_meta(self, key: str) -> str | None
    async def save_sim_config(self, controller_id: int, preset: str, gain: float,
        tau1: float, tau2: float, dead_time: float, pid_enabled: bool = False,
        pid_kp: float = 1.0, pid_ti: float = 10.0, pid_td: float = 0.0,
        pid_mode: int = 0, auto_sp_enabled: bool = False, auto_sp_min_pct: float = 30.0,
        auto_sp_max_pct: float = 70.0, auto_dist_enabled: bool = False,
        auto_dist_max_pct: float = 10.0, pid_sp: float = 50.0) -> None
    async def get_sim_config(self, controller_id: int) -> dict | None
    async def list_sim_configs(self) -> list[dict]
# REMOVED: SQLiteRepository.db (aiosqlite.Connection). Do not reintroduce.
```

### Injection rule (how every data consumer is wired from phase 1 on)

`repo.session_factory` is THE injectable for `.spid` data access on the main loop. It is safe to capture eagerly (constructor injection) because `reopen()` re-binds it in place. Changed constructor signatures:

```python
SQLiteHistorian(session_factory: async_sessionmaker[AsyncSession])
AlarmRepository(session_factory: async_sessionmaker[AsyncSession])
AuditRepository(session_factory: async_sessionmaker[AsyncSession])
AIRepository(session_factory: async_sessionmaker[AsyncSession])
SystemEventRepository(session_factory: async_sessionmaker[AsyncSession])   # was aiosqlite.Connection
DBWorker(bus: EventBus, repo: SQLiteRepository,
         flush_interval_s: float = 5.0, batch_size: int = 500)             # was historian=
```

All repository *method* signatures and return shapes (dicts with the same alias keys — `controller_id`, `alarm_type`, `"limit"`, `status`, ... — and `User`/`Controller`/`TelemetryFrame` objects) are unchanged, so `create_app(...)`, every router, `ExportWorker`, `AlarmWorker`, and `SystemEventWorker` are consumed exactly as before.

### `UserRepository` — `smart_pid_core.adapters.outbound.user_repo`

```python
class UserRepository:
    def __init__(self, db_path: Path) -> None                 # unchanged
    session_factory: async_sessionmaker[AsyncSession]         # NEW public (engine C)
    async def initialize(self) -> None
    async def close(self) -> None
    async def create(self, username: str, password_hash: str, role: str) -> User
    async def get_by_username(self, username: str) -> User | None
    async def list_all(self) -> list[User]
    async def get_by_id(self, user_id: int) -> User | None
    async def update(self, user_id: int, role: str | None = None,
                     password_hash: str | None = None, active: bool | None = None) -> User | None
    async def deactivate(self, user_id: int) -> User | None
# REMOVED: UserRepository.db property. users.db writes outside this class go
# through user_repo.session_factory (see _migrate_users_if_needed / _migrate_user_roles).
```

### `ProjectService` — `smart_pid_core.application.project_service`

```python
ProjectService(repo, loop_manager, projects_dir, simulator_adapter=None,
               daemon_state=None, opcua_adapter=None, db_worker=None)
async def prepare_download(self) -> Path    # checkpoints engine A, returns live .spid path
# REMOVED: download_path() (sync). Router calls prepare_download().
# new_project/open_project/import_project drain+restart the DB worker around repo.reopen().
```

### `main.py` phase-0 names (kept importable, now on sessions)

```python
_ROLE_VALUE_MAP: tuple[tuple[str, str], ...]              # (("ADMIN","admin"),("SUPERVISOR","admin"),("OPERATOR","user"))
async def _migrate_user_roles(user_repo: UserRepository) -> None    # engine-C sessions
async def _seed_default_admin(user_repo: UserRepository) -> None    # untouched (public API only)
async def _migrate_users_if_needed(spid_path: Path, users_db_path: Path) -> None
async def _load_alarm_configs(session_factory) -> dict[int, AlarmConfig]
async def _retention_cleanup(session_factory, interval_hours: int = 24) -> None
```

### Guarantees later phases build on

- **Roles/auth surface (phase 2 codegen, phases 4–10 frontend):** untouched by phase 1; regenerating the OpenAPI dump after phase 1 yields no diff.
- **`GET /project/download`** (phase 10 projects UI): same route, same response; the streamed `.spid` is now guaranteed WAL-complete.
- **Realtime (`phase 3 RealtimeProvider`)**: WS envelope and `RealtimeWS` bridge untouched.
- **Historian throughput** (phase 4/7 trends): Core executemany pinned; `packages/smart_pid_core/scripts/bench_historian.py` + `BENCH.md` remain in-tree for regression checks.
- **`tests/core/integration/test_engine_lifecycle.py`** is the permanent guard for the reopen/download/delete/busy-timeout invariants; extend it (do not fork it) if later phases touch project lifecycle.
