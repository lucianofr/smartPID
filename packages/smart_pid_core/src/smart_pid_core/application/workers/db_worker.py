"""DB Worker — subscribes to bus, buffers telemetry, flushes to SQLite in batches."""
from __future__ import annotations

import asyncio
import threading
from collections import deque
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import msgpack
import zmq

from smart_pid_domain.models.signal import FFSignal
from smart_pid_domain.models.telemetry import TelemetryFrame

if TYPE_CHECKING:
    from smart_pid_core.adapters.outbound.historian import SQLiteHistorian
    from smart_pid_core.application.event_bus import EventBus


class DBWorker:
    """Daemon thread that subscribes to TELEMETRY.* and flushes batches to SQLite."""

    def __init__(
        self,
        bus: EventBus,
        historian: SQLiteHistorian,
        flush_interval_s: float = 5.0,
        batch_size: int = 500,
    ) -> None:
        self._bus = bus
        self._historian = historian
        self._flush_interval_s = flush_interval_s
        self._batch_size = batch_size
        self._buffer: deque[TelemetryFrame] = deque(maxlen=10_000)
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="db-worker")
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5.0)
            self._thread = None

    def _run(self) -> None:
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(self._run_async())
        finally:
            loop.close()

    async def _run_async(self) -> None:
        sub = self._bus.create_subscriber(b"TELEMETRY")
        while not self._stop_event.is_set():
            try:
                # Wait for messages up to flush interval
                msg = sub.recv(timeout_ms=int(self._flush_interval_s * 1000))
                if msg is not None:
                    self._process_message(msg)
                # Drain remaining without blocking
                while True:
                    msg = sub.recv(timeout_ms=0)
                    if msg is None:
                        break
                    self._process_message(msg)
            except zmq.ZMQError:
                break
            # Flush
            await self._flush()
        # Final flush on shutdown
        await self._flush()

    def _process_message(self, msg: tuple[bytes, bytes]) -> None:
        _topic, payload = msg
        try:
            data = msgpack.unpackb(payload)
            ts = datetime.fromisoformat(data["timestamp"]).replace(tzinfo=UTC)
            frame = TelemetryFrame(
                controller_id=data["controller_id"],
                pv=FFSignal.good(data["pv"], ts),
                sp=FFSignal.good(data["sp"], ts),
                co=FFSignal.good(data["co"], ts),
                bkcal_in=FFSignal.good(data.get("bkcal_in", 0.0), ts),
                integral_val=data["integral_val"],
                timestamp=ts,
            )
            self._buffer.append(frame)
        except (KeyError, ValueError, msgpack.UnpackException):
            pass

    async def _flush(self) -> None:
        if not self._buffer:
            return
        batch = list(self._buffer)
        self._buffer.clear()
        await self._historian.write_batch(batch)
