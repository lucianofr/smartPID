"""Unit tests for StatsCalculator — pure domain service."""
from __future__ import annotations

import pytest


class TestStatsCalculatorBasic:
    def test_empty_calculator_returns_zero(self):
        from smart_pid_core.domain.services.stats_calculator import StatsCalculator

        calc = StatsCalculator(window_size=100, span=100.0, setpoint=50.0)
        assert calc.iae == 0.0
        assert calc.itae == 0.0
        assert calc.ise == 0.0
        assert calc.mse == 0.0
        assert calc.std_dev == 0.0
        assert calc.total_variation == 0.0
        assert calc.mean_abs_error == 0.0
        assert calc.pk_pk_error == 0.0
        assert calc.reversals == 0
        assert calc.tv_per_sample == 0.0

    def test_iae_accumulates_absolute_error(self):
        from smart_pid_core.domain.services.stats_calculator import StatsCalculator

        calc = StatsCalculator(window_size=100, span=100.0, setpoint=50.0)
        # 3 samples with errors: +5, -3, +2, dt=1.0 each
        calc.add_sample(error=5.0, co=50.0, dt=1.0)
        calc.add_sample(error=-3.0, co=50.0, dt=1.0)
        calc.add_sample(error=2.0, co=50.0, dt=1.0)
        assert calc.iae == pytest.approx(10.0)  # |5|+|-3|+|2| = 10

    def test_itae_weighs_by_time(self):
        from smart_pid_core.domain.services.stats_calculator import StatsCalculator

        calc = StatsCalculator(window_size=100, span=100.0, setpoint=50.0)
        # t=1: |e|=5, t=2: |e|=3, t=3: |e|=2
        calc.add_sample(error=5.0, co=50.0, dt=1.0)   # t=1, contrib: 1*5=5
        calc.add_sample(error=-3.0, co=50.0, dt=1.0)   # t=2, contrib: 2*3=6
        calc.add_sample(error=2.0, co=50.0, dt=1.0)    # t=3, contrib: 3*2=6
        assert calc.itae == pytest.approx(17.0)

    def test_ise_accumulates_squared_error(self):
        from smart_pid_core.domain.services.stats_calculator import StatsCalculator

        calc = StatsCalculator(window_size=100, span=100.0, setpoint=50.0)
        calc.add_sample(error=3.0, co=50.0, dt=1.0)
        calc.add_sample(error=4.0, co=50.0, dt=1.0)
        assert calc.ise == pytest.approx(25.0)  # 9+16=25

    def test_mse_is_mean_squared_error(self):
        from smart_pid_core.domain.services.stats_calculator import StatsCalculator

        calc = StatsCalculator(window_size=100, span=100.0, setpoint=50.0)
        calc.add_sample(error=3.0, co=50.0, dt=1.0)
        calc.add_sample(error=4.0, co=50.0, dt=1.0)
        assert calc.mse == pytest.approx(12.5)  # 25/2

    def test_std_dev_of_constant_is_zero(self):
        from smart_pid_core.domain.services.stats_calculator import StatsCalculator

        calc = StatsCalculator(window_size=100, span=100.0, setpoint=50.0)
        for _ in range(10):
            calc.add_sample(error=5.0, co=50.0, dt=1.0)
        assert calc.std_dev == pytest.approx(0.0)

    def test_std_dev_known_series(self):
        from smart_pid_core.domain.services.stats_calculator import StatsCalculator

        calc = StatsCalculator(window_size=100, span=100.0, setpoint=50.0)
        values = [2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0]
        for v in values:
            calc.add_sample(error=v, co=50.0, dt=1.0)
        # std dev of [2,4,4,4,5,5,7,9] = 2.0 (population)
        assert calc.std_dev == pytest.approx(2.0, abs=0.01)

    def test_total_variation_counts_co_changes(self):
        from smart_pid_core.domain.services.stats_calculator import StatsCalculator

        calc = StatsCalculator(window_size=100, span=100.0, setpoint=50.0)
        calc.add_sample(error=0.0, co=50.0, dt=1.0)
        calc.add_sample(error=0.0, co=55.0, dt=1.0)  # delta: 5
        calc.add_sample(error=0.0, co=52.0, dt=1.0)  # delta: 3
        calc.add_sample(error=0.0, co=58.0, dt=1.0)  # delta: 6
        assert calc.total_variation == pytest.approx(14.0)

    def test_variability_sp(self):
        from smart_pid_core.domain.services.stats_calculator import StatsCalculator

        calc = StatsCalculator(window_size=100, span=100.0, setpoint=50.0)
        values = [2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0]
        for v in values:
            calc.add_sample(error=v, co=50.0, dt=1.0)
        # variability_sp = 2*sigma/SP = 2*2.0/50.0 = 0.08
        assert calc.variability_sp == pytest.approx(0.08, abs=0.01)

    def test_variability_range(self):
        from smart_pid_core.domain.services.stats_calculator import StatsCalculator

        calc = StatsCalculator(window_size=100, span=100.0, setpoint=50.0)
        values = [2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0]
        for v in values:
            calc.add_sample(error=v, co=50.0, dt=1.0)
        # variability_range = 2*sigma/SPAN = 2*2.0/100.0 = 0.04
        assert calc.variability_range == pytest.approx(0.04, abs=0.01)


