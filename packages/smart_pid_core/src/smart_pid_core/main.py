"""Smart PID Core Engine — backend daemon entry point."""
from __future__ import annotations

import asyncio
import logging
import signal
import sys

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

logger = structlog.get_logger()


async def run_daemon(settings: CoreSettings) -> None:
    """Bootstrap and run the backend daemon until interrupted."""
    logger.info("starting_daemon", api_port=settings.api_port, zmq_port=settings.zmq_publish_port)

    # Phase 1 components
    repo = SQLiteRepository(settings.db_path)
    await repo.initialize()
    historian = SQLiteHistorian(repo.db)
    bus = EventBus()
    bus.start()
    loop_manager = LoopManager(bus=bus)
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

    # Phase 2: User repo + seed admin
    user_repo = UserRepository(repo.db)
    users = await user_repo.list_all()
    if not users:
        admin_hash = hash_password("admin")
        await user_repo.create("admin", admin_hash, "admin")
        logger.warning("seeded_default_admin", msg="Change default admin password!")

    # Phase 5: AI Repository
    from smart_pid_core.adapters.outbound.ai_repo import AIRepository

    ai_repo = AIRepository(repo.db)

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
    )

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
    if simulator_adapter is not None:
        simulator_adapter.stop()
    if opcua_adapter is not None:
        opcua_adapter.stop()
    loop_manager.stop_all()
    bus.stop()
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
