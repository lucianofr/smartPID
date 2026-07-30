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
from smart_pid_domain.dtos.simulator import (
    AutoDisturbanceRequest,
    AutoSPRequest,
    ControllerSimStatus,
)
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
    pid_structure: int = 0  # 0=ISA, 1=PARALLEL, 2=SERIES
    # PV scale (used for auto-excitation span calculation)
    pv_min: float = 0.0
    pv_max: float = 100.0
    # Auto SP variation
    auto_sp_enabled: bool = False
    auto_sp_min_pct: float = 30.0
    auto_sp_max_pct: float = 70.0
    auto_sp_elapsed_s: float = 0.0
    # Auto disturbance injection
    auto_dist_enabled: bool = False
    auto_dist_max_pct: float = 10.0
    auto_dist_elapsed_s: float = 0.0
    # Live computed values (updated each tick)
    live_pv: float = 0.0
    live_error: float = 0.0
    live_process_input: float = 0.0
    live_process_output: float = 0.0
    live_disturbance_output: float = 0.0


# How the simulator encodes its Mode node, and therefore the only correct
# mode_int_map for a simulator-backed controller. _ControllerSim.pid_mode and
# the /simulator/{id}/pid/mode route both use this encoding; the OPC-UA adapter
# needs it to decode Mode back into a ControllerMode.
SIMULATOR_MODE_INT_MAP: dict[str, int] = {"MAN": 0, "AUTO": 1}

