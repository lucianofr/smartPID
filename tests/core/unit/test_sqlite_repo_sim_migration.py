"""Regression tests for Configuracao_Simulador forward migration + write locking.

Two defects are covered here:

1. **Schema drift.** ``Configuracao_Simulador`` went through three generations:

   * gen1 (<= commit 3dec29c) — 6 columns, no PID block.
   * gen2 (commit 5421327^) — 11 columns, ``pid_*`` added to ``_DDL`` with NO
     back-fill in ``_apply_migrations``.
   * gen3 (commit 5421327) — 17 columns, ``auto_*``/``pid_sp`` added WITH a
     back-fill.

   ``CREATE TABLE IF NOT EXISTS`` silently leaves an older table in place, so a
   gen1/gen2 ``.spid`` kept a narrow table and ``save_sim_config`` failed with
   ``table Configuracao_Simulador has no column named pid_enabled``.

2. **Write-lock contention.** Two connections write one ``.spid`` under WAL
   (engine A on the main loop, engine B on the DB-worker loop). WAL allows a
   single writer; the loser waits ``busy_timeout`` and then raises
   ``database is locked``.
"""
from __future__ import annotations

import asyncio
import sqlite3
import time

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from smart_pid_core.adapters.inbound import sim_persistence
from smart_pid_core.adapters.inbound.sim_persistence import persist_sim_config
from smart_pid_core.adapters.outbound.db_engine import (
    SQLITE_BUSY_TIMEOUT_MS,
    create_sqlite_engine,
)
from smart_pid_core.adapters.outbound.sqlite_repo import SQLiteRepository

# Historical DDL, reproduced verbatim from git history so the test keeps
# describing the real on-disk shape rather than a guess.
_GEN1_SIM_DDL = """
CREATE TABLE Configuracao_Simulador (
    controlador_id INTEGER PRIMARY KEY,
    preset         TEXT NOT NULL DEFAULT 'fopdt_default',
    gain           REAL NOT NULL,
    tau1           REAL NOT NULL,
    tau2           REAL NOT NULL,
    dead_time      REAL NOT NULL
);
"""

_GEN2_SIM_DDL = """
CREATE TABLE Configuracao_Simulador (
    controlador_id INTEGER PRIMARY KEY,
    preset         TEXT NOT NULL DEFAULT 'fopdt_default',
    gain           REAL NOT NULL,
    tau1           REAL NOT NULL,
    tau2           REAL NOT NULL,
    dead_time      REAL NOT NULL,
    pid_enabled    INTEGER NOT NULL DEFAULT 0,
    pid_kp         REAL NOT NULL DEFAULT 1.0,
    pid_ti         REAL NOT NULL DEFAULT 10.0,
    pid_td         REAL NOT NULL DEFAULT 0.0,
    pid_mode       INTEGER NOT NULL DEFAULT 0
);
"""

# Every column the current save_sim_config INSERT names.
_EXPECTED_SIM_COLUMNS = (
    "controlador_id", "preset", "gain", "tau1", "tau2", "dead_time",
    "pid_enabled", "pid_kp", "pid_ti", "pid_td", "pid_mode",
    "auto_sp_enabled", "auto_sp_min_pct", "auto_sp_max_pct",
    "auto_dist_enabled", "auto_dist_max_pct", "pid_sp",
    "auto_sp_period_s", "auto_dist_period_s", "pv_min", "pv_max",
)

_FULL_SAVE_KWARGS = {
    "controller_id": 1, "preset": "TEMPERATURE",
    "gain": 1.5, "tau1": 60.0, "tau2": 20.0, "dead_time": 10.0,
    "pid_enabled": True, "pid_kp": 0.64, "pid_ti": 38.5, "pid_td": 4.2,
    "pid_mode": 1,
    "auto_sp_enabled": True, "auto_sp_min_pct": 45.0, "auto_sp_max_pct": 70.0,
    "auto_dist_enabled": False, "auto_dist_max_pct": 10.0, "pid_sp": 50.0,
    "auto_sp_period_s": 360.0, "auto_dist_period_s": 45.0,
    "pv_min": -50.0, "pv_max": 250.0,
}


