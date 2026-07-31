"""Smart PID Core Engine — backend daemon entry point."""
from __future__ import annotations

import asyncio
import contextlib
import logging
import signal
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

import structlog
import uvicorn

from smart_pid_core.adapters.factory import AdapterFactory
from smart_pid_core.adapters.inbound.api.app import create_app
from smart_pid_core.adapters.inbound.api.auth import hash_password
from smart_pid_core.adapters.inbound.sim_persistence import persist_sim_config
from smart_pid_core.adapters.inbound.simulator_adapter import SIMULATOR_MODE_INT_MAP
from smart_pid_core.adapters.outbound.historian import SQLiteHistorian
from smart_pid_core.adapters.outbound.sqlite_repo import SQLiteRepository
from smart_pid_core.adapters.outbound.user_repo import UserRepository
from smart_pid_core.application.daemon_state import DaemonState
from smart_pid_core.application.event_bus import EventBus
from smart_pid_core.application.loop_manager import LoopManager
from smart_pid_core.application.telemetry_publisher import TelemetryPublisher
from smart_pid_core.application.tuning_store import TuningRecommendationStore
from smart_pid_core.config import CoreSettings
from smart_pid_domain.enums import ExecutionMode, UserRole

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from smart_pid_domain.models.alarm_config import AlarmConfig

logger = structlog.get_logger()
async def _load_alarm_configs(session_factory) -> dict[int, AlarmConfig]:  # noqa: ANN001
    """Load alarm configurations from Configuracao_Alarmes table."""
    from sqlalchemy import text

    from smart_pid_domain.enums import AlarmPriority
    from smart_pid_domain.models.alarm_config import AlarmConfig as _AC

    configs: dict[int, _AC] = {}
    try:
        async with session_factory() as session:
            result = await session.execute(
                text("SELECT * FROM Configuracao_Alarmes ORDER BY controlador_id")
            )
            rows = result.mappings().all()
    except Exception:
        logger.debug("alarm_configs_not_loaded", exc_info=True)
        return configs

    by_controller: dict[int, dict] = {}
    for row in rows:
        cid = row["controlador_id"]
        if cid not in by_controller:
            by_controller[cid] = {}
        atype = row["tipo_alarme"]
        by_controller[cid][atype] = {
            "enabled": bool(row["habilitado"]),
            "value": row["limite"],
            "priority": AlarmPriority(row["prioridade"]),
            "hysteresis": row["histerese"],
            "delay_on_s": row["delay_on_s"] if "delay_on_s" in row.keys() else 0.0,  # noqa: SIM118
            "delay_off_s": row["delay_off_s"] if "delay_off_s" in row.keys() else 0.0,  # noqa: SIM118
        }

    for cid, alarms in by_controller.items():

        def _get(
            name: str,
            default_priority: AlarmPriority = AlarmPriority.WARNING,
            _alarms: dict = alarms,
        ) -> tuple[bool, float, AlarmPriority, float, float]:
            a = _alarms.get(name, {})
            return (
                a.get("enabled", False),
                a.get("value", 0.0),
                a.get("priority", default_priority),
                a.get("delay_on_s", 0.0),
                a.get("delay_off_s", 0.0),
            )

        hihi_e, hihi_v, hihi_p, hihi_don, hihi_doff = _get("HIHI", AlarmPriority.CRITICAL)
        hi_e, hi_v, hi_p, hi_don, hi_doff = _get("HI")
        lo_e, lo_v, lo_p, lo_don, lo_doff = _get("LO")
        lolo_e, lolo_v, lolo_p, lolo_don, lolo_doff = _get("LOLO", AlarmPriority.CRITICAL)
        dvhi_e, dvhi_v, dvhi_p, dvhi_don, dvhi_doff = _get("DV_HI", AlarmPriority.ADVISORY)
        dvlo_e, dvlo_v, dvlo_p, dvlo_don, dvlo_doff = _get("DV_LO", AlarmPriority.ADVISORY)
        deadband = max((a.get("hysteresis", 0.0) for a in alarms.values()), default=0.0)

        configs[cid] = _AC(
            hihi_enabled=hihi_e,
            hihi_value=hihi_v,
            hihi_priority=hihi_p,
            hihi_delay_on_s=hihi_don,
            hihi_delay_off_s=hihi_doff,
            hi_enabled=hi_e,
            hi_value=hi_v,
            hi_priority=hi_p,
            hi_delay_on_s=hi_don,
            hi_delay_off_s=hi_doff,
            lo_enabled=lo_e,
            lo_value=lo_v,
            lo_priority=lo_p,
            lo_delay_on_s=lo_don,
            lo_delay_off_s=lo_doff,
            lolo_enabled=lolo_e,
            lolo_value=lolo_v,
            lolo_priority=lolo_p,
            lolo_delay_on_s=lolo_don,
            lolo_delay_off_s=lolo_doff,
            dv_hi_enabled=dvhi_e,
            dv_hi_value=dvhi_v,
            dv_hi_priority=dvhi_p,
            dv_hi_delay_on_s=dvhi_don,
            dv_hi_delay_off_s=dvhi_doff,
            dv_lo_enabled=dvlo_e,
            dv_lo_value=dvlo_v,
            dv_lo_priority=dvlo_p,
            dv_lo_delay_on_s=dvlo_don,
            dv_lo_delay_off_s=dvlo_doff,
            deadband_percent=deadband,
        )
    return configs


