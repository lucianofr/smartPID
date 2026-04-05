"""MonitorWorker — enriches telemetry and publishes STATUS for monitor mode.

In monitor mode the PIDWorker does not run, so nothing publishes ``STATUS.{id}``.
MonitorWorker fills this gap:

* Subscribes to ``TELEMETRY.{id}`` from EventBus (published by IOWorker).
* Enriches: calculates error (PV − SP), detects CO saturation via limit_bits.
* Publishes ``STATUS.{id}`` — consumed by AlarmWorker, StatsWorker,
  TelemetryPublisher, and HMI.
"""
from __future__ import annotations

import logging
import threading
import time
from typing import TYPE_CHECKING

import msgpack

if TYPE_CHECKING:
    from smart_pid_core.application.event_bus import EventBus

logger = logging.getLogger(__name__)

_DEFAULT_SIGNAL: dict[str, object] = {
    "value": 0.0,
    "severity": "GOOD",
    "limit_bits": "NONE",
    "sub_status": "NONE",
}


class MonitorWorker:
    """Subscribes to TELEMETRY.{id}, enriches with error/saturation, publishes STATUS.{id}."""

    def __init__(
        self,
        bus: EventBus,
        controller_id: int,
        scan_rate_ms: int = 100,
    ) -> None:
        self._bus = bus
        self._cid = controller_id
        self._scan_rate_s = scan_rate_ms / 1000.0
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def controller_id(self) -> int:
        return self._cid

    def start(self) -> None:
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            daemon=True,
            name=f"monitor-worker-{self._cid}",
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5.0)
            self._thread = None

    def is_alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def _run(self) -> None:
        sub = self._bus.create_subscriber(f"TELEMETRY.{self._cid}".encode())
        pub = self._bus.create_publisher()
        time.sleep(0.02)  # let ZMQ subscriptions propagate

        logger.info("MonitorWorker started for controller %s", self._cid)

        try:
            while not self._stop_event.is_set():
                tick_start = time.monotonic()
                latest = self._drain_latest(sub)
                if latest is not None:
                    status_msg = self._enrich(latest)
                    pub.send(
                        f"STATUS.{self._cid}".encode(),
                        msgpack.packb(status_msg),
                    )

                elapsed = time.monotonic() - tick_start
                sleep_time = self._scan_rate_s - elapsed
                if sleep_time > 0:
                    self._stop_event.wait(timeout=sleep_time)
        finally:
            sub.close()
            pub.close()

    @staticmethod
    def _drain_latest(sub) -> dict | None:  # noqa: ANN001
        """Drain all pending telemetry messages and return the latest one."""
        latest = None
        while True:
            msg = sub.recv(timeout_ms=0)
            if msg is None:
                break
            _topic, payload = msg
            latest = msgpack.unpackb(payload)
        return latest

    @staticmethod
    def _enrich(telem: dict) -> dict:
        """Enrich a TELEMETRY message into a STATUS message with error and saturation."""
        # Extract PV and SP values (handle both dict and plain float)
        pv_data = telem["pv"]
        sp_data = telem["sp"]
        pv_val = pv_data["value"] if isinstance(pv_data, dict) else float(pv_data)
        sp_val = sp_data["value"] if isinstance(sp_data, dict) else float(sp_data)
        error = pv_val - sp_val

        # Detect CO saturation from limit_bits
        co_data = telem["co"]
        co_limit = co_data.get("limit_bits", "NONE") if isinstance(co_data, dict) else "NONE"
        saturated = co_limit.upper() in ("HIGH_LIMITED", "LOW_LIMITED")

        return {
            "controller_id": telem["controller_id"],
            "pv": telem["pv"],
            "sp": telem["sp"],
            "co": telem["co"],
            "mode": telem.get("mode", "UNKNOWN"),
            "bkcal_in": telem.get("bkcal_in", dict(_DEFAULT_SIGNAL)),
            "bkcal_out": telem.get("bkcal_out", dict(_DEFAULT_SIGNAL)),
            "integral_val": telem.get("integral_val", 0.0),
            "error": error,
            "saturated": saturated,
            "timestamp": telem.get("timestamp", time.time()),
        }
