"""I/O Worker — reads telemetry from OPC-UA adapter and publishes to event bus."""
from __future__ import annotations

import logging
import threading
import time
from typing import TYPE_CHECKING

import msgpack

from smart_pid_domain.enums import InitSubStatus, LimitBits, SignalSeverity
from smart_pid_domain.models.signal import FFSignal, FFSignalStatus

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

    _PARAMS_READ_INTERVAL_S: float = 10.0

    def __init__(
        self,
        bus: EventBus,
        opcua_adapter: OPCUAAdapter,
        controller_ids: list[int],
        scan_interval_s: float = 0.1,
        execution_mode: str = "execute",
    ) -> None:
        self._bus = bus
        self._opcua = opcua_adapter
        self._controller_ids = list(controller_ids)
        self._scan_interval_s = scan_interval_s
        self._execution_mode = execution_mode
        self._skip_bkcal_write = execution_mode == "monitor"
        self._was_connected: bool = False
        self._ever_connected: bool = False
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_params_read: float = 0.0

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

    @staticmethod
    def _deserialize_bkcal_out(data: dict) -> FFSignal:
        """Deserialize BKCAL_OUT from an ACTION.CTRL msgpack dict."""
        raw = data.get("bkcal_out", {})
        if isinstance(raw, (float, int)):
            return FFSignal.good(float(raw))
        status = FFSignalStatus(
            severity=SignalSeverity(raw.get("severity", "GOOD")),
            limit_bits=LimitBits(raw.get("limit_bits", "NONE")),
            sub_status=InitSubStatus(raw.get("sub_status", "NONE")),
        )
        return FFSignal(value=float(raw.get("value", 0.0)), status=status)

    def _run(self) -> None:
        """Main loop: read from OPC-UA, publish to bus, write BKCAL_OUT back."""
        pub = self._bus.create_publisher()
        action_sub = None
        if not self._skip_bkcal_write:
            action_sub = self._bus.create_subscriber(b"ACTION.CTRL")
        # Wait briefly for bus subscriptions to propagate
        time.sleep(0.05)

        while not self._stop_event.is_set():
            tick_start = time.monotonic()
            is_connected = self._opcua.is_connected

            # Detect reconnect: was disconnected, now connected, and had connected before
            if is_connected and not self._was_connected and self._ever_connected:
                self._publish_reconnect_events(pub)

            if is_connected:
                self._ever_connected = True

            self._was_connected = is_connected

            if is_connected:
                for cid in self._controller_ids:
                    try:
                        frame = self._opcua.read_telemetry(cid)
                        mode = self._opcua.read_actual_mode(cid)
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
                            "mode": mode.value if mode else "UNKNOWN",
                            "integral_val": frame.integral_val,
                            "timestamp": frame.timestamp.isoformat(),
                        })
                        pub.send(topic, payload)
                    except (KeyError, ConnectionError):
                        pass
                    except Exception:
                        logger.exception(
                            "io_worker_read_error controller_id=%s", cid,
                        )

                # Read tuning params every 10s and publish PARAMS.{id}
                now = time.monotonic()
                if now - self._last_params_read >= self._PARAMS_READ_INTERVAL_S:
                    self._last_params_read = now
                    self._read_and_publish_params(pub)

                # Drain ACTION.CTRL.* messages and write BKCAL_OUT to OPC-UA
                if action_sub is not None:
                    self._drain_and_write_bkcal(action_sub)

            elapsed = time.monotonic() - tick_start
            sleep_time = self._scan_interval_s - elapsed
            if sleep_time > 0:
                self._stop_event.wait(timeout=sleep_time)

    def _publish_reconnect_events(self, pub) -> None:  # noqa: ANN001
        """Publish SYS.RECONNECT.{cid} for each controller after OPC-UA reconnect."""
        reconnect_pub = pub
        for cid in self._controller_ids:
            try:
                frame = self._opcua.read_telemetry(cid)
                data = {
                    "controller_id": cid,
                    "co": frame.co.value,
                    "pv": frame.pv.value,
                    "sp": frame.sp.value,
                }
                reconnect_pub.send(
                    f"SYS.RECONNECT.{cid}".encode(),
                    msgpack.packb(data),
                )
                logger.info("reconnect_event_published controller_id=%s", cid)
            except Exception:
                logger.exception("reconnect_read_error controller_id=%s", cid)

    def _read_and_publish_params(self, pub) -> None:  # noqa: ANN001
        """Read Kp/Ti/Td from OPC-UA for each controller and publish PARAMS.{id}."""
        for cid in self._controller_ids:
            try:
                params = self._opcua.read_pid_params(cid)
                if params is None:
                    continue
                topic = f"PARAMS.{cid}".encode()
                payload = msgpack.packb({
                    "controller_id": cid,
                    "kp": params.kp,
                    "ti": params.ti,
                    "td": params.td,
                    "timestamp": params.timestamp,
                })
                pub.send(topic, payload)
            except (KeyError, ConnectionError):
                pass
            except Exception:
                logger.exception(
                    "io_worker_params_read_error controller_id=%s", cid,
                )

    def _drain_and_write_bkcal(self, action_sub) -> None:
        """Drain ACTION.CTRL.* messages from bus and write BKCAL_OUT to OPC-UA."""
        while True:
            msg = action_sub.recv(timeout_ms=0)
            if msg is None:
                break
            _topic, payload = msg
            try:
                data = msgpack.unpackb(payload)
                cid = data["controller_id"]
                bkcal_out = self._deserialize_bkcal_out(data)
                self._opcua.write_bkcal_out(cid, bkcal_out)
            except (KeyError, ConnectionError):
                pass
            except Exception:
                logger.exception("io_worker_bkcal_write_error")
