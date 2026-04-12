"""Unit tests for FuzzyEngine — IAE-based Ti/Ki tuning with oscillation detection."""
from __future__ import annotations

import pytest

from smart_pid_domain.enums import ControlObjective, ProcessSpeed


class TestMembershipFunctions:
    def test_triangular_center(self):
        from smart_pid_core.domain.services.fuzzy_engine import triangular_mf

        assert triangular_mf(0.0, -50.0, 0.0, 50.0) == pytest.approx(1.0)

    def test_triangular_left_edge(self):
        from smart_pid_core.domain.services.fuzzy_engine import triangular_mf

        assert triangular_mf(-50.0, -50.0, 0.0, 50.0) == pytest.approx(0.0)

    def test_triangular_right_edge(self):
        from smart_pid_core.domain.services.fuzzy_engine import triangular_mf

        assert triangular_mf(50.0, -50.0, 0.0, 50.0) == pytest.approx(0.0)

    def test_triangular_midpoint(self):
        from smart_pid_core.domain.services.fuzzy_engine import triangular_mf

        assert triangular_mf(-25.0, -50.0, 0.0, 50.0) == pytest.approx(0.5)

    def test_trapezoidal_plateau(self):
        from smart_pid_core.domain.services.fuzzy_engine import trapezoidal_mf

        assert trapezoidal_mf(1.0, 0.0, 0.0, 2.0, 5.0) == pytest.approx(1.0)

    def test_trapezoidal_slope(self):
        from smart_pid_core.domain.services.fuzzy_engine import trapezoidal_mf

        assert trapezoidal_mf(3.5, 0.0, 0.0, 2.0, 5.0) == pytest.approx(0.5)

    def test_trapezoidal_outside(self):
        from smart_pid_core.domain.services.fuzzy_engine import trapezoidal_mf

        assert trapezoidal_mf(10.0, 0.0, 0.0, 2.0, 5.0) == pytest.approx(0.0)


class TestFuzzification:
    """Fuzzify uses absolute [0, 100] universe with 5 levels: ZO, SM, ME, LA, VL."""

    def test_fuzzify_zero_input(self):
        from smart_pid_core.domain.services.fuzzy_engine import FuzzyEngine

        engine = FuzzyEngine()
        memberships = engine.fuzzify(0.0)
        assert memberships["ZO"] == pytest.approx(1.0)
        assert memberships["VL"] == pytest.approx(0.0)

    def test_fuzzify_large_input(self):
        from smart_pid_core.domain.services.fuzzy_engine import FuzzyEngine

        engine = FuzzyEngine()
        memberships = engine.fuzzify(100.0)
        assert memberships["VL"] == pytest.approx(1.0)
        assert memberships["ZO"] == pytest.approx(0.0)

    def test_fuzzify_medium_input(self):
        from smart_pid_core.domain.services.fuzzy_engine import FuzzyEngine

        engine = FuzzyEngine()
        memberships = engine.fuzzify(25.0)
        # Should peak at ME (center=25)
        assert memberships["ME"] == pytest.approx(1.0)


class TestRuleMatrices:
    def test_sp_tracking_has_25_rules(self):
        from smart_pid_core.domain.services.fuzzy_engine import RULE_MATRICES

        matrix = RULE_MATRICES[ControlObjective.SP_TRACKING]
        assert len(matrix) == 5  # 5 rows (|error|)
        for row in matrix:
            assert len(row) == 5  # 5 columns (|delta_error|)

    def test_disturbance_rejection_has_25_rules(self):
        from smart_pid_core.domain.services.fuzzy_engine import RULE_MATRICES

        matrix = RULE_MATRICES[ControlObjective.DISTURBANCE_REJECTION]
        assert len(matrix) == 5

    def test_surge_level_has_25_rules(self):
        from smart_pid_core.domain.services.fuzzy_engine import RULE_MATRICES

        matrix = RULE_MATRICES[ControlObjective.SURGE_LEVEL]
        assert len(matrix) == 5


