"""Project lifecycle orchestration — new, open, import, download, delete."""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import aiosqlite

from smart_pid_domain.dtos.project import ProjectListItem, ProjectResponse

if TYPE_CHECKING:
    from smart_pid_core.adapters.outbound.sqlite_repo import SQLiteRepository
    from smart_pid_core.application.loop_manager import LoopManager


class ProjectService:
    """Manages project files in a backend-controlled directory."""

    def __init__(
        self,
        repo: SQLiteRepository,
        loop_manager: LoopManager,
        projects_dir: Path,
        simulator_adapter: object | None = None,
    ) -> None:
        self._repo = repo
        self._loop_manager = loop_manager
        self._projects_dir = projects_dir
        self._simulator_adapter = simulator_adapter

    @property
    def projects_dir(self) -> Path:
        return self._projects_dir

    async def get_current(self) -> ProjectResponse:
        """Return metadata about the currently-open project."""
        name = await self._repo.get_meta("nome") or self._repo._db_path.stem
        controllers = await self._repo.list_all()
        return ProjectResponse(
            name=name,
            path=self._repo._db_path.name,
            controller_count=len(controllers),
        )

    async def list_projects(self) -> list[ProjectListItem]:
        """List all .spid files in the projects directory."""
        items: list[ProjectListItem] = []
        for spid in sorted(self._projects_dir.glob("*.spid")):
            count = 0
            try:
                async with aiosqlite.connect(spid) as db:
                    async with db.execute(
                        "SELECT COUNT(*) FROM Controladores"
                    ) as cur:
                        row = await cur.fetchone()
                        count = row[0] if row else 0
            except Exception:
                pass
            items.append(ProjectListItem(
                name=spid.stem,
                controller_count=count,
                size_bytes=spid.stat().st_size,
            ))
        return items

    async def new_project(self, name: str) -> ProjectResponse:
        """Create a new empty project in the projects directory."""
        dest = self._projects_dir / f"{name}.spid"
        if dest.exists():
            raise FileExistsError(f"Project '{name}' already exists")
        self._loop_manager.stop_all()
        self._stop_simulator()
        await self._repo.reopen(dest)
        await self._repo.set_meta("nome", name)
        return ProjectResponse(
            name=name,
            path=dest.name,
            controller_count=0,
        )

    async def open_project(self, name: str) -> ProjectResponse:
        """Open an existing project by name."""
        path = self._projects_dir / f"{name}.spid"
        if not path.exists():
            raise FileNotFoundError(f"Project '{name}' not found")
        self._loop_manager.stop_all()
        self._stop_simulator()
        await self._repo.reopen(path)
        await self._load_simulator_configs()
        return await self.get_current()

    async def import_project(self, name: str, data: bytes) -> ProjectResponse:
        """Import an uploaded .spid file into the projects directory."""
        dest = self._projects_dir / f"{name}.spid"
        if dest.exists():
            raise FileExistsError(f"Project '{name}' already exists")
        dest.write_bytes(data)
        self._loop_manager.stop_all()
        self._stop_simulator()
        await self._repo.reopen(dest)
        await self._load_simulator_configs()
        return await self.get_current()

    def download_path(self) -> Path:
        """Return the filesystem path of the active project for download."""
        return self._repo._db_path

    async def delete_project(self, name: str) -> None:
        """Delete a project file. Cannot delete the active project."""
        path = self._projects_dir / f"{name}.spid"
        if not path.exists():
            raise FileNotFoundError(f"Project '{name}' not found")
        if path == self._repo._db_path:
            raise ValueError(f"Cannot delete the active project '{name}'")
        path.unlink()

    def is_managed_project_active(self) -> bool:
        """Return True if the active project is inside the projects directory."""
        try:
            self._repo._db_path.resolve().relative_to(
                self._projects_dir.resolve()
            )
            return True
        except ValueError:
            return False

    async def _load_simulator_configs(self) -> None:
        """Restore simulator state from Configuracao_Simulador."""
        if self._simulator_adapter is None:
            return
        if not hasattr(self._simulator_adapter, "load_sim_config"):
            return
        configs = await self._repo.list_sim_configs()
        for cfg in configs:
            self._simulator_adapter.load_sim_config(cfg)

    def _stop_simulator(self) -> None:
        """Stop the simulator adapter if present."""
        if self._simulator_adapter is not None and hasattr(
            self._simulator_adapter, "stop"
        ):
            self._simulator_adapter.stop()