async def _migrate_users_if_needed(spid_path: Path, users_db_path: Path) -> None:
    """Auto-migrate users from .spid to standalone users.db if needed."""
    if users_db_path.exists():
        return
    if not spid_path.exists():
        return

    import aiosqlite

    async with aiosqlite.connect(spid_path) as db:
        async with db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='Usuarios'"
        ) as cur:
            if await cur.fetchone() is None:
                return

        async with db.execute(
            "SELECT nome, senha_hash, perfil, ativo, criado_em FROM Usuarios"
        ) as cur:
            rows = await cur.fetchall()

    if not rows:
        return

    user_repo = UserRepository(users_db_path)
    await user_repo.initialize()
    for row in rows:
        with contextlib.suppress(Exception):
            await user_repo.db.execute(
                "INSERT INTO Usuarios (nome, senha_hash, perfil, ativo, criado_em)"
                " VALUES (?, ?, ?, ?, ?)",
                (row[0], row[1], row[2], row[3], row[4]),
            )
    await user_repo.db.commit()
    await user_repo.close()
    logger.info(
        "migrated_users", count=len(rows), source=str(spid_path), target=str(users_db_path),
    )


_ROLE_VALUE_MAP: tuple[tuple[str, str], ...] = (
    ("ADMIN", "admin"),
    ("SUPERVISOR", "admin"),
    ("OPERATOR", "user"),
)


async def _migrate_user_roles(user_repo: UserRepository) -> None:
    """Rewrite legacy role values in users.db idempotently (spec §9.4)."""
    migrated = 0
    for legacy, new in _ROLE_VALUE_MAP:
        cursor = await user_repo.db.execute(
            "UPDATE Usuarios SET perfil = ? WHERE perfil = ?",
            (new, legacy),
        )
        migrated += max(cursor.rowcount, 0)
    await user_repo.db.commit()
    if migrated:
        logger.info("migrated_user_roles", rows=migrated)


async def _seed_default_admin(user_repo: UserRepository) -> None:
    """Create the default admin account when users.db has no rows."""
    if await user_repo.list_all():
        return
    admin_hash = hash_password("admin")
    await user_repo.create("admin", admin_hash, UserRole.ADMIN.value)
    logger.warning(
        "seeded_default_admin",
        msg="SECURITY: Default admin account created with password 'admin'. "
        "Change it immediately.",
    )


