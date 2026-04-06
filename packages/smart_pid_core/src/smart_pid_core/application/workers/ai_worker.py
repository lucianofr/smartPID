"""AI Worker — Ki optimization via Fuzzy or RL, triggered by STATS publication.

Only runs when the loop is in an automatic mode (AUTO, CAS, RCAS).
Cadence is driven by STATS.{id} messages from StatsWorker, ensuring
performance indices are computed first, then AI optimizes based on them.
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
    """Subscribes to TELEMETRY + STATS, runs AI engine, publishes ACTION.AI + LOG.AI.

    AI computation is triggered by STATS.{id} messages (same cadence as
    performance statistics) and only executes when the loop is in an
    automatic mode (AUTO, CAS, RCAS).
    """

    def __init__(self, bus: EventBus, controller: Controller) -> None:
        self._bus = bus
        self._controller = controller
        self._ai_config = controller.ai_config
        self._ki_current = controller.pid_params.reset  # Ti (integral time)
        self._last_pv: float = 0.0
        self._last_sp: float = 0.0
        self._last_co: float = 0.0
        self._last_mode: str = ""
        self._prev_error: float = 0.0
        self._has_telemetry = False
        self._engine = self._create_engine()
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
        stats_sub = self._bus.create_subscriber(
            f"STATS.{self.controller_id}".encode()
        )
        pub = self._bus.create_publisher()
        time.sleep(0.02)

        while not self._stop_event.is_set():
            try:
                # Drain latest telemetry (non-blocking)
                self._drain_telemetry(telem_sub)

                # Wait for STATS trigger (blocking with timeout for stop check)
                stats_msg = stats_sub.recv(timeout_ms=200)
                if stats_msg is None:
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
                    )
                else:
                    # RL engine
                    decision = self._engine.compute_gamma(
                        error=error,
                        delta_error=delta_error,
                        ki_current=self._ki_current,
                        span=self._controller.pv_scale.span,
                        co=self._last_co,
                        integral_val=0.0,
                        objective=self._ai_config.objective,
                        speed=self._controller.process_speed,
                        limit_min=self._ai_config.limit_min,
                        limit_max=self._ai_config.limit_max,
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
                self._last_co = data.get("co", 0.0)
                self._last_mode = data.get("mode", "")
                self._has_telemetry = True
            except (KeyError, ValueError, msgpack.UnpackException):
                pass
