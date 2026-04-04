"""Stats Worker — computes loop performance metrics at scan rate."""
from __future__ import annotations

import logging
import threading
import time
from typing import TYPE_CHECKING

import msgpack
import zmq

from smart_pid_core.domain.services.stats_calculator import StatsCalculator

if TYPE_CHECKING:
    from smart_pid_core.application.event_bus import EventBus
    from smart_pid_domain.models.controller import Controller

logger = logging.getLogger(__name__)


class StatsWorker:
    """Subscribes to TELEMETRY and ACTION.CTRL, computes metrics, publishes STATS."""

    def __init__(
        self,
        bus: EventBus,
        controller: Controller,
        window_size: int = 1800,
        publish_interval: int = 60,
    ) -> None:
        self._bus = bus
        self._controller = controller
        self._publish_interval = publish_interval
        self._calculator = StatsCalculator(
            window_size=window_size,
            span=controller.pv_scale.span,
            setpoint=50.0,  # Updated from telemetry
        )
        self._last_sp: float = 50.0
        self._last_co: float = 0.0
        self._last_pv: float = 0.0
        self._has_telemetry: bool = False
        self._sample_count_since_publish: int = 0
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def controller_id(self) -> int:
        return self._controller.id

    def start(self) -> None:
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            daemon=True,
            name=f"stats-worker-{self.controller_id}",
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5.0)
            self._thread = None

    def is_alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def get_current_stats(self) -> dict[str, float]:
        """Return current stats snapshot (thread-safe via GIL for simple reads)."""
        calc = self._calculator
        return {
            "controller_id": self.controller_id,
            "iae": calc.iae,
            "itae": calc.itae,
            "ise": calc.ise,
            "mse": calc.mse,
            "std_dev": calc.std_dev,
            "total_variation": calc.total_variation,
            "variability_sp": calc.variability_sp,
            "variability_range": calc.variability_range,
            "sample_count": calc.sample_count,
        }

    def _run(self) -> None:
        telem_sub = self._bus.create_subscriber(
            f"TELEMETRY.{self.controller_id}".encode()
        )
        action_sub = self._bus.create_subscriber(
            f"ACTION.CTRL.{self.controller_id}".encode()
        )
        pub = self._bus.create_publisher()
        scan_s = self._controller.scan_rate_ms / 1000.0
        time.sleep(0.02)

        while not self._stop_event.is_set():
            try:
                tick_start = time.monotonic()
                self._drain_telemetry(telem_sub)
                self._drain_actions(action_sub)

                # Add sample if we have received telemetry data
                if self._has_telemetry:
                    error = self._last_sp - self._last_pv
                    self._calculator._setpoint = self._last_sp
                    self._calculator.add_sample(
                        error=error,
                        co=self._last_co,
                        dt=scan_s,
                    )
                    self._sample_count_since_publish += 1

                # Publish stats periodically
                if self._sample_count_since_publish >= self._publish_interval:
                    stats = self.get_current_stats()
                    topic = f"STATS.{self.controller_id}".encode()
                    pub.send(topic, msgpack.packb(stats))
                    self._sample_count_since_publish = 0

                elapsed = time.monotonic() - tick_start
                sleep_time = scan_s - elapsed
                if sleep_time > 0:
                    self._stop_event.wait(timeout=sleep_time)
            except zmq.ZMQError:
                break

    def _drain_telemetry(self, sub) -> None:
        while True:
            msg = sub.recv(timeout_ms=0)
            if msg is None:
                break
            _topic, payload = msg
            try:
                data = msgpack.unpackb(payload)
                self._last_pv = data["pv"]
                self._last_sp = data["sp"]
                self._has_telemetry = True
            except (KeyError, ValueError, msgpack.UnpackException):
                pass

    def _drain_actions(self, sub) -> None:
        while True:
            msg = sub.recv(timeout_ms=0)
            if msg is None:
                break
            _topic, payload = msg
            try:
                data = msgpack.unpackb(payload)
                self._last_co = data["co"]
            except (KeyError, ValueError, msgpack.UnpackException):
                pass
