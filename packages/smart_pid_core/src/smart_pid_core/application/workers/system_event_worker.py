"""SystemEventWorker — facade for emitting and persisting system events."""
from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import msgpack

if TYPE_CHECKING:
    from smart_pid_core.application.event_bus import EventBus

logger = logging.getLogger(__name__)


class SystemEventWorker:
    """Thread-safe facade: any component can call emit() to record a system event."""

    def __init__(
        self,
        bus: EventBus,
        system_event_repo: Any = None,
        event_loop: asyncio.AbstractEventLoop | None = None,
    ) -> None:
        self._bus = bus
        self._repo = system_event_repo
        self._event_loop = event_loop
        self._pub = bus.create_publisher()

    def emit(self, source: str, severity: str, message: str) -> None:
        """Publish system event on bus and enqueue persistence. Thread-safe."""
        now = datetime.now(tz=UTC).isoformat()
        event_data = {
            "source": source,
            "severity": severity,
            "message": message,
            "timestamp": now,
        }

        # Publish on ZMQ bus
        try:
            self._pub.send(b"EVENT.SYSTEM", msgpack.packb(event_data))
        except Exception:
            logger.exception("system_event_publish_error")

        # Schedule persistence
        if self._repo is not None and self._event_loop is not None:
            self._event_loop.call_soon_threadsafe(
                asyncio.ensure_future,
                self._persist(source, severity, message),
            )

    async def _persist(self, source: str, severity: str, message: str) -> None:
        try:
            await self._repo.insert_event(source, severity, message)
        except Exception:
            logger.exception("system_event_persist_error")
