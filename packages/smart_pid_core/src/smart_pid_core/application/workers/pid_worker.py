"""PID Worker — high-priority daemon thread executing PID at the controller's scan rate."""
from __future__ import annotations

import dataclasses
import threading
import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import msgpack
import zmq

from smart_pid_core.domain.services.pid_engine import PIDState
from smart_pid_core.domain.services.pid_mode_manager import BlockStatus
from smart_pid_domain.enums import ControllerMode, InitSubStatus
from smart_pid_domain.models.signal import FFSignal, FFSignalStatus

if TYPE_CHECKING:
    from smart_pid_core.application.event_bus import EventBus
    from smart_pid_core.domain.services.pid_engine import PIDEngine
    from smart_pid_core.domain.services.pid_mode_manager import ModeManager
    from smart_pid_domain.models.controller import Controller


def _deserialize_ff_signal(data: dict | float | int) -> FFSignal:
    """Deserialize an FFSignal from msgpack data.

    Backward compatible: plain float/int is wrapped as FFSignal.good(value).
    """
    if isinstance(data, (float, int)):
        return FFSignal.good(float(data))
    from smart_pid_domain.enums import LimitBits, SignalSeverity
    return FFSignal(
        value=float(data.get("value", 0.0)),
        status=FFSignalStatus(
            severity=SignalSeverity(data.get("severity", "GOOD")),
            limit_bits=LimitBits(data.get("limit_bits", "NONE")),
            sub_status=InitSubStatus(data.get("sub_status", "NONE")),
        ),
        timestamp=None,
    )


def _serialize_ff_signal(signal: FFSignal) -> dict:
    """Serialize an FFSignal to a msgpack-compatible dict."""
    return {
        "value": signal.value,
        "severity": signal.status.severity.value,
        "limit_bits": signal.status.limit_bits.value,
        "sub_status": signal.status.sub_status.value,
    }


