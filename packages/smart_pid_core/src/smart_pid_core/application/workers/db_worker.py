"""DB Worker — subscribes to bus, buffers telemetry, flushes to SQLite in batches."""
from __future__ import annotations

import asyncio
import contextlib
import threading
from collections import deque
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import msgpack
import structlog
import zmq
from sqlalchemy.ext.asyncio import async_sessionmaker

from smart_pid_core.adapters.outbound.db_engine import create_sqlite_engine
from smart_pid_core.adapters.outbound.historian import SQLiteHistorian
from smart_pid_domain.enums import InitSubStatus, LimitBits, SignalSeverity
from smart_pid_domain.models.signal import FFSignal, FFSignalStatus
from smart_pid_domain.models.telemetry import TelemetryFrame

if TYPE_CHECKING:
    from smart_pid_core.adapters.outbound.sqlite_repo import SQLiteRepository
    from smart_pid_core.application.event_bus import EventBus


class DBWorker:
    """Daemon thread that subscribes to TELEMETRY.* and LOG.AI.*, flushing to SQLite."""

    def __init__(
        self,
        bus: EventBus,
        repo: SQLiteRepository,
        flush_interval_s: float = 5.0,
        batch_size: int = 500,
    ) -> None:
        self._bus = bus
        self._repo = repo
        self._historian: SQLiteHistorian | None = None  # built per-run on the worker loop
        self._flush_interval_s = flush_interval_s
        self._batch_size = batch_size
        self._buffer: deque[TelemetryFrame] = deque(maxlen=10_000)
        self._ai_log_buffer: deque[dict] = deque(maxlen=1_000)
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._log = structlog.get_logger()
        #: Rows in the most recent telemetry batch, reported when a flush drops it.
        self._last_batch_rows = 0
        #: Count of dropped flushes. Non-zero means the historian has holes.
        self.flush_failures = 0

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
        # Engine B — same .spid file, THIS thread's private loop (AsyncEngine
        # is loop-affine). Created at thread start against the repo's current
        # path; disposed in the finally block, so a stopped worker never holds
        # a pooled handle on the file.
        engine = create_sqlite_engine(self._repo.db_path)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        self._historian = SQLiteHistorian(session_factory)
        telem_sub = self._bus.create_subscriber(b"TELEMETRY")
        ai_sub = self._bus.create_subscriber(b"LOG.AI.")
        try:
            while not self._stop_event.is_set():
                try:
                    # Wait for telemetry messages up to flush interval
                    msg = telem_sub.recv(timeout_ms=int(self._flush_interval_s * 1000))
                    if msg is not None:
                        self._process_message(msg)
                    # Drain remaining telemetry without blocking
                    while True:
                        msg = telem_sub.recv(timeout_ms=0)
                        if msg is None:
                            break
                        self._process_message(msg)
                    # Drain AI log messages without blocking
                    while True:
                        msg = ai_sub.recv(timeout_ms=0)
                        if msg is None:
                            break
                        self._process_ai_log(msg)
                except zmq.ZMQError:
                    break
                # Flush both buffers. _safe_flush never raises: a DB error here
                # used to escape this loop and silently kill the worker thread.
                await self._safe_flush()
        finally:
            # Final flush on shutdown, then release engine B completely.
            # _safe_flush is non-raising, so dispose() always runs.
            await self._safe_flush()
            await engine.dispose()

    def _process_message(self, msg: tuple[bytes, bytes]) -> None:
        _topic, payload = msg
        try:
            data = msgpack.unpackb(payload)
            ts = datetime.fromisoformat(data["timestamp"]).replace(tzinfo=UTC)

            def _to_signal(raw: object) -> FFSignal:
                if isinstance(raw, (float, int)):
                    return FFSignal.good(float(raw), ts)
                if isinstance(raw, dict):
                    status = FFSignalStatus(
                        severity=SignalSeverity(raw.get("severity", "GOOD")),
                        limit_bits=LimitBits(raw.get("limit_bits", "NONE")),
                        sub_status=InitSubStatus(raw.get("sub_status", "NONE")),
                    )
                    return FFSignal(
                        value=float(raw.get("value", 0.0)),
                        status=status,
                        timestamp=ts,
                    )
                return FFSignal.good(0.0, ts)

            frame = TelemetryFrame(
                controller_id=data["controller_id"],
                pv=_to_signal(data["pv"]),
                sp=_to_signal(data["sp"]),
                co=_to_signal(data["co"]),
                bkcal_in=_to_signal(data.get("bkcal_in", 0.0)),
                integral_val=data["integral_val"],
                timestamp=ts,
            )
            self._buffer.append(frame)
        except (KeyError, ValueError, msgpack.UnpackException):
            pass

    def _process_ai_log(self, msg: tuple[bytes, bytes]) -> None:
        _topic, payload = msg
        try:
            data = msgpack.unpackb(payload)
            self._ai_log_buffer.append(data)
        except (ValueError, msgpack.UnpackException):
            pass

    async def _flush_ai_logs(self) -> None:
        if not self._ai_log_buffer:
            return
        batch = list(self._ai_log_buffer)
        self._ai_log_buffer.clear()
        for entry in batch:
            with contextlib.suppress(Exception):
                await self._historian.write_ai_log(entry)

    async def _flush(self) -> None:
        if not self._buffer:
            return
        batch = list(self._buffer)
        self._buffer.clear()
        self._last_batch_rows = len(batch)
        await self._historian.write_batch(batch)

    async def _safe_flush(self) -> None:
        """Flush both buffers; a DB error must never kill the worker thread.

        Degradation is **drop the batch**, deliberately:

        * ``_buffer`` is already a bounded ``deque(maxlen=10_000)`` that sheds
          the oldest frames under pressure, so shedding on a failed write is the
          same contract the buffer already honours.
        * Re-queueing would head-of-line block behind a persistently locked file
          and evict *newer* frames to hold *older* ones — a worse historian than
          the gap it avoids.
        * There is no backpressure path to the publisher (ZMQ SUB drops on the
          subscriber side), so the only alternatives are drop or unbounded growth.

        The live HMI telemetry path (ZMQ PUB) is untouched; only the historian
        record has a hole, and ``flush_failures`` plus the structured log make
        that hole observable instead of silent.
        """
        for label, flush in (
            ("telemetry", self._flush),
            ("ai_log", self._flush_ai_logs),
        ):
            try:
                await flush()
            except Exception as exc:  # noqa: BLE001 — worker must survive anything
                self.flush_failures += 1
                self._log.error(
                    "historian_flush_failed",
                    buffer=label,
                    dropped_rows=self._last_batch_rows if label == "telemetry" else 0,
                    total_failures=self.flush_failures,
                    reason=str(exc),
                )