async def _sim_persist_flusher(
    adapter,  # noqa: ANN001
    repo: SQLiteRepository,
    stop_event: asyncio.Event,
    interval_s: float = 2.0,
) -> None:
    """Periodically persist simulator controllers whose PID config changed via OPC-UA.

    REST routes already persist on-demand. This flusher covers writes that reach
    the simulator via OPC-UA (e.g. Ti updates from the Fuzzy/RL AI engine) which
    otherwise live only in memory and are lost on restart.
    """
    _log = structlog.get_logger()
    while not stop_event.is_set():
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(stop_event.wait(), timeout=interval_s)
        for cid in adapter.consume_dirty_cids():
            try:
                await persist_sim_config(adapter, repo, cid)
                await _mirror_sim_pid_params(adapter, repo, cid)
            except Exception:
                _log.exception("sim_persist_flush_failed", controller_id=cid)


async def _mirror_sim_pid_params(
    adapter,  # noqa: ANN001
    repo: SQLiteRepository,
    controller_id: int,
) -> None:
    """Mirror a SUPERVISORY controller's live simulator PID tuning into its
    stored config, so the loop-config view matches the PID the simulator is
    actually running. SmartPID does not own a SUPERVISORY loop's tuning — the
    simulator/DCS does — so its config must follow, not lead. DDC loops own
    their tuning and are left untouched."""
    from dataclasses import replace

    try:
        controller = await repo.get(controller_id)
    except KeyError:
        return
    if controller.execution_mode is not ExecutionMode.SUPERVISORY:
        return
    st = adapter.get_pid_status(controller_id)
    p = controller.pid_params
    if (p.gain, p.reset, p.rate) == (st["kp"], st["ti"], st["td"]):
        return
    updated = replace(
        controller,
        pid_params=replace(p, gain=st["kp"], reset=st["ti"], rate=st["td"]),
    )
    await repo.save(updated)


#: Rows removed per retention statement. Measured on a 1.5 M-row / 142 MB
#: ``Log_Processo``: 5 000 rows holds the WAL write lock 72 ms, 20 000 holds it
#: 279 ms, 50 000 holds it 361 ms. 5 000 keeps a single statement an order of
#: magnitude below the 2 s simulator-flush cadence even on a multi-hundred-MB
#: file, so pruning never starves the other WAL writer the way the previous
#: single unbounded DELETE did (2.87 s for 1.18 M rows, ~25-30 s at 1 GB).
_RETENTION_BATCH_ROWS = 5_000

#: Pause between batches: yields the event loop and, more importantly, drops the
#: write lock long enough for engine B's telemetry flush to claim it.
_RETENTION_BATCH_PAUSE_S = 0.05

#: table -> retention window in days.
_RETENTION_POLICY: tuple[tuple[str, int], ...] = (
    ("Log_Alarmes", 30),
    ("Log_System_Events", 30),
    ("Log_Sintonia_IA", 7),
    ("Log_Processo", 7),
)


async def _prune_table(
    session_factory: async_sessionmaker[AsyncSession],
    table: str,
    cutoff_iso: str,
    batch_rows: int,
) -> int:
    """Delete rows older than *cutoff_iso* from *table* in bounded batches.

    Each statement is capped by ``LIMIT`` and committed on its own, so the write
    lock is taken and released once per batch instead of being held for the whole
    backlog. Returns the number of rows removed.
    """
    from sqlalchemy import text

    total = 0
    while True:
        async with session_factory() as session:
            result = await session.execute(
                text(
                    f"DELETE FROM {table} WHERE rowid IN ("  # noqa: S608
                    f" SELECT rowid FROM {table} WHERE timestamp <= :cutoff"
                    f" LIMIT :batch)"
                ),
                {"cutoff": cutoff_iso, "batch": batch_rows},
            )
            await session.commit()
        removed = max(result.rowcount, 0)
        total += removed
        if removed < batch_rows:
            return total
        await asyncio.sleep(_RETENTION_BATCH_PAUSE_S)


