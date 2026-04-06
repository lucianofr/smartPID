"""Smart PID Core Engine — backend daemon entry point."""
from __future__ import annotations

import asyncio
import logging
import signal
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import structlog
import uvicorn

from smart_pid_core.adapters.factory import AdapterFactory
from smart_pid_core.adapters.inbound.api.app import create_app
from smart_pid_core.adapters.inbound.api.auth import hash_password
from smart_pid_core.adapters.outbound.historian import SQLiteHistorian
from smart_pid_core.adapters.outbound.sqlite_repo import SQLiteRepository
from smart_pid_core.adapters.outbound.user_repo import UserRepository
from smart_pid_core.application.event_bus import EventBus
from smart_pid_core.application.loop_manager import LoopManager
from smart_pid_core.application.telemetry_publisher import TelemetryPublisher
from smart_pid_core.config import CoreSettings

if TYPE_CHECKING:
    from smart_pid_domain.models.alarm_config import AlarmConfig

logger = structlog.get_logger()
async def _load_alarm_configs(db) -> dict[int, AlarmConfig]:  # noqa: ANN001
    """Load alarm configurations from Configuracao_Alarmes table."""
    from smart_pid_domain.enums import AlarmPriority
    from smart_pid_domain.models.alarm_config import AlarmConfig as _AC

    configs: dict[int, _AC] = {}
    try:
        async with db.execute("SELECT * FROM Configuracao_Alarmes ORDER BY controlador_id") as cur:
            rows = await cur.fetchall()
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
            "delay_on_ms": row.get("delay_on_ms", 0) or 0,
            "delay_off_ms": row.get("delay_off_ms", 0) or 0,
        }

    for cid, alarms in by_controller.items():

        def _get(
            name: str,
            default_priority: AlarmPriority = AlarmPriority.WARNING,
            _alarms: dict = alarms,
        ) -> tuple[bool, float, AlarmPriority, int, int]:
            a = _alarms.get(name, {})
            return (
                a.get("enabled", False),
                a.get("value", 0.0),
                a.get("priority", default_priority),
                a.get("delay_on_ms", 0),
                a.get("delay_off_ms", 0),
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
            hihi_delay_on_ms=hihi_don,
            hihi_delay_off_ms=hihi_doff,
            hi_enabled=hi_e,
            hi_value=hi_v,
            hi_priority=hi_p,
            hi_delay_on_ms=hi_don,
            hi_delay_off_ms=hi_doff,
            lo_enabled=lo_e,
            lo_value=lo_v,
            lo_priority=lo_p,
            lo_delay_on_ms=lo_don,
            lo_delay_off_ms=lo_doff,
            lolo_enabled=lolo_e,
            lolo_value=lolo_v,
            lolo_priority=lolo_p,
            lolo_delay_on_ms=lolo_don,
            lolo_delay_off_ms=lolo_doff,
            dv_hi_enabled=dvhi_e,
            dv_hi_value=dvhi_v,
            dv_hi_priority=dvhi_p,
            dv_hi_delay_on_ms=dvhi_don,
            dv_hi_delay_off_ms=dvhi_doff,
            dv_lo_enabled=dvlo_e,
            dv_lo_value=dvlo_v,
            dv_lo_priority=dvlo_p,
            dv_lo_delay_on_ms=dvlo_don,
            dv_lo_delay_off_ms=dvlo_doff,
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
        try:
            await user_repo.db.execute(
                "INSERT INTO Usuarios (nome, senha_hash, perfil, ativo, criado_em)"
                " VALUES (?, ?, ?, ?, ?)",
                (row[0], row[1], row[2], row[3], row[4]),
            )
        except Exception:
            pass  # Skip duplicates
    await user_repo.db.commit()
    await user_repo.close()
    logger.info(
        "migrated_users", count=len(rows), source=str(spid_path), target=str(users_db_path),
    )


async def run_daemon(settings: CoreSettings) -> None:
    """Bootstrap and run the backend daemon until interrupted."""
    logger.info(
        "starting_daemon",
        api_port=settings.api_port,
        zmq_port=settings.zmq_publish_port,
        execution_mode=settings.execution_mode,
    )
    logger.info("SmartPID daemon starting in %s mode", settings.execution_mode)

    # Phase 1 components
    repo = SQLiteRepository(settings.db_path)
    await repo.initialize()
    historian = SQLiteHistorian(repo.db)
    bus = EventBus()
    bus.start()
    from smart_pid_core.domain.services.alarm_engine import AlarmEngine
    _alarm_engine = AlarmEngine()
    loop_manager = LoopManager(
        bus=bus,
        execution_mode=settings.execution_mode,
        alarm_engine=_alarm_engine,
    )
    logger.info("event_bus_started")

    # Phase 4: Adapter factory (simulator or OPC-UA)
    adapter_factory = AdapterFactory(settings)
    simulator_adapter = adapter_factory.simulator_adapter
    if simulator_adapter is not None:
        controllers = await repo.list_all()
        for ctrl in controllers:
            simulator_adapter.register_controller(ctrl.id)
        simulator_adapter.start()
        logger.info("simulator_started", port=settings.simulator_port)

    # Phase 3b: OPC-UA adapter lifecycle
    opcua_adapter = adapter_factory.opcua_adapter
    if opcua_adapter is not None:
        controllers = await repo.list_all()
        for ctrl in controllers:
            tb = ctrl.tag_bindings
            if tb.node_id_pv:  # Only register if tags are configured
                opcua_adapter.register_controller(
                    controller_id=ctrl.id,
                    node_id_pv=tb.node_id_pv,
                    node_id_sp=tb.node_id_sp,
                    node_id_co=tb.node_id_co,
                    node_id_integral=tb.node_id_integral,
                )
        opcua_adapter.start()
        logger.info("opcua_adapter_started", endpoint=settings.opcua_endpoint)

    # Migrate users from .spid to standalone users.db if needed
    await _migrate_users_if_needed(settings.db_path, settings.users_db_path)

    # Phase 2: User repo + seed admin (standalone DB)
    user_repo = UserRepository(settings.users_db_path)
    await user_repo.initialize()
    users = await user_repo.list_all()
    if not users:
        admin_hash = hash_password("admin")
        await user_repo.create("admin", admin_hash, "ADMIN")
        logger.warning(
            "seeded_default_admin",
            msg="SECURITY: Default admin account created with password 'admin'. "
            "Change it immediately via the /users API or set SPID_ADMIN_PASSWORD env var.",
        )

    # Project service
    from smart_pid_core.application.project_service import ProjectService

    project_service = ProjectService(
        repo=repo, loop_manager=loop_manager,
        simulator_adapter=simulator_adapter,
    )

    # Phase 5: AI Repository
    from smart_pid_core.adapters.outbound.ai_repo import AIRepository

    ai_repo = AIRepository(repo.db)

    # Phase 6: Alarm + Audit infrastructure
    from smart_pid_core.adapters.outbound.alarm_repo import AlarmRepository
    from smart_pid_core.adapters.outbound.audit_repo import AuditRepository
    from smart_pid_core.application.workers.alarm_worker import AlarmWorker

    alarm_repo = AlarmRepository(repo.db)
    audit_repo = AuditRepository(repo.db)

    # Build alarm configs from Configuracao_Alarmes table
    alarm_configs = await _load_alarm_configs(repo.db)
    alarm_worker = AlarmWorker(bus=bus, alarm_configs=alarm_configs, alarm_repo=alarm_repo)
    alarm_worker.start()
    logger.info("alarm_worker_started")

    # I-INT-1: DBWorker — persist telemetry to SQLite
    from smart_pid_core.application.workers.db_worker import DBWorker

    db_worker = DBWorker(bus=bus, historian=historian)
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

    # C-INT-3: ExportWorker — CSV/JSON export jobs
    from smart_pid_core.application.export_worker import ExportWorker

    export_dir = str(settings.db_path.parent / "exports")
    export_worker = ExportWorker(historian=historian, export_dir=export_dir)
    logger.info("export_worker_created", export_dir=export_dir)

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
        project_service=project_service,
        alarm_repo=alarm_repo,
        audit_repo=audit_repo,
    )

    # Set export_worker on app.state so the export router can use it
    app.state.export_worker = export_worker

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

    # Run uvicorn and wait for shutdown signal concurrently
    server_task = asyncio.create_task(server.serve())
    logger.info("daemon_ready")

    await stop_event.wait()
    logger.info("shutting_down")

    # Graceful shutdown in correct order
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