# OPC-UA parameters whose mutation changes persistent PID configuration.
# CO and SP are excluded: they are transient runtime values written every
# scan by the control loop, and persisting them would thrash the DB.
_OPCUA_PERSISTABLE_PARAMS: frozenset[str] = frozenset({
    "kp", "ti", "td", "mode", "pid_structure", "pid_sp",
})


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
        # Controllers whose persistable config changed via OPC-UA since the
        # last flush. Drained by the main-loop flusher through consume_dirty_cids().
        self._dirty_cids: set[int] = set()

    def start_opcua(self) -> None:
        """Start only the OPC-UA server (without simulation loop)."""
        self._opcua_server.start()

    def stop_opcua(self) -> None:
        """Stop only the OPC-UA server (without affecting simulation loop)."""
        self._opcua_server.stop()

    @property
    def opcua_running(self) -> bool:
        return self._opcua_server.is_running

    @property
    def opcua_port(self) -> int:
        return self._opcua_server.port

    @property
    def opcua_endpoint(self) -> str:
        return self._opcua_server.endpoint

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        # Ensure at least one default controller for standalone simulation
        with self._lock:
            if not self._controllers:
                self._controllers[0] = _ControllerSim(controller_id=0)
                self._opcua_server.register_controller(0)
                logger.info("Simulator: created default controller (id=0)")
        self._stop_event.clear()
        # OPC-UA server is managed independently via start_opcua()/stop_opcua()
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="simulator")
        self._thread.start()
        logger.info("Simulator started (interval=%dms)", self._settings.simulator_interval_ms)

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
        # OPC-UA server is managed independently via start_opcua()/stop_opcua()
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
            elif param == "pid_structure":
                ctrl.pid_structure = int(value)
            elif param == "pid_sp":
                ctrl.sp = value
            elif param == "mode":
                ctrl.pid_mode = int(value)
            if param in _OPCUA_PERSISTABLE_PARAMS:
                self._dirty_cids.add(controller_id)

    def consume_dirty_cids(self) -> list[int]:
        """Return and clear the list of controllers whose persistable config
        changed via OPC-UA since the last call.

        Thread-safe.
        """
        with self._lock:
            if not self._dirty_cids:
                return []
            dirty = list(self._dirty_cids)
            self._dirty_cids.clear()
        return dirty

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

    def set_pid_sp(self, controller_id: int, sp: float) -> None:
        with self._lock:
            ctrl = self._controllers[controller_id]
            ctrl.sp = sp

    def set_pid_params(self, controller_id: int, kp: float, ti: float, td: float) -> None:
        with self._lock:
            ctrl = self._controllers[controller_id]
            ctrl.pid_params.gain = kp
            ctrl.pid_params.reset = ti
            ctrl.pid_params.rate = td
        self._sync_pid_config_to_opcua(controller_id)

    def _sync_pid_config_to_opcua(self, controller_id: int) -> None:
        """Push PID configuration (kp/ti/td/structure/enabled) to OPC-UA once.

        Called on config changes (preset load, set_pid_params, register) so the
        OPC-UA nodes reflect the current config without racing with external
        writes from the AI optimizer or HMI.
        """
        with self._lock:
            ctrl = self._controllers.get(controller_id)
            if ctrl is None:
                return
            values = {
                "kp": ctrl.pid_params.gain,
                "ti": ctrl.pid_params.reset,
                "td": ctrl.pid_params.rate,
                "pid_structure": ctrl.pid_structure,
                "pid_enabled": ctrl.pid_enabled,
            }
        self._opcua_server.update_values(controller_id=controller_id, values=values)

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

    def register_controller(
        self, controller_id: int, pv_min: float = 0.0, pv_max: float = 100.0,
    ) -> None:
        with self._lock:
            if controller_id not in self._controllers:
                self._controllers[controller_id] = _ControllerSim(
                    controller_id=controller_id,
                    pv_min=pv_min,
                    pv_max=pv_max,
                )
                self._opcua_server.register_controller(controller_id)

    def has_controller(self, controller_id: int) -> bool:
        """Return True when *controller_id* has simulation state here.

        A controller can exist in the project database and still be absent
        from the simulator (created while the daemon was running, or the
        simulator is disabled), so callers must not infer one from the other.
        """
        with self._lock:
            return controller_id in self._controllers

    def unregister_controller(self, controller_id: int) -> bool:
        """Drop a controller's simulation state. True if it was present.

        Called when a controller is deleted: without it the tick loop keeps
        integrating a process model nothing owns any more and every
        ``/simulator/*`` route keeps answering for a loop that is gone.

        The controller's OPC-UA nodes are left in the address space —
        ``OPCUAServer`` exposes no node-removal API — but they stop being
        updated because ``_tick`` only walks ``self._controllers``.
        """
        with self._lock:
            removed = self._controllers.pop(controller_id, None) is not None
            # Drop any pending persist for this id so the flusher cannot
            # write a config row back for a controller that no longer exists.
            self._dirty_cids.discard(controller_id)
        if removed:
            logger.info("Simulator: unregistered controller (id=%d)", controller_id)
        return removed

    def set_preset(self, controller_id: int, preset: ProcessPresetName) -> None:
        with self._lock:
            ctrl = self._controllers[controller_id]
            p = PRESETS[preset]
            ctrl.model.update_parameters(
                gain=p.gain, tau1=p.tau1, tau2=p.tau2, dead_time=p.dead_time,
            )
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
            # Update in place to preserve PV continuity; new TF takes effect
            # on the next tick without snapping the output back to zero.
            ctrl.model.update_parameters(
                gain=gain, tau1=tau1, tau2=tau2, dead_time=dead_time,
            )
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

    def set_auto_sp(self, controller_id: int, req: AutoSPRequest) -> None:
        """Configure (and enable/disable) auto SP variation for a controller."""
        with self._lock:
            if controller_id not in self._controllers:
                raise KeyError(controller_id)
            ctrl = self._controllers[controller_id]
            ctrl.auto_sp_enabled = req.enabled
            ctrl.auto_sp_min_pct = req.sp_min_pct
            ctrl.auto_sp_max_pct = req.sp_max_pct
            if not req.enabled:
                ctrl.auto_sp_elapsed_s = 0.0

    def set_auto_disturbance(self, controller_id: int, req: AutoDisturbanceRequest) -> None:
        """Configure (and enable/disable) auto disturbance injection for a controller."""
        with self._lock:
            if controller_id not in self._controllers:
                raise KeyError(controller_id)
            ctrl = self._controllers[controller_id]
            ctrl.auto_dist_enabled = req.enabled
            ctrl.auto_dist_max_pct = req.max_amplitude_pct
            if not req.enabled:
                ctrl.auto_dist_elapsed_s = 0.0

    def load_sim_config(self, cfg: dict) -> None:
        """Restore a controller's simulator state from a persisted config dict."""
        cid = cfg["controlador_id"]
        with self._lock:
            ctrl = self._controllers.get(cid)
            if ctrl is None:
                return
            ctrl.preset_name = cfg["preset"]
            ctrl.gain = cfg["gain"]
            ctrl.tau1 = cfg["tau1"]
            tau2 = cfg["tau2"]
            ctrl.tau2 = tau2 if tau2 else None
            ctrl.dead_time = cfg["dead_time"]
            ctrl.model = ProcessModel(
                gain=ctrl.gain, tau1=ctrl.tau1, tau2=ctrl.tau2, dead_time=ctrl.dead_time,
            )
            ctrl.pid_enabled = cfg.get("pid_enabled", False)
            ctrl.pid_params.gain = cfg.get("pid_kp", 1.0)
            ctrl.pid_params.reset = cfg.get("pid_ti", 10.0)
            ctrl.pid_params.rate = cfg.get("pid_td", 0.0)
            ctrl.pid_mode = cfg.get("pid_mode", 0)
            ctrl.sp = cfg.get("pid_sp", 50.0)
            # Auto SP / Auto Disturbance
            ctrl.auto_sp_enabled = cfg.get("auto_sp_enabled", False)
            ctrl.auto_sp_min_pct = cfg.get("auto_sp_min_pct", 30.0)
            ctrl.auto_sp_max_pct = cfg.get("auto_sp_max_pct", 70.0)
            ctrl.auto_dist_enabled = cfg.get("auto_dist_enabled", False)
            ctrl.auto_dist_max_pct = cfg.get("auto_dist_max_pct", 10.0)
        self._sync_pid_config_to_opcua(cid)

    def _build_status(self, ctrl: _ControllerSim) -> ControllerSimStatus:
        """Build a ControllerSimStatus from a _ControllerSim instance."""
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
            auto_sp=AutoSPRequest(
                enabled=ctrl.auto_sp_enabled,
                sp_min_pct=ctrl.auto_sp_min_pct,
                sp_max_pct=ctrl.auto_sp_max_pct,
            ),
            auto_disturbance=AutoDisturbanceRequest(
                enabled=ctrl.auto_dist_enabled,
                max_amplitude_pct=ctrl.auto_dist_max_pct,
            ),
            pv=ctrl.live_pv,
            sp=ctrl.sp,
            co=ctrl.last_co,
            error=ctrl.live_error,
            process_input=ctrl.live_process_input,
            process_output=ctrl.live_process_output,
            disturbance_output=ctrl.live_disturbance_output,
        )

    def get_config_dict(self, controller_id: int) -> dict:
        """Return the current sim config as a dict suitable for save_sim_config()."""
        with self._lock:
            ctrl = self._controllers[controller_id]
            return {
                "controller_id": ctrl.controller_id,
                "preset": ctrl.preset_name,
                "gain": ctrl.gain,
                "tau1": ctrl.tau1,
                "tau2": ctrl.tau2 if ctrl.tau2 is not None else 0.0,
                "dead_time": ctrl.dead_time,
                "pid_enabled": ctrl.pid_enabled,
                "pid_kp": ctrl.pid_params.gain,
                "pid_ti": ctrl.pid_params.reset,
                "pid_td": ctrl.pid_params.rate,
                "pid_mode": ctrl.pid_mode,
                "auto_sp_enabled": ctrl.auto_sp_enabled,
                "auto_sp_min_pct": ctrl.auto_sp_min_pct,
                "auto_sp_max_pct": ctrl.auto_sp_max_pct,
                "auto_dist_enabled": ctrl.auto_dist_enabled,
                "auto_dist_max_pct": ctrl.auto_dist_max_pct,
                "pid_sp": ctrl.sp,
            }

    def get_controller_status(self, controller_id: int) -> ControllerSimStatus:
        with self._lock:
            return self._build_status(self._controllers[controller_id])

    def get_status(self) -> dict[int, ControllerSimStatus]:
        with self._lock:
            return {
                cid: self._build_status(ctrl)
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
                # --- Auto-excitation ---
                period_s = max(10.0 * ctrl.tau1, 1.0)
                span = ctrl.pv_max - ctrl.pv_min

                if ctrl.auto_sp_enabled:
                    ctrl.auto_sp_elapsed_s += dt
                    if ctrl.auto_sp_elapsed_s >= period_s:
                        ctrl.auto_sp_elapsed_s = 0.0
                        if span > 0:
                            lo = ctrl.pv_min + ctrl.auto_sp_min_pct / 100.0 * span
                            hi = ctrl.pv_min + ctrl.auto_sp_max_pct / 100.0 * span
                            ctrl.sp = random.uniform(lo, hi)

                if ctrl.auto_dist_enabled:
                    ctrl.auto_dist_elapsed_s += dt
                    if ctrl.auto_dist_elapsed_s >= period_s:
                        ctrl.auto_dist_elapsed_s = 0.0
                        if span > 0:
                            max_amp = ctrl.auto_dist_max_pct / 100.0 * span
                            ctrl.step_amplitude = random.uniform(-max_amp, max_amp)
                            ctrl.step_active = True
                            # step disturbance persists until next firing or manual clear

                # Process model step (raw output before disturbances)
                process_output = ctrl.model.step(co=ctrl.last_co, dt=dt)

                # Disturbance contribution
                disturbance = 0.0
                if ctrl.step_active:
                    disturbance += ctrl.step_amplitude
                if ctrl.noise_active:
                    disturbance += random.gauss(0, ctrl.noise_amplitude)

                pv = process_output + disturbance

                # Store live values for status queries
                ctrl.live_pv = pv
                ctrl.live_process_input = ctrl.last_co
                ctrl.live_process_output = process_output
                ctrl.live_disturbance_output = disturbance

                # Internal PID: compute CO when enabled and AUTO
                error = ctrl.sp - pv
                ctrl.live_error = error
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

                # Echo only state values computed by the simulator. PID config
                # (kp/ti/td/pid_structure/pid_enabled) is owned by external
                # clients (HMI, AI optimizer) and re-writing it every tick races
                # with their OPC-UA writes and reverts their changes.
                # Config is pushed separately via _sync_pid_config_to_opcua().
                self._opcua_server.update_values(
                    controller_id=ctrl.controller_id,
                    values={
                        "pv": pv,
                        "sp": ctrl.sp,
                        "co": ctrl.last_co,
                        "mode": ctrl.pid_mode,
                        "status": 1 if ctrl.pid_enabled else 0,
                        "pid_sp": ctrl.sp,
                        "pid_cv": ctrl.pid_state.cv,
                        "error": error,
                        "process_input": ctrl.last_co,
                        "process_output": process_output,
                        "disturbance_output": disturbance,
                    },
                )