def _build_legacy_db(path, sim_ddl: str) -> None:
    """Create a pre-existing .spid holding only a legacy simulator table."""
    con = sqlite3.connect(path)
    con.executescript(sim_ddl)
    con.commit()
    con.close()


def _sim_columns(path) -> list[str]:
    con = sqlite3.connect(path)
    try:
        return [r[1] for r in con.execute("PRAGMA table_info(Configuracao_Simulador)")]
    finally:
        con.close()


class TestLegacySimSchemaMigration:
    """A stale .spid must be brought forward to the current DDL on open."""

    @pytest.mark.parametrize(
        ("label", "ddl"),
        [
            pytest.param("gen1", _GEN1_SIM_DDL, id="gen1_6_columns"),
            pytest.param("gen2", _GEN2_SIM_DDL, id="gen2_11_columns"),
        ],
    )
    async def test_legacy_db_gains_every_column_the_insert_needs(
        self, tmp_path, label: str, ddl: str,
    ) -> None:
        db_path = tmp_path / f"{label}.spid"
        _build_legacy_db(db_path, ddl)
        before = _sim_columns(db_path)
        assert "pid_sp" not in before, "fixture must start stale"

        repo = SQLiteRepository(db_path)
        await repo.initialize()
        try:
            after = _sim_columns(db_path)
            missing = [c for c in _EXPECTED_SIM_COLUMNS if c not in after]
            assert not missing, f"migration left columns missing: {missing}"
        finally:
            await repo.close()

    @pytest.mark.parametrize(
        ("label", "ddl"),
        [
            pytest.param("gen1", _GEN1_SIM_DDL, id="gen1_6_columns"),
            pytest.param("gen2", _GEN2_SIM_DDL, id="gen2_11_columns"),
        ],
    )
    async def test_save_sim_config_succeeds_on_migrated_legacy_db(
        self, tmp_path, label: str, ddl: str,
    ) -> None:
        """This is the exact call that raised 'no column named pid_enabled'."""
        db_path = tmp_path / f"{label}.spid"
        _build_legacy_db(db_path, ddl)

        repo = SQLiteRepository(db_path)
        await repo.initialize()
        try:
            await repo.save_sim_config(**_FULL_SAVE_KWARGS)
            cfg = await repo.get_sim_config(1)
            assert cfg is not None
            assert cfg["pid_enabled"] is True
            assert cfg["pid_kp"] == 0.64
            assert cfg["pid_ti"] == 38.5
            assert cfg["pid_mode"] == 1
            assert cfg["auto_sp_min_pct"] == 45.0
            assert cfg["pid_sp"] == 50.0
        finally:
            await repo.close()

    async def test_legacy_rows_are_preserved_with_defaults(self, tmp_path) -> None:
        """ALTER TABLE ADD COLUMN must keep existing rows and default the rest."""
        db_path = tmp_path / "withrow.spid"
        _build_legacy_db(db_path, _GEN1_SIM_DDL)
        con = sqlite3.connect(db_path)
        con.execute(
            "INSERT INTO Configuracao_Simulador"
            " (controlador_id, preset, gain, tau1, tau2, dead_time)"
            " VALUES (7, 'LEGACY', 3.0, 5.0, 1.0, 2.0)"
        )
        con.commit()
        con.close()

        repo = SQLiteRepository(db_path)
        await repo.initialize()
        try:
            cfg = await repo.get_sim_config(7)
            assert cfg is not None
            assert cfg["preset"] == "LEGACY"
            assert cfg["gain"] == 3.0
            # back-filled columns land on their DDL defaults
            assert cfg["pid_enabled"] is False
            assert cfg["pid_kp"] == 1.0
            assert cfg["pid_ti"] == 10.0
            assert cfg["auto_sp_min_pct"] == 30.0
            assert cfg["pid_sp"] == 50.0
        finally:
            await repo.close()

    async def test_migration_is_idempotent(self, tmp_path) -> None:
        """Re-opening an already-current file must not fail or duplicate work."""
        db_path = tmp_path / "idem.spid"
        _build_legacy_db(db_path, _GEN1_SIM_DDL)
        repo = SQLiteRepository(db_path)
        await repo.initialize()
        first = _sim_columns(db_path)
        await repo.close()

        repo2 = SQLiteRepository(db_path)
        await repo2.initialize()  # must not raise "duplicate column name"
        try:
            assert _sim_columns(db_path) == first
            await repo2.save_sim_config(**_FULL_SAVE_KWARGS)
        finally:
            await repo2.close()


