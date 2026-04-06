"""SimulatorAdapter — digital twin implementing TelemetrySource + ControlWriter."""
from __future__ import annotations

import logging
import random
import threading
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from smart_pid_core.adapters.inbound.opcua_server import OPCUAServer
from smart_pid_core.domain.services.pid_engine import PIDEngine, PIDState
from smart_pid_core.domain.services.process_models import ProcessModel
from smart_pid_domain.dtos.simulator import ControllerSimStatus
from smart_pid_domain.models.controller import PIDParams
from smart_pid_domain.models.process_preset import PRESETS
from smart_pid_domain.models.signal import FFSignal

if TYPE_CHECKING:
    from smart_pid_core.config import CoreSettings
    from smart_pid_domain.enums import ProcessPresetName

logger = logging.getLogger(__name__)


@dataclass
class _ControllerSim:
    """Mutable state for one simulated controller."""

    controller_id: int
    model: ProcessModel = field(default_factory=lambda: ProcessModel(
        gain=1.2, tau1=3.0, tau2=None, dead_time=1.0,
    ))
    preset_name: str = "FLOW"
    gain: float = 1.2
    tau1: float = 3.0
    tau2: float | None = None
    dead_time: float = 1.0
    last_co: float = 0.0
    sp: float = 50.0
    step_active: bool = False
    step_amplitude: float = 0.0
    noise_active: bool = False
    noise_amplitude: float = 0.0
    # Internal PID
    pid_enabled: bool = False
    pid_params: PIDParams = field(default_factory=PIDParams)
    pid_state: PIDState = field(default_factory=PIDState)
    pid_mode: int = 0  # 0=MAN, 1=AUTO


