"""Project lifecycle orchestration — new, open, import, download, delete."""
from __future__ import annotations

import asyncio
import os
import re
from pathlib import Path
from typing import TYPE_CHECKING

import aiosqlite

from smart_pid_domain.dtos.project import ProjectListItem, ProjectResponse

if TYPE_CHECKING:
    from smart_pid_core.adapters.outbound.sqlite_repo import SQLiteRepository
    from smart_pid_core.application.daemon_state import DaemonState
    from smart_pid_core.application.loop_manager import LoopManager
    from smart_pid_core.application.workers.db_worker import DBWorker

# Project names are restricted to a safe, portable character set. This blocks
# path traversal (``..``, ``/``, ``\``), absolute paths, NUL bytes and other
# non-portable characters before the name is ever used to build a filesystem
# path. Length is capped to keep names well within filesystem limits.
_MAX_PROJECT_NAME_LEN = 128
_PROJECT_NAME_RE = re.compile(rf"^[A-Za-z0-9._\- ]{{1,{_MAX_PROJECT_NAME_LEN}}}$")

# Every SQLite database starts with this; a cheap first gate on an upload that
# claims to be a .spid archive.
_SQLITE_MAGIC = b"SQLite format 3\x00"


def _read_prefix(path: Path, size: int) -> bytes:
    """Read the first ``size`` bytes of ``path`` (blocking; call in a thread)."""
    with path.open("rb") as fh:
        return fh.read(size)


