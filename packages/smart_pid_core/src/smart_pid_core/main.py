"""Smart PID Core Engine — backend daemon entry point."""
from __future__ import annotations
import asyncio
import logging
import signal
import sys
import structlog
from smart_pid_core.application.event_bus import EventBus
from smart_pid_core.application.loop_manager import LoopManager
from smart_pid_core.config import CoreSettings

logger = structlog.get_logger()


async def run_daemon(settings: CoreSettings) -> None:
    """Bootstrap and run the backend daemon until interrupted."""
    logger.info("starting_daemon", api_port=settings.api_port, zmq_port=settings.zmq_publish_port)
    bus = EventBus()
    bus.start()
    logger.info("event_bus_started")
    loop_manager = LoopManager(bus=bus)
    stop_event = asyncio.Event()

    def handle_signal() -> None:
        logger.info("shutdown_signal_received")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, handle_signal)

    logger.info("daemon_ready")
    await stop_event.wait()
    logger.info("shutting_down")
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