class TestOscillationMetrics:
    def test_mean_abs_error(self):
        from smart_pid_core.domain.services.stats_calculator import StatsCalculator

        calc = StatsCalculator(window_size=100, span=100.0, setpoint=50.0)
        for e in [3.0, -4.0, 5.0]:
            calc.add_sample(error=e, co=50.0, dt=1.0)
        assert calc.mean_abs_error == pytest.approx(4.0)  # (3+4+5)/3

    def test_pk_pk_error(self):
        from smart_pid_core.domain.services.stats_calculator import StatsCalculator

        calc = StatsCalculator(window_size=100, span=100.0, setpoint=50.0)
        for e in [-2.0, 5.0, 3.0, -7.0, 1.0]:
            calc.add_sample(error=e, co=50.0, dt=1.0)
        assert calc.pk_pk_error == pytest.approx(12.0)  # 5 - (-7)

    def test_reversals_counts_direction_changes(self):
        from smart_pid_core.domain.services.stats_calculator import StatsCalculator

        calc = StatsCalculator(window_size=100, span=100.0, setpoint=50.0)
        # 0 → 5 → 2 → 8 → 4 : reversals at each peak/valley = 3
        for e in [0.0, 5.0, 2.0, 8.0, 4.0]:
            calc.add_sample(error=e, co=50.0, dt=1.0)
        assert calc.reversals == 3

    def test_reversals_ignores_sub_noise_steps(self):
        from smart_pid_core.domain.services.stats_calculator import StatsCalculator

        # reversal_noise_frac default 0.005 of span → 0.5 abs. Tiny 0.1
        # wiggles must not fabricate reversals.
        calc = StatsCalculator(window_size=100, span=100.0, setpoint=50.0)
        for e in [5.0, 5.1, 4.9, 5.0]:  # all differences < 0.5
            calc.add_sample(error=e, co=50.0, dt=1.0)
        assert calc.reversals == 0

    def test_reversals_ramp_is_zero(self):
        from smart_pid_core.domain.services.stats_calculator import StatsCalculator

        calc = StatsCalculator(window_size=100, span=100.0, setpoint=50.0)
        for k in range(20):
            calc.add_sample(error=float(k), co=50.0, dt=1.0)
        assert calc.reversals == 0

    def test_zero_crossings_ignores_sp_step_transient(self):
        """Regression: an error that stays on one side of zero during
        settling must report zero_crossings = 0 so SP steps are not
        confused with oscillation.
        """
        from smart_pid_core.domain.services.stats_calculator import StatsCalculator

        calc = StatsCalculator(window_size=50, span=100.0, setpoint=0.0)
        # First-order decay from -30 to 0, no sign flip.
        import math
        for k in range(50):
            calc.add_sample(error=-30.0 * math.exp(-k / 10.0),
                            co=50.0, dt=1.0)
        # Reversals may be non-zero (smooth curvature near 0 fails below
        # the noise threshold, then picks up again), but zero_crossings
        # must stay zero.
        assert calc.zero_crossings == 0

    def test_zero_crossings_counts_oscillation(self):
        """A clean sinewave with 4 full cycles has 8 half-cycle crossings."""
        from smart_pid_core.domain.services.stats_calculator import StatsCalculator

        calc = StatsCalculator(window_size=200, span=100.0, setpoint=0.0)
        import math
        for k in range(200):
            calc.add_sample(error=30.0 * math.sin(2 * math.pi * k / 50.0),
                            co=50.0, dt=1.0)
        assert calc.zero_crossings >= 6  # at least 6 of the expected ~7-8

    def test_recent_pk_pk_walks_back_when_settling_dominates_recent_window(
        self,
    ):
        """Regression: when the last 40% of the window is all settling
        (e.g. a recent SP-step cooldown), recent_pk_pk_error must walk
        backward to the last non-settling samples instead of returning
        zero.
        """
        import math

        from smart_pid_core.domain.services.stats_calculator import StatsCalculator

        calc = StatsCalculator(window_size=200, span=100.0, setpoint=0.0)
        # Older 120 samples: clean oscillation (non-settling).
        for k in range(120):
            calc.add_sample(
                error=30.0 * math.sin(2 * math.pi * k / 40.0),
                co=50.0, dt=1.0, is_settling=False,
            )
        # Last 80 samples: settling cooldown (would have masked the
        # entire recent sub-window in the old implementation).
        for _ in range(80):
            calc.add_sample(error=10.0, co=50.0, dt=1.0, is_settling=True)

        # Should reflect the oscillation amplitude from the older samples,
        # not zero.
        assert calc.recent_pk_pk_error > 50.0

    def test_settling_samples_are_masked_from_oscillation_metrics(self):
        """is_settling=True samples must NOT contribute to pk_pk,
        reversals or zero_crossings, but MUST still count toward IAE.
        """
        from smart_pid_core.domain.services.stats_calculator import StatsCalculator

        calc = StatsCalculator(window_size=20, span=100.0, setpoint=0.0)
        # Big swings flagged as settling.
        for e in [-30.0, +30.0, -30.0, +30.0]:
            calc.add_sample(error=e, co=50.0, dt=1.0, is_settling=True)
        # Small steady error not flagged.
        for _ in range(16):
            calc.add_sample(error=0.0, co=50.0, dt=1.0)
        assert calc.pk_pk_error == 0.0
        assert calc.reversals == 0
        assert calc.zero_crossings == 0
        # IAE still includes the masked samples (4 × 30 × 1.0 = 120).
        assert calc.iae == pytest.approx(120.0)

    def test_zero_crossings_two_opposite_sp_steps_gives_at_most_one(self):
        from smart_pid_core.domain.services.stats_calculator import StatsCalculator

        calc = StatsCalculator(window_size=200, span=100.0, setpoint=0.0)
        import math
        # Decay from -30 to 0 (60 samples)
        for k in range(60):
            calc.add_sample(error=-30.0 * math.exp(-k / 20.0),
                            co=50.0, dt=1.0)
        # Quiet (40 samples)
        for _ in range(40):
            calc.add_sample(error=0.0, co=50.0, dt=1.0)
        # Decay from +30 to 0 (60 samples)
        for k in range(60):
            calc.add_sample(error=30.0 * math.exp(-k / 20.0),
                            co=50.0, dt=1.0)
        for _ in range(40):
            calc.add_sample(error=0.0, co=50.0, dt=1.0)
        # Error region goes from negative → zero → positive → zero.
        # One sign transition only.
        assert calc.zero_crossings <= 1

    def test_recent_pk_pk_ignores_stale_samples(self):
        """Regression: once the loop settles, recent_pk_pk must drop even
        when the full window still contains old oscillation data.
        """
        from smart_pid_core.domain.services.stats_calculator import StatsCalculator

        calc = StatsCalculator(window_size=20, span=100.0, setpoint=0.0)
        # First 10 samples: big swings.
        for e in [-30.0, 30.0, -30.0, 30.0, -30.0,
                  30.0, -30.0, 30.0, -30.0, 30.0]:
            calc.add_sample(error=e, co=50.0, dt=1.0)
        # Last 10 samples: flat at zero.
        for _ in range(10):
            calc.add_sample(error=0.0, co=50.0, dt=1.0)

        # Full window still sees the old oscillation.
        assert calc.pk_pk_error > 50.0
        assert calc.reversals > 2
        # Recent sub-window (40%, i.e. last 8 samples) is entirely flat.
        assert calc.recent_pk_pk_error == 0.0
        assert calc.recent_reversals == 0

    def test_tv_per_sample(self):
        from smart_pid_core.domain.services.stats_calculator import StatsCalculator

        calc = StatsCalculator(window_size=100, span=100.0, setpoint=50.0)
        for co in [50.0, 52.0, 49.0, 51.0]:  # |Δ|: 2, 3, 2 → TV=7, n-1=3
            calc.add_sample(error=0.0, co=co, dt=1.0)
        assert calc.tv_per_sample == pytest.approx(7.0 / 3.0)


class TestStatsCalculatorWindow:
    def test_sliding_window_evicts_old_samples(self):
        from smart_pid_core.domain.services.stats_calculator import StatsCalculator

        calc = StatsCalculator(window_size=3, span=100.0, setpoint=50.0)
        calc.add_sample(error=10.0, co=50.0, dt=1.0)
        calc.add_sample(error=20.0, co=50.0, dt=1.0)
        calc.add_sample(error=30.0, co=50.0, dt=1.0)
        # Window: [10, 20, 30], IAE = 60
        assert calc.iae == pytest.approx(60.0)

        calc.add_sample(error=5.0, co=50.0, dt=1.0)
        # Window: [20, 30, 5], IAE recomputed from window
        assert calc.sample_count == 3

    def test_reset_clears_all(self):
        from smart_pid_core.domain.services.stats_calculator import StatsCalculator

        calc = StatsCalculator(window_size=100, span=100.0, setpoint=50.0)
        calc.add_sample(error=5.0, co=50.0, dt=1.0)
        calc.reset()
        assert calc.iae == 0.0
        assert calc.sample_count == 0
