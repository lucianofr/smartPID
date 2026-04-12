"""Unit tests for FuzzyEngineV2 — 3-input (IAE, OSC, TV) → Δ_Ti strategy."""
from __future__ import annotations

import math

import pytest


class TestMembershipFunctions:
    def test_iae_low_boundary(self):
        from smart_pid_core.domain.services.fuzzy_engine_v2 import MF_IAE, _fuzzify
        mfs = _fuzzify(0.0, MF_IAE)
        assert mfs["LOW"] == pytest.approx(1.0)
        assert mfs["HIGH"] == pytest.approx(0.0)

    def test_iae_high_boundary(self):
        from smart_pid_core.domain.services.fuzzy_engine_v2 import MF_IAE, _fuzzify
        mfs = _fuzzify(1.0, MF_IAE)
        assert mfs["HIGH"] == pytest.approx(1.0)
        assert mfs["LOW"] == pytest.approx(0.0)

    def test_osc_stable_at_zero(self):
        from smart_pid_core.domain.services.fuzzy_engine_v2 import MF_OSC, _fuzzify
        mfs = _fuzzify(0.0, MF_OSC)
        assert mfs["STABLE"] == pytest.approx(1.0)

    def test_eff_moderate_peak(self):
        from smart_pid_core.domain.services.fuzzy_engine_v2 import MF_EFF, _fuzzify
        mfs = _fuzzify(0.6, MF_EFF)
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


# ===========================================================================
# Strategy 2 — Disturbance Rejection
# ===========================================================================


class TestDisturbanceRejectionStateMachine:
    def _make(self):
        from smart_pid_core.domain.services.fuzzy_engine_v2 import (
            FuzzyEngineV2DisturbanceRejection,
        )
        # tau=10s, e_max_full=5%, dt=1s
        return FuzzyEngineV2DisturbanceRejection(
            tau_estimate_sec=10.0, e_max_norm_full=0.05, dt_sec=1.0,
        )

    def test_quiet_signal_stays_idle_and_holds_ti(self):
        engine = self._make()
        for _ in range(20):
            engine.update_sample(error_frac=0.005)
        assert engine.state == "IDLE"
        d = engine.compute_adjustment(ti_current=10.0, limit_min=0.1, limit_max=100.0)
        assert d.delta_ti == 0.0
        assert d.new_ti == 10.0

    def test_trigger_moves_to_active(self):
        engine = self._make()
        engine.update_sample(error_frac=0.03)  # above 2% deadband
        assert engine.state == "ACTIVE"

    def test_return_to_band_ends_event_after_dwell(self):
        engine = self._make()
        # Trigger + 5 samples of disturbance
        for _ in range(5):
            engine.update_sample(error_frac=0.04)
        assert engine.state == "ACTIVE"
        # Return to band — needs 3 consecutive in-band samples
        for _ in range(3):
            engine.update_sample(error_frac=0.005)
        assert engine.state == "SETTLING"

    def test_full_event_produces_ready_decision(self):
        engine = self._make()
        # Disturbance of peak 4% for 8 samples
        for _ in range(8):
            engine.update_sample(error_frac=0.04)
        # Return
        for _ in range(3):
            engine.update_sample(error_frac=0.005)
        # Post-event window of 15 samples
        for _ in range(15):
            engine.update_sample(error_frac=0.003)
        assert engine.decision_ready
        assert engine.state == "IDLE"  # reset after finalise
        d = engine.compute_adjustment(ti_current=10.0, limit_min=0.1, limit_max=100.0)
        assert "E_MAX" in d.inputs
        assert not engine.decision_ready  # consumed


