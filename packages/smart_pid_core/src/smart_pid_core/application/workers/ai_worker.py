"""AI Worker — Ki optimization via Fuzzy or RL on a fixed timer.

Only runs when the loop is in an automatic mode (AUTO, CAS, RCAS).
Cadence is determined by ProcessSpeed.ai_period_s — independent of
STATS publication rate.
"""
from __future__ import annotations

import json
import logging
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
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

    def __init__(
        self,
        bus: EventBus,
        controller: Controller,
        initial_ki: float | None = None,
        model_dir: Path | None = None,
    ) -> None:
        self._bus = bus
        self._controller = controller
        self._ai_config = controller.ai_config
        # AI period = 3 × TSS (wait for process to settle before next adjustment)
        self._ai_period_s = 3.0 * controller.tss_s
        self._integral_type = controller.integral_type.value  # "GAIN_KI" or "TIME_TI"
        self._execution_mode = controller.execution_mode.value  # "SUPERVISORY" or "DDC"
        # Resume from last AI-computed Ki if available, otherwise use config default
        self._ki_current = initial_ki if initial_ki is not None else controller.pid_params.reset
        self._ki_from_opcua: float | None = None  # latest Ti/Ki from OPC-UA telemetry
        self._ki_from_opcua_prev: float | None = None  # previous OPC-UA read (change detection)
        self._model_dir = model_dir  # directory for persisting RL model weights
        self._last_pv: float = 0.0
        self._last_sp: float = 0.0
        self._last_co: float = 0.0
        self._last_integral: float = 0.0
        self._last_mode: str = ""
        self._prev_error: float = 0.0
        self._has_telemetry = False
        self._latest_stats: dict | None = None  # most recent STATS.{cid} snapshot
        self._engine = self._create_engine()
        # Master optimizer enable (ENABLE_OPTIMIZER). Seeded from the persisted
        # per-loop flag and toggled at runtime via CMD.AI start/stop.
        self._enabled = controller.optimization_enabled
        self._paused = False
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def controller_id(self) -> int:
        return self._controller.id

    def _create_engine(self):
        if self._ai_config.engine == AIEngine.FUZZY:
            from smart_pid_core.domain.services.fuzzy_engine_v2 import (
                FuzzyEngineV2Dispatcher,
            )

            # Fuzzy stats window covers ~5 × TSS so mis-tuned loops whose
            # oscillation period can reach 2–4 × TSS still fit at least one
            # full cycle in the window (the detector needs ≥ 2 direction
            # reversals to flag OSC). The stats_worker/Performance window
            # is kept at 1 × TSS for the UI; this one is fuzzy-only.
            scan_rate_s = max(self._controller.scan_rate_s, 1e-3)
            window_samples = max(
                10, int(5.0 * self._controller.tss_s / scan_rate_s),
            )
            return FuzzyEngineV2Dispatcher(
                objective=self._ai_config.objective,
                dt_sec=scan_rate_s,
                window_samples=window_samples,
            )
        elif self._ai_config.engine == AIEngine.RL:
            from smart_pid_core.domain.services.rl_engine import RLEngine

            engine = RLEngine(algorithm="SAC")
            # Apply per-controller RL config from ai_config
            engine._fallback._kp = self._ai_config.rl_fallback_kp
            engine._fallback._kd = self._ai_config.rl_fallback_kd
            engine._train_interval = self._ai_config.rl_train_interval
            return engine
        return None

    def start(self) -> None:
        if self._engine is None:
            logger.debug(
                "ai_worker_skip controller_id=%d reason=engine=NONE",
                self.controller_id,
            )
            return
        # Restore RL state from disk (if available)
        self._load_rl_state()
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
        # Persist RL state to disk
        self._save_rl_state()

    def is_alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @property
    def is_enabled(self) -> bool:
        return self._enabled

    @property
    def is_paused(self) -> bool:
        """Paused holds the optimizer off without discarding its state.

        Distinct from stopped: `stop` disables the optimizer, `pause` suspends
        it so `start` resumes from the same tuning rather than re-learning.
        """
        return self._paused

    def set_enabled(self, enabled: bool) -> None:
        """Toggle the optimizer enable flag directly (thread-safe via GIL).

        Used by the REST optimization command for an immediate effect even when
        the worker thread is not draining its command queue.
        """
        self._enabled = enabled

    def update_process_speed(self, process_speed) -> None:
        """Hot-reload AI period when process speed changes. Thread-safe via GIL."""
        self._ai_period_s = 3.0 * self._controller.tss_s

    def update_tss(self, tss_s: float) -> None:
        """Hot-reload AI period when TSS changes. Thread-safe via GIL."""
        self._ai_period_s = 3.0 * tss_s

    def set_paused(self, paused: bool) -> None:
        """Set the pause hold directly, mirroring `set_enabled`.

        The REST handlers publish CMD.AI *and* call this: a per-request
        publisher that is closed immediately can lose its first message to the
        ZeroMQ slow-joiner race, which made pause/resume non-deterministic.
        """
        self._paused = paused

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
        stats_sub = self._bus.create_subscriber(
            f"STATS.{self.controller_id}".encode()
        )
        # The PID worker publishes the loop's OWN mode on STATUS. That is the
        # authoritative value: for a DDC loop SmartPID owns the mode, and even
        # for SUPERVISORY the PID worker has already synced it from telemetry.
        # Relying on the TELEMETRY copy alone left the AI permanently skipped,
        # because that field is UNKNOWN whenever mode_int_map is unset.
        status_sub = self._bus.create_subscriber(
            f"STATUS.{self.controller_id}".encode()
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

                # Drain latest stats snapshot from StatsWorker
                self._drain_stats(stats_sub)

                # Authoritative loop mode from the PID worker
                self._drain_status(status_sub)

                # Check if it's time to run AI
                now = time.monotonic()
                if now < next_run:
                    wait = min(next_run - now, 0.5)
                    self._stop_event.wait(timeout=wait)
                    continue

                next_run = now + self._ai_period_s

                # Skip if disabled via CMD.AI stop, or held by CMD.AI pause
                if not self._enabled or self._paused:
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

                # Sync ki_current from OPC-UA only when the DCS value changed
                # externally (manual tuning or DCS clamping).  Re-reading the
                # same stale value must NOT revert an AI-computed Ki.
                if (
                    self._ki_from_opcua is not None
                    and self._ki_from_opcua != self._ki_from_opcua_prev
                ):
                    self._ki_current = self._ki_from_opcua
                self._ki_from_opcua_prev = self._ki_from_opcua

                error = self._last_sp - self._last_pv
                delta_error = error - self._prev_error

                if self._ai_config.engine == AIEngine.FUZZY:
                    # Both SP_TRACKING and DR consume the StatsWorker
                    # snapshot when available: SP derives its three
                    # indicators from the rolling window directly, and DR
                    # overlays the stats-based OSC on top of its event
                    # state machine (the post-event σ used to lie — see
                    # fuzzy_engine_v2 docstring). Surge Level keeps its
                    # per-sample PV/CO window and falls back.
                    from smart_pid_domain.enums import ControlObjective
                    stats_aware = self._ai_config.objective in (
                        ControlObjective.SP_TRACKING,
                        ControlObjective.DISTURBANCE_REJECTION,
                    )
                    if stats_aware and self._latest_stats is not None:
                        decision = self._engine.compute_adjustment_from_stats(
                            stats=self._latest_stats,
                            span=self._controller.pv_scale.span,
                            ti_current=self._ki_current,
                            limit_min=self._ai_config.limit_min,
                            limit_max=self._ai_config.limit_max,
                        )
                    else:
                        decision = self._engine.compute_adjustment(
                            ti_current=self._ki_current,
                            limit_min=self._ai_config.limit_min,
                            limit_max=self._ai_config.limit_max,
                        )
                    # V2 returns delta_ti ∈ [−0.5..+1.5]. For GAIN_KI loops the
                    # integral parameter has the opposite sense, so invert.
                    if self._integral_type == "GAIN_KI":
                        new_ki = self._ki_current / (1.0 + decision.delta_ti)
                        new_ki = max(
                            self._ai_config.limit_min,
                            min(self._ai_config.limit_max, new_ki),
                        )
                    else:
                        # AIDecisionV2 uses `new_ti` (already clamped inside V2).
                        new_ki = decision.new_ti
                    gamma_value = decision.delta_ti
                    reasoning = decision.reasoning
                else:
                    # RL engine (unchanged V1 interface)
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
                    new_ki = decision.new_ki
                    gamma_value = decision.gamma
                    reasoning = decision.reasoning

                old_ki = self._ki_current
                self._ki_current = new_ki
                self._prev_error = error

                # Publish ACTION.AI
                action_data = {
                    "controller_id": self.controller_id,
                    "gamma": gamma_value,
                    "new_ki": new_ki,
                    "engine": self._ai_config.engine.value,
                    "objective": self._ai_config.objective.value,
                    "integral_type": self._integral_type,
                    "execution_mode": self._execution_mode,
                    "reasoning": reasoning,
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
                    "gamma": gamma_value,
                    "old_ki": old_ki,
                    "new_ki": new_ki,
                    "reasoning": reasoning,
                    "timestamp": datetime.now(tz=UTC).isoformat(),
                }
                pub.send(
                    f"LOG.AI.{self.controller_id}".encode(),
                    msgpack.packb(log_data),
                )

                # Persist RL state after each AI cycle
                self._save_rl_state()
            except zmq.ZMQError:
                break
            except Exception:
                # Never let a transient error kill the worker thread silently —
                # log and keep looping so the optimizer stays alive.
                logger.exception(
                    "ai_worker_iteration_error controller_id=%d engine=%s",
                    self.controller_id,
                    self._ai_config.engine.value,
                )

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
                    self._paused = False
                    logger.info("ai_worker_enabled cid=%d", self.controller_id)
                elif action == "pause":
                    # Previously unhandled: the router published this and
                    # returned 200, but the optimizer kept running.
                    self._paused = True
                    logger.info("ai_worker_paused cid=%d", self.controller_id)
                elif action == "stop":
                    self._enabled = False
                    self._paused = False
                    logger.info("ai_worker_disabled cid=%d", self.controller_id)
            except Exception:
                pass

    def _rl_state_path(self) -> Path | None:
        """Return the path for persisting RL state JSON, or None."""
        if self._model_dir is None:
            return None
        return self._model_dir / f"rl_state_{self.controller_id}.json"

    def _save_rl_state(self) -> None:
        """Persist RL engine state (model weights + replay buffer) to disk."""
        from smart_pid_core.domain.services.rl_engine import RLEngine

        if not isinstance(self._engine, RLEngine) or self._model_dir is None:
            return
        try:
            state = self._engine.save_state(self._model_dir)
            state_path = self._rl_state_path()
            if state_path is not None:
                state_path.write_text(json.dumps(state), encoding="utf-8")
                logger.info(
                    "rl_state_saved cid=%d steps=%d buffer=%d",
                    self.controller_id,
                    state.get("step_count", 0),
                    len(state.get("replay_buffer", [])),
                )
        except Exception:
            logger.warning("rl_state_save_failed cid=%d", self.controller_id, exc_info=True)

    def _load_rl_state(self) -> None:
        """Restore RL engine state from disk (if available)."""
        from smart_pid_core.domain.services.rl_engine import RLEngine

        if not isinstance(self._engine, RLEngine) or self._model_dir is None:
            return
        state_path = self._rl_state_path()
        if state_path is None or not state_path.exists():
            return
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
            self._engine.load_state(state, self._model_dir)
            logger.info("rl_state_loaded cid=%d", self.controller_id)
        except Exception:
            logger.warning("rl_state_load_failed cid=%d", self.controller_id, exc_info=True)

    def _drain_status(self, sub) -> None:  # noqa: ANN001
        """Take the loop's authoritative mode from the PID worker's STATUS.

        Overrides the PLC-sourced mode carried on TELEMETRY, which is UNKNOWN
        whenever `mode_int_map` is unset and is the wrong owner for DDC loops.
        """
        while True:
            msg = sub.recv(timeout_ms=0)
            if msg is None:
                break
            _topic, payload = msg
            try:
                mode = msgpack.unpackb(payload).get("mode")
                if mode:
                    self._last_mode = mode
            except Exception:  # noqa: BLE001 — a bad frame must not stop tuning
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
                # PLC-sourced mode. Only trust it as a fallback: it is
                # UNKNOWN whenever mode_int_map is unset, and for a DDC loop
                # SmartPID owns the mode anyway. _drain_status() overrides
                # this with the PID worker's authoritative value.
                if not self._last_mode or self._last_mode == "UNKNOWN":
                    self._last_mode = data.get("mode", "")
                self._has_telemetry = True

                # Always sync Ki/Ti from the latest OPC-UA read.
                # The 'ti' field in telemetry maps to the OPC-UA node_id_ti,
                # which holds Ti or Ki depending on the DCS configuration.
                ti_val = data.get("ti")
                if ti_val is not None:
                    self._ki_from_opcua = float(ti_val)

                # Feed per-sample state for DR / Surge Level engines only —
                # they keep event state machines and PV/CO buffers. SP_TRACKING
                # consumes StatsWorker snapshots via _drain_stats instead, so
                # the two subsystems share a single rolling window.
                from smart_pid_domain.enums import ControlObjective
                if (
                    self._ai_config.engine == AIEngine.FUZZY
                    and self._ai_config.objective != ControlObjective.SP_TRACKING
                    and self._engine is not None
                    and self._enabled
                    and self._is_auto_mode()
                ):
                    span = self._controller.pv_scale.span
                    eu_min = self._controller.pv_scale.eu_min
                    error = self._last_sp - self._last_pv
                    error_frac = (error / span) if span > 0 else 0.0
                    pv_frac = (
                        (self._last_pv - eu_min) / span if span > 0 else 0.5
                    )
                    co_frac = self._last_co / 100.0
                    self._engine.update_sample(error_frac, pv_frac, co_frac)
            except (KeyError, ValueError, msgpack.UnpackException):
                pass

    def _drain_stats(self, sub) -> None:
        """Cache the most recent STATS.{cid} snapshot from StatsWorker.

        Only used by the SP_TRACKING path; other objectives keep their own
        per-sample state.
        """
        while True:
            msg = sub.recv(timeout_ms=0)
            if msg is None:
                break
            _topic, payload = msg
            try:
                data = msgpack.unpackb(payload)
                if isinstance(data, dict):
                    self._latest_stats = data
            except (ValueError, msgpack.UnpackException):
                pass