class ProjectService:
    """Manages project files in a backend-controlled directory."""

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

    @property
    def projects_dir(self) -> Path:
        return self._projects_dir

    def _safe_project_path(self, name: str) -> Path:
        """Validate ``name`` and resolve it to a path inside ``projects_dir``.

        Raises ``ValueError`` for any name that contains path separators,
        traversal sequences, absolute paths, NUL bytes or other non-portable
        characters, or whose resolved location would escape the projects
        directory. This is the single choke point for all filesystem access
        derived from caller-supplied project names.
        """
        if not isinstance(name, str) or not _PROJECT_NAME_RE.fullmatch(name):
            raise ValueError(f"Invalid project name: {name!r}")
        if name in {".", ".."} or name.strip() == "":
            raise ValueError(f"Invalid project name: {name!r}")
        base = self._projects_dir.resolve()
        dest = (base / f"{name}.spid").resolve()
        if dest.parent != base:
            raise ValueError("Project name escapes the projects directory")
        return dest

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
                async with (
                    aiosqlite.connect(spid) as db,
                    db.execute("SELECT COUNT(*) FROM Controladores") as cur,
                ):
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
        dest = self._safe_project_path(name)
        if dest.exists():
            raise FileExistsError(f"Project '{name}' already exists")
        self._stop_simulator()
        self._stop_opcua()
        await self._stop_db_worker()
        await self._repo.reopen(dest)
        await self._repo.set_meta("nome", name)
        if self._daemon_state:
            self._daemon_state.set_active_project(name)
        self._start_db_worker()
        return ProjectResponse(
            name=name,
            path=dest.name,
            controller_count=0,
        )

    async def open_project(self, name: str) -> ProjectResponse:
        """Open an existing project by name."""
        path = self._safe_project_path(name)
        if not path.exists():
            raise FileNotFoundError(f"Project '{name}' not found")
        self._stop_simulator()
        await self._stop_db_worker()
        await self._repo.reopen(path)
        await self._load_simulator_configs()
        await self._start_control_loops()
        await self._load_opcua_endpoint()
        if self._daemon_state:
            self._daemon_state.set_active_project(name)
        self._start_db_worker()
        return await self.get_current()

    async def import_project(self, name: str, source: Path) -> ProjectResponse:
        """Install a staged upload as ``name`` and make it the active project.

        ``source`` is a fully-received staging file produced by the API layer,
        not a buffer: an import of any size costs one chunk of memory. It is
        validated as a real archive and then *moved* into place, so a rejected
        upload never becomes a project. The move is an ``os.replace`` within
        ``projects_dir``, hence same-filesystem and atomic.
        """
        dest = self._safe_project_path(name)
        if dest.exists():
            raise FileExistsError(f"Project '{name}' already exists")
        await self._assert_valid_archive(source)
        os.replace(source, dest)
        self._stop_simulator()
        await self._stop_db_worker()
        await self._repo.reopen(dest)
        # The archive still carries the name it was exported under, but the
        # project is identified by the file it landed in — without this,
        # /project/current and the import response echo the donor's name while
        # /project/list shows the requested one.
        await self._repo.set_meta("nome", name)
        await self._load_simulator_configs()
        await self._start_control_loops()
        await self._load_opcua_endpoint()
        if self._daemon_state:
            self._daemon_state.set_active_project(name)
        self._start_db_worker()
        return await self.get_current()

    async def _assert_valid_archive(self, source: Path) -> None:
        """Reject anything the daemon could not actually run as a project.

        Import re-points the live repository at the uploaded file, so a bad
        archive does not merely fail — it takes the running plant down with it,
        after the switch, with no project left to serve. So the check is not a
        sniff test: it performs the same open-and-read the install is about to
        perform, on the staging copy, where failure costs nothing.

        Three gates, cheapest first:
        1. the SQLite header, which rejects anything that is not a database;
        2. a ``Controladores`` table, which rejects databases that are not
           projects (bootstrap would otherwise silently adopt a foreign file by
           creating the missing tables);
        3. a real repository open plus ``list_all()``, which is the operation
           ``reopen`` will run and the one that fails on a project written by
           an incompatible schema version.
        """
        from smart_pid_core.adapters.outbound.sqlite_repo import SQLiteRepository

        header = await asyncio.to_thread(_read_prefix, source, len(_SQLITE_MAGIC))
        if header != _SQLITE_MAGIC:
            raise ValueError("Not a valid .spid project archive")
        try:
            async with (
                aiosqlite.connect(source) as db,
                db.execute("SELECT COUNT(*) FROM Controladores"),
            ):
                pass
        except Exception as exc:
            raise ValueError("Not a valid .spid project archive") from exc

        probe = SQLiteRepository(source)
        try:
            await probe.initialize()
            await probe.list_all()
        except Exception as exc:
            raise ValueError(
                f"Project archive cannot be read by this version: {exc}"
            ) from exc
        finally:
            # Disposing the probe engine drops the -wal/-shm siblings it made
            # beside the staging file, so the move below carries the whole DB.
            await probe.close()

    async def prepare_download(self) -> Path:
        """Checkpoint engine A, then return the live .spid path for streaming.

        GET /project/download must never stream a file whose recent writes
        still sit in the -wal sibling (spec §10).
        """
        await self._repo.checkpoint()
        return self._repo.db_path

    async def delete_project(self, name: str) -> None:
        """Delete a project file. Cannot delete the active project."""
        path = self._safe_project_path(name)
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
        """Register controllers and restore simulator state after project switch."""
        if self._simulator_adapter is None:
            return
        # Register all controllers so OPC-UA nodes are created
        if hasattr(self._simulator_adapter, "register_controller"):
            controllers = await self._repo.list_all()
            for ctrl in controllers:
                self._simulator_adapter.register_controller(
                    ctrl.id,
                    pv_min=ctrl.pv_scale.eu_min,
                    pv_max=ctrl.pv_scale.eu_max,
                )
        # Restore simulator preset/PID state
        if hasattr(self._simulator_adapter, "load_sim_config"):
            configs = await self._repo.list_sim_configs()
            for cfg in configs:
                self._simulator_adapter.load_sim_config(cfg)

    async def _start_control_loops(self) -> None:
        """Start PID/Monitor loops for all controllers in the active project."""
        controllers = await self._repo.list_all()
        for ctrl in controllers:
            self._loop_manager.start_loop(ctrl)

    def _stop_simulator(self) -> None:
        """Stop the simulator adapter if present."""
        if self._simulator_adapter is not None and hasattr(
            self._simulator_adapter, "stop"
        ):
            self._simulator_adapter.stop()

    async def _load_opcua_endpoint(self) -> None:
        """Read opcua_endpoint from metadata and auto-connect or stop adapter."""
        if self._opcua_adapter is None:
            return
        endpoint = await self._repo.get_meta("opcua_endpoint")
        if endpoint:
            if endpoint != self._opcua_adapter.endpoint or not self._opcua_adapter.is_connected:
                self._opcua_adapter.set_endpoint(endpoint)
                self._opcua_adapter.start()
        else:
            self._opcua_adapter.stop()

    def _stop_opcua(self) -> None:
        """Stop the OPC-UA adapter if present."""
        if self._opcua_adapter is not None and hasattr(self._opcua_adapter, "stop"):
            self._opcua_adapter.stop()

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