async def _retention_cleanup(
    session_factory: async_sessionmaker[AsyncSession],
    interval_hours: int = 24,
    batch_rows: int = _RETENTION_BATCH_ROWS,
) -> None:
    """Prune aged log rows: first pass at startup, then every *interval_hours*.

    The pass runs FIRST and sleeps afterwards. Sleeping first meant a daemon
    restarted more often than daily never pruned anything, which is how the
    active project file reached 1.08 GB.

    This is started as a detached background task and deliberately does NOT gate
    ``daemon_ready``: on a large backlog the first pass is tens of seconds of
    wall clock, and an operator staring at an unresponsive UI is a worse failure
    than an oversized file. Chunking keeps each statement's lock hold in the tens
    of milliseconds, so the pass stays invisible to the PID and telemetry paths
    while it runs.

    Cutoffs are ISO-8601 strings built to match how every one of these tables
    stores its ``timestamp`` (``datetime.isoformat()``). The previous predicate
    used ``datetime('now', ...)``, whose space separator sorts below the stored
    'T', so rows just past the cutoff compared greater and were never pruned.
    """
    _log = structlog.get_logger()
    while True:
        try:
            now = datetime.now(tz=UTC)
            removed: dict[str, int] = {}
            for table, days in _RETENTION_POLICY:
                cutoff = (now - timedelta(days=days)).isoformat()
                count = await _prune_table(session_factory, table, cutoff, batch_rows)
                if count:
                    removed[table] = count
            _log.info("retention_cleanup_complete", removed=removed or None)
        except Exception:
            _log.exception("retention_cleanup_error")
        await asyncio.sleep(interval_hours * 3600)