class TestDisturbanceRejectionRules:
    def _run_event(
        self, engine, peak_abs_err: float, duration_samples: int,
        residual_amp: float = 0.0,
    ):
        """Feed a synthetic disturbance event into the engine."""
        import math as _math

        # Ramp up to peak within the event window
        for k in range(duration_samples):
            # Simple triangular shape: peak at mid-event
            frac = k / max(1, duration_samples - 1)
            e = peak_abs_err * (2 * frac) if frac <= 0.5 else peak_abs_err * (2 - 2 * frac)
            engine.update_sample(error_frac=e)
        # Exit dwell
        for _ in range(3):
            engine.update_sample(error_frac=0.005)
        # Post-event window with configured residual oscillation
        for k in range(15):
            noise = residual_amp * _math.sin(k * _math.pi / 3.0)
            engine.update_sample(error_frac=noise)

    def test_R1_slow_weak_response_reduces_ti(self):
        """Big peak, slow recovery, calm post-event → Δ_Ti negative."""
        from smart_pid_core.domain.services.fuzzy_engine_v2 import (
            FuzzyEngineV2DisturbanceRejection,
        )
        engine = FuzzyEngineV2DisturbanceRejection(
            tau_estimate_sec=10.0, e_max_norm_full=0.05, dt_sec=1.0,
        )
        # peak 5% (e_max_norm=1.0 HIGH), duration 80 samples = 8τ (SLOW),
        # residual 0 (STABLE)
        self._run_event(engine, peak_abs_err=0.05, duration_samples=80)
        d = engine.compute_adjustment(ti_current=10.0, limit_min=0.1, limit_max=100.0)
        assert d.delta_ti < -0.1, f"Δ_Ti={d.delta_ti} should be clearly negative"
        assert d.new_ti < 10.0

    def test_R2_fast_but_oscillatory_increases_ti(self):
        """Moderate peak, fast recovery, HIGH residual osc → Δ_Ti positive.

        Tests the residual-osc rule (any HIGH osc → A) by feeding a rapid
        recovery followed by a residual sinewave that barely stays in-band
        enough to trigger SETTLING. Uses infer() directly to bypass the
        exit-dwell complication (tested separately).
        """
        from smart_pid_core.domain.services.fuzzy_engine_v2 import (
            FuzzyEngineV2DisturbanceRejection,
        )
        engine = FuzzyEngineV2DisturbanceRejection()
        # e_max=MED(0.6), t_rec=FAST(1.0), osc=HIGH(0.8) — R2' should fire AM
        delta, _mfs = engine.infer(e_max=0.6, t_rec=1.0, osc=0.8)
        assert delta > 0.1, f"Δ_Ti={delta} should be positive (AM for MED+FAST+HIGH osc)"

    def test_R1_via_infer_reduces_strongly_with_high_peak_slow_stable(self):
        """Direct infer: HIGH peak + SLOW recovery + STABLE osc → RM."""
        from smart_pid_core.domain.services.fuzzy_engine_v2 import (
            FuzzyEngineV2DisturbanceRejection,
        )
        engine = FuzzyEngineV2DisturbanceRejection()
        delta, _mfs = engine.infer(e_max=1.0, t_rec=8.0, osc=0.05)
        assert delta < -0.2, f"Δ_Ti={delta} should be strongly negative (RM)"

    def test_R3_big_peak_fast_recovery_maintains_ti(self):
        """Big impact handled quickly (physics-limited) → maintain."""
        from smart_pid_core.domain.services.fuzzy_engine_v2 import (
            FuzzyEngineV2DisturbanceRejection,
        )
        engine = FuzzyEngineV2DisturbanceRejection(
            tau_estimate_sec=10.0, e_max_norm_full=0.05, dt_sec=1.0,
        )
        # peak 5% HIGH, duration 5 samples = 0.5τ FAST, residual 0 STABLE
        self._run_event(engine, peak_abs_err=0.05, duration_samples=5)
        d = engine.compute_adjustment(ti_current=10.0, limit_min=0.1, limit_max=100.0)
        assert abs(d.delta_ti) < 0.05, (
            f"Δ_Ti={d.delta_ti} should be near zero (physics compromise)"
        )


# ===========================================================================
# Strategy 3 — Surge Level / Averaging Control
# ===========================================================================


