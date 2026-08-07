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


class TestOscillationEvidenceIsDistinguishableFromCalm:
    """A window the settling mask ate reports zeros for every oscillation
    metric. Consumers must be able to tell that apart from a genuinely
    steady loop, or a limit cycle reads as calm."""

    @staticmethod
    def _calc(span=100.0):
        from smart_pid_core.domain.services.stats_calculator import StatsCalculator
        return StatsCalculator(window_size=50, span=span, setpoint=50.0)

    def test_osc_sample_count_reports_admissible_samples(self):
        calc = self._calc()
        for i in range(20):
            calc.add_sample(error=1.0, co=10.0, dt=1.0, is_settling=i < 15)
        assert calc.sample_count == 20
        assert calc.osc_sample_count == 5

    def test_a_fully_masked_window_reports_zero_admissible_samples(self):
        calc = self._calc()
        for _ in range(20):
            calc.add_sample(error=5.0, co=10.0, dt=1.0, is_settling=True)
        assert calc.sample_count == 20
        assert calc.osc_sample_count == 0
        # Every oscillation metric is a structural zero here, which is
        # precisely why the count above has to exist.
        assert calc.pk_pk_error == 0.0
        assert calc.reversals == 0
        assert calc.zero_crossings == 0

    def test_sp_pk_pk_tracks_setpoint_travel(self):
        calc = self._calc()
        for sp in (40.0, 60.0, 55.0, 70.0, 30.0):
            calc.add_sample(error=1.0, co=10.0, dt=1.0, sp=sp)
        assert calc.sp_pk_pk == pytest.approx(40.0)

    def test_sp_defaults_to_the_calculator_setpoint(self):
        calc = self._calc()
        for _ in range(5):
            calc.add_sample(error=1.0, co=10.0, dt=1.0)
        assert calc.sp_pk_pk == pytest.approx(0.0)

    def test_osc_score_is_judged_against_setpoint_travel(self):
        """The same error swing is a limit cycle on a fixed setpoint and an
        ordinary step response on one that is being driven around."""
        fixed = self._calc()
        moving = self._calc()
        for i in range(40):
            err = 10.0 if i % 2 == 0 else -10.0
            fixed.add_sample(error=err, co=10.0 + (i % 2), dt=1.0, sp=50.0)
            moving.add_sample(error=err, co=10.0 + (i % 2), dt=1.0,
                              sp=30.0 if i % 8 < 4 else 70.0)
        assert fixed.osc_score() > moving.osc_score()
        assert fixed.osc_score() == pytest.approx(1.0)