async def run_daemon(settings: CoreSettings) -> None:
    """Bootstrap and run the backend daemon until interrupted."""
    logger.info(
        "starting_daemon",
        api_port=settings.api_port,
        zmq_port=settings.zmq_publish_port,
        execution_mode=settings.execution_mode,
        simulator_enabled=settings.simulator_enabled,
        simulator_port=settings.simulator_port,
    )
    logger.info("SmartPID daemon starting in %s mode", settings.execution_mode)

    # Ensure projects directory exists
    settings.projects_dir.mkdir(parents=True, exist_ok=True)

    # Phase 1 components
    repo = SQLiteRepository(settings.db_path)
    await repo.initialize()

    # Restore last active project BEFORE registering controllers so that
    # simulator / OPC-UA adapters see the correct controller set.
    daemon_state = DaemonState()
    last_project = daemon_state.active_project
    if last_project and repo._db_path.name == "project.spid":
        restore_path = settings.projects_dir / f"{last_project}.spid"
        if restore_path.exists():
            logger.info("restoring_last_project", name=last_project)
            await repo.reopen(restore_path)
        else:
            logger.warning("last_project_not_found", name=last_project)
            daemon_state.set_active_project(None)

    historian = SQLiteHistorian(repo.session_factory)
    bus = EventBus()
    bus.start()
    model_dir = settings.db_path.parent / "models"
    # One store shared by the producers (AIWorker, via LoopManager) and the
    # consumers (the /commands tuning routes, via app.state).
    tuning_store = TuningRecommendationStore()
    loop_manager = LoopManager(
        bus=bus,
        execution_mode=settings.execution_mode,
        model_dir=model_dir,
        tuning_store=tuning_store,
    )
    logger.info("event_bus_started")

    # Phase 4: Adapter factory (simulator or OPC-UA)
    adapter_factory = AdapterFactory(settings)
    simulator_adapter = adapter_factory.simulator_adapter
    if simulator_adapter is not None:
        controllers = await repo.list_all()
        for ctrl in controllers:
            simulator_adapter.register_controller(
                ctrl.id,
                pv_min=ctrl.pv_scale.eu_min,
                pv_max=ctrl.pv_scale.eu_max,
            )
        logger.info(
            "simulator_controllers_registered",
            count=len(controllers),
            ids=[c.id for c in controllers],
        )
        # Restore persisted simulator configs from DB
        sim_configs = await repo.list_sim_configs()
        for cfg in sim_configs:
            simulator_adapter.load_sim_config(cfg)
        if sim_configs:
            logger.info("simulator_configs_restored", count=len(sim_configs))

        simulator_adapter.start_opcua()
        logger.info("opcua_server_started", port=settings.simulator_port)
        simulator_adapter.start()
        logger.info("simulator_started", port=settings.simulator_port)
    else:
        logger.info("simulator_disabled", hint="set SPID_SIMULATOR_ENABLED=true to enable")

    # Phase 3b: OPC-UA adapter lifecycle
    opcua_adapter = adapter_factory.opcua_adapter
    if opcua_adapter is not None:
        if simulator_adapter is not None:
            # Simulator mode: use the simulator's actual node IDs (auto-assigned)
            # but keep mode_int_map from database (user-configured mapping)
            sim_node_ids = simulator_adapter._opcua_server.controller_node_ids
            # The mode map comes from the simulator, not the database, for the
            # same reason the node ids do: in simulator mode the twin owns the
            # address space, so it also owns how its Mode node is encoded. The
            # DB's tag_bindings describe a real DCS and are empty for every
            # controller the simulator auto-registered ({} -> read_actual_mode
            # returns None -> every STATUS frame reported mode "UNKNOWN").
            # Not persisted back to the project: that would duplicate a
            # constant the simulator owns, drift if its encoding changed, and
            # mutate the user's .spid file as a side effect of enabling the
            # simulator.
            for ctrl_id, nodes in sim_node_ids.items():
                mode_map = dict(SIMULATOR_MODE_INT_MAP)
                mode_node = nodes.get("mode", "")
                opcua_adapter.register_controller(
                    controller_id=ctrl_id,
                    node_id_pv=nodes.get("pv", ""),
                    node_id_sp=nodes.get("sp", ""),
                    node_id_co=nodes.get("co", ""),
                    node_id_kp=nodes.get("kp", ""),
                    node_id_ti=nodes.get("ti", ""),
                    node_id_td=nodes.get("td", ""),
                    node_id_mode_target=mode_node,
                    node_id_mode_actual=mode_node,
                    mode_int_map=mode_map,
                )
            logger.info(
                "opcua_adapter_registered_from_simulator",
                controllers=list(sim_node_ids.keys()),
            )
        else:
            # Real OPC-UA: use database tag_bindings
            controllers = await repo.list_all()
            for ctrl in controllers:
                tb = ctrl.tag_bindings
                if tb.node_id_pv:
                    opcua_adapter.register_controller(
                        controller_id=ctrl.id,
                        node_id_pv=tb.node_id_pv,
                        node_id_sp=tb.node_id_sp,
                        node_id_co=tb.node_id_co,
                        node_id_integral=tb.node_id_integral,
                        node_id_bkcal_in=tb.node_id_bkcal_in,
                        node_id_bkcal_out=tb.node_id_bkcal_out,
                        node_id_kp=tb.node_id_kp,
                        node_id_ti=tb.node_id_ti,
                        node_id_td=tb.node_id_td,
                        node_id_mode_target=tb.node_id_mode_target,
                        node_id_mode_actual=tb.node_id_mode_actual,
                        mode_int_map=tb.mode_int_map,
                    )
        opcua_adapter.start()
        logger.info("opcua_adapter_started", endpoint=opcua_adapter.endpoint)

    # Migrate users from .spid to standalone users.db if needed
    await _migrate_users_if_needed(settings.db_path, settings.users_db_path)

    # Phase 2: User repo + role-value migration + seed admin (standalone DB)
    user_repo = UserRepository(settings.users_db_path)
    await user_repo.initialize()
    await _migrate_user_roles(user_repo)
    await _seed_default_admin(user_repo)

    # Phase 5: AI Repository
    from smart_pid_core.adapters.outbound.ai_repo import AIRepository

    ai_repo = AIRepository(repo.session_factory)

    # Phase 6: Alarm + Audit infrastructure
    from smart_pid_core.adapters.outbound.alarm_repo import AlarmRepository
    from smart_pid_core.adapters.outbound.audit_repo import AuditRepository
    from smart_pid_core.application.workers.alarm_worker import AlarmWorker

    alarm_repo = AlarmRepository(repo.session_factory)
    audit_repo = AuditRepository(repo.session_factory)

    # Build alarm configs from Configuracao_Alarmes table
    alarm_configs = await _load_alarm_configs(repo.session_factory)
    alarm_worker = AlarmWorker(
        bus=bus, alarm_configs=alarm_configs, alarm_repo=alarm_repo,
        event_loop=asyncio.get_running_loop(),
    )
    # Seed engine with active alarms from DB so it can generate CLEARED
    # transitions for alarms that were active before daemon restart
    try:
        db_active = await alarm_repo.get_active()
        genuinely_active = [a for a in db_active if a.get("cleared_at") is None]
        alarm_worker.seed_active_alarms(genuinely_active)
        if genuinely_active:
            logger.info("alarm_engine_seeded", count=len(genuinely_active))
    except Exception:
        logger.debug("alarm_seed_skipped", exc_info=True)

    alarm_worker.start()
    logger.info("alarm_worker_started")

    # System events infrastructure
    from smart_pid_core.adapters.outbound.system_event_repo import SystemEventRepository
    from smart_pid_core.application.workers.system_event_worker import SystemEventWorker

    system_event_repo = SystemEventRepository(repo.session_factory)
    system_event_worker = SystemEventWorker(
        bus=bus, system_event_repo=system_event_repo,
        event_loop=asyncio.get_running_loop(),
    )
    system_event_worker.emit("BACKEND", "INFO", "Backend started")
    logger.info("system_event_worker_started")

    # I-INT-1: DBWorker — persist telemetry to SQLite
    from smart_pid_core.application.workers.db_worker import DBWorker

    db_worker = DBWorker(bus=bus, repo=repo)
    db_worker.start()
    logger.info("db_worker_started")

    # C-INT-2: I/O Worker — read OPC-UA and publish TELEMETRY events to bus
    from smart_pid_core.application.workers.io_worker import IOWorker

    all_controllers = await repo.list_all()
    io_controller_ids = [c.id for c in all_controllers]
    io_worker = IOWorker(
        bus=bus,
        opcua_adapter=adapter_factory.opcua_adapter,
        controller_ids=io_controller_ids,
        scan_interval_s=settings.simulator_interval_ms / 1000.0
        if settings.simulator_enabled
        else 0.1,
        execution_mode=settings.execution_mode,
    )
    io_worker.start()
    logger.info("io_worker_started")

    # Resume AI Ki from last DB entry for each controller
    last_ki_map: dict[int, float] = {}
    for ctrl in all_controllers:
        last_ki = await ai_repo.get_last_ki(ctrl.id)
        if last_ki is not None:
            last_ki_map[ctrl.id] = last_ki
            logger.info("ai_ki_resumed", controller_id=ctrl.id, ki=last_ki)

    # Start PID/Monitor control loops for all controllers
    for ctrl in all_controllers:
        loop_manager.start_loop(ctrl, initial_ki=last_ki_map.get(ctrl.id))
    logger.info("control_loops_started", count=len(all_controllers))

    # Populate AlarmWorker controller metadata for event enrichment
    for ctrl in all_controllers:
        alarm_worker.update_controller_meta(ctrl.id, ctrl.name, ctrl.description)
        alarm_worker.update_pv_range(ctrl.id, ctrl.pv_scale.eu_min, ctrl.pv_scale.eu_max)

    # C-INT-3: ExportWorker — CSV/JSON export jobs
    from smart_pid_core.application.export_worker import ExportWorker

    export_dir = str(settings.db_path.parent / "exports")
    export_worker = ExportWorker(historian=historian, export_dir=export_dir)
    logger.info("export_worker_created", export_dir=export_dir)

    # Project service (daemon_state created earlier, before controller registration)
    from smart_pid_core.application.project_service import ProjectService

    project_service = ProjectService(
        repo=repo,
        loop_manager=loop_manager,
        projects_dir=settings.projects_dir,
        simulator_adapter=simulator_adapter,
        daemon_state=daemon_state,
        opcua_adapter=opcua_adapter,
        db_worker=db_worker,
    )

    # Phase 2: FastAPI
    app = create_app(
        repo=repo,
        historian=historian,
        user_repo=user_repo,
        loop_manager=loop_manager,
        settings=settings,
        simulator_adapter=simulator_adapter,
        opcua_adapter=opcua_adapter,
        stats_workers=loop_manager.get_stats_workers(),
        ai_workers=loop_manager.get_ai_workers(),
        ai_repo=ai_repo,
        alarm_repo=alarm_repo,
        alarm_worker=alarm_worker,
        audit_repo=audit_repo,
        system_event_repo=system_event_repo,
        project_service=project_service,
        event_bus=bus,
        tuning_store=tuning_store,
    )

    # Set export_worker on app.state so the export router can use it
    app.state.export_worker = export_worker
    # Expose SystemEventWorker so routes can broadcast user-action events
    # (displayed live in the HMI alarm panel alongside backend events).
    app.state.system_event_worker = system_event_worker

    # Phase 2: Telemetry Publisher
    telemetry_pub = TelemetryPublisher(bus=bus, publish_port=settings.zmq_publish_port)
    await telemetry_pub.start()

    # Embedded uvicorn
    uv_config = uvicorn.Config(
        app=app,
        host=settings.api_host,
        port=settings.api_port,
        log_level=settings.log_level.lower(),
    )
    server = uvicorn.Server(uv_config)

    stop_event = asyncio.Event()

    def handle_signal() -> None:
        logger.info("shutdown_signal_received")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, handle_signal)

    # Data retention cleanup (daily)
    cleanup_task = asyncio.create_task(_retention_cleanup(repo.session_factory))

    # Simulator config flusher (drains dirty set from OPC-UA-initiated writes)
    sim_flush_task: asyncio.Task | None = None
    if simulator_adapter is not None:
        sim_flush_task = asyncio.create_task(
            _sim_persist_flusher(simulator_adapter, repo, stop_event)
        )

    # Run uvicorn and wait for shutdown signal concurrently
    server_task = asyncio.create_task(server.serve())
    logger.info("daemon_ready")

    await stop_event.wait()
    system_event_worker.emit("BACKEND", "INFO", "Backend shutdown")
    logger.info("shutting_down")

    # Graceful shutdown in correct order
    cleanup_task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await cleanup_task
    if sim_flush_task is not None:
        # stop_event already set — let the flusher complete one last drain
        with contextlib.suppress(Exception):
            await asyncio.wait_for(sim_flush_task, timeout=3.0)
        if simulator_adapter is not None:
            for cid in simulator_adapter.consume_dirty_cids():
                with contextlib.suppress(Exception):
                    await persist_sim_config(simulator_adapter, repo, cid)
    server.should_exit = True
    await server_task
    await telemetry_pub.stop()
    io_worker.stop()
    db_worker.stop()
    # Stop OPC-UA client BEFORE simulator (client depends on server)
    if opcua_adapter is not None:
        opcua_adapter.stop()
    if simulator_adapter is not None:
        simulator_adapter.stop()
        simulator_adapter.stop_opcua()
    alarm_worker.stop()
    loop_manager.stop_all()
    bus.stop()
    # Close user DB before project DB
    await user_repo.close()
    # I-INT-3: Close SQLite connection to finalize WAL
    await repo.close()
    logger.info("daemon_stopped")


def main() -> None:
    """CLI entry point."""
    try:
        settings = CoreSettings()  # type: ignore[call-arg]
    except Exception as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        print("Ensure SPID_JWT_SECRET is set in environment or .env file.", file=sys.stderr)
        sys.exit(1)

    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)
    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
    )
    asyncio.run(run_daemon(settings))
if __name__ == "__main__":
    main()