class SimulatorAdapter:
    """Digital twin adapter — TelemetrySource + ControlWriter."""

    def __init__(self, settings: CoreSettings) -> None:
        self._settings = settings
        self._controllers: dict[int, _ControllerSim] = {}
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._pid_engine = PIDEngine()
        self._opcua_server = OPCUAServer(port=settings.simulator_port)
        self._opcua_server.set_on_write(self._on_opcua_write)

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._opcua_server.start()
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="simulator")
        self._thread.start()
        logger.info("Simulator started (interval=%dms)", self._settings.simulator_interval_ms)

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
        self._opcua_server.stop()
        logger.info("Simulator stopped")

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def _on_opcua_write(self, controller_id: int, param: str, value: float) -> None:
        """Handle writes from OPC-UA clients (e.g., OPCUAAdapter writing CO)."""
        with self._lock:
            ctrl = self._controllers.get(controller_id)
            if ctrl is None:
                return
            if param == "co":
                ctrl.last_co = value
            elif param == "sp":
                ctrl.sp = value
            elif param == "kp":
                ctrl.pid_params.gain = value
            elif param == "ti":
                ctrl.pid_params.reset = value
            elif param == "td":
                ctrl.pid_params.rate = value
            elif param == "pid_mode":
                ctrl.pid_mode = int(value)
            elif param == "pid_sp":
                ctrl.sp = value

    def write_output(self, controller_id: int, co: float) -> None:
        with self._lock:
            ctrl = self._controllers.get(controller_id)
            if ctrl is not None:
                ctrl.last_co = co

    def write_parameter(self, controller_id: int, param: str, value: float) -> None:
        """No-op for simulator — satisfies ControlWriter protocol."""

    def enable_pid(self, controller_id: int, enabled: bool) -> None:
        with self._lock:
            ctrl = self._controllers[controller_id]
            ctrl.pid_enabled = enabled
            if enabled:
                ctrl.pid_state = self._pid_engine.bumpless_transfer(
                    ctrl.pid_state, current_pv=0.0, current_co=ctrl.last_co,
                    params=ctrl.pid_params,
                )

    def set_pid_params(self, controller_id: int, kp: float, ti: float, td: float) -> None:
        with self._lock:
            ctrl = self._controllers[controller_id]
            ctrl.pid_params.gain = kp
            ctrl.pid_params.reset = ti
            ctrl.pid_params.rate = td

    def set_pid_mode(self, controller_id: int, mode: int) -> None:
        with self._lock:
            ctrl = self._controllers[controller_id]
            ctrl.pid_mode = mode

    def get_pid_status(self, controller_id: int) -> dict:
        with self._lock:
            ctrl = self._controllers[controller_id]
            return {
                "enabled": ctrl.pid_enabled,
                "kp": ctrl.pid_params.gain,
                "ti": ctrl.pid_params.reset,
                "td": ctrl.pid_params.rate,
                "mode": ctrl.pid_mode,
                "cv": ctrl.pid_state.cv,
            }

    def register_controller(self, controller_id: int) -> None:
        with self._lock:
            if controller_id not in self._controllers:
                self._controllers[controller_id] = _ControllerSim(controller_id=controller_id)
                self._opcua_server.register_controller(controller_id)

    def set_preset(self, controller_id: int, preset: ProcessPresetName) -> None:
        with self._lock:
            ctrl = self._controllers[controller_id]
            p = PRESETS[preset]
            ctrl.model = ProcessModel.from_preset(p)
            ctrl.preset_name = preset.value
            ctrl.gain = p.gain
            ctrl.tau1 = p.tau1
            ctrl.tau2 = p.tau2
            ctrl.dead_time = p.dead_time

    def set_parameters(
        self,
        controller_id: int,
        gain: float,
        tau1: float,
        tau2: float | None,
        dead_time: float,
    ) -> None:
        with self._lock:
            ctrl = self._controllers[controller_id]
            ctrl.model = ProcessModel(gain=gain, tau1=tau1, tau2=tau2, dead_time=dead_time)
            ctrl.preset_name = "CUSTOM"
            ctrl.gain = gain
            ctrl.tau1 = tau1
            ctrl.tau2 = tau2
            ctrl.dead_time = dead_time

    def inject_step(self, controller_id: int, amplitude: float) -> None:
        with self._lock:
            ctrl = self._controllers[controller_id]
            ctrl.step_active = True
            ctrl.step_amplitude = amplitude

    def inject_noise(self, controller_id: int, amplitude: float) -> None:
        with self._lock:
            ctrl = self._controllers[controller_id]
            ctrl.noise_active = True
            ctrl.noise_amplitude = amplitude

    def clear_disturbance(self, controller_id: int) -> None:
        with self._lock:
            ctrl = self._controllers[controller_id]
            ctrl.step_active = False
            ctrl.step_amplitude = 0.0
            ctrl.noise_active = False
            ctrl.noise_amplitude = 0.0

    def get_controller_status(self, controller_id: int) -> ControllerSimStatus:
        with self._lock:
            ctrl = self._controllers[controller_id]
            return ControllerSimStatus(
                preset=ctrl.preset_name,
                gain=ctrl.gain,
                tau1=ctrl.tau1,
                tau2=ctrl.tau2,
                dead_time=ctrl.dead_time,
                step_active=ctrl.step_active,
                step_amplitude=ctrl.step_amplitude,
                noise_active=ctrl.noise_active,
                noise_amplitude=ctrl.noise_amplitude,
                pid_enabled=ctrl.pid_enabled,
                pid_kp=ctrl.pid_params.gain,
                pid_ti=ctrl.pid_params.reset,
                pid_td=ctrl.pid_params.rate,
                pid_mode=ctrl.pid_mode,
                pid_cv=ctrl.pid_state.cv,
            )

    def get_status(self) -> dict[int, ControllerSimStatus]:
        with self._lock:
            return {
                cid: ControllerSimStatus(
                    preset=ctrl.preset_name,
                    gain=ctrl.gain,
                    tau1=ctrl.tau1,
                    tau2=ctrl.tau2,
                    dead_time=ctrl.dead_time,
                    step_active=ctrl.step_active,
                    step_amplitude=ctrl.step_amplitude,
                    noise_active=ctrl.noise_active,
                    noise_amplitude=ctrl.noise_amplitude,
                    pid_enabled=ctrl.pid_enabled,
                    pid_kp=ctrl.pid_params.gain,
                    pid_ti=ctrl.pid_params.reset,
                    pid_td=ctrl.pid_params.rate,
                    pid_mode=ctrl.pid_mode,
                    pid_cv=ctrl.pid_state.cv,
                )
                for cid, ctrl in self._controllers.items()
            }

    def _run_loop(self) -> None:
        interval_s = self._settings.simulator_interval_ms / 1000.0
        while not self._stop_event.is_set():
            start = time.monotonic()
            self._tick(interval_s)
            elapsed = time.monotonic() - start
            sleep_time = interval_s - elapsed
            if sleep_time > 0:
                self._stop_event.wait(timeout=sleep_time)

    def _tick(self, dt: float) -> None:
        with self._lock:
            for ctrl in self._controllers.values():
                pv = ctrl.model.step(co=ctrl.last_co, dt=dt)
                if ctrl.step_active:
                    pv += ctrl.step_amplitude
                if ctrl.noise_active:
                    pv += random.gauss(0, ctrl.noise_amplitude)

                # Internal PID: compute CO when enabled and AUTO
                if ctrl.pid_enabled and ctrl.pid_mode == 1:
                    result = self._pid_engine.compute(
                        params=ctrl.pid_params,
                        state=ctrl.pid_state,
                        pv=FFSignal.good(pv),
                        sp=FFSignal.good(ctrl.sp),
                        bkcal_in=FFSignal.good(ctrl.pid_state.cv),
                        dt=dt,
                        out_limits=(0.0, 100.0),
                    )
                    ctrl.pid_state = result.new_state
                    ctrl.last_co = result.cv

                self._opcua_server.update_values(
                    controller_id=ctrl.controller_id,
                    pv=pv,
                    sp=ctrl.sp,
                    co=ctrl.last_co,
                )
