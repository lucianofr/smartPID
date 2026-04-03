"""PID Worker — high-priority daemon thread executing PID at the controller's scan rate."""
from __future__ import annotations

import threading
import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import msgpack
import zmq

from smart_pid_core.domain.services.pid_engine import PIDState
from smart_pid_core.domain.services.pid_mode_manager import BlockStatus
from smart_pid_domain.enums import ControllerMode

if TYPE_CHECKING:
    from smart_pid_core.application.event_bus import EventBus
    from smart_pid_core.domain.services.pid_engine import PIDEngine
    from smart_pid_core.domain.services.pid_mode_manager import ModeManager
    from smart_pid_domain.models.controller import Controller


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
        self._last_pv: float = 0.0
        self._last_sp: float = 0.0
        self._last_co: float = 0.0
        self._has_telemetry = False
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

    def set_mode(self, mode: ControllerMode) -> None:
        self._mode = mode

    def _run(self) -> None:
        telem_sub = self._bus.create_subscriber(f"TELEMETRY.{self.controller_id}".encode())
        ai_sub = self._bus.create_subscriber(f"ACTION.AI.{self.controller_id}".encode())
        pub = self._bus.create_publisher()
        scan_s = self._controller.scan_rate_ms / 1000.0
        time.sleep(0.02)  # Let subscriptions propagate

        while not self._stop_event.is_set():
            try:
                tick_start = time.monotonic()
                self._drain_telemetry(telem_sub)
                self._drain_ai_actions(ai_sub)

                if self._has_telemetry and self._mode in {
                    ControllerMode.AUTO, ControllerMode.CAS, ControllerMode.RCAS
                }:
                    params = self._controller.pid_params
                    out_limits = (self._controller.out_lo_lim, self._controller.out_hi_lim)
                    arw_limits = (self._controller.arw_lo_lim, self._controller.arw_hi_lim)
                    direct_acting = self._controller.control_opts.direct_acting
                    result = self._engine.compute(
                        params=params, state=self._state, pv=self._last_pv, sp=self._last_sp,
                        dt=scan_s, out_limits=out_limits, direct_acting=direct_acting,
                        arw_limits=arw_limits,
                    )
                    self._state = result.new_state
                    self._last_co = result.cv
                    action_data = {
                        "controller_id": self.controller_id, "co": result.cv,
                        "integral_val": result.new_state.cv, "delta_cv": result.delta_cv,
                        "timestamp": datetime.now(tz=UTC).isoformat(),
                    }
                    topic = f"ACTION.CTRL.{self.controller_id}".encode()
                    pub.send(topic, msgpack.packb(action_data))

                if self._has_telemetry:
                    telem_data = {
                        "controller_id": self.controller_id, "pv": self._last_pv,
                        "sp": self._last_sp, "co": self._last_co,
                        "integral_val": self._state.cv,
                        "timestamp": datetime.now(tz=UTC).isoformat(), "status": "GOOD",
                    }
                    pub.send(f"STATUS.{self.controller_id}".encode(), msgpack.packb(telem_data))

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
                if not self._has_telemetry:
                    self._last_co = data.get("co", 0.0)
                self._has_telemetry = True
            except (KeyError, ValueError, msgpack.UnpackException):
                pass

    def _drain_ai_actions(self, sub) -> None:
        while True:
            msg = sub.recv(timeout_ms=0)
            if msg is None:
                break
            # AI actions will be handled in Phase 5
