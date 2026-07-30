"""Shared helper to persist a SimulatorAdapter's controller state to the repo.

Used by:
- REST router /simulator/... endpoints (explicit user actions).
- Main-loop background flusher that drains the adapter's dirty set after
  OPC-UA-initiated mutations (e.g. fuzzy-tuned Ti).

Failure policy
--------------
A simulator mutation applies to the in-memory adapter FIRST; this helper only
writes that state through. So a persistence failure means "the operator's
change took effect but will not survive a restart" — not "the request failed".
Raising here turned that into an HTTP 500 on ``/simulator/{id}/pid/mode`` even
though the change was live, which is actively misleading.

A terminal failure is reported as ``False`` plus a structured
``sim_persist_failed`` log rather than an exception. Callers that want to
surface it to the operator can act on the return value; ignoring it degrades to
"applied but not persisted", which is the truthful outcome.

Retry policy
------------
SQLite's ``busy_timeout`` already does the waiting for the common case (one
writer queued behind another), so retrying after the budget is exhausted just
adds latency to a request that is already slow — sustained contention will not
clear in another 100 ms. A lock error that comes back *fast*, however, means the
busy handler was bypassed entirely (``SQLITE_BUSY_SNAPSHOT``: a connection
holding a read snapshot tried to promote to a write), and that one is worth an
immediate cheap retry.

So the retry is conditional on how long the failure took: fast failures retry,
budget-exhausted failures do not. That keeps the worst case at roughly one
``busy_timeout`` instead of ``_MAX_ATTEMPTS`` of them.
"""
from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING

import structlog
from sqlalchemy.exc import OperationalError

from smart_pid_core.adapters.outbound.db_engine import SQLITE_BUSY_TIMEOUT_MS

if TYPE_CHECKING:
    from smart_pid_core.adapters.inbound.simulator_adapter import SimulatorAdapter
    from smart_pid_core.adapters.outbound.sqlite_repo import SQLiteRepository

_log = structlog.get_logger()

#: Total attempts for one persist. ``INSERT OR REPLACE`` is idempotent, so a
#: retry is always safe.
_MAX_ATTEMPTS = 3

#: Base backoff between attempts, doubled each time (0.1 s, 0.2 s).
_RETRY_BACKOFF_S = 0.1

#: Fraction of the busy budget that counts as "the handler really did wait".
#: Above this, contention is sustained and retrying only adds latency.
_BUDGET_CONSUMED_RATIO = 0.8


def _is_lock_error(exc: OperationalError) -> bool:
    """True when *exc* is SQLite's write-lock contention error."""
    message = str(exc.orig if exc.orig is not None else exc).lower()
    return "database is locked" in message or "database is busy" in message


async def persist_sim_config(
    adapter: SimulatorAdapter,
    repo: SQLiteRepository,
    controller_id: int,
) -> bool:
    """Read current sim state from *adapter* and persist it via *repo*.

    Returns ``True`` when the row was written, ``False`` when the controller is
    unknown to the adapter or the write could not be completed. Never raises on
    lock contention.
    """
    try:
        cfg = adapter.get_config_dict(controller_id)
    except KeyError:
        return False

    for attempt in range(1, _MAX_ATTEMPTS + 1):
        started = time.monotonic()
        try:
            await repo.save_sim_config(
                controller_id=cfg["controller_id"],
                preset=cfg["preset"],
                gain=cfg["gain"],
                tau1=cfg["tau1"],
                tau2=cfg["tau2"],
                dead_time=cfg["dead_time"],
                pid_enabled=cfg["pid_enabled"],
                pid_kp=cfg["pid_kp"],
                pid_ti=cfg["pid_ti"],
                pid_td=cfg["pid_td"],
                pid_mode=cfg["pid_mode"],
                auto_sp_enabled=cfg["auto_sp_enabled"],
                auto_sp_min_pct=cfg["auto_sp_min_pct"],
                auto_sp_max_pct=cfg["auto_sp_max_pct"],
                auto_dist_enabled=cfg["auto_dist_enabled"],
                auto_dist_max_pct=cfg["auto_dist_max_pct"],
                pid_sp=cfg.get("pid_sp", 50.0),
            )
        except OperationalError as exc:
            waited_ms = (time.monotonic() - started) * 1000
            budget_exhausted = (
                waited_ms >= SQLITE_BUSY_TIMEOUT_MS * _BUDGET_CONSUMED_RATIO
            )
            give_up = (
                not _is_lock_error(exc)
                or budget_exhausted
                or attempt == _MAX_ATTEMPTS
            )
            if give_up:
                _log.error(
                    "sim_persist_failed",
                    controller_id=controller_id,
                    attempts=attempt,
                    waited_ms=round(waited_ms),
                    busy_budget_exhausted=budget_exhausted,
                    reason=str(exc.orig if exc.orig is not None else exc),
                    detail="simulator change is live in memory but was not saved",
                )
                return False
            await asyncio.sleep(_RETRY_BACKOFF_S * (2 ** (attempt - 1)))
        else:
            if attempt > 1:
                _log.warning(
                    "sim_persist_recovered",
                    controller_id=controller_id,
                    attempts=attempt,
                )
            return True
    return False
