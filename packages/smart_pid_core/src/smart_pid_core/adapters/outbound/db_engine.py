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
