"""Bus Bridge — QTimer on main thread drains SimpleQueue -> typed Qt Signals."""
from __future__ import annotations

import time
from queue import Empty, SimpleQueue

from PySide6.QtCore import QObject, QTimer, Signal


class BusBridge(QObject):
    """Bridges network thread data into Qt signal/slot world."""

    telemetry_received = Signal(int, object)     # (controller_id, frame_dict)
    alarm_received = Signal(int, object)         # (controller_id, alarm_dict)
    system_state_changed = Signal(object)        # (state_dict)
    connection_lost = Signal()
    connection_restored = Signal()

    def __init__(
        self,
        queue: SimpleQueue,
        refresh_ms: int = 33,
        heartbeat_timeout_s: float = 5.0,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._queue = queue
        self._refresh_ms = refresh_ms
        self._heartbeat_timeout = heartbeat_timeout_s
        self._latest: dict[int, dict] = {}
        self._last_frame_time: float = 0.0
        self._connected = True
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._drain)

    def start(self) -> None:
        self._last_frame_time = time.monotonic()
        self._timer.start(self._refresh_ms)

    def stop(self) -> None:
        self._timer.stop()

    def set_refresh_ms(self, ms: int) -> None:
        """Update the drain interval (milliseconds)."""
        self._refresh_ms = ms
        if self._timer.isActive():
            self._timer.setInterval(ms)

    def latest(self, controller_id: int) -> dict | None:
        return self._latest.get(controller_id)

    def _drain(self) -> None:
        batch: dict[int, dict] = {}
        alarms: list[tuple[int, dict]] = []

        # Drain all available messages
        while True:
            try:
                topic, data = self._queue.get_nowait()
            except Empty:
                break

            if topic.startswith("STATUS."):
                cid = data.get("controller_id", 0)
                batch[cid] = data  # keep only latest per controller
                self._last_frame_time = time.monotonic()
            elif topic.startswith("EVENT.ALARM."):
                cid = data.get("controller_id", 0)
                alarms.append((cid, data))
                self._last_frame_time = time.monotonic()

        # Emit batched telemetry (one per controller)
        for cid, frame in batch.items():
            frame = self._normalize_frame(frame)
            self._latest[cid] = frame
            self.telemetry_received.emit(cid, frame)

        # Emit all alarms (never drop)
        for cid, alarm in alarms:
            self.alarm_received.emit(cid, alarm)

        self._check_heartbeat()

    @staticmethod
    def _normalize_frame(frame: dict) -> dict:
        """Flatten FFSignal dicts to plain floats for widget consumption."""
        for key in ("pv", "sp", "co", "bkcal_in", "bkcal_out"):
            val = frame.get(key)
            if isinstance(val, dict):
                frame[key] = val.get("value", 0.0)
        return frame

    def _check_heartbeat(self) -> None:
        # Heartbeat check
        if self._last_frame_time > 0:
            elapsed = time.monotonic() - self._last_frame_time
            if elapsed > self._heartbeat_timeout and self._connected:
                self._connected = False
                self.connection_lost.emit()
            elif elapsed <= self._heartbeat_timeout and not self._connected:
                self._connected = True
                self.connection_restored.emit()
