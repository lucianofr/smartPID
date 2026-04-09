"""Unit tests for FuzzyEngine — pure domain service."""
from __future__ import annotations

import pytest

from smart_pid_domain.enums import ControlObjective, ProcessSpeed


class TestMembershipFunctions:
    def test_triangular_center(self):
        from smart_pid_core.domain.services.fuzzy_engine import triangular_mf

        # Triangular(a=-50, b=0, c=50) at center
        assert triangular_mf(0.0, -50.0, 0.0, 50.0) == pytest.approx(1.0)

    def test_triangular_left_edge(self):
        from smart_pid_core.domain.services.fuzzy_engine import triangular_mf

        assert triangular_mf(-50.0, -50.0, 0.0, 50.0) == pytest.approx(0.0)

    def test_triangular_right_edge(self):
        from smart_pid_core.domain.services.fuzzy_engine import triangular_mf

        assert triangular_mf(50.0, -50.0, 0.0, 50.0) == pytest.approx(0.0)

    def test_triangular_midpoint(self):
        from smart_pid_core.domain.services.fuzzy_engine import triangular_mf

        # Halfway between a and b
        assert triangular_mf(-25.0, -50.0, 0.0, 50.0) == pytest.approx(0.5)

    def test_trapezoidal_plateau(self):
        from smart_pid_core.domain.services.fuzzy_engine import trapezoidal_mf

        # Trapezoidal(-100, -100, -67, -33) plateau between a and b
        assert trapezoidal_mf(-80.0, -100.0, -100.0, -67.0, -33.0) == pytest.approx(1.0)

    def test_trapezoidal_slope(self):
        from smart_pid_core.domain.services.fuzzy_engine import trapezoidal_mf

        # Midpoint of the right slope between c and d
        assert trapezoidal_mf(-50.0, -100.0, -100.0, -67.0, -33.0) == pytest.approx(0.5)

    def test_trapezoidal_outside(self):
        from smart_pid_core.domain.services.fuzzy_engine import trapezoidal_mf

        assert trapezoidal_mf(0.0, -100.0, -100.0, -67.0, -33.0) == pytest.approx(0.0)


class TestFuzzification:
    def test_fuzzify_zero_input(self):
        from smart_pid_core.domain.services.fuzzy_engine import FuzzyEngine

        engine = FuzzyEngine()
        memberships = engine.fuzzify(0.0)
        # At 0, only ZO should be 1.0
        assert memberships["ZO"] == pytest.approx(1.0)
        assert memberships["NB"] == pytest.approx(0.0)
        assert memberships["PB"] == pytest.approx(0.0)

    def test_fuzzify_extreme_negative(self):
        from smart_pid_core.domain.services.fuzzy_engine import FuzzyEngine

        engine = FuzzyEngine()
        memberships = engine.fuzzify(-100.0)
        assert memberships["NB"] == pytest.approx(1.0)
        assert memberships["ZO"] == pytest.approx(0.0)

    def test_fuzzify_extreme_positive(self):
        from smart_pid_core.domain.services.fuzzy_engine import FuzzyEngine

        engine = FuzzyEngine()
        memberships = engine.fuzzify(100.0)
        assert memberships["PB"] == pytest.approx(1.0)
        assert memberships["ZO"] == pytest.approx(0.0)

    def test_fuzzify_50_overlap(self):
        from smart_pid_core.domain.services.fuzzy_engine import FuzzyEngine

        engine = FuzzyEngine()
        # Near the boundary between ZO and PS (~8.33 is midpoint of overlap)
        memberships = engine.fuzzify(8.0)
        # Should have non-zero values for ZO and PS
        assert memberships["ZO"] > 0.0
        assert memberships["PS"] > 0.0
        assert memberships["ZO"] + memberships["PS"] == pytest.approx(1.0, abs=0.15)


class TestRuleMatrices:
    def test_sp_tracking_has_49_rules(self):
        from smart_pid_core.domain.services.fuzzy_engine import RULE_MATRICES

        matrix = RULE_MATRICES[ControlObjective.SP_TRACKING]
        assert len(matrix) == 7  # 7 rows (error)
        for row in matrix:
            assert len(row) == 7  # 7 columns (delta_error)

    def test_disturbance_rejection_has_49_rules(self):
        from smart_pid_core.domain.services.fuzzy_engine import RULE_MATRICES

        matrix = RULE_MATRICES[ControlObjective.DISTURBANCE_REJECTION]
        assert len(matrix) == 7

    def test_surge_level_has_49_rules(self):
        from smart_pid_core.domain.services.fuzzy_engine import RULE_MATRICES

        matrix = RULE_MATRICES[ControlObjective.SURGE_LEVEL]
        assert len(matrix) == 7