class TestOvershootFrac:
    """SP-step overshoot — the one indicator computed *through* the settling
    mask, because that is exactly where a step transient lives.
    """

    @staticmethod
    def _calc(pairs, *, span=100.0, window=200):
        """Feed (sp, pv) pairs. Every sample is flagged as settling, so any
        non-zero result also proves the mask does not hide the transient.
        """
        from smart_pid_core.domain.services.stats_calculator import StatsCalculator

        calc = StatsCalculator(window_size=window, span=span, setpoint=pairs[0][0])
        for sp, pv in pairs:
            calc._setpoint = sp
            calc.add_sample(error=sp - pv, co=50.0, dt=1.0, is_settling=True, sp=sp)
        return calc

    def test_up_step_overshoot_is_a_fraction_of_the_step(self):
        # SP 40 -> 60 (step of 20), PV peaks at 70 -> 10/20.
        calc = self._calc([(40.0, 40.0)] * 5 + [(60.0, 70.0)] + [(60.0, 60.0)] * 10)
        assert calc.overshoot_frac == pytest.approx(0.5)

    def test_it_reads_through_the_settling_mask(self):
        """The oscillation metrics are blind here by design; the overshoot
        indicator exists precisely to see what they cannot."""
        calc = self._calc([(40.0, 40.0)] * 5 + [(60.0, 70.0)] + [(60.0, 60.0)] * 10)
        assert calc.osc_sample_count == 0
        assert calc.pk_pk_error == 0.0
        assert calc.zero_crossings == 0
        assert calc.overshoot_frac > 0.0

    def test_down_step_overshoot_uses_the_step_direction(self):
        # SP 60 -> 50 (step of 10), PV dips to 47 -> 3/10.
        calc = self._calc([(60.0, 60.0)] * 5 + [(50.0, 47.0)] + [(50.0, 50.0)] * 10)
        assert calc.overshoot_frac == pytest.approx(0.3)

    def test_no_setpoint_change_is_never_overshoot(self):
        calc = self._calc([(50.0, 50.0 + (k % 7)) for k in range(30)])
        assert calc.overshoot_frac == 0.0

    def test_excursion_below_the_noise_floor_is_ignored(self):
        # 0.3 EU on a span of 100 is under the 0.005 x span reversal floor.
        calc = self._calc([(40.0, 40.0)] * 5 + [(60.0, 60.3)] + [(60.0, 60.0)] * 10)
        assert calc.overshoot_frac == 0.0

    def test_approaching_the_new_setpoint_is_not_overshoot(self):
        """PV climbing towards the new SP without ever crossing it carries a
        large error, but it is approach error, not overshoot."""
        approach = [(60.0, 40.0 + 1.8 * k) for k in range(11)]
        calc = self._calc([(40.0, 40.0)] * 5 + approach + [(60.0, 58.0)] * 5)
        assert calc.overshoot_frac == 0.0

    def test_the_worst_step_in_the_window_wins(self):
        calc = self._calc(
            [(40.0, 40.0)] * 3
            + [(60.0, 62.0)] + [(60.0, 60.0)] * 8      # 2/20 = 0.10
            + [(40.0, 34.0)] + [(40.0, 40.0)] * 8      # 6/20 = 0.30
        )
        assert calc.overshoot_frac == pytest.approx(0.3)

    def test_consecutive_sp_changes_merge_into_one_step(self):
        """A setpoint ramping to target over adjacent samples is one event of
        20, not two of 10 — otherwise the fraction doubles."""
        calc = self._calc(
            [(40.0, 40.0)] * 3
            + [(50.0, 40.0), (60.0, 45.0)]
            + [(60.0, 70.0)] + [(60.0, 60.0)] * 8
        )
        assert calc.overshoot_frac == pytest.approx(0.5)

    def test_distant_same_direction_steps_stay_separate(self):
        """Two 20-unit steps ten samples apart are two events; merging them
        would report 10/40 instead of 10/20."""
        calc = self._calc(
            [(40.0, 40.0)] * 3
            + [(60.0, 60.0)] * 10
            + [(80.0, 90.0)] + [(80.0, 80.0)] * 8
        )
        assert calc.overshoot_frac == pytest.approx(0.5)

    def test_a_step_on_the_last_sample_has_no_excursion_yet(self):
        calc = self._calc([(40.0, 40.0)] * 5 + [(60.0, 40.0)])
        assert calc.overshoot_frac == 0.0

    def test_too_few_samples_or_no_span_is_zero(self):
        from smart_pid_core.domain.services.stats_calculator import StatsCalculator

        assert StatsCalculator(window_size=10, span=100.0, setpoint=50.0).overshoot_frac == 0.0
        assert self._calc([(40.0, 40.0)]).overshoot_frac == 0.0
        assert self._calc(
            [(40.0, 40.0)] * 3 + [(60.0, 70.0)] * 5, span=0.0,
        ).overshoot_frac == 0.0


class TestOscPeriod:
    """Oscillation period read off the spacing of the settling-masked
    zero crossings. 0.0 means "not measurable", never "not oscillating".
    """

    @staticmethod
    def _sine(period_s, *, amplitude=10.0, n=100, is_settling=False):
        import math

        from smart_pid_core.domain.services.stats_calculator import StatsCalculator

        calc = StatsCalculator(window_size=200, span=100.0, setpoint=0.0)
        for k in range(n):
            calc.add_sample(
                error=amplitude * math.sin(2 * math.pi * k / period_s),
                co=50.0, dt=1.0, is_settling=is_settling,
            )
        return calc

    def test_measures_full_period_of_a_clean_sinewave(self):
        # Crossings land one sample after each half-cycle, so the gaps are
        # half-periods and the reported value is the full period.
        assert self._sine(20.0).osc_period_s == pytest.approx(20.0, rel=0.15)

    def test_quiet_series_under_noise_threshold_is_unmeasured(self):
        from smart_pid_core.domain.services.stats_calculator import StatsCalculator

        # |error| < reversal_noise_frac × span = 0.5 → no admissible sample.
        calc = StatsCalculator(window_size=100, span=100.0, setpoint=0.0)
        for k in range(100):
            calc.add_sample(error=0.1 if k % 2 else -0.1, co=50.0, dt=1.0)
        assert calc.osc_period_s == 0.0

    def test_too_few_crossings_is_unmeasured(self):
        from smart_pid_core.domain.services.stats_calculator import StatsCalculator

        def _flips(sequence):
            calc = StatsCalculator(window_size=100, span=100.0, setpoint=0.0)
            for e in sequence:
                calc.add_sample(error=e, co=50.0, dt=1.0)
            return calc.osc_period_s

        # Single step: one sign flip, no interval at all.
        assert _flips([-30.0] * 10 + [30.0] * 10) == 0.0
        # Two crossings give one interval — a lone gap is not an estimate.
        assert _flips([-30.0] * 5 + [30.0] * 5 + [-30.0] * 5) == 0.0
        # Three crossings is the first measurable case.
        assert _flips([-30.0] * 5 + [30.0] * 5 + [-30.0] * 5 + [30.0] * 5) == 10.0

    def test_settling_samples_are_ignored(self):
        # Same wave that measures 20.0 above, flagged as an SP-step
        # transient: chasing a setpoint is not oscillation.
        assert self._sine(20.0, is_settling=True).osc_period_s == 0.0
