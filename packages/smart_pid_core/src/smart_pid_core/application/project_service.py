"""Project lifecycle orchestration — new, open, import, download, delete."""
from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import TYPE_CHECKING

import aiosqlite

from smart_pid_core.adapters.outbound.simulator_client import bind_opcua_client
from smart_pid_domain.dtos.project import (
    ProjectListItem,
    ProjectResponse,
    validate_project_name,
)

if TYPE_CHECKING:
    from smart_pid_core.adapters.outbound.simulator_client import SimulatorClient
    from smart_pid_core.adapters.outbound.sqlite_repo import SQLiteRepository
    from smart_pid_core.application.daemon_state import DaemonState
    from smart_pid_core.application.loop_manager import LoopManager
    from smart_pid_core.application.workers.alarm_worker import AlarmWorker
    from smart_pid_core.application.workers.db_worker import DBWorker
    from smart_pid_core.application.workers.io_worker import IOWorker

# ``validate_project_name`` (domain) is the single definition of what a legal
# project name is; it is applied at the API boundary by the request DTOs and
# again here, which is the authoritative choke point for every filesystem
# access derived from a caller-supplied name. Keeping one function means the
# boundary can never drift laxer than the path builder behind it.

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
        simulator_client: SimulatorClient | None = None,
        daemon_state: DaemonState | None = None,
        opcua_adapter: object | None = None,
        db_worker: DBWorker | None = None,
        io_worker: IOWorker | None = None,
        alarm_worker: AlarmWorker | None = None,
    ) -> None:
        self._repo = repo
        self._loop_manager = loop_manager
        self._projects_dir = projects_dir
        self._simulator_client = simulator_client
        self._daemon_state = daemon_state
        self._opcua_adapter = opcua_adapter
        self._db_worker = db_worker
        self._io_worker = io_worker
        self._alarm_worker = alarm_worker

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
        validate_project_name(name)
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
        await self._stop_simulator()
        self._stop_opcua()
        await self._stop_db_worker()
        await self._repo.reopen(dest)
        await self._repo.set_meta("nome", name)
        await self._reload_alarm_worker()
        if self._daemon_state:
            self._daemon_state.set_active_project(name)
        self._start_db_worker()
        await self._resync_simulator_link()
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
        await self._stop_simulator()
        await self._stop_db_worker()
        await self._repo.reopen(path)
        await self._load_simulator_configs()
        await self._start_control_loops()
        await self._load_opcua_endpoint()
        await self._reload_alarm_worker()
        if self._daemon_state:
            self._daemon_state.set_active_project(name)
        self._start_db_worker()
        await self._resync_simulator_link()
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
        await self._stop_simulator()
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
        await self._reload_alarm_worker()
        if self._daemon_state:
            self._daemon_state.set_active_project(name)
        self._start_db_worker()
        await self._resync_simulator_link()
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
        if self._simulator_client is None:
            return
        # Register all controllers so OPC-UA nodes are created
        controllers = await self._repo.list_all()
        for ctrl in controllers:
            await self._simulator_client.register_controller(
                ctrl.id,
                pv_min=ctrl.pv_scale.eu_min,
                pv_max=ctrl.pv_scale.eu_max,
            )
        # Restore simulator preset/PID state
        configs = await self._repo.list_sim_configs()
        for cfg in configs:
            await self._simulator_client.load_sim_config(cfg)

    async def _start_control_loops(self) -> None:
        """Start PID/Monitor loops for all controllers in the active project.

        Also registers each controller with the I/O worker's scan list —
        without this, a project opened after daemon boot gets live
        PIDWorker/AIWorker threads that never receive TELEMETRY.{cid}
        because IOWorker only knew about the boot-time controller set.
        """
        controllers = await self._repo.list_all()
        for ctrl in controllers:
            self._loop_manager.start_loop(ctrl)
            if self._io_worker is not None:
                self._io_worker.add_controller(ctrl.id)

    async def _reload_alarm_worker(self) -> None:
        """Re-point the alarm evaluator at the project that is now open.

        Sibling of the IOWorker note above, and the same class of bug: the
        AlarmWorker caches limits, controller names and PV ranges by controller
        id, so without this a switch leaves it evaluating the PREVIOUS project's
        limits against the new project's ids — phantom alarms in a project that
        configures none, enriched with the wrong (or a missing) tag name.
        """
        if self._alarm_worker is None:
            return
        from smart_pid_core.adapters.outbound.alarm_repo import AlarmRepository
        from smart_pid_core.application.workers.alarm_worker import load_alarm_configs

        configs = await load_alarm_configs(self._repo.session_factory)
        controllers = await self._repo.list_all()
        try:
            active = await AlarmRepository(self._repo.session_factory).get_active()
        except Exception:
            active = []
        self._alarm_worker.reload_project(configs, controllers, active)

    async def _stop_simulator(self) -> None:
        """Stop the twin (via its client) if present."""
        if self._simulator_client is not None:
            await self._simulator_client.stop()

    async def _resync_simulator_link(self) -> None:
        """Bring the twin and its OPC-UA client back up after a project switch.

        Every project entry point stops the simulator (and ``new_project`` the
        OPC-UA client too) to drop the previous project's state, but nothing
        started them again: from the first project switch on, the twin stopped
        integrating and ``IOWorker`` — which skips its whole scan while the
        adapter is offline, silently — published no TELEMETRY at all. The loops
        were live and ``/system/status`` healthy, with every stats counter
        frozen at zero until a daemon restart.

        No-op without a simulator: against a real DCS the endpoint comes from
        the project (``_load_opcua_endpoint``), not from us.
        """
        sim = self._simulator_client
        if sim is None:
            return
        await sim.start()
        if self._opcua_adapter is None:
            return
        controllers = await self._repo.list_all()
        await bind_opcua_client(self._opcua_adapter, sim, [c.id for c in controllers])
        self._opcua_adapter.start()

    async def _load_opcua_endpoint(self) -> None:
        """Read opcua_endpoint from metadata and auto-connect or stop adapter."""
        if self._opcua_adapter is None:
            return
        if self._simulator_client is not None:
            # The twin owns the address space and the endpoint the factory
            # already pointed the client at; a stale real-DCS endpoint saved in
            # the project must not steal the client away from it.
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