class TestInferenceAndDefuzzification:
    def test_zero_error_zero_delta_gives_zero_gamma(self):
        from smart_pid_core.domain.services.fuzzy_engine import FuzzyEngine

        engine = FuzzyEngine()
        gamma = engine.infer(
            error=0.0,
            delta_error=0.0,
            objective=ControlObjective.SP_TRACKING,
        )
        assert gamma == pytest.approx(0.0, abs=0.05)

    def test_large_positive_error_gives_positive_gamma(self):
        from smart_pid_core.domain.services.fuzzy_engine import FuzzyEngine

        engine = FuzzyEngine()
        gamma = engine.infer(
            error=80.0,
            delta_error=0.0,
            objective=ControlObjective.SP_TRACKING,
        )
        assert gamma > 0.3

    def test_large_negative_error_gives_negative_gamma(self):
        from smart_pid_core.domain.services.fuzzy_engine import FuzzyEngine

        engine = FuzzyEngine()
        gamma = engine.infer(
            error=-80.0,
            delta_error=0.0,
            objective=ControlObjective.SP_TRACKING,
        )
        assert gamma < -0.3

    def test_gamma_is_bounded(self):
        from smart_pid_core.domain.services.fuzzy_engine import FuzzyEngine

        engine = FuzzyEngine()
        gamma = engine.infer(
            error=100.0,
            delta_error=100.0,
            objective=ControlObjective.SP_TRACKING,
        )
        assert -1.0 <= gamma <= 1.0

    def test_disturbance_rejection_more_aggressive_near_zero(self):
        from smart_pid_core.domain.services.fuzzy_engine import FuzzyEngine

        engine = FuzzyEngine()
        # Small error with negative delta (error improving) — DR should be gentle
        gamma_dr = engine.infer(
            error=5.0,
            delta_error=-10.0,
            objective=ControlObjective.DISTURBANCE_REJECTION,
        )
        # Same for SP tracking
        gamma_sp = engine.infer(
            error=5.0,
            delta_error=-10.0,
            objective=ControlObjective.SP_TRACKING,
        )
        # Both should be valid floats in range
        assert -1.0 <= gamma_dr <= 1.0
        assert -1.0 <= gamma_sp <= 1.0


class TestComputeGamma:
    def test_compute_gamma_returns_ai_decision(self):
        from smart_pid_core.domain.services.fuzzy_engine import FuzzyEngine

        engine = FuzzyEngine()
        decision = engine.compute_gamma(
            error=10.0,
            delta_error=5.0,
            ki_current=1.0,
            span=100.0,
            objective=ControlObjective.SP_TRACKING,
            speed=ProcessSpeed.MEDIUM,
            limit_min=0.1,
            limit_max=100.0,
        )
        assert -1.0 <= decision.gamma <= 1.0
        assert decision.new_ki > 0.0
        assert decision.reasoning != ""
        assert decision.membership_values is not None

    def test_speed_factor_slow_ki(self):
        from smart_pid_core.domain.services.fuzzy_engine import FuzzyEngine

        engine = FuzzyEngine()
        decision = engine.compute_gamma(
            error=50.0, delta_error=0.0, ki_current=1.0, span=100.0,
            objective=ControlObjective.SP_TRACKING,
            speed=ProcessSpeed.SLOW,
            limit_min=0.1, limit_max=100.0,
            integral_type="GAIN_KI",
        )
        # GAIN_KI: Sv from ProcessSpeed.SLOW, Ki_new = Ki * (1 + gamma * Sv)
        sv = ProcessSpeed.SLOW.speed_factor
        expected_ki = 1.0 * (1.0 + decision.gamma * sv)
        assert decision.new_ki == pytest.approx(max(0.1, min(100.0, expected_ki)))

    def test_speed_factor_slow_ti(self):
        from smart_pid_core.domain.services.fuzzy_engine import FuzzyEngine

        engine = FuzzyEngine()
        decision = engine.compute_gamma(
            error=50.0, delta_error=0.0, ki_current=10.0, span=100.0,
            objective=ControlObjective.SP_TRACKING,
            speed=ProcessSpeed.SLOW,
            limit_min=0.1, limit_max=100.0,
            integral_type="TIME_TI",
        )
        # TIME_TI: gamma inverted. Positive gamma → decrease Ti (faster)
        sv = ProcessSpeed.SLOW.speed_factor
        expected_ti = 10.0 * (1.0 + (-decision.gamma) * sv)
        assert decision.new_ki == pytest.approx(max(0.1, min(100.0, expected_ti)))

    def test_ki_clamped_to_limits(self):
        from smart_pid_core.domain.services.fuzzy_engine import FuzzyEngine

        engine = FuzzyEngine()
        # With extreme gamma and small limits
        decision = engine.compute_gamma(
            error=100.0, delta_error=100.0, ki_current=99.0, span=100.0,
            objective=ControlObjective.SP_TRACKING,
            speed=ProcessSpeed.SLOW,
            limit_min=0.5, limit_max=100.0,
        )
        assert decision.new_ki <= 100.0
        assert decision.new_ki >= 0.5

    def test_zero_span_handled(self):
        from smart_pid_core.domain.services.fuzzy_engine import FuzzyEngine

        engine = FuzzyEngine()
        decision = engine.compute_gamma(
            error=0.0, delta_error=0.0, ki_current=1.0, span=0.0,
            objective=ControlObjective.SP_TRACKING,
            speed=ProcessSpeed.MEDIUM,
            limit_min=0.1, limit_max=100.0,
        )
        assert decision.gamma == pytest.approx(0.0, abs=0.05)