class TestInferenceAndDefuzzification:
    def test_zero_error_zero_delta_gives_zero_gamma(self):
        from smart_pid_core.domain.services.fuzzy_engine import FuzzyEngine

        engine = FuzzyEngine()
        gamma = engine.infer(
            abs_error=0.0, abs_delta_error=0.0,
            objective=ControlObjective.SP_TRACKING,
        )
        assert gamma == pytest.approx(0.0, abs=0.05)

    def test_large_error_small_delta_gives_positive_gamma(self):
        """High steady-state offset → gamma positive → decrease Ti."""
        from smart_pid_core.domain.services.fuzzy_engine import FuzzyEngine

        engine = FuzzyEngine()
        gamma = engine.infer(
            abs_error=80.0, abs_delta_error=2.0,
            objective=ControlObjective.SP_TRACKING,
        )
        assert gamma > 0.3

    def test_large_error_large_delta_gives_negative_gamma(self):
        """Oscillating → gamma negative → increase Ti."""
        from smart_pid_core.domain.services.fuzzy_engine import FuzzyEngine

        engine = FuzzyEngine()
        gamma = engine.infer(
            abs_error=50.0, abs_delta_error=80.0,
            objective=ControlObjective.SP_TRACKING,
        )
        assert gamma < 0.0

    def test_gamma_is_bounded(self):
        from smart_pid_core.domain.services.fuzzy_engine import FuzzyEngine

        engine = FuzzyEngine()
        gamma = engine.infer(
            abs_error=100.0, abs_delta_error=100.0,
            objective=ControlObjective.SP_TRACKING,
        )
        assert -1.0 <= gamma <= 1.0

    def test_both_error_signs_give_same_gamma_for_ti(self):
        """Positive and negative errors of same magnitude → same Ti adjustment."""
        from smart_pid_core.domain.services.fuzzy_engine import FuzzyEngine

        engine = FuzzyEngine()
        d1 = engine.compute_gamma(
            error=20.0, delta_error=0.0, ki_current=10.0, span=100.0,
            objective=ControlObjective.SP_TRACKING,
            speed=ProcessSpeed.MEDIUM, limit_min=0.1, limit_max=100.0,
            integral_type="TIME_TI",
        )
        engine2 = FuzzyEngine()
        d2 = engine2.compute_gamma(
            error=-20.0, delta_error=0.0, ki_current=10.0, span=100.0,
            objective=ControlObjective.SP_TRACKING,
            speed=ProcessSpeed.MEDIUM, limit_min=0.1, limit_max=100.0,
            integral_type="TIME_TI",
        )
        # Same |error| should produce same gamma and same new_ki
        assert d1.gamma == pytest.approx(d2.gamma, abs=0.01)
        assert d1.new_ki == pytest.approx(d2.new_ki, abs=0.01)


class TestComputeGamma:
    def test_compute_gamma_returns_ai_decision(self):
        from smart_pid_core.domain.services.fuzzy_engine import FuzzyEngine

        engine = FuzzyEngine()
        decision = engine.compute_gamma(
            error=10.0, delta_error=5.0, ki_current=1.0, span=100.0,
            objective=ControlObjective.SP_TRACKING,
            speed=ProcessSpeed.MEDIUM, limit_min=0.1, limit_max=100.0,
        )
        assert -1.0 <= decision.gamma <= 1.0
        assert decision.new_ki > 0.0
        assert decision.reasoning != ""
        assert decision.membership_values is not None

    def test_steady_offset_decreases_ti(self):
        """With steady offset (no oscillation), Ti should decrease."""
        from smart_pid_core.domain.services.fuzzy_engine import FuzzyEngine

        engine = FuzzyEngine()
        decision = engine.compute_gamma(
            error=30.0, delta_error=0.0, ki_current=20.0, span=100.0,
            objective=ControlObjective.SP_TRACKING,
            speed=ProcessSpeed.MEDIUM, limit_min=0.1, limit_max=100.0,
            integral_type="TIME_TI",
        )
        # Positive gamma → effective_gamma = -gamma → Ti should decrease
        assert decision.gamma > 0.0
        assert decision.new_ki < 20.0

    def test_ki_clamped_to_limits(self):
        from smart_pid_core.domain.services.fuzzy_engine import FuzzyEngine

        engine = FuzzyEngine()
        decision = engine.compute_gamma(
            error=100.0, delta_error=100.0, ki_current=99.0, span=100.0,
            objective=ControlObjective.SP_TRACKING,
            speed=ProcessSpeed.SLOW, limit_min=0.5, limit_max=100.0,
        )
        assert decision.new_ki <= 100.0
        assert decision.new_ki >= 0.5

    def test_zero_span_handled(self):
        from smart_pid_core.domain.services.fuzzy_engine import FuzzyEngine

        engine = FuzzyEngine()
        decision = engine.compute_gamma(
            error=0.0, delta_error=0.0, ki_current=1.0, span=0.0,
            objective=ControlObjective.SP_TRACKING,
            speed=ProcessSpeed.MEDIUM, limit_min=0.1, limit_max=100.0,
        )
        assert decision.gamma == pytest.approx(0.0, abs=0.05)


