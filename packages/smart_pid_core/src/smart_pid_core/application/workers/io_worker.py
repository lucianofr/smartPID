"""I/O Worker — reads telemetry from OPC-UA adapter and publishes to event bus."""
from __future__ import annotations

import logging
import threading
import time
from typing import TYPE_CHECKING

import msgpack

if TYPE_CHECKING:
    from smart_pid_core.adapters.outbound.opcua_adapter import OPCUAAdapter
    from smart_pid_core.application.event_bus import EventBus

logger = logging.getLogger(__name__)


class IOWorker:
    """Daemon thread that periodically reads telemetry from OPCUAAdapter
    and publishes TELEMETRY.{controller_id} events to the internal bus.

    This is the entry point of the data pipeline: without it, no PV values
    reach the PID workers, DB worker, or telemetry publisher.
    """

    def __init__(
        self,
        bus: EventBus,
        opcua_adapter: OPCUAAdapter,
        controller_ids: list[int],
        scan_interval_s: float = 0.1,
    ) -> None:
        self._bus = bus
        self._opcua = opcua_adapter
        self._controller_ids = list(controller_ids)
        self._scan_interval_s = scan_interval_s
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def add_controller(self, controller_id: int) -> None:
        """Register an additional controller for scanning."""
        if controller_id not in self._controller_ids:
            self._controller_ids.append(controller_id)

    def start(self) -> None:
        """Start the I/O worker thread."""
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="io-worker")
        self._thread.start()
        logger.info("io_worker_started controllers=%s", self._controller_ids)

    def stop(self) -> None:
        """Stop the I/O worker thread."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5.0)
            self._thread = None
        logger.info("io_worker_stopped")

    def _run(self) -> None:
        """Main loop: read from OPC-UA, publish to bus."""
        pub = self._bus.create_publisher()
        # Wait briefly for bus subscriptions to propagate
        time.sleep(0.05)

        while not self._stop_event.is_set():
            tick_start = time.monotonic()

            if self._opcua.is_connected:
                for cid in self._controller_ids:
                    try:
                        frame = self._opcua.read_telemetry(cid)
                        topic = f"TELEMETRY.{cid}".encode()
                        payload = msgpack.packb({
                            "controller_id": frame.controller_id,
                            "pv": {
                                "value": frame.pv.value,
                                "severity": frame.pv.status.severity.value,
                                "limit_bits": frame.pv.status.limit_bits.value,
                                "sub_status": frame.pv.status.sub_status.value,
                            },
                            "sp": {
                                "value": frame.sp.value,
                                "severity": frame.sp.status.severity.value,
                                "limit_bits": frame.sp.status.limit_bits.value,
                                "sub_status": frame.sp.status.sub_status.value,
                            },
                            "co": {
                                "value": frame.co.value,
                                "severity": frame.co.status.severity.value,
                                "limit_bits": frame.co.status.limit_bits.value,
                                "sub_status": frame.co.status.sub_status.value,
                            },
                            "bkcal_in": {
                                "value": frame.bkcal_in.value,
                                "severity": frame.bkcal_in.status.severity.value,
                                "limit_bits": frame.bkcal_in.status.limit_bits.value,
                                "sub_status": frame.bkcal_in.status.sub_status.value,
                            },
                            "integral_val": frame.integral_val,
                            "timestamp": frame.timestamp.isoformat(),
                        })
                        pub.send(topic, payload)
                    except (KeyError, ConnectionError):
                        # Controller not registered or OPC-UA disconnected
                        pass
                    except Exception:
                        logger.exception(
                            "io_worker_read_error controller_id=%s", cid,
                        )

            elapsed = time.monotonic() - tick_start
            sleep_time = self._scan_interval_s - elapsed
            if sleep_time > 0:
                self._stop_event.wait(timeout=sleep_time)
