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
PRAGMAs: ``journal_mode=WAL``, ``busy_timeout`` (see
``SQLITE_BUSY_TIMEOUT_MS``; two ``.spid`` writers now exist under WAL), and
``foreign_keys`` explicitly OFF — the DDL's ``ON DELETE CASCADE`` clauses are
deliberately inert today; enabling FKs would activate cascades and new FK
violations, a forbidden behavior change.

Engines A and B write the same ``.spid`` concurrently. WAL admits exactly one
writer at a time; the loser blocks in SQLite's busy handler for at most
``busy_timeout`` and then raises ``database is locked``. The budget therefore
has to outlast the *longest* write another engine can hold, which is set by
``DBWorker.flush_interval_s`` (5.0 s by default) plus whatever commit and WAL
autocheckpoint work that batch triggers on a multi-hundred-MB project file.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import AsyncAdaptedQueuePool

if TYPE_CHECKING:
    from pathlib import Path

#: How long a blocked writer waits for the WAL write lock before SQLite gives
#: up with ``database is locked``. Sized at 3x ``DBWorker.flush_interval_s``
#: (5.0 s) so a writer can ride out several consecutive telemetry flushes,
#: while staying below SQLAlchemy's 30 s pool checkout timeout — a request must
#: never be able to burn the pool wait *and* the busy wait back to back.
SQLITE_BUSY_TIMEOUT_MS = 15_000


def _apply_sqlite_pragmas(dbapi_connection: Any, connection_record: Any) -> None:  # noqa: ARG001
    """Sync ``connect`` listener run for every new pooled connection.

    ``dbapi_connection`` is SQLAlchemy's pep-249 adapter over the aiosqlite
    connection; sync-style cursor calls here drive the async driver
    internally (the documented recipe for asyncio dialects).
    """
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute(f"PRAGMA busy_timeout={SQLITE_BUSY_TIMEOUT_MS}")
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