class TestOscillationDetection:
    """Oscillation detector should override fuzzy rules when process oscillates."""

    def test_oscillation_increases_ti(self):
        """Oscillating error should produce negative gamma → Ti increases."""
        from smart_pid_core.domain.services.fuzzy_engine import FuzzyEngine

        engine = FuzzyEngine()
        ti = 5.0
        errors = [30.0, -30.0] * 20  # alternating
        prev = 0.0
        for err in errors:
            de = err - prev
            d = engine.compute_gamma(
                error=err, delta_error=de, ki_current=ti, span=100.0,
                objective=ControlObjective.SP_TRACKING,
                speed=ProcessSpeed.MEDIUM, limit_min=0.1, limit_max=100.0,
                integral_type="TIME_TI",
            )
            ti = d.new_ki
            prev = err
        assert ti > 10.0, f"Ti={ti} should have increased from 5.0 with oscillation"

    def test_settled_process_no_damping(self):
        """Steady offset without oscillation should decrease Ti (more integral)."""
        from smart_pid_core.domain.services.fuzzy_engine import FuzzyEngine

        engine = FuzzyEngine()
        ti = 30.0
        for _ in range(20):
            d = engine.compute_gamma(
                error=10.0, delta_error=0.0, ki_current=ti, span=100.0,
                objective=ControlObjective.SP_TRACKING,
                speed=ProcessSpeed.MEDIUM, limit_min=0.1, limit_max=100.0,
                integral_type="TIME_TI",
            )
            ti = d.new_ki
        assert ti < 25.0, f"Ti={ti} should have decreased from 30.0 with steady offset"

    def test_measurement_noise_does_not_increase_ti(self):
        """Regression: small-amplitude noise around SP must NOT drive Ti up.

        Reported after previous fix: with K=1, τ1=10, τ2=5, θ=3 the optimal Ti≈13
        but fuzzy drove Ti past 33 because the low osc amplitude threshold treated
        ±2% noise as oscillation.
        """
        import random

        from smart_pid_core.domain.services.fuzzy_engine import FuzzyEngine

        random.seed(42)
        engine = FuzzyEngine()
        ti = 13.0
        prev = 0.0
        for _ in range(100):
            err = random.uniform(-2.0, 2.0)  # ±2% of span noise
            de = err - prev
            d = engine.compute_gamma(
                error=err, delta_error=de, ki_current=ti, span=100.0,
                objective=ControlObjective.SP_TRACKING,
                speed=ProcessSpeed.MEDIUM, limit_min=0.1, limit_max=100.0,
                integral_type="TIME_TI",
            )
            ti = d.new_ki
            prev = err
        assert ti < 15.0, (
            f"Ti={ti} — noise around SP must not drive Ti above 15 (started at 13)"
        )

    def test_high_variability_forces_ti_increase_not_decrease(self):
        """High variability + persistent error must NOT reduce Ti.

        Classic ambiguity: |e| mid-range, |Δe| small at the peak of an
        oscillation looks identical to a steady offset. The variability
        gate (2σ/span) disambiguates: if the recent window has high
        variance, it's oscillation, not offset.
        """
        import math

        from smart_pid_core.domain.services.fuzzy_engine import FuzzyEngine

        engine = FuzzyEngine()
        ti = 20.0
        prev = 0.0
        # Sinewave amp=8%, period=6 samples. At peaks |e|≈8 (ME), |Δe|≈0 — the
        # ambiguous cell. Without the gate, rules fire PM → Ti decreases.
        for k in range(40):
            err = 8.0 * math.sin(k * math.pi / 3.0)
            de = err - prev
            d = engine.compute_gamma(
                error=err, delta_error=de, ki_current=ti, span=100.0,
                objective=ControlObjective.SP_TRACKING,
                speed=ProcessSpeed.MEDIUM, limit_min=0.1, limit_max=100.0,
                integral_type="TIME_TI",
            )
            ti = d.new_ki
            prev = err
        assert ti >= 20.0, f"Ti={ti} must not drop when variability is high (oscillation)"

    def test_low_variability_steady_offset_reduces_ti(self):
        """Low variability + persistent error = true steady offset → reduce Ti."""
        from smart_pid_core.domain.services.fuzzy_engine import FuzzyEngine

        engine = FuzzyEngine()
        ti = 30.0
        # Constant error 12% — std=0, variability=0%, pure offset.
        for _ in range(20):
            d = engine.compute_gamma(
                error=12.0, delta_error=0.0, ki_current=ti, span=100.0,
                objective=ControlObjective.SP_TRACKING,
                speed=ProcessSpeed.MEDIUM, limit_min=0.1, limit_max=100.0,
                integral_type="TIME_TI",
            )
            ti = d.new_ki
        assert ti < 20.0, f"Ti={ti} should drop from 30 with steady offset + zero variability"

    def test_growing_oscillation_raises_ti_rapidly(self):
        """Fast detection + aggressive damping: Ti must climb quickly when PV oscillates.

        Plant with growing oscillation (5%→15% over 20 cycles) should see
        >30% Ti increase within 10 samples of detection.
        """
        import math

        from smart_pid_core.domain.services.fuzzy_engine import FuzzyEngine

        engine = FuzzyEngine()
        ti_start = 5.0
        ti = ti_start
        prev = 0.0
        # Growing sine: amp 5% → 15% over 20 samples, 4-sample period
        for k in range(20):
            amp = 5.0 + 10.0 * (k / 20.0)
            err = amp * math.sin(k * math.pi / 2.0)
            de = err - prev
            d = engine.compute_gamma(
                error=err, delta_error=de, ki_current=ti, span=100.0,
                objective=ControlObjective.SP_TRACKING,
                speed=ProcessSpeed.MEDIUM, limit_min=0.1, limit_max=100.0,
                integral_type="TIME_TI",
            )
            ti = d.new_ki
            prev = err
        assert ti > ti_start * 1.30, (
            f"Ti={ti} — growing oscillation should raise Ti by >30% from {ti_start}"
        )

    def test_self_damping_oscillation_does_not_overshoot_ti(self):
        """Regression: when oscillation is damping on its own, Ti should stabilise.

        Otherwise the engine keeps adding integral damping and overshoots the
        IAE/ITAE-optimal Ti.
        """
        import math

        from smart_pid_core.domain.services.fuzzy_engine import FuzzyEngine

        engine = FuzzyEngine()
        ti = 20.0
        prev = 0.0
        # Strong damping: 15% -> ~2% over 80 samples
        for k in range(80):
            amp = 15.0 * math.exp(-k / 20.0)
            err = amp * math.sin(k * math.pi / 4.0)
            de = err - prev
            d = engine.compute_gamma(
                error=err, delta_error=de, ki_current=ti, span=100.0,
                objective=ControlObjective.SP_TRACKING,
                speed=ProcessSpeed.MEDIUM, limit_min=0.1, limit_max=100.0,
                integral_type="TIME_TI",
            )
            ti = d.new_ki
            prev = err
        # Initial phase may raise Ti; once damping trend is detected, Ti must level off.
        assert ti < 40.0, (
            f"Ti={ti} overshot — self-damping oscillation should stop raising Ti"
        )