class TestSurgeLevelIndicators:
    def test_l_margin_at_centre(self):
        from smart_pid_core.domain.services.fuzzy_engine_v2 import (
            FuzzyEngineV2SurgeLevel,
        )
        engine = FuzzyEngineV2SurgeLevel(dt_sec=60.0)
        engine.update_sample(pv_frac=0.5, co_frac=0.5)
        assert engine._l_margin() == pytest.approx(0.0)

    def test_l_margin_critical(self):
        from smart_pid_core.domain.services.fuzzy_engine_v2 import (
            FuzzyEngineV2SurgeLevel,
        )
        engine = FuzzyEngineV2SurgeLevel(dt_sec=60.0)
        engine.update_sample(pv_frac=0.97, co_frac=0.5)
        assert engine._l_margin() == pytest.approx(0.47)

    def test_tv_with_calm_valve_is_zero(self):
        from smart_pid_core.domain.services.fuzzy_engine_v2 import (
            FuzzyEngineV2SurgeLevel,
        )
        engine = FuzzyEngineV2SurgeLevel(dt_sec=60.0)
        for _ in range(20):
            engine.update_sample(pv_frac=0.5, co_frac=0.5)
        assert engine._tv_mv() == 0.0

    def test_dl_dt_positive_when_heading_toward_upper_limit(self):
        from smart_pid_core.domain.services.fuzzy_engine_v2 import (
            FuzzyEngineV2SurgeLevel,
        )
        engine = FuzzyEngineV2SurgeLevel(dt_sec=60.0)
        # PV climbing from 0.6 to 0.9 over 20 samples (20 minutes)
        for k in range(20):
            pv = 0.6 + 0.3 * (k / 19)
            engine.update_sample(pv_frac=pv, co_frac=0.5)
        # margin went 0.1 → 0.4 over 19 minutes → +0.3/19 ≈ 1.58%/min
        rate = engine._dl_dt()
        assert rate > 1.0, f"dL/dt={rate} should be clearly positive"

    def test_dl_dt_negative_when_returning_to_centre(self):
        from smart_pid_core.domain.services.fuzzy_engine_v2 import (
            FuzzyEngineV2SurgeLevel,
        )
        engine = FuzzyEngineV2SurgeLevel(dt_sec=60.0)
        # PV falling from 0.9 back to 0.6
        for k in range(20):
            pv = 0.9 - 0.3 * (k / 19)
            engine.update_sample(pv_frac=pv, co_frac=0.5)
        rate = engine._dl_dt()
        assert rate < -1.0, f"dL/dt={rate} should be clearly negative (escaping)"


class TestSurgeLevelRules:
    def test_R1_safe_level_with_chattering_valve_relaxes_hard(self):
        """Safe level + high valve TV → Δ_Ti strongly positive (AM)."""
        from smart_pid_core.domain.services.fuzzy_engine_v2 import (
            FuzzyEngineV2SurgeLevel,
        )
        engine = FuzzyEngineV2SurgeLevel(dt_sec=60.0)
        # PV near 50%, CO jumping 10% each sample
        for k in range(20):
            engine.update_sample(pv_frac=0.5, co_frac=0.5 + 0.05 * (-1) ** k)
        d = engine.compute_adjustment(ti_current=60.0, limit_min=1.0, limit_max=10000.0)
        assert d.delta_ti > 0.3, f"Δ_Ti={d.delta_ti} should be strongly positive (AM)"
        assert d.new_ti > 60.0

    def test_R2_ideal_surge_operation_maintains(self):
        """Safe level + calm valve + slow rate → Δ_Ti ≈ 0."""
        from smart_pid_core.domain.services.fuzzy_engine_v2 import (
            FuzzyEngineV2SurgeLevel,
        )
        engine = FuzzyEngineV2SurgeLevel(dt_sec=60.0)
        for _ in range(20):
            engine.update_sample(pv_frac=0.5, co_frac=0.5)
        d = engine.compute_adjustment(ti_current=60.0, limit_min=1.0, limit_max=10000.0)
        assert abs(d.delta_ti) < 0.1, f"Δ_Ti={d.delta_ti} should be near zero"

    def test_R3_critical_racing_to_limit_reduces_drastically(self):
        """Critical level + racing toward limit → Δ_Ti strongly negative (RD).

        Uses a faster sample rate (10s) so the computed rate hits the HIGH MF.
        """
        from smart_pid_core.domain.services.fuzzy_engine_v2 import (
            FuzzyEngineV2SurgeLevel,
        )
        engine = FuzzyEngineV2SurgeLevel(dt_sec=10.0)  # 10 s per sample
        # 20 samples = 200 s = 3.33 min. Margin grows 0.42→0.49 (7%).
        # Rate = 7% / 3.33 min ≈ 2.1%/min → HIGH.
        for k in range(20):
            pv = 0.92 + 0.07 * (k / 19)
            engine.update_sample(pv_frac=pv, co_frac=0.5)
        d = engine.compute_adjustment(ti_current=60.0, limit_min=1.0, limit_max=10000.0)
        assert d.delta_ti < -0.3, (
            f"Δ_Ti={d.delta_ti} should be strongly negative (emergency RD)"
        )
        assert d.new_ti < 60.0

    def test_R4_critical_but_escaping_relaxes_gently(self):
        """Critical level but recovering on its own → Δ_Ti positive (A)."""
        from smart_pid_core.domain.services.fuzzy_engine_v2 import (
            FuzzyEngineV2SurgeLevel,
        )
        engine = FuzzyEngineV2SurgeLevel(dt_sec=60.0)
        # Level was near limit but coming back to centre: 0.95 → 0.80
        for k in range(20):
            pv = 0.95 - 0.15 * (k / 19)
            engine.update_sample(pv_frac=pv, co_frac=0.5)
        d = engine.compute_adjustment(ti_current=60.0, limit_min=1.0, limit_max=10000.0)
        assert d.delta_ti > 0.0, (
            f"Δ_Ti={d.delta_ti} should be positive (start relaxing)"
        )


