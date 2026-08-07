"""Stats Worker — computes loop performance metrics at scan rate."""
from __future__ import annotations

import contextlib
import logging
import threading
import time
from typing import TYPE_CHECKING

import msgpack
import zmq

from smart_pid_core.domain.services.stats_calculator import StatsCalculator

if TYPE_CHECKING:
    from smart_pid_core.application.event_bus import (
        BusPublisher,
        BusSubscriber,
        EventBus,
    )
    from smart_pid_domain.models.controller import Controller

logger = logging.getLogger(__name__)


class StatsWorker:
    """Subscribes to TELEMETRY and ACTION.CTRL, computes metrics, publishes STATS."""

    def __init__(
        self,
        bus: EventBus,
        controller: Controller,
    ) -> None:
        self._bus = bus
        self._controller = controller
        # Stats window = 5 × TSS. A well-tuned loop shows ~5 response
        # cycles in this window (smooth metrics for the UI); a mis-tuned
        # loop's oscillation (period up to ~2 × TSS) fits at least two
        # full cycles, giving the fuzzy tuner enough direction reversals
        # to flag oscillation reliably.
        stats_window_s = 5.0 * controller.tss_s
        window_size = max(10, int(stats_window_s / controller.scan_rate_s))
        self._publish_interval = max(1, int(5.0 / controller.scan_rate_s))
        self._calculator = StatsCalculator(
            window_size=window_size,
            span=controller.pv_scale.span,
            setpoint=50.0,  # Updated from telemetry
        )
        self._last_sp: float = 50.0
        self._last_co: float = 0.0
        self._last_pv: float = 0.0
        self._has_telemetry: bool = False
        self._sample_count_since_publish: int = 0
        # SP-step detection: when |ΔSP|/span > _SP_CHANGE_FRAC, start a
        # cooldown during which samples are flagged as settling — kept
        # out of the oscillation metrics so the fuzzy does not confuse
        # SP tracking with oscillation. 2 × TSS gives ~exp(-8) residual
        # at the boundary (well below the noise threshold), so when the
        # next SP step lands the previous transient is fully decayed.
        #
        # The cooldown is only the UPPER bound. It is released early, at
        # the first zero crossing of the error after the step, because
        # that is where the one-sided SP-chasing excursion actually ends.
        # Without the early release a setpoint that moves faster than
        # 2 × TSS (the simulator's auto-SP defaults to 30 s against a
        # 60 s TSS) re-arms the cooldown forever and flags EVERY sample
        # as settling. The oscillation metrics then read a structural
        # zero, the tuner sees "steady with a standing offset", and it
        # reduces Ti on a loop that is in fact in a limit cycle. A mask
        # that can mute the whole window is not a mask.
        self._sp_change_frac = 0.01  # 1% of span = significant step
        self._settling_cooldown_samples = max(
            1, int(2.0 * controller.tss_s / controller.scan_rate_s),
        )
        self._settling_remaining: int = 0
        # Sign of the error when the current settling window opened; the
        # excursion is over once the error crosses back through zero.
        self._settling_sign: int = 0
        self._settling_noise_thr = 0.005 * controller.pv_scale.span
        self._prev_sp_at_sample: float | None = None
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def controller_id(self) -> int:
        return self._controller.id

    def start(self) -> None:
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            daemon=True,
            name=f"stats-worker-{self.controller_id}",
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5.0)
            self._thread = None

    def is_alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def get_current_stats(self) -> dict[str, float]:
        """Return current stats snapshot (thread-safe via GIL for simple reads)."""
        calc = self._calculator
        return {
            "controller_id": self.controller_id,
            "iae": calc.iae,
            "itae": calc.itae,
            "ise": calc.ise,
            "mse": calc.mse,
            "std_dev": calc.std_dev,
            "total_variation": calc.total_variation,
            "variability_sp": calc.variability_sp,
            "variability_range": calc.variability_range,
            "mean_abs_error": calc.mean_abs_error,
            "pk_pk_error": calc.pk_pk_error,
            "reversals": calc.reversals,
            "zero_crossings": calc.zero_crossings,
            "recent_pk_pk_error": calc.recent_pk_pk_error,
            "recent_reversals": calc.recent_reversals,
            "tv_per_sample": calc.tv_per_sample,
            "osc": calc.osc_score(),
            "osc_period_s": calc.osc_period_s,
            "sample_count": calc.sample_count,
            # Excitation context for the fuzzy OSC detector: how many
            # samples it is allowed to look at, and how far the setpoint
            # itself travelled. Without these the detector cannot tell
            # "measured calm" from "measured nothing", nor a limit cycle
            # from a step response.
            "osc_sample_count": calc.osc_sample_count,
            "sp_pk_pk": calc.sp_pk_pk,
            # Step-shape input for the SP-tracking fuzzy strategy: the one
            # indicator that reads through the settling mask.
            "overshoot": calc.overshoot_frac,
        }

    def _run(self) -> None:
        telem_sub = self._bus.create_subscriber(
            f"TELEMETRY.{self.controller_id}".encode()
        )
        action_sub = self._bus.create_subscriber(
            f"ACTION.CTRL.{self.controller_id}".encode()
        )
        pub = self._bus.create_publisher()
        scan_s = self._controller.scan_rate_s
        time.sleep(0.02)

        try:
            self._loop(telem_sub, action_sub, pub, scan_s)
        finally:
            # Close in the creating thread: see PIDWorker._run for why
            # leaving these to ctx.destroy() hangs EventBus.stop().
            for sock in (telem_sub, action_sub, pub):
                with contextlib.suppress(Exception):
                    sock.close()

    def _loop(
        self,
        telem_sub: BusSubscriber,
        action_sub: BusSubscriber,
        pub: BusPublisher,
        scan_s: float,
    ) -> None:
        """Run the stats loop until stopped. Socket lifetime is _run's job."""
        while not self._stop_event.is_set():
            try:
                tick_start = time.monotonic()
                self._drain_telemetry(telem_sub)
                self._drain_actions(action_sub)

                # Add sample if we have received telemetry data
                if self._has_telemetry:
                    error = self._last_sp - self._last_pv
                    self._calculator._setpoint = self._last_sp
                    # Detect a SP step large enough to start a settling
                    # cooldown. Samples flagged as settling stay out of
                    # the oscillation metrics.
                    if (
                        self._prev_sp_at_sample is not None
                        and self._calculator._span > 0
                        and (
                            abs(self._last_sp - self._prev_sp_at_sample)
                            / self._calculator._span
                            > self._sp_change_frac
                        )
                    ):
                        self._settling_remaining = self._settling_cooldown_samples
                        self._settling_sign = 1 if error > 0 else -1
                    self._prev_sp_at_sample = self._last_sp
                    is_settling = self._settling_remaining > 0
                    if is_settling:
                        self._settling_remaining -= 1
                        # Early release: the one-sided SP-chasing excursion
                        # is over the moment the error crosses back through
                        # zero. A limit cycle keeps crossing zero, so this
                        # release makes the mask structurally incapable of
                        # hiding one — which the bare cooldown was not.
                        if (
                            self._settling_sign != 0
                            and abs(error) > self._settling_noise_thr
                            and (1 if error > 0 else -1) != self._settling_sign
                        ):
                            self._settling_remaining = 0
                            self._settling_sign = 0
                    self._calculator.add_sample(
                        error=error,
                        co=self._last_co,
                        dt=scan_s,
                        is_settling=is_settling,
                        sp=self._last_sp,
                    )
                    self._sample_count_since_publish += 1

                # Publish stats periodically
                if self._sample_count_since_publish >= self._publish_interval:
                    stats = self.get_current_stats()
                    topic = f"STATS.{self.controller_id}".encode()
                    pub.send(topic, msgpack.packb(stats))
                    self._sample_count_since_publish = 0

                elapsed = time.monotonic() - tick_start
                sleep_time = scan_s - elapsed
                if sleep_time > 0:
                    self._stop_event.wait(timeout=sleep_time)
            except zmq.ZMQError:
                break
            except Exception:
                # A single malformed frame must not take the metrics thread
                # down: /controllers/{id}/stats would keep serving the last
                # snapshot forever, so a dead worker looks exactly like a
                # perfectly steady loop. Same guard, same reason, as
                # PIDWorker._loop — including the paced retry, without which
                # a persistent fault spins this thread at 100% CPU.
                logger.exception(
                    "stats_worker_iteration_error controller_id=%d",
                    self.controller_id,
                )
                self._stop_event.wait(timeout=scan_s)

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
                self._last_pv = pv_raw["value"] if isinstance(pv_raw, dict) else float(pv_raw)
                self._last_sp = sp_raw["value"] if isinstance(sp_raw, dict) else float(sp_raw)
                # CO is included in TELEMETRY from IOWorker
                co_raw = data.get("co")
                if co_raw is not None:
                    self._last_co = (
                        co_raw["value"] if isinstance(co_raw, dict) else float(co_raw)
                    )
                self._has_telemetry = True
            except (KeyError, ValueError, msgpack.UnpackException):
                pass

    def _drain_actions(self, sub) -> None:
        while True:
            msg = sub.recv(timeout_ms=0)
            if msg is None:
                break
            _topic, payload = msg
            try:
                data = msgpack.unpackb(payload)
                co_raw = data["co"]
                self._last_co = co_raw["value"] if isinstance(co_raw, dict) else float(co_raw)
            except (KeyError, ValueError, msgpack.UnpackException):
                pass
