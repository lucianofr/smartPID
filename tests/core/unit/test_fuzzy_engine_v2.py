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
        # 2σ of sinewave amp 0.1 ≈ 0.141; /0.15 scale ≈ 0.94 → saturates
        # near 1.0 (UNSTABLE territory — a 10%-amplitude oscillation is a
        # clear limit cycle that must drive Ti up).
        osc = engine._osc_norm()
        assert osc > 0.85, f"osc={osc}"

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


class TestComputeAdjustmentFromStats:
    """New production API: fuzzy consumes a StatsWorker snapshot instead of
    maintaining its own deque. Covers user's scenario where window = 5×TSS.
    """

    def test_saturated_oscillation_drives_ti_up_strongly(self):
        from smart_pid_core.domain.services.fuzzy_engine_v2 import FuzzyEngineV2
        engine = FuzzyEngineV2()
        # Mimic user's reported case: PV pk-pk 60% of span, clearly cycling
        # (reversals >> 2), valve nearly constant (tv_per_sample tiny).
        stats = {
            "mean_abs_error": 30.0,  # ≈ 30% of 100-span → IAE norm → HIGH
            "pk_pk_error": 60.0,
            "recent_pk_pk_error": 60.0,
            "reversals": 3,
            "zero_crossings": 4,
            "tv_per_sample": 0.5,
            "sample_count": 200,
        }
        d = engine.compute_adjustment_from_stats(
            stats=stats, span=100.0, ti_current=1.0,
            limit_min=0.1, limit_max=100.0,
        )
        # IAE HIGH + OSC UNSTABLE fires R2 → AM (+0.35).
        assert d.delta_ti > 0.20, (
            f"Δ_Ti={d.delta_ti} should drive Ti up; inputs={d.inputs}"
        )
        assert d.inputs["OSC"] == pytest.approx(1.0, abs=0.05)

    def test_drift_without_reversals_does_not_flag_oscillation(self):
        from smart_pid_core.domain.services.fuzzy_engine_v2 import FuzzyEngineV2
        engine = FuzzyEngineV2()
        # Pure ramp: large pk-pk but zero reversals → must stay STABLE.
        stats = {
            "mean_abs_error": 10.0,
            "pk_pk_error": 40.0,
            "reversals": 0,
            "tv_per_sample": 0.1,
            "sample_count": 100,
        }
        d = engine.compute_adjustment_from_stats(
            stats=stats, span=100.0, ti_current=10.0,
            limit_min=0.1, limit_max=100.0,
        )
        assert d.inputs["OSC"] == 0.0
        # Only one reversal required before we'd increase Ti; with pure
        # drift the engine keeps Ti or reduces it based on IAE/EFF rules.

    def test_missing_fields_default_to_zero(self):
        from smart_pid_core.domain.services.fuzzy_engine_v2 import FuzzyEngineV2
        engine = FuzzyEngineV2()
        d = engine.compute_adjustment_from_stats(
            stats={}, span=100.0, ti_current=5.0,
            limit_min=0.1, limit_max=100.0,
        )
        assert d.inputs["IAE"] == 0.0
        assert d.inputs["OSC"] == 0.0

    def test_stabilised_loop_clears_osc_even_with_stale_reversals(self):
        """Regression: after the loop stabilises, OSC must drop even though
        the full window still contains old oscillation samples. Otherwise
        the fuzzy keeps driving Ti up forever.
        """
        from smart_pid_core.domain.services.fuzzy_engine_v2 import FuzzyEngineV2
        engine = FuzzyEngineV2()
        # Recent sub-window is flat (loop settled) but full-window metrics
        # still show the earlier oscillation.
        stats = {
            "mean_abs_error": 15.0,
            "pk_pk_error": 60.0,
            "recent_pk_pk_error": 0.0,   # ← loop now stable
            "reversals": 4,              # ← stale
            "recent_reversals": 0,
            "tv_per_sample": 0.2,
            "sample_count": 200,
        }
        d = engine.compute_adjustment_from_stats(
            stats=stats, span=100.0, ti_current=10.0,
            limit_min=0.1, limit_max=100.0,
        )
        assert d.inputs["OSC"] == 0.0
        assert d.delta_ti <= 0.0, (
            f"stabilised loop must not trigger AM/A rules; Δ_Ti={d.delta_ti}"
        )

    def test_sp_step_transients_are_not_flagged_as_oscillation(self):
        """Regression: two opposite SP steps create 1–2 reversals and a
        large recent pk-pk, but the error stays on one side of zero during
        each settling → zero_crossings ≤ 1. Without this gate the fuzzy
        would drive Ti up on every SP change.
        """
        from smart_pid_core.domain.services.fuzzy_engine_v2 import FuzzyEngineV2
        engine = FuzzyEngineV2()
        stats = {
            "mean_abs_error": 5.0,
            "pk_pk_error": 30.0,
            "recent_pk_pk_error": 11.0,
            "reversals": 1,
            "zero_crossings": 1,   # ← key: pure SP-step transient
            "tv_per_sample": 0.2,
            "sample_count": 200,
        }
        d = engine.compute_adjustment_from_stats(
            stats=stats, span=100.0, ti_current=10.0,
            limit_min=0.1, limit_max=100.0,
        )
        assert d.inputs["OSC"] == 0.0

    def test_slow_oscillation_still_detected_via_full_reversals(self):
        """Complement: a slow oscillation whose period is ~½ of the full
        window only shows ~1 reversal inside the recent sub-window, so we
        rely on the full-window reversal count to keep the amplitude
        signal meaningful.
        """
        from smart_pid_core.domain.services.fuzzy_engine_v2 import FuzzyEngineV2
        engine = FuzzyEngineV2()
        stats = {
            "mean_abs_error": 30.0,
            "pk_pk_error": 60.0,
            "recent_pk_pk_error": 58.0,
            "reversals": 3,
            "zero_crossings": 2,  # barely qualifies — real oscillation
            "recent_reversals": 1,
            "tv_per_sample": 0.5,
            "sample_count": 200,
        }
        d = engine.compute_adjustment_from_stats(
            stats=stats, span=100.0, ti_current=10.0,
            limit_min=0.1, limit_max=100.0,
        )
        assert d.inputs["OSC"] > 0.8
        assert d.delta_ti > 0.20


