"""AI Worker — Ki optimization via Fuzzy or RL on a fixed timer.

Only runs when the loop is in an automatic mode (AUTO, CAS, RCAS).
Cadence is determined by ProcessSpeed.ai_period_s — independent of
STATS publication rate.
"""
from __future__ import annotations

import logging
import threading
import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import msgpack
import zmq

from smart_pid_domain.enums import AIEngine, ControllerMode

if TYPE_CHECKING:
    from smart_pid_core.application.event_bus import EventBus
    from smart_pid_domain.models.controller import Controller

logger = logging.getLogger(__name__)

# Modes where the PID is in closed-loop control and AI tuning is meaningful
_AUTO_MODES = frozenset({
    ControllerMode.AUTO,
    ControllerMode.CAS,
    ControllerMode.RCAS,
})


class AIWorker:
    """Subscribes to TELEMETRY, runs AI engine on a timer, publishes ACTION.AI + LOG.AI.

    AI computation runs every ProcessSpeed.ai_period_s seconds and only
    executes when the loop is in an automatic mode (AUTO, CAS, RCAS).
    """

    def __init__(self, bus: EventBus, controller: Controller) -> None:
        self._bus = bus
        self._controller = controller
        self._ai_config = controller.ai_config
        # AI period = 3 × TSS (wait for process to settle before next adjustment)
        self._ai_period_s = 3.0 * controller.tss_s
        self._integral_type = controller.integral_type.value  # "GAIN_KI" or "TIME_TI"
        self._execution_mode = controller.execution_mode.value  # "SUPERVISORY" or "DDC"
        self._ki_current = controller.pid_params.reset  # initial from config
        self._ki_from_opcua: float | None = None  # latest Ti/Ki from OPC-UA telemetry
        self._last_pv: float = 0.0
        self._last_sp: float = 0.0
        self._last_co: float = 0.0
        self._last_integral: float = 0.0
        self._last_mode: str = ""
        self._prev_error: float = 0.0
        self._has_telemetry = False
        self._engine = self._create_engine()
        self._enabled = True  # controlled via CMD.AI start/stop
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def controller_id(self) -> int:
        return self._controller.id

    def _create_engine(self):
        if self._ai_config.engine == AIEngine.FUZZY:
            from smart_pid_core.domain.services.fuzzy_engine import FuzzyEngine

            return FuzzyEngine()
        elif self._ai_config.engine == AIEngine.RL:
            from smart_pid_core.domain.services.rl_engine import RLEngine

            return RLEngine()
        return None

    def start(self) -> None:
        if self._engine is None:
            logger.debug(
                "ai_worker_skip controller_id=%d reason=engine=NONE",
                self.controller_id,
            )
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            daemon=True,
            name=f"ai-worker-{self.controller_id}",
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
    def is_enabled(self) -> bool:
        return self._enabled

    def update_process_speed(self, process_speed) -> None:
        """Hot-reload AI period when process speed changes. Thread-safe via GIL."""
        self._ai_period_s = 3.0 * self._controller.tss_s

    def update_tss(self, tss_s: float) -> None:
        """Hot-reload AI period when TSS changes. Thread-safe via GIL."""
        self._ai_period_s = 3.0 * tss_s

    def _is_auto_mode(self) -> bool:
        """Return True if the last known controller mode allows AI tuning."""
        try:
            mode = ControllerMode(self._last_mode)
        except ValueError:
            return False
        return mode in _AUTO_MODES

    def _run(self) -> None:
        telem_sub = self._bus.create_subscriber(
            f"TELEMETRY.{self.controller_id}".encode()
        )
        cmd_sub = self._bus.create_subscriber(
            f"CMD.AI.{self.controller_id}".encode()
        )
        pub = self._bus.create_publisher()
        time.sleep(0.02)

        next_run = time.monotonic() + self._ai_period_s

        while not self._stop_event.is_set():
            try:
                # Drain commands (start/stop)
                self._drain_commands(cmd_sub)

                # Drain latest telemetry (non-blocking)
                self._drain_telemetry(telem_sub)

                # Check if it's time to run AI
                now = time.monotonic()
                if now < next_run:
                    wait = min(next_run - now, 0.5)
                    self._stop_event.wait(timeout=wait)
                    continue

                next_run = now + self._ai_period_s

                # Skip if disabled via CMD.AI stop
                if not self._enabled:
                    continue

                # Only compute if we have telemetry AND mode is automatic
                if not self._has_telemetry or self._engine is None:
                    continue
                if not self._is_auto_mode():
                    logger.debug(
                        "ai_worker_skip controller_id=%d reason=mode=%s",
                        self.controller_id,
                        self._last_mode,
                    )
                    continue

                # Sync ki_current from latest OPC-UA telemetry read
                if self._ki_from_opcua is not None:
                    self._ki_current = self._ki_from_opcua

                error = self._last_sp - self._last_pv
                delta_error = error - self._prev_error

                if self._ai_config.engine == AIEngine.FUZZY:
                    decision = self._engine.compute_gamma(
                        error=error,
                        delta_error=delta_error,
                        ki_current=self._ki_current,
                        span=self._controller.pv_scale.span,
                        objective=self._ai_config.objective,
                        speed=self._controller.process_speed,
                        limit_min=self._ai_config.limit_min,
                        limit_max=self._ai_config.limit_max,
                        integral_type=self._integral_type,
                    )
                else:
                    # RL engine
                    decision = self._engine.compute_gamma(
                        error=error,
                        delta_error=delta_error,
                        ki_current=self._ki_current,
                        span=self._controller.pv_scale.span,
                        co=self._last_co,
                        integral_val=self._last_integral,
                        objective=self._ai_config.objective,
                        speed=self._controller.process_speed,
                        limit_min=self._ai_config.limit_min,
                        limit_max=self._ai_config.limit_max,
                        integral_type=self._integral_type,
                    )

                old_ki = self._ki_current
                self._ki_current = decision.new_ki
                self._prev_error = error

                # Publish ACTION.AI
                action_data = {
                    "controller_id": self.controller_id,
                    "gamma": decision.gamma,
                    "new_ki": decision.new_ki,
                    "engine": self._ai_config.engine.value,
                    "objective": self._ai_config.objective.value,
                    "integral_type": self._integral_type,
                    "execution_mode": self._execution_mode,
                    "reasoning": decision.reasoning,
                    "timestamp": datetime.now(tz=UTC).isoformat(),
                }
                pub.send(
                    f"ACTION.AI.{self.controller_id}".encode(),
                    msgpack.packb(action_data),
                )

                # Publish LOG.AI
                log_data = {
                    "controller_id": self.controller_id,
                    "engine": self._ai_config.engine.value,
                    "gamma": decision.gamma,
                    "old_ki": old_ki,
                    "new_ki": decision.new_ki,
                    "reasoning": decision.reasoning,
                    "timestamp": datetime.now(tz=UTC).isoformat(),
                }
                pub.send(
                    f"LOG.AI.{self.controller_id}".encode(),
                    msgpack.packb(log_data),
                )
            except zmq.ZMQError:
                break

    def _drain_commands(self, sub) -> None:
        """Drain CMD.AI messages and update enabled state."""
        while True:
            msg = sub.recv(timeout_ms=0)
            if msg is None:
                break
            _topic, payload = msg
            try:
                data = msgpack.unpackb(payload)
                action = data.get("action", "")
                if action == "start":
                    self._enabled = True
                    logger.info("ai_worker_enabled cid=%d", self.controller_id)
                elif action == "stop":
                    self._enabled = False
                    logger.info("ai_worker_disabled cid=%d", self.controller_id)
            except Exception:
                pass

    def _drain_telemetry(self, sub) -> None:
        while True:
            msg = sub.recv(timeout_ms=0)
            if msg is None:
                break
            _topic, payload = msg
            try:
                data = msgpack.unpackb(payload)
                pv_raw = data["pv"]
                sp_raw = data["sp"]
                co_raw = data.get("co", 0.0)
                self._last_pv = pv_raw["value"] if isinstance(pv_raw, dict) else float(pv_raw)
                self._last_sp = sp_raw["value"] if isinstance(sp_raw, dict) else float(sp_raw)
                self._last_co = co_raw["value"] if isinstance(co_raw, dict) else float(co_raw)
                self._last_integral = float(data.get("integral_val", 0.0))
                self._last_mode = data.get("mode", "")
                self._has_telemetry = True

                # Always sync Ki/Ti from the latest OPC-UA read.
                # The 'ti' field in telemetry maps to the OPC-UA node_id_ti,
                # which holds Ti or Ki depending on the DCS configuration.
                ti_val = data.get("ti")
                if ti_val is not None:
                    self._ki_from_opcua = float(ti_val)
            except (KeyError, ValueError, msgpack.UnpackException):
                pass
