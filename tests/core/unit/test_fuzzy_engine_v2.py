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

    def test_compute_adjustment_fires_per_ai_cycle_under_oscillation(self):
        """Regression: in production the AI worker calls compute_adjustment
        at its own cadence (AI period = 3·TSS), NOT on every sample. Before
        the eager-check fix, the engine only emitted a limit-cycle decision
        once per ≥3τ of ACTIVE samples — so most AI cycles returned "holding"
        (Δ_Ti=0) and Ti barely moved. Every AI cycle that sees sustained
        oscillation must now yield a damping decision.
        """
        import math as _math

        engine = self._make()
        # 20 AI cycles, each with 15 oscillation samples between calls.
        # 15 samples is well below the 3τ threshold (30 samples at default
        # τ=10s, dt=1s), so the time-based trigger would never fire and the
        # original implementation returned Δ_Ti=0 for every single cycle.
        non_zero = 0
        for _ in range(20):
            for k in range(15):
                engine.update_sample(error_frac=0.2 * _math.sin(2 * _math.pi * k / 10))
            d = engine.compute_adjustment(
                ti_current=1.0, limit_min=0.1, limit_max=100.0,
            )
            if d.delta_ti > 0.0:
                non_zero += 1
        # Must get a damping decision on essentially every AI cycle after the
        # first few (when zero-crossings start accumulating).
        assert non_zero >= 15, (
            f"Only {non_zero}/20 AI cycles emitted a damping decision; "
            f"expected ≥ 15"
        )

    def test_slow_recovery_above_ten_tau_still_fires(self):
        """Regression from real log: E_max=1.50 T_rec=13.20τ OSC=0.42 Δ_Ti=0.

        MF_T_REC_DR.SLOW was trap(5, 7, 10, 10), which returns 0 for any
        x > 10. When a disturbance recovery takes longer than 10τ, ALL
        three t_rec memberships (FAST, MED, SLOW) read 0, every rule that
        mentions t_rec fails, and the engine emits Δ_Ti=0 — doing nothing
        while the loop clearly needs Ti reduced. SLOW must saturate: any
        recovery beyond the plateau is still definitively SLOW.
        """
        from smart_pid_core.domain.services.fuzzy_engine_v2 import (
            MF_E_MAX_DR, MF_T_REC_DR, MF_OSC_DR, RULES_DR, OUTPUT_CENTERS_DR,
            _fuzzify, _run_rules,
        )
        mfs = {
            "e_max": _fuzzify(1.50, MF_E_MAX_DR),
            "t_rec": _fuzzify(13.20, MF_T_REC_DR),
            "osc":   _fuzzify(0.42, MF_OSC_DR),
        }
        # SLOW must saturate — not drop back to zero past its plateau.
        assert mfs["t_rec"]["SLOW"] == 1.0, (
            f"MF_T_REC_DR.SLOW(13.20) must saturate to 1.0, got {mfs['t_rec']}"
        )
        delta, _ = _run_rules(mfs, RULES_DR, OUTPUT_CENTERS_DR)
        assert delta != 0.0, (
            f"Rule base must produce a non-zero decision; got Δ_Ti={delta}"
        )

    def test_event_path_with_residual_oscillation_damps_not_reduces(self):
        """If a finalised event carries residual oscillation (OSC≥MED),
        the situation is ambiguous between "real slow recovery" and
        "limit-cycle half-cycle classified as an event". A real slow
        recovery would call for reducing Ti (more action), but that
        makes a limit cycle worse. The engine must default to damping
        (Δ_Ti > 0) whenever residual oscillation is non-trivial.
        """
        engine = self._make()
        # Drive an event that finalises via SETTLING with OSC≈MED
        # (the exact indicator pattern from the reported log entry).
        for _ in range(50):
            engine.update_sample(error_frac=0.10)  # long excursion one-sided
        for _ in range(3):
            engine.update_sample(error_frac=0.005)  # dwell → SETTLING
        # 15 post-event samples carrying oscillation residue
        import math as _math
        for k in range(15):
            engine.update_sample(error_frac=0.12 * _math.sin(k))
        assert engine.decision_ready
        d = engine.compute_adjustment(
            ti_current=1.0, limit_min=0.1, limit_max=100.0,
        )
        assert d.delta_ti > 0.0, (
            f"Event with residual oscillation must damp (Ti up), not "
            f"reduce; got Δ_Ti={d.delta_ti}, reasoning={d.reasoning}"
        )

    def test_reducing_direction_is_weaker_than_increasing(self):
        """Reducing Ti is high-risk; increasing is low-risk. The rule base
        is asymmetric: the magnitude of any reducing prescription must not
        exceed half the magnitude of the AM (limit-cycle) increase, so
        the engine can't unwind a hard-won stable point.

        Note: pure STABLE events no longer reduce — a reduction requires
        at least MED oscillation signal (rule R1' HIGH/SLOW/MED → R).
        """
        from smart_pid_core.domain.services.fuzzy_engine_v2 import (
            MF_E_MAX_DR, MF_T_REC_DR, MF_OSC_DR, RULES_DR, OUTPUT_CENTERS_DR,
            _fuzzify, _run_rules,
        )

        # Strongest reducing case today: R1' (HIGH / SLOW / MED → R)
        mfs = {
            "e_max": _fuzzify(1.50, MF_E_MAX_DR),
            "t_rec": _fuzzify(13.10, MF_T_REC_DR),
            "osc":   _fuzzify(0.40, MF_OSC_DR),  # MED peak
        }
        reduce_delta, _ = _run_rules(mfs, RULES_DR, OUTPUT_CENTERS_DR)

        # Extreme increasing case: limit-cycle inputs (LOW / FAST / HIGH → AM)
        mfs_up = {
            "e_max": _fuzzify(0.0, MF_E_MAX_DR),
            "t_rec": _fuzzify(0.0, MF_T_REC_DR),
            "osc":   _fuzzify(1.0, MF_OSC_DR),
        }
        increase_delta, _ = _run_rules(mfs_up, RULES_DR, OUTPUT_CENTERS_DR)

        assert reduce_delta < 0.0, f"R1' must prescribe reduction; got {reduce_delta}"
        assert increase_delta > 0.0, f"AM must prescribe increase; got {increase_delta}"
        assert abs(reduce_delta) <= 0.5 * increase_delta, (
            f"Reducing |Δ_Ti|={abs(reduce_delta):.3f} must be ≤ 50% of "
            f"increasing Δ_Ti={increase_delta:.3f}"
        )

    def test_three_slow_events_do_not_collapse_ti(self):
        """Exact user scenario: Ti converged to stable value, then 3
        consecutive slow-recovery events (HIGH/SLOW/STABLE). Ti must not
        drop by more than 50% of the starting value before the next
        limit-cycle correction can engage.
        """
        engine = self._make()
        ti = 4.58
        for _ in range(3):
            # Drive a "HIGH / SLOW / STABLE" event
            for _s in range(150):
                engine.update_sample(error_frac=0.10)  # big one-sided error
            for _s in range(3):
                engine.update_sample(error_frac=0.005)
            for _s in range(15):
                engine.update_sample(error_frac=0.003)  # low residual
            assert engine.decision_ready
            d = engine.compute_adjustment(
                ti_current=ti, limit_min=0.1, limit_max=100.0,
            )
            ti = d.new_ti
        assert ti >= 0.5 * 4.58, (
            f"3 slow-recovery events collapsed Ti {4.58} → {ti:.2f}; "
            f"must stay ≥ 50% of starting value"
        )

    def test_post_limit_cycle_cooldown_suppresses_reductions(self):
        """After a limit-cycle firing, the loop is on the edge of stability.
        Reducing Ti right after damping (even by a small amount) can tip it
        back into oscillation. Event-path reductions must be suppressed for
        a cooldown window after every limit-cycle firing.

        Reproduces the user's scenario: Ti 2.64 → 3.37 (LC) → 4.30 (LC) →
        4.30 (hold) → 3.87 (event reduction) → loop starts oscillating again.
        """
        engine = self._make()
        ti = 2.64
        # Two consecutive limit-cycle firings (engine stuck in oscillation)
        import math as _math
        for _cycle in range(2):
            for k in range(50):
                engine.update_sample(error_frac=0.2 * _math.sin(2 * _math.pi * k / 20))
            d = engine.compute_adjustment(ti_current=ti, limit_min=0.1, limit_max=100.0)
            assert "limit-cycle" in d.reasoning, f"Expected LC firing, got {d.reasoning}"
            ti = d.new_ti
        # Loop has stabilised. A slow-recovery event arrives immediately
        # after (as in the user's log, 2 min after second LC firing).
        for _s in range(150):
            engine.update_sample(error_frac=0.10)  # big one-sided error
        for _s in range(3):
            engine.update_sample(error_frac=0.005)
        for _s in range(15):
            engine.update_sample(error_frac=0.003)  # low residual
        assert engine.decision_ready
        d = engine.compute_adjustment(ti_current=ti, limit_min=0.1, limit_max=100.0)
        # Must NOT reduce Ti while still in cooldown from the recent LC firings.
        assert d.delta_ti >= 0.0, (
            f"Event reduction right after limit-cycle firings must be "
            f"suppressed; got Δ_Ti={d.delta_ti}, reasoning={d.reasoning}"
        )

    def test_stats_based_osc_forces_damping_when_loop_oscillates(self):
        """Regression: StatsWorker shows pkpk=46% span, zc=10, reversals=9
        (loop is CLEARLY oscillating). Event-path post-event σ gives OSC≈0.18
        because 15 samples undersample the cycle. With a stats-driven OSC
        (same algorithm as SP_TRACKING: pkpk/span gated by zc+reversals),
        the rule base must see OSC=HIGH and fire damping (Δ_Ti > 0).

        The user's log at 15:17:38 — E_max=1.50 T_rec=17.00τ OSC=0.16
        Δ_Ti=−0.10 — reduced Ti while the chart showed heavy oscillation.
        Must instead damp.
        """
        engine = self._make()
        # Stats snapshot matching the user's status bar
        stats = {
            "recent_pk_pk_error": 46.0,  # % span
            "pk_pk_error": 46.0,
            "zero_crossings": 10,
            "reversals": 9,
            "mean_abs_error": 10.0,
            "tv_per_sample": 1.0,
            "sample_count": 200,
        }
        span = 100.0
        d = engine.compute_adjustment_from_stats(
            stats=stats, span=span,
            ti_current=4.44, limit_min=0.1, limit_max=100.0,
        )
        assert d.delta_ti > 0.0, (
            f"Stats-confirmed oscillation must damp (Ti up); got "
            f"Δ_Ti={d.delta_ti}, reasoning={d.reasoning}"
        )

    def test_stats_based_osc_rejects_isolated_disturbance(self):
        """Regression: an isolated big disturbance dragged PV way below SP
        then recovered. The rolling 200-sample window still carries the
        excursion, so stats reported pkpk=40 % span / zc=2 / reversals=2 —
        the old gate passed it, the limit-cycle path fired, Ti ran up to
        the guardrail. A true limit cycle has many more zero crossings
        AND a large time-average |error|; an isolated spike has the
        crossings only at the recovery edges and a small mean_abs relative
        to pk_pk.
        """
        engine = self._make()
        # Isolated disturbance: huge pkpk (40 % span), minimal zc/reversals
        # (PV went down, came back — 2 crossings at most), small mean_abs
        # because the loop sat at SP most of the window.
        stats = {
            "recent_pk_pk_error": 40.0,
            "pk_pk_error": 40.0,
            "zero_crossings": 2,
            "reversals": 2,
            "mean_abs_error": 1.5,  # small — spike on quiet baseline
            "tv_per_sample": 0.5,
            "sample_count": 200,
        }
        d = engine.compute_adjustment_from_stats(
            stats=stats, span=100.0,
            ti_current=48.0, limit_min=0.1, limit_max=100.0,
        )
        # Must NOT fire the limit-cycle override for an isolated excursion.
        assert "limit-cycle" not in d.reasoning, (
            f"Isolated disturbance triggered limit-cycle override: "
            f"reasoning={d.reasoning}"
        )
        assert d.delta_ti <= 0.0, (
            f"Isolated disturbance must not increase Ti; got "
            f"Δ_Ti={d.delta_ti}"
        )

    def test_stats_based_osc_accepts_sustained_oscillation(self):
        """The opposite: real limit cycle with many zero crossings and a
        mean_abs/pk_pk ratio close to the sinusoid value (~0.32). Must
        still fire damping.
        """
        engine = self._make()
        # Sustained ±20% oscillation → pkpk=40, sinusoid mean_abs ≈ 12.7
        stats = {
            "recent_pk_pk_error": 40.0,
            "pk_pk_error": 40.0,
            "zero_crossings": 10,
            "reversals": 9,
            "mean_abs_error": 12.7,
            "tv_per_sample": 2.0,
            "sample_count": 200,
        }
        d = engine.compute_adjustment_from_stats(
            stats=stats, span=100.0,
            ti_current=4.0, limit_min=0.1, limit_max=100.0,
        )
        assert d.delta_ti > 0.0, (
            f"Sustained oscillation must damp; got Δ_Ti={d.delta_ti}"
        )

    def test_inter_event_overshoot_is_detected(self):
        """Regression from user log at Ti=8.9041: big disturbance event
        finalises normally (state → IDLE), then a short time later a
        second, opposite-sign event fires (the overshoot of the first).
        Neither event alone triggers the in-event overshoot detector
        (they both have 0 sign changes within their own ACTIVE phase).
        Engine must detect the pattern across events.
        """
        engine = self._make()
        # --- Event 1: big positive disturbance, clean recovery ---
        for _ in range(80):
            engine.update_sample(error_frac=0.20)
        # exit dwell
        for _ in range(3):
            engine.update_sample(error_frac=0.005)
        # post-event window: mostly quiet (no overshoot inside this window)
        for _ in range(15):
            engine.update_sample(error_frac=0.003)
        # SETTLING completed → state IDLE, decision_inputs from _finalise_event
        # Consume decision (would be Δ=0 via rule R1 → M) to clear the slot.
        assert engine.decision_ready
        d1 = engine.compute_adjustment(
            ti_current=8.90, limit_min=0.1, limit_max=100.0,
        )

        # --- 20 quiet samples elapse (overshoot starts building) ---
        for _ in range(20):
            engine.update_sample(error_frac=0.01)  # in-band, quiet

        # --- Event 2: overshoot surfaces as a new event of OPPOSITE sign ---
        for _ in range(30):
            engine.update_sample(error_frac=-0.05)  # PV above SP, error negative
        for _ in range(3):
            engine.update_sample(error_frac=-0.005)
        for _ in range(15):
            engine.update_sample(error_frac=-0.003)

        assert engine.decision_ready
        d2 = engine.compute_adjustment(
            ti_current=8.90, limit_min=0.1, limit_max=100.0,
        )
        assert d2.delta_ti > 0.0, (
            f"Second event of opposite sign IS the overshoot of the first — "
            f"must damp (Ti up); got Δ_Ti={d2.delta_ti}, "
            f"reasoning={d2.reasoning}"
        )

    def test_consecutive_same_sign_events_do_not_trigger_overshoot(self):
        """Two successive disturbances on the SAME side of SP (e.g. two
        load drops in a row) are not overshoot. Must go through the
        normal path.
        """
        engine = self._make()
        for _ in range(80):
            engine.update_sample(error_frac=0.20)
        for _ in range(3):
            engine.update_sample(error_frac=0.005)
        for _ in range(15):
            engine.update_sample(error_frac=0.003)
        engine.compute_adjustment(ti_current=8.90, limit_min=0.1, limit_max=100.0)

        for _ in range(20):
            engine.update_sample(error_frac=0.01)

        # Another positive-side disturbance
        for _ in range(30):
            engine.update_sample(error_frac=0.20)
        for _ in range(3):
            engine.update_sample(error_frac=0.005)
        for _ in range(15):
            engine.update_sample(error_frac=0.003)

        d = engine.compute_adjustment(ti_current=8.90, limit_min=0.1, limit_max=100.0)
        # Same-sign events: must not trigger overshoot damping.
        assert "overshoot" not in d.reasoning, (
            f"Same-sign consecutive events wrongly flagged as overshoot: "
            f"reasoning={d.reasoning}"
        )

    def test_overshoot_in_settling_window_damps(self):
        """Regression from the user chart: the disturbance drives error
        negative, recovery stays on the negative side until it reaches
        the deadband, SETTLING starts, and THEN the overshoot surfaces
        (error crosses SP) during the post-event window. The old
        `_active_zero_crossings` check (ACTIVE only) misses it, and the
        15-sample σ metric reads only ~0.12 which is below the MED
        threshold. Engine must still damp.
        """
        engine = self._make()
        # Disturbance: error stays on the negative side
        for _ in range(15):
            engine.update_sample(error_frac=-0.15)
        for e in [-0.10, -0.07, -0.04, -0.02, -0.01]:
            engine.update_sample(error_frac=e)
        # 3 in-band dwell samples — still on negative side
        for _ in range(3):
            engine.update_sample(error_frac=-0.005)
        # SETTLING: overshoot surfaces HERE, crossing SP to positive side
        for e in [0.01, 0.03, 0.06, 0.08, 0.07, 0.05, 0.03, 0.01, 0.0,
                  -0.01, -0.005, 0.0, 0.0, 0.0, 0.0]:
            engine.update_sample(error_frac=e)
        assert engine.decision_ready
        d = engine.compute_adjustment(
            ti_current=8.9, limit_min=0.1, limit_max=100.0,
        )
        assert d.delta_ti > 0.0, (
            f"Overshoot surfacing in SETTLING window must damp Ti; got "
            f"Δ_Ti={d.delta_ti}, reasoning={d.reasoning}"
        )

    def test_event_with_overshoot_damps_not_holds(self):
        """Regression: the user's chart shows PV dropping to 30 then
        recovering past SP to 55 (overshoot), then settling to 50. Classic
        "Ti too small". The post-event σ is tiny (PV is calm by the time
        SETTLING collects samples), so the event path reads OSC≈0.04 and
        rule R1 (now M) holds. But the overshoot DID happen — the error
        changed sign once during ACTIVE. A single sign change on recovery
        must redirect the finalisation to the limit-cycle path so Ti
        goes up.
        """
        engine = self._make()
        # Smooth one-crossing overshoot trajectory:
        # +20 % sustained → gradual descent through zero → overshoot to
        # −5 % → gradual recovery → in-band. Exactly 1 sign change.
        for _ in range(60):
            engine.update_sample(error_frac=0.20)
        for e in [0.15, 0.10, 0.05, -0.02, -0.05, -0.05, -0.05, -0.05,
                  -0.05, -0.05, -0.05, -0.05, -0.05, -0.04, -0.03]:
            engine.update_sample(error_frac=e)
        for _ in range(3):
            engine.update_sample(error_frac=-0.005)
        for _ in range(15):
            engine.update_sample(error_frac=-0.002)
        assert engine.decision_ready
        d = engine.compute_adjustment(
            ti_current=11.35, limit_min=0.1, limit_max=100.0,
        )
        assert d.delta_ti > 0.0, (
            f"Overshoot on recovery must damp (Ti up), got Δ_Ti={d.delta_ti}; "
            f"reasoning={d.reasoning}"
        )

    def test_event_without_overshoot_still_holds(self):
        """Negative: a clean recovery (no sign change during ACTIVE)
        must continue to hold Ti — the overshoot detector must not
        fire on every slow recovery, only on those that cross SP
        during the return.
        """
        engine = self._make()
        # Clean recovery: error +20 → +10 → +5 → +1 (in-band).
        for _ in range(30):
            engine.update_sample(error_frac=0.20)
        for _ in range(10):
            engine.update_sample(error_frac=0.10)
        for _ in range(5):
            engine.update_sample(error_frac=0.05)
        for _ in range(3):
            engine.update_sample(error_frac=0.005)
        for _ in range(15):
            engine.update_sample(error_frac=0.002)
        assert engine.decision_ready
        d = engine.compute_adjustment(
            ti_current=11.35, limit_min=0.1, limit_max=100.0,
        )
        assert d.delta_ti == 0.0, (
            f"Clean slow recovery must hold; got Δ_Ti={d.delta_ti}; "
            f"reasoning={d.reasoning}"
        )

    def test_stable_slow_recovery_does_not_reduce_ti(self):
        """Regression: after limit-cycle firings pushed Ti up to a safe
        value, every subsequent slow disturbance kept nibbling Ti back
        down via rule R1 (HIGH/SLOW/STABLE → RM). The user's log showed
        Ti 11.7 → 10.5 → 9.5 → 8.5 through three consecutive disturbances
        with OSC=0.04 (fully stable). With no oscillation signal, the
        engine must hold Ti — not grind it toward the edge of stability.
        """
        from smart_pid_core.domain.services.fuzzy_engine_v2 import (
            FuzzyEngineV2DisturbanceRejection,
        )
        engine = FuzzyEngineV2DisturbanceRejection()
        # Exact indicators from the user's 2026-04-14 19:59:04 entry.
        delta, _mfs = engine.infer(e_max=1.50, t_rec=16.80, osc=0.04)
        assert delta >= 0.0, (
            f"HIGH peak + SLOW recovery + STABLE residual must not reduce "
            f"Ti (no oscillation signal); got Δ_Ti={delta}"
        )

    def test_stats_based_osc_holds_when_loop_is_quiet(self):
        """Conversely, if stats show no oscillation (small pkpk, low zc),
        DR should fall back to normal behaviour (event-path or hold)."""
        engine = self._make()
        stats = {
            "recent_pk_pk_error": 2.0,  # 2% span — quiet
            "pk_pk_error": 2.0,
            "zero_crossings": 0,
            "reversals": 0,
            "mean_abs_error": 0.5,
            "tv_per_sample": 0.1,
            "sample_count": 200,
        }
        # No pending event either → must hold.
        d = engine.compute_adjustment_from_stats(
            stats=stats, span=100.0,
            ti_current=4.44, limit_min=0.1, limit_max=100.0,
        )
        assert d.delta_ti == 0.0, (
            f"Quiet loop must hold Ti; got Δ_Ti={d.delta_ti}"
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
        # New semantics: a slow disturbance with STABLE residual no longer
        # reduces Ti (that just grinds a conservative loop toward the edge
        # of stability). Only MED+ oscillation residue triggers a cut.
        # Outcome must be neutral (hold) or up.
        assert d.delta_ti >= 0.0, (
            f"Stable residual must not reduce Ti; got Δ_Ti={d.delta_ti}"
        )

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

    def test_R1_via_infer_holds_with_high_peak_slow_stable(self):
        """Direct infer: HIGH peak + SLOW recovery + STABLE osc → M (hold).

        A stable loop with a slow disturbance recovery is a conservative
        loop, not a broken one. No oscillation signal ⇒ hold Ti; don't
        grind it down toward the edge of stability.
        """
        from smart_pid_core.domain.services.fuzzy_engine_v2 import (
            FuzzyEngineV2DisturbanceRejection,
        )
        engine = FuzzyEngineV2DisturbanceRejection()
        delta, _mfs = engine.infer(e_max=1.0, t_rec=8.0, osc=0.05)
        assert delta == 0.0, f"Stable slow recovery must hold; got Δ_Ti={delta}"

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


def _sl_engine(**kwargs):
    from smart_pid_core.domain.services.fuzzy_engine_v2 import (
        FuzzyEngineV2SurgeLevel,
    )
    return FuzzyEngineV2SurgeLevel(**kwargs)


def _feed(engine, pvs, *, error_frac=0.0, cos=None):
    """Drive the engine with a PV trajectory (and optional CO trajectory)."""
    cos = [0.5] * len(pvs) if cos is None else cos
    for pv, co in zip(pvs, cos, strict=True):
        engine.update_sample(error_frac=error_frac, pv_frac=pv, co_frac=co)


def _ramp(start, end, n=20):
    return [start + (end - start) * (k / (n - 1)) for k in range(n)]


class TestSurgeLevelIndicators:
    def test_pos_at_band_centre_is_zero(self):
        engine = _sl_engine(dt_sec=60.0)
        _feed(engine, [0.5])
        assert engine._pos() == pytest.approx(0.0)

    def test_pos_on_band_edge_is_one(self):
        """Default band 20-80 → PV at 80 % sits exactly on the wall."""
        engine = _sl_engine(dt_sec=60.0)
        _feed(engine, [0.8])
        assert engine._pos() == pytest.approx(1.0)

    def test_pos_outside_band_exceeds_one(self):
        engine = _sl_engine(dt_sec=60.0)
        _feed(engine, [0.95])
        assert engine._pos() == pytest.approx(1.5)  # |95-50| / 30

    def test_custom_band_rescales_position(self):
        """A narrow band makes the same PV far more critical."""
        engine = _sl_engine(dt_sec=60.0, band_lo_pct=40.0, band_hi_pct=60.0)
        _feed(engine, [0.7])
        assert engine._pos() == pytest.approx(2.0)  # |70-50| / 10

    def test_tv_with_calm_valve_is_zero(self):
        engine = _sl_engine(dt_sec=60.0)
        _feed(engine, [0.5] * 20)
        assert engine._tv_mv() == 0.0

    def test_dpos_positive_when_heading_for_a_wall(self):
        engine = _sl_engine(dt_sec=10.0)
        _feed(engine, _ramp(0.6, 0.9))
        # pos 0.333 → 1.333 over 190 s (3.17 min) → ≈ +0.32 m/min
        assert engine._dpos() > 0.25, f"dPOS={engine._dpos()} must be positive"

    def test_dpos_negative_when_returning_to_centre(self):
        engine = _sl_engine(dt_sec=10.0)
        _feed(engine, _ramp(0.9, 0.6))
        assert engine._dpos() < -0.25, f"dPOS={engine._dpos()} must be negative"

    def test_err_norm_scales_by_configured_threshold(self):
        """1 % error against a 5 % "small" threshold → 0.2 (deep in SMALL)."""
        engine = _sl_engine(dt_sec=60.0, error_small_pct=5.0)
        _feed(engine, [0.5] * 20, error_frac=0.01)
        assert engine._err_norm() == pytest.approx(0.2)

    def test_err_norm_is_sign_invariant(self):
        engine = _sl_engine(dt_sec=60.0)
        _feed(engine, [0.5] * 20, error_frac=-0.10)
        assert engine._err_norm() == pytest.approx(2.0)

    def test_max_co_ramp_in_pct_per_minute(self):
        """0.25 % of CO per 1 s sample is a 15 %/min slew."""
        engine = _sl_engine(dt_sec=1.0)
        cos = [0.5 + 0.0025 * k for k in range(20)]
        _feed(engine, [0.5] * 20, cos=cos)
        assert engine._max_co_ramp_pct_min() == pytest.approx(15.0)

    def test_invalid_band_falls_back_to_defaults_with_warning(self, caplog):
        """T-C8 — a corrupt/legacy band (lo ≥ hi) must not divide by zero."""
        import logging
        with caplog.at_level(logging.WARNING):
            engine = _sl_engine(band_lo_pct=70.0, band_hi_pct=30.0)
        assert engine._band_lo_pct == 20.0
        assert engine._band_hi_pct == 80.0
        assert "surge_level_band_invalid" in caplog.text

    def test_unset_band_matches_explicit_20_80(self):
        """C-default — None bounds and an explicit 20/80 band are identical."""
        default = _sl_engine(dt_sec=60.0)
        explicit = _sl_engine(dt_sec=60.0, band_lo_pct=20.0, band_hi_pct=80.0)
        _feed(default, _ramp(0.55, 0.85))
        _feed(explicit, _ramp(0.55, 0.85))
        a = default.compute_adjustment(60.0, 1.0, 10000.0)
        b = explicit.compute_adjustment(60.0, 1.0, 10000.0)
        assert a.delta_ti == pytest.approx(b.delta_ti)


class TestSurgeLevelRules:
    def test_S1_outside_band_and_stalled_reduces_drastically(self):
        """T-C1 — band violation with no recovery → hardest correction."""
        engine = _sl_engine(dt_sec=60.0, band_lo_pct=40.0, band_hi_pct=60.0)
        _feed(engine, [0.70] * 20)  # pos = 2.0 → OUT, dPOS = 0 → STILL
        d = engine.compute_adjustment(60.0, 1.0, 10000.0)
        assert d.delta_ti <= -0.4, f"Δ_Ti={d.delta_ti} must be RD (inputs={d.inputs})"
        assert d.new_ti < 60.0

    def test_S2_outside_but_escaping_holds_instead_of_slamming(self):
        """S2 — already returning fast: hold, do not stack another RD."""
        engine = _sl_engine(dt_sec=1.0, band_lo_pct=40.0, band_hi_pct=60.0)
        _feed(engine, _ramp(0.75, 0.65))  # pos 2.5 → 1.5, both OUT
        d = engine.compute_adjustment(60.0, 1.0, 10000.0)
        assert d.delta_ti == pytest.approx(0.0), f"inputs={d.inputs}"

    def test_S2_reentering_band_does_not_trigger_rd(self):
        """T-C2 — 61 % → 57 % on a 40-60 band: coming home, so never RD."""
        engine = _sl_engine(dt_sec=1.0, band_lo_pct=40.0, band_hi_pct=60.0)
        _feed(engine, _ramp(0.61, 0.57))
        d = engine.compute_adjustment(60.0, 1.0, 10000.0)
        assert d.delta_ti > -0.1, f"Δ_Ti={d.delta_ti} must not be RD"

    def test_S3_near_wall_and_closing_boosts_integral(self):
        engine = _sl_engine(dt_sec=1.0, band_lo_pct=40.0, band_hi_pct=60.0)
        _feed(engine, _ramp(0.55, 0.585))  # pos 0.5 → 0.85 (NEAR), TOWARD
        d = engine.compute_adjustment(60.0, 1.0, 10000.0)
        assert -0.4 < d.delta_ti < -0.05, f"Δ_Ti={d.delta_ti} should be R"

    def test_S4_near_wall_but_still_holds(self):
        engine = _sl_engine(dt_sec=60.0, band_lo_pct=40.0, band_hi_pct=60.0)
        _feed(engine, [0.585] * 20)  # pos 0.85 → NEAR, dPOS 0 → STILL
        d = engine.compute_adjustment(60.0, 1.0, 10000.0)
        assert d.delta_ti == pytest.approx(0.0), f"inputs={d.inputs}"

    def test_S5_near_wall_but_escaping_starts_relaxing(self):
        engine = _sl_engine(dt_sec=1.0, band_lo_pct=40.0, band_hi_pct=60.0)
        _feed(engine, _ramp(0.60, 0.585))  # pos 1.0 → 0.85, escaping
        d = engine.compute_adjustment(60.0, 1.0, 10000.0)
        assert d.delta_ti > 0.05, f"Δ_Ti={d.delta_ti} should relax (A)"

    def test_S6_safe_level_with_chattering_valve_relaxes_hard(self):
        """T-C5 — the valve is the thing being protected."""
        engine = _sl_engine(dt_sec=60.0)
        cos = [0.5 + 0.05 * (-1) ** k for k in range(20)]
        _feed(engine, [0.5] * 20, cos=cos)
        d = engine.compute_adjustment(60.0, 1.0, 10000.0)
        assert d.delta_ti >= 0.5, f"Δ_Ti={d.delta_ti} should be AM"
        assert d.new_ti > 60.0

    def test_S7_safe_and_on_target_pushes_integral_to_minimum(self):
        """T-C3 — inside the band with a small error → maximum smoothness."""
        engine = _sl_engine(dt_sec=60.0)
        _feed(engine, [0.5] * 20, error_frac=0.01)  # 1 % < 5 % threshold
        d = engine.compute_adjustment(60.0, 1.0, 10000.0)
        assert d.delta_ti >= 0.6, f"Δ_Ti={d.delta_ti} should drive Ti up hard"

    def test_S8_safe_small_error_moving_valve_still_relaxes(self):
        engine = _sl_engine(dt_sec=60.0)
        cos = [0.5 + 0.00625 * (-1) ** k for k in range(20)]  # TV ≈ 0.25
        _feed(engine, [0.5] * 20, error_frac=0.01, cos=cos)
        d = engine.compute_adjustment(60.0, 1.0, 10000.0)
        assert d.delta_ti >= 0.6, f"Δ_Ti={d.delta_ti} should be AM"

    def test_S9_safe_with_standing_offset_tolerates_it(self):
        """T-C4 — averaging control does not chase offset."""
        engine = _sl_engine(dt_sec=60.0)
        _feed(engine, [0.5] * 20, error_frac=0.10)  # 10 % ≫ 5 % threshold
        d = engine.compute_adjustment(60.0, 1.0, 10000.0)
        assert abs(d.delta_ti) < 0.05, f"Δ_Ti={d.delta_ti} should hold"

    def test_S10_safe_offset_with_working_valve_relaxes_gently(self):
        engine = _sl_engine(dt_sec=60.0)
        cos = [0.5 + 0.00625 * (-1) ** k for k in range(20)]  # TV ≈ 0.25
        _feed(engine, [0.5] * 20, error_frac=0.10, cos=cos)
        d = engine.compute_adjustment(60.0, 1.0, 10000.0)
        assert d.delta_ti == pytest.approx(0.30), f"inputs={d.inputs}"


class TestSurgeLevelCoRampGate:
    def _closing_on_wall_with_ramp(self, **kwargs):
        """Geometry that makes the rule base ask for R (Δ_Ti = −0.25),
        while CO slews at 15 %/min."""
        engine = _sl_engine(
            dt_sec=1.0, band_lo_pct=40.0, band_hi_pct=60.0, **kwargs,
        )
        cos = [0.5 + 0.0025 * k for k in range(20)]  # 15 %/min
        _feed(engine, _ramp(0.55, 0.585), cos=cos)
        return engine

    def test_gate_overrides_a_tightening_rule(self):
        """T-C6 — safety validation beats inference: never tighten on a
        valve that is already slewing too fast."""
        engine = self._closing_on_wall_with_ramp(co_ramp_max_pct_min=10.0)
        d = engine.compute_adjustment(60.0, 1.0, 10000.0)
        assert d.delta_ti == pytest.approx(0.15)
        assert d.inputs["co_ramp_violation"] is True
        assert d.inputs["CO_RAMP"] == pytest.approx(15.0)
        assert "[CO-RAMP]" in d.reasoning

    def test_gate_disabled_by_zero_leaves_the_rule_alone(self):
        """T-C7 — 0 disables the gate entirely."""
        engine = self._closing_on_wall_with_ramp(co_ramp_max_pct_min=0.0)
        d = engine.compute_adjustment(60.0, 1.0, 10000.0)
        assert d.delta_ti < 0.0, f"Δ_Ti={d.delta_ti} — rule must stand"
        assert d.inputs["co_ramp_violation"] is False
        assert "[CO-RAMP]" not in d.reasoning

    def test_ramp_below_threshold_does_not_trip_the_gate(self):
        engine = self._closing_on_wall_with_ramp(co_ramp_max_pct_min=20.0)
        d = engine.compute_adjustment(60.0, 1.0, 10000.0)
        assert d.delta_ti < 0.0
        assert d.inputs["co_ramp_violation"] is False


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
        """Surge dispatcher should use PV (not error) for positioning."""
        from smart_pid_core.domain.services.fuzzy_engine_v2 import (
            FuzzyEngineV2Dispatcher,
        )
        from smart_pid_domain.enums import ControlObjective
        d = FuzzyEngineV2Dispatcher(
            ControlObjective.SURGE_LEVEL, dt_sec=10.0,
        )
        # Tank sitting well outside the default 20-80 band and not returning
        for k in range(20):
            pv = 0.92 + 0.07 * (k / 19)
            d.update_sample(error_frac=0.0, pv_frac=pv, co_frac=0.5)
        decision = d.compute_adjustment(ti_current=60.0, limit_min=1.0, limit_max=10000.0)
        assert decision.delta_ti < -0.3  # emergency RD
        assert "POS" in decision.inputs

    def test_dispatcher_feeds_error_to_surge_engine(self):
        """T-C9 — the 3-arg sample must reach the SL engine's ERR input."""
        from smart_pid_core.domain.services.fuzzy_engine_v2 import (
            FuzzyEngineV2Dispatcher,
        )
        from smart_pid_domain.enums import ControlObjective
        d = FuzzyEngineV2Dispatcher(ControlObjective.SURGE_LEVEL, dt_sec=60.0)
        for _ in range(20):
            d.update_sample(error_frac=0.10, pv_frac=0.5, co_frac=0.5)
        decision = d.compute_adjustment(ti_current=60.0, limit_min=1.0, limit_max=10000.0)
        assert decision.inputs["ERR"] == pytest.approx(2.0)  # 10 % / 5 %

    def test_dispatcher_forwards_surge_band_config(self):
        from smart_pid_core.domain.services.fuzzy_engine_v2 import (
            FuzzyEngineV2Dispatcher,
        )
        from smart_pid_domain.enums import ControlObjective
        d = FuzzyEngineV2Dispatcher(
            ControlObjective.SURGE_LEVEL,
            sl_band_lo_pct=40.0,
            sl_band_hi_pct=60.0,
            sl_error_small_pct=2.0,
            sl_co_ramp_max_pct_min=0.0,
        )
        assert d.engine._band_lo_pct == 40.0
        assert d.engine._band_hi_pct == 60.0
        assert d.engine._error_small_pct == 2.0
        assert d.engine._co_ramp_max_pct_min == 0.0

    def test_dispatcher_rejects_unknown_objective(self):
        from smart_pid_core.domain.services.fuzzy_engine_v2 import (
            FuzzyEngineV2Dispatcher,
        )
        class _Fake:
            value = "XXX"
        with pytest.raises(ValueError):
            FuzzyEngineV2Dispatcher(_Fake())  # type: ignore[arg-type]


class TestSPTrackingNeverInvertsOnAnOscillatingLoop:
    """Regression: the tuner reduced Ti on a loop that was in a limit cycle.

    Two faults combined. StatsWorker's SP-step settling mask could cover the
    whole window, zeroing every oscillation indicator; the engine then read
    OSC=0 as "steady" and the rule ``IAE=HIGH & OSC=STABLE & EFF=EXCESS``
    said RM (-0.35). Three cycles of that on an already-oscillating loop is
    exactly what was reported.
    """

    @staticmethod
    def _stats(**over):
        base = {
            "mean_abs_error": 16.0,   # IAE high
            "pk_pk_error": 0.0,
            "recent_pk_pk_error": 0.0,
            "reversals": 0,
            "zero_crossings": 0,
            "tv_per_sample": 18.0,    # valve thrashing -> EFF EXCESS
            "sample_count": 300,
            "osc_sample_count": 300,
            "sp_pk_pk": 0.0,
        }
        base.update(over)
        return base

    def _decide(self, stats, ti=1.0):
        from smart_pid_core.domain.services.fuzzy_engine_v2 import FuzzyEngineV2
        return FuzzyEngineV2().compute_adjustment_from_stats(
            stats=stats, span=100.0, ti_current=ti,
            limit_min=0.05, limit_max=600.0,
        )

    def test_thrashing_valve_with_a_standing_error_never_speeds_the_integrator(self):
        """High IAE + calm-looking PV + EXCESS valve effort is a loop at its
        limit, not a slow one. This is the exact rule that produced -0.35."""
        d = self._decide(self._stats())
        assert d.delta_ti >= 0.0, d.reasoning

    def test_a_masked_window_is_a_hold_not_a_verdict(self):
        """When the settling mask ate the window there is no evidence at all,
        and 'no evidence' must not read as 'steady with an offset'."""
        d = self._decide(self._stats(osc_sample_count=0))
        assert d.delta_ti == 0.0
        assert d.new_ti == 1.0
        assert "admissible" in d.reasoning

    def test_confirmed_limit_cycle_increases_ti(self):
        d = self._decide(self._stats(
            recent_pk_pk_error=60.0, reversals=40, zero_crossings=38,
        ))
        assert d.delta_ti > 0.0
        assert d.new_ti > 1.0

    def test_sustained_reduction_needs_a_calm_valve(self):
        """The reduce path still exists — it just needs the real signature:
        a standing offset the valve is NOT fighting."""
        d = self._decide(self._stats(tv_per_sample=0.2), ti=50.0)
        assert d.delta_ti < 0.0
        assert d.new_ti < 50.0

    def test_amplitude_is_judged_against_the_excitation(self):
        """A 20-unit error swing is a limit cycle when the setpoint never
        moved, and an ordinary step response when it jumped 40."""
        osc = {"recent_pk_pk_error": 20.0, "reversals": 30, "zero_crossings": 28,
               "mean_abs_error": 4.0, "tv_per_sample": 2.0}
        fixed_sp = self._decide(self._stats(**osc, sp_pk_pk=0.0))
        moving_sp = self._decide(self._stats(**osc, sp_pk_pk=40.0))
        assert fixed_sp.inputs["OSC"] > moving_sp.inputs["OSC"]
        assert fixed_sp.inputs["OSC"] == pytest.approx(1.0)

    def test_a_fixed_setpoint_keeps_the_original_amplitude_scale(self):
        """sp_pk_pk = 0 must reproduce the pre-change behaviour exactly:
        15 % of span saturates the amplitude term."""
        d = self._decide(self._stats(
            recent_pk_pk_error=15.0, reversals=10, zero_crossings=10,
            mean_abs_error=4.0, tv_per_sample=2.0, sp_pk_pk=0.0,
        ))
        assert d.inputs["OSC"] == pytest.approx(1.0)
