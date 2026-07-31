"""AI Worker — Ki optimization via Fuzzy or RL on a fixed timer.

Only runs when the loop is in an automatic mode (AUTO, CAS, RCAS).
Cadence is determined by ProcessSpeed.ai_period_s — independent of
STATS publication rate.

Two distinct tuning paths live here and must not be conflated:

1. The **continuous integral nudge** — the engine adjusts only Ki/Ti every
   ``3 × tss`` and the result goes out on ``ACTION.AI.{cid}``, which
   ``IOWorker`` writes straight to the PLC for SUPERVISORY loops.
2. The **full PID retune proposal** — Kp, Ti *and* Td together, synthesised
   by IMC/lambda tuning from an identified FOPDT model.  A far larger
   intervention, so it is never written: it lands in the
   ``TuningRecommendationStore`` as a PENDING recommendation and is applied
   only after explicit admin confirmation via ``POST /commands/apply-tuning``.
"""
from __future__ import annotations

import contextlib
import json
import logging
import math
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

import msgpack
import zmq

from smart_pid_core.domain.services.tuning_recommender import (
    identify_fopdt,
    recommend_pid,
)
from smart_pid_domain.enums import AIEngine, ControllerMode, IntegralType
from smart_pid_domain.events import TuningRecommended
from smart_pid_domain.models.tuning import TuningRecommendation

if TYPE_CHECKING:
    from smart_pid_core.application.event_bus import (
        BusPublisher,
        BusSubscriber,
        EventBus,
    )
    from smart_pid_core.application.tuning_store import TuningRecommendationStore
    from smart_pid_core.domain.services.tuning_recommender import TuningProposal
    from smart_pid_domain.models.controller import Controller

logger = logging.getLogger(__name__)

# Modes where the PID is in closed-loop control and AI tuning is meaningful
_AUTO_MODES = frozenset({
    ControllerMode.AUTO,
    ControllerMode.CAS,
    ControllerMode.RCAS,
})

# Fallback steady-state band, in % of SP, when neither the loop nor the daemon
# configures one. While |PV - SP| stays inside it the loop is at rest, and
# moving Ki/Ti there buys nothing while arming an overshoot on the next step.
_DEFAULT_STABILITY_BAND_PCT = 2.0

