"""Project lifecycle orchestration — new, open, save-as."""
from __future__ import annotations

import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from smart_pid_domain.dtos.project import ProjectResponse

if TYPE_CHECKING:
    from smart_pid_core.adapters.outbound.sqlite_repo import SQLiteRepository
    from smart_pid_core.application.loop_manager import LoopManager


class ProjectService:
    """Manages project file lifecycle (create, open, save-as)."""

    def __init__(
        self,
        repo: SQLiteRepository,
        loop_manager: LoopManager,
        simulator_adapter: object | None = None,
    ) -> None:
        self._repo = repo
        self._loop_manager = loop_manager
        self._simulator_adapter = simulator_adapter

    async def get_current(self) -> ProjectResponse:
        """Return metadata about the currently-open project."""
        name = await self._repo.get_meta("nome") or self._repo._db_path.stem
        controllers = await self._repo.list_all()
        return ProjectResponse(
            name=name,
            path=str(self._repo._db_path),
            controller_count=len(controllers),
        )

    async def new_project(self, name: str, path: Path) -> ProjectResponse:
        """Stop loops, create a fresh .spid file, store metadata."""
        self._loop_manager.stop_all()
        self._stop_simulator()
        await self._repo.reopen(path)
        now = datetime.now(UTC).isoformat()
        await self._repo.set_meta("nome", name)
        await self._repo.set_meta("criado_em", now)
        return ProjectResponse(
            name=name,
            path=str(path),
            controller_count=0,
        )

    async def open_project(self, path: Path) -> ProjectResponse:
        """Stop loops and open an existing .spid file."""
        if not path.exists():
            raise FileNotFoundError(f"Project file not found: {path}")
        self._loop_manager.stop_all()
        self._stop_simulator()
        await self._repo.reopen(path)
        await self._load_simulator_configs()
        return await self.get_current()

    async def _load_simulator_configs(self) -> None:
        """Restore simulator state from Configuracao_Simulador."""
        if self._simulator_adapter is None:
            return
        if not hasattr(self._simulator_adapter, "load_sim_config"):
            return
        configs = await self._repo.list_sim_configs()
        for cfg in configs:
            self._simulator_adapter.load_sim_config(cfg)

    async def save_as(self, path: Path) -> ProjectResponse:
        """Copy the current DB to *path* and reopen at the new location."""
        # Commit pending writes then close
        await self._repo.db.commit()
        await self._repo.db.close()
        # Copy the file
        shutil.copy2(self._repo._db_path, path)
        # Reopen at the new path (does NOT stop loops)
        self._repo._db_path = path
        await self._repo.initialize()
        return await self.get_current()

    def _stop_simulator(self) -> None:
        """Stop the simulator adapter if present."""
        if self._simulator_adapter is not None and hasattr(
            self._simulator_adapter, "stop"
        ):
            self._simulator_adapter.stop()
