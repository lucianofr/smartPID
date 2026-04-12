"""Unit tests for FuzzyEngineV2 — 3-input (IAE, OSC, TV) → Δ_Ti strategy."""
from __future__ import annotations

import math

import pytest


class TestMembershipFunctions:
    def test_iae_low_boundary(self):
        from smart_pid_core.domain.services.fuzzy_engine_v2 import MF_IAE, FuzzyEngineV2
        mfs = FuzzyEngineV2._fuzzify(0.0, MF_IAE)
        assert mfs["LOW"] == pytest.approx(1.0)
        assert mfs["HIGH"] == pytest.approx(0.0)

    def test_iae_high_boundary(self):
        from smart_pid_core.domain.services.fuzzy_engine_v2 import MF_IAE, FuzzyEngineV2
        mfs = FuzzyEngineV2._fuzzify(1.0, MF_IAE)
        assert mfs["HIGH"] == pytest.approx(1.0)
        assert mfs["LOW"] == pytest.approx(0.0)

    def test_osc_stable_at_zero(self):
        from smart_pid_core.domain.services.fuzzy_engine_v2 import MF_OSC, FuzzyEngineV2
        mfs = FuzzyEngineV2._fuzzify(0.0, MF_OSC)
        assert mfs["STABLE"] == pytest.approx(1.0)

    def test_eff_moderate_peak(self):
        from smart_pid_core.domain.services.fuzzy_engine_v2 import MF_EFF, FuzzyEngineV2
        mfs = FuzzyEngineV2._fuzzify(0.6, MF_EFF)
        assert mfs["MODERATE"] == pytest.approx(1.0)


class TestIndicators:
    def test_iae_norm_zero_on_empty(self):
        from smart_pid_core.domain.services.fuzzy_engine_v2 import FuzzyEngineV2
        engine = FuzzyEngineV2()
        assert engine._iae_norm() == 0.0

    def test_iae_norm_saturates_at_20pct(self):
        from smart_pid_core.domain.services.fuzzy_engine_v2 import FuzzyEngineV2
        engine = FuzzyEngineV2()
        for _ in range(20):
            engine.update_sample(error_frac=0.25, co_frac=0.0)
        assert engine._iae_norm() == pytest.approx(1.0)

    def test_osc_norm_sinewave_amp_10pct(self):
        from smart_pid_core.domain.services.fuzzy_engine_v2 import FuzzyEngineV2
        engine = FuzzyEngineV2()
        # amp 10% of span, period 8 samples
        for k in range(20):
            e = 0.10 * math.sin(k * math.pi / 4.0)
            engine.update_sample(error_frac=e, co_frac=0.0)
        # 2σ of sinewave amp 0.1 ≈ 0.141; /0.5 scale ≈ 0.283
        osc = engine._osc_norm()
        assert 0.2 < osc < 0.4, f"osc={osc}"

    def test_eff_norm_constant_co_is_zero(self):
        from smart_pid_core.domain.services.fuzzy_engine_v2 import FuzzyEngineV2
        engine = FuzzyEngineV2()
        for _ in range(20):
            engine.update_sample(error_frac=0.0, co_frac=0.5)
        assert engine._eff_norm() == 0.0

    def test_eff_norm_alternating_co_is_high(self):
        from smart_pid_core.domain.services.fuzzy_engine_v2 import FuzzyEngineV2
        engine = FuzzyEngineV2()
        # CO jumping 0.15 each sample
        for k in range(20):
            engine.update_sample(error_frac=0.0, co_frac=0.5 + 0.075 * (-1) ** k)
        eff = engine._eff_norm()
        assert eff == pytest.approx(1.0, abs=0.1), f"eff={eff}"

    def test_deadband_filters_small_errors(self):
        from smart_pid_core.domain.services.fuzzy_engine_v2 import FuzzyEngineV2
        engine = FuzzyEngineV2()
        for _ in range(20):
            engine.update_sample(error_frac=0.01, co_frac=0.0)  # below 2% deadband
        # All stored as 0 → IAE norm = 0
        assert engine._iae_norm() == 0.0


