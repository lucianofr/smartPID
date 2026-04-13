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


class StatsCalculator:
    """Computes loop performance metrics over a sliding window.

    Pure domain service — no I/O, no threading.
    """

    # Δerror below (reversal_noise_thr × span) is ignored when counting
    # direction reversals, so quantisation noise does not inflate the count.
    _DEFAULT_REVERSAL_NOISE_FRAC = 0.005

    def __init__(
        self,
        window_size: int,
        span: float,
        setpoint: float,
        reversal_noise_frac: float = _DEFAULT_REVERSAL_NOISE_FRAC,
    ) -> None:
        self._window_size = window_size
        self._span = span
        self._setpoint = setpoint
        self._reversal_noise_frac = reversal_noise_frac
        self._samples: deque[_Sample] = deque(maxlen=window_size)
        self._elapsed_time = 0.0

    @property
    def sample_count(self) -> int:
        return len(self._samples)

    def add_sample(self, error: float, co: float, dt: float) -> None:
        """Add a new sample to the sliding window."""
        self._elapsed_time += dt
        self._samples.append(
            _Sample(
                error=error,
                co=co,
                dt=dt,
                elapsed_time=self._elapsed_time,
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

    @property
    def pk_pk_error(self) -> float:
        """Peak-to-peak of error over the window (raw engineering units)."""
        if not self._samples:
            return 0.0
        errors = [s.error for s in self._samples]
        return max(errors) - min(errors)

    @property
    def reversals(self) -> int:
        """Direction reversals in the error series.

        A reversal is a sample where Δerror flips sign relative to the
        previous non-negligible Δerror. Steps below ``reversal_noise_frac
        × span`` are skipped so noise does not inflate the count.
        """
        n = len(self._samples)
        if n < 2:
            return 0
        errors = [s.error for s in self._samples]
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