class TestConcurrentWriters:
    """Engine A (main loop) and engine B (DB worker) share one .spid file."""

    async def test_busy_timeout_covers_db_worker_flush_interval(self) -> None:
        """Sizing invariant: the busy budget must outlast a flush window.

        DBWorker flushes every ``flush_interval_s`` (default 5.0 s). A
        busy_timeout equal to that period lets a single slow flush starve the
        other writer for the whole window, which is what produced the observed
        HTTP 500s.
        """
        import inspect

        from smart_pid_core.application.workers.db_worker import DBWorker

        default_flush_s = (
            inspect.signature(DBWorker.__init__).parameters["flush_interval_s"].default
        )
        min_required_ms = default_flush_s * 1000 * 3
        assert min_required_ms <= SQLITE_BUSY_TIMEOUT_MS, (
            f"busy_timeout {SQLITE_BUSY_TIMEOUT_MS}ms must leave headroom over "
            f"several {default_flush_s}s flush windows (>= {min_required_ms}ms)"
        )

    async def test_writer_waits_out_a_competing_write_lock(self, tmp_path) -> None:
        """A blocked writer must wait for the lock, not raise 'database is locked'."""
        db_path = tmp_path / "contended.spid"
        repo = SQLiteRepository(db_path)
        await repo.initialize()

        hold_s = 1.0
        engine_b = create_sqlite_engine(db_path)
        lock_acquired = asyncio.Event()

        async def hold_write_lock() -> None:
            async with engine_b.connect() as conn:
                raw = await conn.get_raw_connection()
                driver = raw.driver_connection
                # BEGIN IMMEDIATE takes the WAL write lock straight away.
                await driver.execute("BEGIN IMMEDIATE")
                await driver.execute(
                    "INSERT INTO Log_Processo"
                    " (controlador_id, timestamp, pv, sp, co, integral_val)"
                    " VALUES (1, '2026-07-30T00:00:00+00:00', 1.0, 1.0, 1.0, 0.0)"
                )
                lock_acquired.set()
                await asyncio.sleep(hold_s)
                await driver.commit()

        holder = asyncio.create_task(hold_write_lock())
        try:
            await asyncio.wait_for(lock_acquired.wait(), timeout=5.0)
            started = time.monotonic()
            # Must block until the holder commits, then succeed.
            await repo.save_sim_config(**_FULL_SAVE_KWARGS)
            waited = time.monotonic() - started
            assert waited >= hold_s * 0.5, (
                f"expected to block on the write lock, returned in {waited:.3f}s"
            )
            cfg = await repo.get_sim_config(1)
            assert cfg is not None
            assert cfg["pid_enabled"] is True
        finally:
            await holder
            await engine_b.dispose()
            await repo.close()

    async def test_interleaved_writes_from_both_engines_never_lock(
        self, tmp_path,
    ) -> None:
        """Engine A sim writes interleaved with engine B telemetry batches."""
        db_path = tmp_path / "interleaved.spid"
        repo = SQLiteRepository(db_path)
        await repo.initialize()
        engine_b = create_sqlite_engine(db_path)
        rounds = 25
        errors: list[str] = []

        async def sim_writer() -> None:
            for i in range(rounds):
                try:
                    await repo.save_sim_config(
                        **{**_FULL_SAVE_KWARGS, "controller_id": (i % 5) + 1},
                    )
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"engineA: {exc}")
                await asyncio.sleep(0)

        async def telemetry_writer() -> None:
            for i in range(rounds):
                try:
                    async with engine_b.begin() as conn:
                        await conn.execute(
                            text(
                                "INSERT INTO Log_Processo (controlador_id,"
                                " timestamp, pv, sp, co, integral_val)"
                                " VALUES (:cid, :ts, 1.0, 1.0, 1.0, 0.0)"
                            ),
                            [
                                {"cid": 1, "ts": f"2026-07-30T00:00:{i:02d}+00:00"}
                                for _ in range(50)
                            ],
                        )
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"engineB: {exc}")
                await asyncio.sleep(0)

        try:
            await asyncio.gather(sim_writer(), telemetry_writer())
            locked = [e for e in errors if "database is locked" in e]
            assert not locked, f"lock contention surfaced: {locked[:3]}"
            assert not errors, f"unexpected write errors: {errors[:3]}"
        finally:
            await engine_b.dispose()
            await repo.close()