# --- Steady-state observation gates for process-gain identification -------
# "At rest" means PV and CO have both stopped moving — NOT that PV sits on SP.
# A loop holding a steady offset (P-dominant, or integral held off by a
# downstream limit) is a perfectly valid operating point for reading a
# steady-state gain, and excluding it would leave the richest data unused.
#
# PV quiescence: the error excursion over the whole stats window, as a
# fraction of span.  Valid as a PV test only while SP is fixed, which
# `_SS_SP_HOLD_TSS` enforces.
_SS_PKPK_FRAC = 0.02
# CO quiescence: mean |dCO| per scan, in % of output range.  The plant only
# reveals its steady-state gain once the valve has stopped moving.
_SS_CO_TV_PCT = 0.1
# The setpoint must have been unchanged for this many TSS, so the stats
# window contains no SP-step transient.
_SS_SP_HOLD_TSS = 1.0
_SS_SP_MOVE_FRAC = 0.001
_SS_MIN_SAMPLES = 10
# Observations are bucketed by operating point so that sitting at one CO for
# an hour cannot swamp the fit with duplicates of the same point.
_SS_CO_BUCKET_PCT = 2.0
_SS_MAX_POINTS = 8
# Fit-quality gates. Too few operating points, too little CO travel, or a weak
# correlation all mean "gain unknown" — never "gain = whatever the noise says".
_GAIN_MIN_POINTS = 3
_GAIN_MIN_CO_SPREAD_PCT = 2.0
_GAIN_MIN_ABS_R = 0.9


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
        tuning_store: TuningRecommendationStore | None = None,
        stability_band_pct: float = _DEFAULT_STABILITY_BAND_PCT,
    ) -> None:
        """``stability_band_pct`` is the daemon-wide steady-state band, in % of
        SP. The loop's own ``Controller.stability_band_pct`` overrides it when
        set; ``None`` there means "inherit this global".
        """
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
        # PLC "process using this PID is running" flag, refreshed from every
        # TELEMETRY frame. None = no PID_[MALHA]_ENABLED tag mapped, which is
        # "unknown", not "stopped", and never blocks the optimizer.
        self._pid_enabled: bool | None = None
        # Steady-state guardrail: the loop's own band wins, else the global.
        self._stability_band_pct = (
            controller.stability_band_pct
            if controller.stability_band_pct is not None
            else stability_band_pct
        )
        self._cycles_since_save = 0  # RL state is persisted every N cycles, not every one
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        # --- Full-retune producer state (worker thread only) --------------
        # Injected directly rather than published on a bus topic: delivery is
        # then synchronous and total.  A bus round-trip would need a new
        # consumer thread and would inherit the ZeroMQ slow-joiner race the
        # rest of this file already works around (see `set_paused`), which for
        # a once-per-3×tss message means silently losing whole proposals.
        self._tuning_store = tuning_store
        # Steady-state (CO%, PV%) observations, keyed by CO operating-point
        # bucket -> (co_pct, pv_pct, monotonic_ts).
        self._ss_points: dict[int, tuple[float, float, float]] = {}
        self._last_ss_record_mono: float = 0.0
        # SP-hold tracking: a stats window straddling an SP step says nothing
        # about whether the process itself has settled.
        self._observed_sp: float | None = None
        self._sp_changed_mono: float = 0.0
        self._last_proposal: TuningProposal | None = None
        self._last_retune_skip: str | None = None

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

            return RLEngine(
                algorithm="SAC",
                learning_rate=self._ai_config.rl_learning_rate,
                fallback_kp=self._ai_config.rl_fallback_kp,
                fallback_kd=self._ai_config.rl_fallback_kd,
                train_interval=self._ai_config.rl_train_interval,
            )
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

    # ------------------------------------------------------------------
    # Full PID retune proposal (confirm-gated) — producer side
    # ------------------------------------------------------------------

    def _observe_steady_state(self) -> None:
        """Record a settled (CO %, PV %) pair for steady-state gain identification.

        The only process gain this daemon can honestly observe is the
        steady-state one, read off pairs of settled operating points::

            K = d(PV %) / d(CO %)

        "Settled" means PV and CO have both stopped moving — deliberately not
        "PV is on setpoint".  A loop parked at a steady offset still sits on
        the process curve, and on many real loops (P-dominant tuning, or an
        integral held off by a downstream limit) that is the *only* place
        distinct operating points ever appear.

        Three conditions must hold together:

        * the setpoint has been unchanged for at least one TSS, so the stats
          window contains no SP-step transient (without this the error-based
          PV test below would be reading SP movement, not PV movement);
        * the error excursion across the window is within ``_SS_PKPK_FRAC`` of
          span — with SP fixed this is exactly "PV is not moving", and it
          stops an oscillating loop passing through PV = SP from posing as a
          steady state;
        * CO travel averages under ``_SS_CO_TV_PCT`` per scan, i.e. the valve
          has stopped moving, so PV is responding to nothing still in flight.

        Successive records are spaced by at least one TSS so the stats window
        has fully refreshed between them.  Pairs are bucketed by CO so that
        dwelling at one operating point cannot flood the fit with duplicates;
        each bucket keeps its freshest observation and the oldest bucket is
        evicted at capacity.
        """
        stats = self._latest_stats
        if not self._has_telemetry or stats is None or not self._is_auto_mode():
            return
        span = self._controller.pv_scale.span
        if span <= 0.0:
            return

        now = time.monotonic()
        tss_s = max(self._controller.tss_s, 1e-3)

        sp = self._last_sp
        if (
            self._observed_sp is None
            or abs(sp - self._observed_sp) > _SS_SP_MOVE_FRAC * span
        ):
            self._observed_sp = sp
            self._sp_changed_mono = now
        if now - self._sp_changed_mono < _SS_SP_HOLD_TSS * tss_s:
            return

        if now - self._last_ss_record_mono < tss_s:
            return
        if float(stats.get("sample_count", 0.0)) < _SS_MIN_SAMPLES:
            return
        if float(stats.get("pk_pk_error", span)) > _SS_PKPK_FRAC * span:
            return
        if float(stats.get("tv_per_sample", 100.0)) > _SS_CO_TV_PCT:
            return

        co_pct = self._last_co
        pv_pct = (self._last_pv - self._controller.pv_scale.eu_min) / span * 100.0
        self._last_ss_record_mono = now
        bucket = int(co_pct // _SS_CO_BUCKET_PCT)
        self._ss_points[bucket] = (co_pct, pv_pct, now)
        if len(self._ss_points) > _SS_MAX_POINTS:
            oldest = min(self._ss_points, key=lambda k: self._ss_points[k][2])
            del self._ss_points[oldest]

    def _estimate_process_gain(self) -> float | None:
        """Least-squares slope of PV % against CO % over the settled points.

        Returns ``None`` — meaning "gain unknown", never a fabricated value —
        unless the observations actually support a slope: at least
        ``_GAIN_MIN_POINTS`` distinct operating points, at least
        ``_GAIN_MIN_CO_SPREAD_PCT`` of CO travel between the extremes, and a
        Pearson correlation of at least ``_GAIN_MIN_ABS_R``.

        The correlation gate is what makes this honest under closed-loop
        control: while the setpoint is held constant PV stays pinned at SP
        whatever the load does to CO, so the points carry no gain information
        and ``r`` collapses.  Only genuine operating-point moves produce a
        correlated PV/CO cloud.
        """
        points = [(co, pv) for co, pv, _ts in self._ss_points.values()]
        n = len(points)
        if n < _GAIN_MIN_POINTS:
            return None
        co_values = [co for co, _pv in points]
        if max(co_values) - min(co_values) < _GAIN_MIN_CO_SPREAD_PCT:
            return None

        pv_values = [pv for _co, pv in points]
        co_mean = sum(co_values) / n
        pv_mean = sum(pv_values) / n
        s_co = sum((c - co_mean) ** 2 for c in co_values)
        s_pv = sum((p - pv_mean) ** 2 for p in pv_values)
        s_copv = sum(
            (c - co_mean) * (p - pv_mean) for c, p in zip(co_values, pv_values, strict=True)
        )
        if s_co <= 0.0 or s_pv <= 0.0:
            return None
        r = s_copv / math.sqrt(s_co * s_pv)
        if abs(r) < _GAIN_MIN_ABS_R:
            return None
        return s_copv / s_co

    def _skip_retune(self, reason: str) -> None:
        """Log why no retune was proposed, once per change of reason.

        "Why is there no recommendation for this loop?" is the first question
        anyone asks, and silence is a bad answer.  Edge-triggered so a loop
        that will never identify does not fill the log.
        """
        if reason != self._last_retune_skip:
            self._last_retune_skip = reason
            logger.info(
                "tuning_retune_skip cid=%d reason=%s points=%d",
                self.controller_id, reason, len(self._ss_points),
            )

    def _optimization_skip_reason(self) -> str | None:
        """Why this cycle must not move the integral term, or None to proceed.

        Two total-skip guards, in order:

        ``'enabled'``
            The PLC's ``PID_[MALHA]_ENABLED`` tag reads 0 — the process this
            loop drives is stopped, so the PV it reports is not a response to
            anything the controller did. ``None`` from the adapter means the
            tag is unmapped, i.e. unknown, and never gates.
        ``'stability_band'``
            ``|PV - SP|`` is inside the loop's stability band. At steady state
            the error carries no information about the tuning, and changing
            Ki/Ti there only arms an overshoot on the next setpoint step.

        Neither guard touches Kp or Kd: the whole cycle is skipped or none of
        it is.
        """
        if self._pid_enabled is False:
            return "enabled"
        band = abs(self._last_sp) * self._stability_band_pct / 100.0
        if abs(self._last_pv - self._last_sp) < band:
            return "stability_band"
        return None

    def _log_optimization_skip(self, reason: str) -> None:
        """Record every skipped optimization, one JSON object per line.

        Not edge-triggered: "the optimizer left this loop alone" is the fact
        being audited, and it must be countable per cycle, not per transition.
        At one line per AI period (3 x TSS) that is not a volume problem.
        """
        logger.info(
            "optimizer_skip %s",
            json.dumps({
                "malha": self.controller_id,
                "timestamp": datetime.now(tz=UTC).isoformat(),
                "reason": reason,
            }),
        )

    def _maybe_recommend_retune(self, pub) -> None:  # noqa: ANN001
        """Synthesise a full PID retune and park it in the store, if warranted.

        Nothing is written to the process here.  The proposal becomes a
        PENDING ``TuningRecommendation`` that an admin must confirm through
        ``POST /commands/apply-tuning/{id}``, where it is clamped again to the
        loop's ``max_tuning_change_pct`` before any write-back.

        Skipped for GAIN_KI loops: the IMC rule yields an integral *time* in
        seconds, and this codebase defines no Ti→Ki unit convention, so
        writing it into a Ki-holding node would silently corrupt the tuning.
        """
        if self._tuning_store is None:
            return
        if self._controller.integral_type != IntegralType.TIME_TI:
            self._skip_retune("integral_type_not_time_ti")
            return

        gain = self._estimate_process_gain()
        if gain is None:
            self._skip_retune("gain_unidentifiable")
            return
        model = identify_fopdt(
            tss_s=self._controller.tss_s,
            dead_time_s=self._ai_config.dead_time_l,
            gain=gain,
        )
        if model is None:
            self._skip_retune("model_unidentifiable")
            return

        current_kp = self._controller.pid_params.gain
        current_ti = self._ki_current  # live Ti, incl. any AI/DCS adjustment
        current_td = self._controller.pid_params.rate
        proposal = recommend_pid(
            model=model,
            objective=self._ai_config.objective,
            current_kp=current_kp,
            current_ti=current_ti,
            current_td=current_td,
            limit_min=self._ai_config.limit_min,
            limit_max=self._ai_config.limit_max,
        )
        if proposal is None:
            self._skip_retune("not_materially_different")
            return

        # Anti-churn: reuse the recommender's own material-difference gate to
        # compare against what we last published. A fresh proposal within the
        # threshold of the standing one is not worth re-raising.
        if self._last_proposal is not None and recommend_pid(
            model=model,
            objective=self._ai_config.objective,
            current_kp=self._last_proposal.kp,
            current_ti=self._last_proposal.ti,
            current_td=self._last_proposal.td,
            limit_min=self._ai_config.limit_min,
            limit_max=self._ai_config.limit_max,
        ) is None:
            self._skip_retune("unchanged_since_last_proposal")
            return
        self._last_retune_skip = None

        timestamp = time.time()
        rec = TuningRecommendation(
            id=uuid4(),
            controller_id=self.controller_id,
            current_kp=current_kp,
            current_ti=current_ti,
            current_td=current_td,
            recommended_kp=proposal.kp,
            recommended_ti=proposal.ti,
            recommended_td=proposal.td,
            reason=proposal.reason,
            timestamp=timestamp,
        )
        self._tuning_store.put(rec)
        self._last_proposal = proposal

        event = TuningRecommended(
            controller_id=self.controller_id,
            current_kp=current_kp,
            current_ti=current_ti,
            current_td=current_td,
            recommended_kp=proposal.kp,
            recommended_ti=proposal.ti,
            recommended_td=proposal.td,
            reason=proposal.reason,
            timestamp=timestamp,
        )
        # Informational only. Deliberately NOT on ACTION.AI.*, which IOWorker
        # writes straight to the PLC — a full retune must never take that path.
        pub.send(
            f"EVENT.TUNING_REC.{self.controller_id}".encode(),
            msgpack.packb({
                "controller_id": event.controller_id,
                "event_id": str(event.event_id),
                "recommendation_id": str(rec.id),
                "current_kp": event.current_kp,
                "current_ti": event.current_ti,
                "current_td": event.current_td,
                "recommended_kp": event.recommended_kp,
                "recommended_ti": event.recommended_ti,
                "recommended_td": event.recommended_td,
                "reason": event.reason,
                "timestamp": event.timestamp,
            }),
        )
        logger.info(
            "tuning_recommended cid=%d K=%.4f tau=%.2f L=%.2f lambda=%.2f "
            "Kp %.4f->%.4f Ti %.3f->%.3f Td %.3f->%.3f",
            self.controller_id, model.gain, model.tau_s, model.dead_time_s,
            proposal.lambda_s, current_kp, proposal.kp,
            current_ti, proposal.ti, current_td, proposal.td,
        )

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

        try:
            self._loop(telem_sub, cmd_sub, stats_sub, status_sub, pub, next_run)
        finally:
            # Close in the creating thread: see PIDWorker._run for why
            # leaving these to ctx.destroy() hangs EventBus.stop().
            for sock in (telem_sub, cmd_sub, stats_sub, status_sub, pub):
                with contextlib.suppress(Exception):
                    sock.close()

    def _loop(
        self,
        telem_sub: BusSubscriber,
        cmd_sub: BusSubscriber,
        stats_sub: BusSubscriber,
        status_sub: BusSubscriber,
        pub: BusPublisher,
        next_run: float,
    ) -> None:
        """Run the tuning loop until stopped. Socket lifetime is _run's job."""
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

                # Sample the process for FOPDT gain identification. Runs on
                # every pass, not just the AI tick: the (CO, PV) pairs it
                # needs only appear while the loop sits at a settled
                # operating point, which is a transient condition.
                self._observe_steady_state()

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

                # Full PID retune proposal (Kp + Ti + Td). Confirm-gated —
                # this only fills the recommendation store, it never writes.
                # Deliberately ahead of the safe-tuning guardrail below: the
                # FOPDT identification it feeds on only sees anything WHILE the
                # loop sits settled, and it cannot move a parameter on its own.
                self._maybe_recommend_retune(pub)

                # Safe-tuning guardrail on the online integral adjustment: PLC
                # reports the process stopped, or the loop is at steady state.
                # Total skip — no Ki/Ti move, and Kp/Kd untouched either way.
                skip_reason = self._optimization_skip_reason()
                if skip_reason is not None:
                    self._log_optimization_skip(skip_reason)
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
                        stats=self._latest_stats,
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

                # Persist RL state periodically -- it's an I/O-heavy JSON
                # dump of the replay buffer + model weights, not needed
                # every cycle. stop() still saves unconditionally.
                self._cycles_since_save += 1
                if self._cycles_since_save >= 10:
                    self._cycles_since_save = 0
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
                # PLC process-running flag, refreshed every frame so a runtime
                # 0 -> 1 resumes tuning on the very next AI cycle. Absent key
                # (a publisher that does not read the tag) leaves it unknown.
                raw_enabled = data.get("pid_enabled")
                self._pid_enabled = (
                    None if raw_enabled is None else bool(raw_enabled)
                )
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