class TestRuleOutcomes:
    """Verify the qualitative behaviour of each named rule."""

    def test_R1_high_iae_stable_smooth_reduces_ti(self):
        """Persistent offset, no oscillation, calm valve → reduce Ti."""
        from smart_pid_core.domain.services.fuzzy_engine_v2 import FuzzyEngineV2
        engine = FuzzyEngineV2()
        # Steady 15% offset, constant CO → IAE high, OSC stable, EFF smooth
        for _ in range(20):
            engine.update_sample(error_frac=0.15, co_frac=0.5)
        d = engine.compute_adjustment(ti_current=20.0, limit_min=0.1, limit_max=100.0)
        assert d.delta_ti < -0.05, f"Δ_Ti={d.delta_ti} should be clearly negative"
        assert d.new_ti < 20.0

    def test_R2_high_iae_unstable_osc_increases_ti_a_lot(self):
        """High IAE + unstable oscillation → Δ_Ti ≈ +0.3 (AM)."""
        from smart_pid_core.domain.services.fuzzy_engine_v2 import FuzzyEngineV2
        engine = FuzzyEngineV2()
        # Square-wave style: large alternating errors, big CO swings
        for k in range(20):
            sign = 1 if k % 2 == 0 else -1
            engine.update_sample(error_frac=0.35 * sign, co_frac=0.5 + 0.2 * sign)
        d = engine.compute_adjustment(ti_current=5.0, limit_min=0.1, limit_max=100.0)
        assert d.delta_ti > 0.20, f"Δ_Ti={d.delta_ti} should be strongly positive"
        assert d.new_ti > 5.0

    def test_R3_excess_effort_oscillation_increases_ti(self):
        """Nervous loop (oscillating + valve chattering) → Δ_Ti positive."""
        from smart_pid_core.domain.services.fuzzy_engine_v2 import FuzzyEngineV2
        engine = FuzzyEngineV2()
        # Clear oscillation (amp 15%) with CO chattering heavily
        for k in range(20):
            e = 0.15 * math.sin(k * math.pi / 4.0)
            co = 0.5 + 0.09 * (-1) ** k
            engine.update_sample(error_frac=e, co_frac=co)
        d = engine.compute_adjustment(ti_current=10.0, limit_min=0.1, limit_max=100.0)
        assert d.delta_ti > 0.0, f"Δ_Ti={d.delta_ti} should be positive (save the valve)"

    def test_R5_settled_holds_ti_stable(self):
        """Low IAE + stable → maintain (Δ_Ti ≈ 0)."""
        from smart_pid_core.domain.services.fuzzy_engine_v2 import FuzzyEngineV2
        engine = FuzzyEngineV2()
        # Tiny residual error, calm CO
        for _k in range(20):
            engine.update_sample(error_frac=0.005, co_frac=0.5)
        d = engine.compute_adjustment(ti_current=15.0, limit_min=0.1, limit_max=100.0)
        assert abs(d.delta_ti) < 0.05, f"Δ_Ti={d.delta_ti} should be near zero"

    def test_ti_is_clamped_to_limits(self):
        from smart_pid_core.domain.services.fuzzy_engine_v2 import FuzzyEngineV2
        engine = FuzzyEngineV2()
        for k in range(20):
            sign = 1 if k % 2 == 0 else -1
            engine.update_sample(error_frac=0.4 * sign, co_frac=0.5)
        d = engine.compute_adjustment(ti_current=99.0, limit_min=0.1, limit_max=100.0)
        assert d.new_ti <= 100.0

    def test_both_error_signs_produce_same_delta(self):
        """Δ_Ti must not depend on the sign of error — only magnitude/statistics."""
        from smart_pid_core.domain.services.fuzzy_engine_v2 import FuzzyEngineV2
        e1 = FuzzyEngineV2()
        for _ in range(20):
            e1.update_sample(error_frac=0.12, co_frac=0.5)
        d1 = e1.compute_adjustment(ti_current=20.0, limit_min=0.1, limit_max=100.0)

        e2 = FuzzyEngineV2()
        for _ in range(20):
            e2.update_sample(error_frac=-0.12, co_frac=0.5)
        d2 = e2.compute_adjustment(ti_current=20.0, limit_min=0.1, limit_max=100.0)

        # IAE uses |e|, OSC uses variance (sign-invariant), EFF uses |ΔCO|
        assert d1.delta_ti == pytest.approx(d2.delta_ti, abs=0.001)


class TestUsersRealScenario:
    def test_high_amp_oscillation_at_low_ti_triggers_strong_ti_increase(self):
        """User's real log: amp ~15%, Ti stuck at 3.87. V2 must raise Ti fast."""
        from smart_pid_core.domain.services.fuzzy_engine_v2 import FuzzyEngineV2
        engine = FuzzyEngineV2()
        # ~15% amp sinewave, big CO swings from the PID reacting
        ti = 3.87
        for _cycle in range(10):
            for k in range(20):
                e = 0.15 * math.sin(k * math.pi / 4.0)
                co = 0.5 + 0.3 * math.sin(k * math.pi / 4.0 + math.pi / 2.0)
                engine.update_sample(error_frac=e, co_frac=co)
            d = engine.compute_adjustment(ti_current=ti, limit_min=0.1, limit_max=100.0)
            ti = d.new_ti
        assert ti > 3.87 * 2.0, f"Ti={ti} did not climb — strategy failed"