class _StubAdapter:
    """Minimal stand-in exposing only what persist_sim_config reads."""

    def __init__(self, known: bool = True) -> None:
        self._known = known

    def get_config_dict(self, controller_id: int) -> dict:
        if not self._known:
            raise KeyError(controller_id)
        return {
            "controller_id": controller_id, "preset": "TEMPERATURE",
            "gain": 1.5, "tau1": 60.0, "tau2": 20.0, "dead_time": 10.0,
            "pid_enabled": True, "pid_kp": 0.64, "pid_ti": 38.5,
            "pid_td": 4.2, "pid_mode": 1,
            "auto_sp_enabled": True, "auto_sp_min_pct": 45.0,
            "auto_sp_max_pct": 70.0, "auto_dist_enabled": False,
            "auto_dist_max_pct": 10.0, "pid_sp": 50.0,
            "auto_sp_period_s": 360.0, "auto_dist_period_s": 45.0,
            "pv_min": -50.0, "pv_max": 250.0,
        }


class _StubRepo:
    """Repo whose save_sim_config fails a configurable number of times."""

    def __init__(
        self,
        failures: int,
        exc: Exception | None = None,
        delay_s: float = 0.0,
    ) -> None:
        self._remaining = failures
        self._exc = exc or OperationalError("INSERT", {}, sqlite3.OperationalError(
            "database is locked",
        ))
        self._delay_s = delay_s
        self.calls = 0

    async def save_sim_config(self, **_kwargs: object) -> None:
        self.calls += 1
        if self._remaining > 0:
            self._remaining -= 1
            if self._delay_s:
                await asyncio.sleep(self._delay_s)
            raise self._exc


class TestPersistSimConfigFailurePolicy:
    """A failed write must not become an HTTP 500 — the change is already live."""

    async def test_returns_false_instead_of_raising_on_lock(self) -> None:
        repo = _StubRepo(failures=99)
        # Must not raise: the router would turn that into a 500.
        assert await persist_sim_config(_StubAdapter(), repo, 2) is False
        assert repo.calls == 3, "expected the bounded retry to run every attempt"

    async def test_retry_recovers_from_a_transient_lock(self) -> None:
        repo = _StubRepo(failures=1)
        assert await persist_sim_config(_StubAdapter(), repo, 2) is True
        assert repo.calls == 2

    async def test_success_first_try_reports_true(self) -> None:
        repo = _StubRepo(failures=0)
        assert await persist_sim_config(_StubAdapter(), repo, 2) is True
        assert repo.calls == 1

    async def test_unknown_controller_reports_false_without_writing(self) -> None:
        repo = _StubRepo(failures=0)
        assert await persist_sim_config(_StubAdapter(known=False), repo, 99) is False
        assert repo.calls == 0

    async def test_exhausted_busy_budget_is_not_retried(self, monkeypatch) -> None:
        """Sustained contention must not be retried — it only adds latency.

        A lock error that already burned the busy budget means SQLite waited and
        lost; another attempt will wait again for nothing.
        """
        monkeypatch.setattr(sim_persistence, "SQLITE_BUSY_TIMEOUT_MS", 50)
        repo = _StubRepo(failures=99, delay_s=0.06)  # > 80% of the 50 ms budget
        assert await persist_sim_config(_StubAdapter(), repo, 2) is False
        assert repo.calls == 1, "a fully-consumed busy budget must not be retried"

    async def test_schema_error_is_not_retried_and_does_not_raise(self) -> None:
        """A non-lock OperationalError (e.g. the old schema drift) fails fast."""
        schema_exc = OperationalError(
            "INSERT", {},
            sqlite3.OperationalError(
                "table Configuracao_Simulador has no column named pid_enabled",
            ),
        )
        repo = _StubRepo(failures=99, exc=schema_exc)
        assert await persist_sim_config(_StubAdapter(), repo, 2) is False
        assert repo.calls == 1, "a schema error must not be retried"
