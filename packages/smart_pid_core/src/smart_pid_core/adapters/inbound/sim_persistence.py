"""Shared helper to persist a SimulatorAdapter's controller state to the repo.

Used by:
- REST router /simulator/... endpoints (explicit user actions).
- Main-loop background flusher that drains the adapter's dirty set after
  OPC-UA-initiated mutations (e.g. fuzzy-tuned Ti).
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from smart_pid_core.adapters.inbound.simulator_adapter import SimulatorAdapter
    from smart_pid_core.adapters.outbound.sqlite_repo import SQLiteRepository


async def persist_sim_config(
    adapter: SimulatorAdapter,
    repo: SQLiteRepository,
    controller_id: int,
) -> None:
    """Read current sim state from *adapter* and persist it via *repo*."""
    try:
        cfg = adapter.get_config_dict(controller_id)
    except KeyError:
        return
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
