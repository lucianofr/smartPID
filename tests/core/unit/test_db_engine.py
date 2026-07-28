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
