"""Telemetry Publisher — bridge from internal EventBus to external ZMQ PUB socket."""
from __future__ import annotations

import asyncio
import contextlib
from typing import TYPE_CHECKING

import structlog
import zmq
import zmq.asyncio

if TYPE_CHECKING:
    from smart_pid_core.application.event_bus import EventBus

logger = structlog.get_logger()

# Topics to bridge from internal bus to external PUB
_BRIDGE_TOPICS = [b"STATUS.", b"ACTION.CTRL.", b"EVENT.ALARM."]


class TelemetryPublisher:
    """Unidirectional bridge: subscribes to internal EventBus (inproc://)
    and republishes on ZMQ PUB socket (tcp://0.0.0.0:{port}).
    """

    def __init__(self, bus: EventBus, publish_port: int = 5555) -> None:
        self._bus = bus
        self._port = publish_port
        self._task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()

    async def start(self) -> None:
        """Start the publisher as an asyncio task."""
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run())
        logger.info("telemetry_publisher_started", port=self._port)

    async def stop(self) -> None:
        """Signal stop and wait for the task to finish."""
        self._stop_event.set()
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        logger.info("telemetry_publisher_stopped")

    async def _run(self) -> None:
        """Main loop: receive from internal bus subscribers, publish externally."""
        ctx = zmq.asyncio.Context()
        pub_socket = ctx.socket(zmq.PUB)
        pub_socket.bind(f"tcp://0.0.0.0:{self._port}")

        # Create internal subscribers for each topic prefix
        subscribers = []
        for topic in _BRIDGE_TOPICS:
            sub = self._bus.create_subscriber(topic)
            subscribers.append(sub)

        loop = asyncio.get_running_loop()

        try:
            while not self._stop_event.is_set():
                for sub in subscribers:
                    # Use run_in_executor to avoid blocking the asyncio loop
                    # with the synchronous ZMQ recv call
                    result = await loop.run_in_executor(
                        None, sub.recv, 10
                    )
                    if result is not None:
                        topic_bytes, payload = result
                        await pub_socket.send_multipart([topic_bytes, payload])
                await asyncio.sleep(0.001)
        except asyncio.CancelledError:
            pass
        finally:
            for sub in subscribers:
                sub.close()
            pub_socket.setsockopt(zmq.LINGER, 0)
            pub_socket.close()
            ctx.term()