# ===========================================================================
# Dispatcher — picks engine by ControlObjective
# ===========================================================================


class TestDispatcher:
    def test_sp_tracking_selects_sp_engine(self):
        from smart_pid_core.domain.services.fuzzy_engine_v2 import (
            FuzzyEngineV2,
            FuzzyEngineV2Dispatcher,
        )
        from smart_pid_domain.enums import ControlObjective
        d = FuzzyEngineV2Dispatcher(ControlObjective.SP_TRACKING)
        assert isinstance(d.engine, FuzzyEngineV2)

    def test_dr_selects_dr_engine(self):
        from smart_pid_core.domain.services.fuzzy_engine_v2 import (
            FuzzyEngineV2Dispatcher,
            FuzzyEngineV2DisturbanceRejection,
        )
        from smart_pid_domain.enums import ControlObjective
        d = FuzzyEngineV2Dispatcher(ControlObjective.DISTURBANCE_REJECTION)
        assert isinstance(d.engine, FuzzyEngineV2DisturbanceRejection)

    def test_surge_selects_surge_engine(self):
        from smart_pid_core.domain.services.fuzzy_engine_v2 import (
            FuzzyEngineV2Dispatcher,
            FuzzyEngineV2SurgeLevel,
        )
        from smart_pid_domain.enums import ControlObjective
        d = FuzzyEngineV2Dispatcher(ControlObjective.SURGE_LEVEL)
        assert isinstance(d.engine, FuzzyEngineV2SurgeLevel)

    def test_dispatcher_routes_sp_tracking_sample(self):
        """SP dispatcher should pass error+CO to the underlying engine."""
        from smart_pid_core.domain.services.fuzzy_engine_v2 import (
            FuzzyEngineV2Dispatcher,
        )
        from smart_pid_domain.enums import ControlObjective
        d = FuzzyEngineV2Dispatcher(ControlObjective.SP_TRACKING)
        for _ in range(20):
            d.update_sample(error_frac=0.15, pv_frac=0.6, co_frac=0.5)
        decision = d.compute_adjustment(ti_current=20.0, limit_min=0.1, limit_max=100.0)
        assert decision.delta_ti < 0  # steady offset → reduce Ti
        assert "IAE" in decision.inputs

    def test_dispatcher_routes_surge_level_sample(self):
        """Surge dispatcher should use PV (not error) from the sample tuple."""
        from smart_pid_core.domain.services.fuzzy_engine_v2 import (
            FuzzyEngineV2Dispatcher,
        )
        from smart_pid_domain.enums import ControlObjective
        d = FuzzyEngineV2Dispatcher(
            ControlObjective.SURGE_LEVEL, dt_sec=10.0,
        )
        # Tank racing toward upper limit
        for k in range(20):
            pv = 0.92 + 0.07 * (k / 19)
            d.update_sample(error_frac=0.0, pv_frac=pv, co_frac=0.5)
        decision = d.compute_adjustment(ti_current=60.0, limit_min=1.0, limit_max=10000.0)
        assert decision.delta_ti < -0.3  # emergency RD
        assert "L_MARGIN" in decision.inputs

    def test_dispatcher_rejects_unknown_objective(self):
        from smart_pid_core.domain.services.fuzzy_engine_v2 import (
            FuzzyEngineV2Dispatcher,
        )
        class _Fake:
            value = "XXX"
        with pytest.raises(ValueError):
            FuzzyEngineV2Dispatcher(_Fake())  # type: ignore[arg-type]
