"""Real-time performance statistics calculator using sliding window."""
from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass


@dataclass
class _Sample:
    """One telemetry sample for statistics."""

    error: float
    co: float
    dt: float
    elapsed_time: float  # cumulative time since window start
    # SP-step transients are kept out of the oscillation metrics
    # (pk-pk, reversals, zero_crossings). They still contribute to IAE
    # and family so error-budget tracking is unaffected.
    is_settling: bool = False


class StatsCalculator:
    """Computes loop performance metrics over a sliding window.

    Pure domain service — no I/O, no threading.
    """

    # Δerror below (reversal_noise_thr × span) is ignored when counting
    # direction reversals, so quantisation noise does not inflate the count.
    _DEFAULT_REVERSAL_NOISE_FRAC = 0.005
    # Fraction of the window used by the "recent" pk-pk / reversal metrics
    # consumed by the fuzzy OSC detector. Picking 0.4 of a 5×TSS window
    # gives a ~2×TSS recent sub-window so OSC drops back to zero within
    # roughly 2×TSS after the loop stabilises, instead of lingering for
    # the full 5×TSS while stale oscillation data ages out.
    _DEFAULT_RECENT_FRACTION = 0.4

    def __init__(
        self,
        window_size: int,
        span: float,
        setpoint: float,
        reversal_noise_frac: float = _DEFAULT_REVERSAL_NOISE_FRAC,
        recent_fraction: float = _DEFAULT_RECENT_FRACTION,
    ) -> None:
        self._window_size = window_size
        self._span = span
        self._setpoint = setpoint
        self._reversal_noise_frac = reversal_noise_frac
        self._recent_fraction = min(1.0, max(0.1, recent_fraction))
        self._samples: deque[_Sample] = deque(maxlen=window_size)
        self._elapsed_time = 0.0

    @property
    def sample_count(self) -> int:
        return len(self._samples)

    def add_sample(
        self,
        error: float,
        co: float,
        dt: float,
        is_settling: bool = False,
    ) -> None:
        """Add a new sample to the sliding window.

        ``is_settling=True`` marks the sample as part of an SP-step
        transient. Settling samples still contribute to IAE / ITAE / ISE
        and standard-deviation metrics, but are ignored by the
        oscillation indicators (pk_pk, reversals, zero_crossings) so
        the fuzzy tuner does not interpret SP-chasing as oscillation.
        """
        self._elapsed_time += dt
        self._samples.append(
            _Sample(
                error=error,
                co=co,
                dt=dt,
                elapsed_time=self._elapsed_time,
                is_settling=is_settling,
            )
        )

    def reset(self) -> None:
        """Clear all samples and reset elapsed time."""
        self._samples.clear()
        self._elapsed_time = 0.0

    @property
    def iae(self) -> float:
        """Integral of Absolute Error: sum(|e| * dt)."""
        return sum(abs(s.error) * s.dt for s in self._samples)

    @property
    def itae(self) -> float:
        """Integral of Time-weighted Absolute Error: sum(t * |e| * dt)."""
        return sum(s.elapsed_time * abs(s.error) * s.dt for s in self._samples)

    @property
    def ise(self) -> float:
        """Integral of Squared Error: sum(e^2 * dt)."""
        return sum(s.error**2 * s.dt for s in self._samples)

    @property
    def mse(self) -> float:
        """Mean Squared Error: ISE / n."""
        n = len(self._samples)
        if n == 0:
            return 0.0
        return self.ise / n

    @property
    def std_dev(self) -> float:
        """Population standard deviation of the error values."""
        n = len(self._samples)
        if n == 0:
            return 0.0
        errors = [s.error for s in self._samples]
        mean = sum(errors) / n
        variance = sum((e - mean) ** 2 for e in errors) / n
        return math.sqrt(variance)

    @property
    def total_variation(self) -> float:
        """Total Variation of CO: sum of |delta_co| between consecutive samples."""
        if len(self._samples) < 2:
            return 0.0
        samples = list(self._samples)
        return sum(abs(samples[i].co - samples[i - 1].co) for i in range(1, len(samples)))

    @property
    def variability_sp(self) -> float:
        """Variability relative to setpoint: 2*sigma/SP."""
        if self._setpoint == 0.0:
            return 0.0
        return 2.0 * self.std_dev / self._setpoint

    @property
    def variability_range(self) -> float:
        """Variability relative to span: 2*sigma/SPAN."""
        if self._span == 0.0:
            return 0.0
        return 2.0 * self.std_dev / self._span

    @property
    def mean_abs_error(self) -> float:
        """Mean |error| over the window (raw engineering units)."""
        n = len(self._samples)
        if n == 0:
            return 0.0
        return sum(abs(s.error) for s in self._samples) / n

    def _osc_errors(self) -> list[float]:
        """Error series with settling (SP-step) samples dropped."""
        return [s.error for s in self._samples if not s.is_settling]

    @property
    def pk_pk_error(self) -> float:
        """Peak-to-peak of error over the window (raw engineering units).

        Excludes samples flagged as settling so a SP step's one-sided
        transient does not inflate the amplitude.
        """
        errors = self._osc_errors()
        if not errors:
            return 0.0
        return max(errors) - min(errors)

    @property
    def reversals(self) -> int:
        """Direction reversals in the error series (settling-masked).

        A reversal is a sample where Δerror flips sign relative to the
        previous non-negligible Δerror. Steps below ``reversal_noise_frac
        × span`` are skipped so noise does not inflate the count.
        """
        errors = self._osc_errors()
        n = len(errors)
        if n < 2:
            return 0
        threshold = self._reversal_noise_frac * self._span
        count = 0
        last_dir = 0
        for i in range(1, n):
            d = errors[i] - errors[i - 1]
            if abs(d) < threshold:
                continue
            cur_dir = 1 if d > 0 else -1
            if last_dir != 0 and cur_dir != last_dir:
                count += 1
            last_dir = cur_dir
        return count

    @property
    def tv_per_sample(self) -> float:
        """Total Variation of CO per sample (raw CO units / sample)."""
        n = len(self._samples)
        if n < 2:
            return 0.0
        return self.total_variation / (n - 1)

    def osc_score(
        self,
        pkpk_full_scale_frac: float = 0.15,
        min_reversals: int = 2,
        min_zero_crossings: int = 2,
    ) -> float:
        """Composite oscillation score, same formula the fuzzy SP-tracking
        tuner uses. Exposed here so the HMI shows the operator the same
        number the engine sees, without re-implementing the gating logic.
        ``recent_pk_pk_error`` rejects stale swings; the reversal /
        zero-crossing gates reject ramps and SP-step transients.
        """
        if self._span <= 0:
            return 0.0
        pk_pk_frac = self.recent_pk_pk_error / self._span
        amp_norm = min(1.0, pk_pk_frac / pkpk_full_scale_frac)
        if (
            self.reversals < min_reversals
            or self.zero_crossings < min_zero_crossings
        ):
            return 0.0
        return amp_norm

    def _recent_errors(self) -> list[float]:
        """Last N non-settling errors for the recent sub-window."""
        n = len(self._samples)
        if n == 0:
            return []
        recent_n = max(4, int(n * self._recent_fraction))
        recent_n = min(n, recent_n)
        return [
            s.error
            for s in list(self._samples)[-recent_n:]
            if not s.is_settling
        ]

    @property
    def recent_pk_pk_error(self) -> float:
        """Peak-to-peak of error over the most recent fraction of the window.

        Used by the fuzzy OSC detector so that a loop which has
        stabilised stops registering as oscillating once the old
        high-amplitude samples age out of the recent sub-window.
        """
        recent = self._recent_errors()
        if not recent:
            return 0.0
        return max(recent) - min(recent)

    @property
    def recent_reversals(self) -> int:
        """Direction reversals within the recent sub-window."""
        recent = self._recent_errors()
        n = len(recent)
        if n < 2:
            return 0
        threshold = self._reversal_noise_frac * self._span
        count = 0
        last_dir = 0
        for i in range(1, n):
            d = recent[i] - recent[i - 1]
            if abs(d) < threshold:
                continue
            cur_dir = 1 if d > 0 else -1
            if last_dir != 0 and cur_dir != last_dir:
                count += 1
            last_dir = cur_dir
        return count

    @property
    def zero_crossings(self) -> int:
        """Count of sign flips of the error signal (settling-masked).

        Samples flagged as settling are skipped so the sign flip that
        happens when a later SP change moves in the opposite direction
        from a previous one does not leak into the oscillation signal.

        Errors within ``reversal_noise_frac × span`` are treated as zero
        so quantisation noise does not inflate the count.
        """
        n = len(self._samples)
        if n < 2:
            return 0
        threshold = self._reversal_noise_frac * self._span
        count = 0
        last_sign = 0
        for s in self._samples:
            if s.is_settling:
                continue
            if abs(s.error) < threshold:
                continue
            cur_sign = 1 if s.error > 0 else -1
            if last_sign != 0 and cur_sign != last_sign:
                count += 1
            last_sign = cur_sign
        return count