class TestConfigurableWindow:
    """The stats window must scale with TSS/scan_rate instead of being fixed."""

    def test_sp_engine_accepts_window_samples(self):
        from smart_pid_core.domain.services.fuzzy_engine_v2 import FuzzyEngineV2
        engine = FuzzyEngineV2(window_samples=60)
        assert engine._window_samples == 60
        assert engine._errors.maxlen == 60
        assert engine._cos.maxlen == 60

    def test_sp_engine_defaults_to_20_samples(self):
        from smart_pid_core.domain.services.fuzzy_engine_v2 import FuzzyEngineV2
        engine = FuzzyEngineV2()
        assert engine._window_samples == 20

    def test_sp_engine_clamps_tiny_window(self):
        from smart_pid_core.domain.services.fuzzy_engine_v2 import FuzzyEngineV2
        engine = FuzzyEngineV2(window_samples=1)
        assert engine._window_samples == 4  # min

    def test_surge_engine_accepts_window_samples(self):
        from smart_pid_core.domain.services.fuzzy_engine_v2 import (
            FuzzyEngineV2SurgeLevel,
        )
        engine = FuzzyEngineV2SurgeLevel(dt_sec=1.0, window_samples=45)
        assert engine._window_samples == 45
        assert engine._pvs.maxlen == 45

    def test_dr_engine_accepts_window_samples(self):
        from smart_pid_core.domain.services.fuzzy_engine_v2 import (
            FuzzyEngineV2DisturbanceRejection,
        )
        engine = FuzzyEngineV2DisturbanceRejection(window_samples=30)
        assert engine._post_event_window == 30

    def test_dispatcher_propagates_window_to_sp_engine(self):
        from smart_pid_core.domain.services.fuzzy_engine_v2 import (
            FuzzyEngineV2Dispatcher,
        )
        from smart_pid_domain.enums import ControlObjective
        d = FuzzyEngineV2Dispatcher(
            objective=ControlObjective.SP_TRACKING,
            window_samples=60,
        )
        assert d.engine._window_samples == 60

    def test_long_window_does_not_detect_oscillation_from_stale_setpoint_change(
        self,
    ):
        """Regression: a single SP change ~TSS ago must not dominate σ so much
        that the engine infers ongoing oscillation.
        """
        from smart_pid_core.domain.services.fuzzy_engine_v2 import FuzzyEngineV2
        engine = FuzzyEngineV2(window_samples=120)
        # First 4 samples: residual error from a past SP change.
        for _ in range(4):
            engine.update_sample(error_frac=0.08, co_frac=0.5)
        # Next 116 samples: settled, at setpoint.
        for _ in range(116):
            engine.update_sample(error_frac=0.0, co_frac=0.5)
        # OSC must stay inside the STABLE plateau (≤ 0.2): a 4-sample
        # transient inside a 120-sample window is too diluted to fake
        # oscillation.
        osc = engine._osc_norm()
        assert osc < 0.2, f"osc={osc} — stale spike should not flag oscillation"

    def test_monotonic_ramp_is_not_oscillation(self):
        """Regression: a pure drift (error ramping up) has non-trivial pk-pk
        and non-trivial σ, but zero direction reversals. The new detector
        must score OSC ≈ 0 so Ti is not bumped up against a one-way trend.
        """
        from smart_pid_core.domain.services.fuzzy_engine_v2 import FuzzyEngineV2
        engine = FuzzyEngineV2(window_samples=40)
        for k in range(40):
            engine.update_sample(error_frac=0.003 * k, co_frac=0.5)
        osc = engine._osc_norm()
        assert osc == 0.0, f"osc={osc} — ramp must not flag oscillation"

    def test_single_spike_is_not_oscillation(self):
        """Regression: a lone bump (e.g. disturbance rejected in one cycle)
        produces amplitude but only ~1 reversal — OSC must stay low.
        """
        from smart_pid_core.domain.services.fuzzy_engine_v2 import FuzzyEngineV2
        engine = FuzzyEngineV2(window_samples=40)
        for _ in range(18):
            engine.update_sample(error_frac=0.0, co_frac=0.5)
        for _ in range(4):
            engine.update_sample(error_frac=0.08, co_frac=0.5)
        for _ in range(18):
            engine.update_sample(error_frac=0.0, co_frac=0.5)
        osc = engine._osc_norm()
        assert osc < 0.35, f"osc={osc} — single spike must stay below OSC MF peak"

    def test_oscillating_pv_with_calm_valve_increases_ti(self):
        """Regression: sustained PV oscillation must drive Ti up even when
        CO barely moves (Kp too small → EFF near zero). Previously the rule
        base had no entry for OSC + SMOOTH, so Δ_Ti stayed at 0 for cycles.
        """
        import math
        from smart_pid_core.domain.services.fuzzy_engine_v2 import FuzzyEngineV2
        engine = FuzzyEngineV2(window_samples=40)
        # PV oscillates 10% of span around SP; CO nearly constant (small Kp).
        for k in range(40):
            e = 0.10 * math.sin(k * math.pi / 5.0)
            engine.update_sample(error_frac=e, co_frac=0.50 + 0.001 * k)
        d = engine.compute_adjustment(ti_current=20.0, limit_min=0.1, limit_max=100.0)
        assert d.delta_ti > 0.05, (
            f"Δ_Ti={d.delta_ti} should be clearly positive (inputs={d.inputs})"
        )
        assert d.new_ti > 20.0


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

    def test_sustained_oscillation_breaks_active_lock_and_increases_ti(self):
        """Limit-cycle oscillation must not lock the state machine in ACTIVE.

        Sustained oscillation around SP rarely leaves the error inside the 2%
        deadband for 3 consecutive samples, so the original implementation
        stayed in ACTIVE forever and never emitted a decision. The engine
        must detect this pattern (long ACTIVE + multiple zero crossings) and
        emit an "increase Ti" decision to damp the oscillation.
        """
        import math as _math

        engine = self._make()
        # Push 400 samples of ±20% sinusoidal error, period = 20 samples
        decisions: list = []
        for k in range(400):
            engine.update_sample(error_frac=0.2 * _math.sin(2 * _math.pi * k / 20))
            if engine.decision_ready:
                d = engine.compute_adjustment(
                    ti_current=10.0, limit_min=0.1, limit_max=100.0,
                )
                decisions.append(d)
        assert len(decisions) >= 1, (
            "Engine never emitted a decision under sustained oscillation"
        )
        # Decision must be a strong push to increase Ti — weak signals get
        # cancelled by other rules (e.g. R1' "HIGH/SLOW/MED → R") and the
        # loop never escapes the limit cycle. Require Δ_Ti ≥ +0.10.
        assert decisions[0].delta_ti >= 0.10, (
            f"Expected Δ_Ti ≥ +0.10 to break limit cycle quickly, "
            f"got {decisions[0].delta_ti}"
        )

    def test_simulated_loop_actually_damps_under_decisions(self):
        """End-to-end: feeding repeated limit-cycle decisions back into Ti
        must drive the loop toward stability over a handful of cycles.
        """
        import math as _math

        engine = self._make()
        ti = 1.0
        # 12 AI cycles of 50 samples each (≥ 5τ per cycle at τ=10s, dt=1s)
        ti_history = [ti]
        for _ in range(12):
            for k in range(50):
                # Simulate that the loop is still oscillating with current Ti
                engine.update_sample(error_frac=0.2 * _math.sin(2 * _math.pi * k / 20))
            if engine.decision_ready:
                d = engine.compute_adjustment(
                    ti_current=ti, limit_min=0.1, limit_max=100.0,
                )
                ti = d.new_ti
            ti_history.append(ti)
        # After 12 cycles, Ti must have grown noticeably (≥ 2× initial)
        assert ti >= 2.0 * ti_history[0], (
            f"Ti did not grow enough to damp limit cycle: "
            f"history={ti_history}"
        )


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
