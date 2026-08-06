"""Trend-buffer worker — fills the in-memory 72-hour ring from the TELEMETRY bus."""
from __future__ import annotations

import contextlib
import threading
from typing import TYPE_CHECKING

import msgpack
import structlog
import zmq

if TYPE_CHECKING:
    from smart_pid_core.application.event_bus import EventBus
    from smart_pid_core.application.trend_buffer import TrendBuffer


class TrendBufferWorker:
    """Daemon thread that subscribes to ``TELEMETRY.*`` and offers every frame
    to the shared :class:`TrendBuffer`, which thins the 10 Hz scan to one
    sample per second.

    Same subscription and payload contract as ``DBWorker`` (msgpack dict with
    ``controller_id``, ``pv``/``sp``/``co`` signal dicts, ISO ``timestamp``) —
    IOWorker is the single publisher for real and simulator loops alike.
    Unlike DBWorker there is no flush and no SQLite: the ring itself is the
    store, so the loop is synchronous and needs no event loop of its own.
    """

    def __init__(self, bus: EventBus, buffer: TrendBuffer) -> None:
        self._bus = bus
        self._buffer = buffer
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._log = structlog.get_logger()

    def start(self) -> None:
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run, daemon=True, name="trend-buffer-worker"
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5.0)
            self._thread = None

    def _run(self) -> None:
        sub = self._bus.create_subscriber(b"TELEMETRY")
        try:
            while not self._stop_event.is_set():
                try:
                    msg = sub.recv(timeout_ms=500)
                except zmq.ZMQError:
                    break
                if msg is None:
                    continue
                self._process(msg)
        finally:
            # ZMQ sockets must be closed by the thread that created them
            # (see DBWorker._run).
            with contextlib.suppress(Exception):
                sub.close()

    def _process(self, msg: tuple[bytes, bytes]) -> None:
        _topic, payload = msg
        try:
            data = msgpack.unpackb(payload)
            ts = self._epoch(data["timestamp"])
            self._buffer.append(
                data["controller_id"],
                ts,
                float(data["pv"]["value"]),
                float(data["sp"]["value"]),
                float(data["co"]["value"]),
            )
        except (KeyError, TypeError, ValueError, msgpack.UnpackException):
            # One malformed frame must not kill the ring for every loop.
            pass

    @staticmethod
    def _epoch(raw: object) -> float:
        """ISO-8601 string or float epoch seconds → epoch seconds (UTC)."""
        if isinstance(raw, (int, float)):
            return float(raw)
        from datetime import UTC, datetime

        dt = datetime.fromisoformat(str(raw))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt.timestamp()