class PIDWorker:
    def __init__(
        self, bus: EventBus, controller: Controller, engine: PIDEngine, mode_manager: ModeManager
    ) -> None:
        self._bus = bus
        self._controller = controller
        self._engine = engine
        self._mode_manager = mode_manager
        self._state = PIDState()
        self._mode = ControllerMode.MAN
        self._block_status = BlockStatus()
        self._last_pv: FFSignal = FFSignal.good(0.0)
        self._last_sp: FFSignal = FFSignal.good(0.0)
        self._last_co: FFSignal = FFSignal.good(0.0)
        self._last_bkcal_in: FFSignal = FFSignal.good(0.0)
        self._last_bkcal_out: FFSignal = FFSignal.good(0.0)
        self._has_telemetry = False
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def controller_id(self) -> int:
        return self._controller.id

    def start(self) -> None:
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run, daemon=True, name=f"pid-worker-{self.controller_id}"
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5.0)
            self._thread = None

    def is_alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @property
    def current_mode(self) -> ControllerMode:
        return self._mode

    def set_mode(self, mode: ControllerMode) -> None:
        with self._lock:
            self._mode = mode

    def set_sp(self, value: float) -> None:
        with self._lock:
            self._last_sp = FFSignal.good(value)

    def set_output(self, value: float) -> None:
        with self._lock:
            self._last_co = FFSignal.good(value)

    def _run(self) -> None:
        telem_sub = self._bus.create_subscriber(f"TELEMETRY.{self.controller_id}".encode())
        ai_sub = self._bus.create_subscriber(f"ACTION.AI.{self.controller_id}".encode())
        pub = self._bus.create_publisher()
        scan_s = self._controller.scan_rate_ms / 1000.0
        time.sleep(0.02)

        while not self._stop_event.is_set():
            try:
                tick_start = time.monotonic()
                self._drain_telemetry(telem_sub)
                self._drain_ai_actions(ai_sub)

                delta_cv = 0.0

                # Evaluate cascade handshake
                cascade_action = self._mode_manager.evaluate_cascade_handshake(
                    current_mode=self._mode,
                    bkcal_in=self._last_bkcal_in,
                )
                if cascade_action.force_mode is not None:
                    self._mode = cascade_action.force_mode
                    if cascade_action.requires_bumpless:
                        self._state = self._engine.bumpless_transfer(
                            state=self._state,
                            current_pv=self._last_pv.value,
                            current_co=self._last_bkcal_in.value,
                            params=self._controller.pid_params,
                        )

                if self._has_telemetry:
                    if (
                        self._mode == ControllerMode.IMAN
                        and cascade_action.tracking_target is not None
                    ):
                        result = self._engine.compute_iman_tracking(
                            state=self._state,
                            pv=self._last_pv,
                            sp=self._last_sp,
                            bkcal_in=self._last_bkcal_in,
                            direct_acting=self._controller.control_opts.direct_acting,
                        )
                        self._state = result.new_state
                        self._last_co = result.bkcal_out
                        self._last_bkcal_out = result.bkcal_out
                        delta_cv = result.delta_cv
                    elif self._mode in {
                        ControllerMode.AUTO,
                        ControllerMode.CAS,
                        ControllerMode.RCAS,
                    }:
                        params = self._controller.pid_params
                        out_limits = (self._controller.out_lo_lim, self._controller.out_hi_lim)
                        arw_limits = (self._controller.arw_lo_lim, self._controller.arw_hi_lim)
                        direct_acting = self._controller.control_opts.direct_acting
                        result = self._engine.compute(
                            params=params,
                            state=self._state,
                            pv=self._last_pv,
                            sp=self._last_sp,
                            bkcal_in=self._last_bkcal_in,
                            dt=scan_s,
                            out_limits=out_limits,
                            direct_acting=direct_acting,
                            arw_limits=arw_limits,
                        )
                        self._state = result.new_state
                        self._last_co = FFSignal.good(result.cv)
                        self._last_bkcal_out = result.bkcal_out
                        delta_cv = result.delta_cv

                    # Publish control action
                    action_data = {
                        "controller_id": self.controller_id,
                        "co": _serialize_ff_signal(self._last_co),
                        "bkcal_out": _serialize_ff_signal(self._last_bkcal_out),
                        "integral_val": self._state.cv,
                        "delta_cv": delta_cv,
                        "timestamp": datetime.now(tz=UTC).isoformat(),
                    }
                    topic = f"ACTION.CTRL.{self.controller_id}".encode()
                    pub.send(topic, msgpack.packb(action_data))

                if self._has_telemetry:
                    telem_data = {
                        "controller_id": self.controller_id,
                        "pv": _serialize_ff_signal(self._last_pv),
                        "sp": _serialize_ff_signal(self._last_sp),
                        "co": _serialize_ff_signal(self._last_co),
                        "bkcal_in": _serialize_ff_signal(self._last_bkcal_in),
                        "bkcal_out": _serialize_ff_signal(self._last_bkcal_out),
                        "integral_val": self._state.cv,
                        "timestamp": datetime.now(tz=UTC).isoformat(),
                    }
                    pub.send(
                        f"STATUS.{self.controller_id}".encode(),
                        msgpack.packb(telem_data),
                    )

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
                self._last_pv = _deserialize_ff_signal(data["pv"])
                self._last_sp = _deserialize_ff_signal(data["sp"])
                if "bkcal_in" in data:
                    self._last_bkcal_in = _deserialize_ff_signal(data["bkcal_in"])
                if not self._has_telemetry:
                    self._last_co = _deserialize_ff_signal(data.get("co", 0.0))
                self._has_telemetry = True
            except (KeyError, ValueError, msgpack.UnpackException):
                pass

    def _drain_ai_actions(self, sub) -> None:
        while True:
            msg = sub.recv(timeout_ms=0)
            if msg is None:
                break
            _topic, payload = msg
            try:
                data = msgpack.unpackb(payload)
                new_ki = data.get("new_ki")
                if new_ki is not None:
                    with self._lock:
                        self._controller.pid_params = dataclasses.replace(
                            self._controller.pid_params, reset=float(new_ki)
                        )
            except (KeyError, ValueError, msgpack.UnpackException):
                pass
