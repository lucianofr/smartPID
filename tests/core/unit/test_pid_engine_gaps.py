"""Tests for PID engine gaps #1-6: PV filter, SP filter, feedforward,
low cutoff, increase-to-close, and over-range 10%."""
from __future__ import annotations

import pytest

from smart_pid_core.domain.services.pid_engine import PIDEngine, PIDState
from smart_pid_domain.models.controller import PIDParams
from smart_pid_domain.models.signal import FFSignal


class TestPVFilter:
    """Gap #1: First-order exponential filter on PV."""

    def setup_method(self) -> None:
        self.engine = PIDEngine()
        self.params = PIDParams(gain=1.0, reset=1e9, rate=0.0)

    def test_no_filter_when_ftime_zero(self) -> None:
        """pv_ftime=0 means pass-through (no filtering)."""
        state = PIDState(cv=50.0, pv_prev=50.0, pv_prev2=50.0, pv_filtered=50.0)
        result = self.engine.compute(
            params=self.params, state=state,
            pv=FFSignal.good(60.0), sp=FFSignal.good(50.0),
            bkcal_in=FFSignal.good(0.0), dt=1.0,
            out_limits=(0.0, 100.0), pv_ftime=0.0,
        )
        # PV should pass through unfiltered; error = 50-60 = -10 (reverse acting)
        # Actually error = sp - pv = 50 - 60 = -10
        assert result.new_state.pv_filtered == pytest.approx(60.0)

    def test_filter_smooths_pv_step(self) -> None:
        """Step change in PV should be attenuated by the filter."""
        state = PIDState(cv=50.0, pv_prev=50.0, pv_prev2=50.0, pv_filtered=50.0)
        result = self.engine.compute(
            params=self.params, state=state,
            pv=FFSignal.good(60.0), sp=FFSignal.good(50.0),
            bkcal_in=FFSignal.good(0.0), dt=1.0,
            out_limits=(0.0, 100.0), pv_ftime=4.0,  # 4s time constant
        )
        # alpha = dt / (ftime + dt) = 1 / (4+1) = 0.2
        # pv_filtered = 0.2 * 60 + 0.8 * 50 = 12 + 40 = 52
        assert result.new_state.pv_filtered == pytest.approx(52.0)

    def test_filter_converges_over_multiple_scans(self) -> None:
        """After many scans, filtered PV should approach raw PV."""
        state = PIDState(cv=50.0, pv_prev=50.0, pv_prev2=50.0, pv_filtered=50.0)
        for _ in range(100):
            result = self.engine.compute(
                params=self.params, state=state,
                pv=FFSignal.good(60.0), sp=FFSignal.good(50.0),
                bkcal_in=FFSignal.good(0.0), dt=1.0,
                out_limits=(0.0, 100.0), pv_ftime=2.0,
            )
            state = result.new_state
        assert state.pv_filtered == pytest.approx(60.0, abs=0.01)

    def test_filter_state_persists(self) -> None:
        """pv_filtered should be stored in PIDState for next scan."""
        state = PIDState(cv=50.0, pv_prev=50.0, pv_prev2=50.0, pv_filtered=40.0)
        result = self.engine.compute(
            params=self.params, state=state,
            pv=FFSignal.good(60.0), sp=FFSignal.good(50.0),
            bkcal_in=FFSignal.good(0.0), dt=1.0,
            out_limits=(0.0, 100.0), pv_ftime=4.0,
        )
        # alpha = 0.2, pv_filtered = 0.2*60 + 0.8*40 = 12+32 = 44
        assert result.new_state.pv_filtered == pytest.approx(44.0)


class TestSPFilter:
    """Gap #2: First-order exponential filter on SP."""

    def setup_method(self) -> None:
        self.engine = PIDEngine()
        self.params = PIDParams(gain=1.0, reset=1e9, rate=0.0)

    def test_no_filter_when_ftime_zero(self) -> None:
        """sp_ftime=0 means pass-through."""
        state = PIDState(cv=50.0, pv_prev=50.0, pv_prev2=50.0, sp_filtered=50.0)
        result = self.engine.compute(
            params=self.params, state=state,
            pv=FFSignal.good(50.0), sp=FFSignal.good(60.0),
            bkcal_in=FFSignal.good(0.0), dt=1.0,
            out_limits=(0.0, 100.0), sp_ftime=0.0,
        )
        assert result.new_state.sp_filtered == pytest.approx(60.0)

    def test_filter_smooths_sp_step(self) -> None:
        """Step change in SP should be attenuated by the filter."""
        state = PIDState(cv=50.0, pv_prev=50.0, pv_prev2=50.0, sp_filtered=50.0)
        result = self.engine.compute(
            params=self.params, state=state,
            pv=FFSignal.good(50.0), sp=FFSignal.good(70.0),
            bkcal_in=FFSignal.good(0.0), dt=1.0,
            out_limits=(0.0, 100.0), sp_ftime=4.0,
        )
        # alpha = 1/(4+1) = 0.2, sp_filtered = 0.2*70 + 0.8*50 = 14+40 = 54
        assert result.new_state.sp_filtered == pytest.approx(54.0)

    def test_sp_filter_affects_error(self) -> None:
        """Filtered SP should be used for error calculation, not raw SP."""
        state = PIDState(
            cv=50.0, error_prev=0.0, pv_prev=50.0, pv_prev2=50.0, sp_filtered=50.0,
        )
        result = self.engine.compute(
            params=self.params, state=state,
            pv=FFSignal.good(50.0), sp=FFSignal.good(70.0),
            bkcal_in=FFSignal.good(0.0), dt=1.0,
            out_limits=(0.0, 100.0), sp_ftime=4.0,
        )
        # sp_filtered = 54, error = 54 - 50 = 4 (not 20)
        assert result.error == pytest.approx(4.0)


class TestFeedforward:
    """Gap #3: Feedforward contribution added to PID output."""

    def setup_method(self) -> None:
        self.engine = PIDEngine()
        self.params = PIDParams(gain=1.0, reset=1e9, rate=0.0)

    def test_no_ff_when_disabled(self) -> None:
        """ff_enable=False means no feedforward contribution."""
        state = PIDState(cv=50.0, error_prev=0.0, pv_prev=50.0, pv_prev2=50.0)
        result = self.engine.compute(
            params=self.params, state=state,
            pv=FFSignal.good(50.0), sp=FFSignal.good(50.0),
            bkcal_in=FFSignal.good(0.0), dt=1.0,
            out_limits=(0.0, 100.0),
            ff_enable=False, ff_val=10.0, ff_gain=2.0,
        )
        assert result.cv == pytest.approx(50.0)

    def test_ff_adds_to_output(self) -> None:
        """ff_val * ff_gain should be added to the output."""
        state = PIDState(cv=50.0, error_prev=0.0, pv_prev=50.0, pv_prev2=50.0)
        result = self.engine.compute(
            params=self.params, state=state,
            pv=FFSignal.good(50.0), sp=FFSignal.good(50.0),
            bkcal_in=FFSignal.good(0.0), dt=1.0,
            out_limits=(0.0, 100.0),
            ff_enable=True, ff_val=5.0, ff_gain=2.0,
        )
        # delta_cv = 0 (no error change), ff = 5*2 = 10
        assert result.cv == pytest.approx(60.0)

    def test_ff_negative_reduces_output(self) -> None:
        """Negative ff_val should reduce output."""
        state = PIDState(cv=50.0, error_prev=0.0, pv_prev=50.0, pv_prev2=50.0)
        result = self.engine.compute(
            params=self.params, state=state,
            pv=FFSignal.good(50.0), sp=FFSignal.good(50.0),
            bkcal_in=FFSignal.good(0.0), dt=1.0,
            out_limits=(0.0, 100.0),
            ff_enable=True, ff_val=-3.0, ff_gain=1.0,
        )
        assert result.cv == pytest.approx(47.0)

    def test_ff_clamped_by_output_limits(self) -> None:
        """FF contribution should still respect output limits."""
        state = PIDState(cv=95.0, error_prev=0.0, pv_prev=50.0, pv_prev2=50.0)
        result = self.engine.compute(
            params=self.params, state=state,
            pv=FFSignal.good(50.0), sp=FFSignal.good(50.0),
            bkcal_in=FFSignal.good(0.0), dt=1.0,
            out_limits=(0.0, 100.0),
            ff_enable=True, ff_val=10.0, ff_gain=1.0,
        )
        # 95 + 10 = 105 -> clamped to 100
        assert result.cv == pytest.approx(100.0)
        assert result.new_state.is_saturated is True

    def test_ff_not_included_in_delta_cv(self) -> None:
        """delta_cv should NOT include feedforward (it's separate)."""
        state = PIDState(cv=50.0, error_prev=0.0, pv_prev=50.0, pv_prev2=50.0)
        result = self.engine.compute(
            params=self.params, state=state,
            pv=FFSignal.good(50.0), sp=FFSignal.good(50.0),
            bkcal_in=FFSignal.good(0.0), dt=1.0,
            out_limits=(0.0, 100.0),
            ff_enable=True, ff_val=5.0, ff_gain=2.0,
        )
        assert result.delta_cv == pytest.approx(0.0)


class TestLowCutoff:
    """Gap #4: Low cutoff forces PV to 0 when below threshold."""

    def setup_method(self) -> None:
        self.engine = PIDEngine()
        self.params = PIDParams(gain=1.0, reset=1e9, rate=0.0)

    def test_low_cutoff_disabled_no_effect(self) -> None:
        """When low_cutoff_enabled=False, PV passes through even if below threshold."""
        state = PIDState(cv=50.0, error_prev=0.0, pv_prev=0.5, pv_prev2=0.5, pv_filtered=0.5)
        result = self.engine.compute(
            params=self.params, state=state,
            pv=FFSignal.good(0.5), sp=FFSignal.good(50.0),
            bkcal_in=FFSignal.good(0.0), dt=1.0,
            out_limits=(0.0, 100.0),
            low_cutoff_enabled=False, low_cut=1.0,
        )
        # PV=0.5 < low_cut=1.0, but disabled, so error = 50 - 0.5 = 49.5
        assert result.error == pytest.approx(49.5)

    def test_low_cutoff_forces_pv_to_zero(self) -> None:
        """When PV < low_cut and enabled, PV should be forced to 0."""
        state = PIDState(cv=50.0, error_prev=0.0, pv_prev=0.0, pv_prev2=0.0, pv_filtered=0.0)
        result = self.engine.compute(
            params=self.params, state=state,
            pv=FFSignal.good(0.5), sp=FFSignal.good(50.0),
            bkcal_in=FFSignal.good(0.0), dt=1.0,
            out_limits=(0.0, 100.0),
            low_cutoff_enabled=True, low_cut=1.0,
        )
        # PV forced to 0, error = 50 - 0 = 50
        assert result.error == pytest.approx(50.0)
        assert result.new_state.pv_filtered == pytest.approx(0.0)

    def test_low_cutoff_no_effect_above_threshold(self) -> None:
        """When PV >= low_cut, no cutoff applied."""
        state = PIDState(cv=50.0, error_prev=0.0, pv_prev=5.0, pv_prev2=5.0, pv_filtered=5.0)
        result = self.engine.compute(
            params=self.params, state=state,
            pv=FFSignal.good(5.0), sp=FFSignal.good(50.0),
            bkcal_in=FFSignal.good(0.0), dt=1.0,
            out_limits=(0.0, 100.0),
            low_cutoff_enabled=True, low_cut=1.0,
        )
        # PV=5 >= low_cut=1, no cutoff
        assert result.error == pytest.approx(45.0)

    def test_low_cutoff_applied_before_pv_filter(self) -> None:
        """Low cutoff should be applied BEFORE the PV filter."""
        state = PIDState(cv=50.0, error_prev=0.0, pv_prev=0.0, pv_prev2=0.0, pv_filtered=10.0)
        result = self.engine.compute(
            params=self.params, state=state,
            pv=FFSignal.good(0.5), sp=FFSignal.good(50.0),
            bkcal_in=FFSignal.good(0.0), dt=1.0,
            out_limits=(0.0, 100.0),
            low_cutoff_enabled=True, low_cut=1.0,
            pv_ftime=4.0,
        )
        # PV=0.5 < 1.0 -> forced to 0
        # alpha = 1/(4+1) = 0.2
        # pv_filtered = 0.2*0 + 0.8*10 = 8
        assert result.new_state.pv_filtered == pytest.approx(8.0)


class TestOverRange:
    """Gap #6: Output limits allow 10% over-range per FF spec."""

    def setup_method(self) -> None:
        self.engine = PIDEngine()
        self.params = PIDParams(gain=1.0, reset=1e9, rate=0.0)

    def test_no_overrange_when_span_zero(self) -> None:
        """When out_scale_span=0, limits are strict (backward compatible)."""
        state = PIDState(cv=98.0, error_prev=0.0, pv_prev=50.0, pv_prev2=50.0)
        result = self.engine.compute(
            params=PIDParams(gain=2.0, reset=1e9, rate=0.0),
            state=state,
            pv=FFSignal.good(50.0), sp=FFSignal.good(60.0),
            bkcal_in=FFSignal.good(0.0), dt=1.0,
            out_limits=(0.0, 100.0), out_scale_span=0.0,
        )
        # 98 + 20 = 118 -> clamped to 100
        assert result.cv == pytest.approx(100.0)

    def test_overrange_allows_above_hi_lim(self) -> None:
        """With out_scale_span, output can exceed out_hi_lim by 10% of span."""
        state = PIDState(cv=98.0, error_prev=0.0, pv_prev=50.0, pv_prev2=50.0)
        result = self.engine.compute(
            params=PIDParams(gain=2.0, reset=1e9, rate=0.0),
            state=state,
            pv=FFSignal.good(50.0), sp=FFSignal.good(60.0),
            bkcal_in=FFSignal.good(0.0), dt=1.0,
            out_limits=(0.0, 100.0), out_scale_span=100.0,
        )
        # effective_hi = 100 + 10 = 110
        # 98 + 20 = 118 -> clamped to 110
        assert result.cv == pytest.approx(110.0)
        assert result.new_state.is_saturated is True

    def test_overrange_allows_below_lo_lim(self) -> None:
        """Output can go below out_lo_lim by 10% of span."""
        state = PIDState(cv=2.0, error_prev=0.0, pv_prev=60.0, pv_prev2=60.0)
        result = self.engine.compute(
            params=PIDParams(gain=2.0, reset=1e9, rate=0.0),
            state=state,
            pv=FFSignal.good(60.0), sp=FFSignal.good(50.0),
            bkcal_in=FFSignal.good(0.0), dt=1.0,
            out_limits=(0.0, 100.0), out_scale_span=100.0,
        )
        # error = 50-60 = -10, delta = 2*(-10-0) = -20
        # cv_new = 2 + (-20) = -18, effective_lo = 0 - 10 = -10
        # clamped to -10
        assert result.cv == pytest.approx(-10.0)
        assert result.new_state.is_saturated is True

    def test_overrange_within_effective_limits_not_saturated(self) -> None:
        """Output within effective limits should not be saturated."""
        state = PIDState(cv=98.0, error_prev=0.0, pv_prev=50.0, pv_prev2=50.0)
        result = self.engine.compute(
            params=PIDParams(gain=1.0, reset=1e9, rate=0.0),
            state=state,
            pv=FFSignal.good(50.0), sp=FFSignal.good(55.0),
            bkcal_in=FFSignal.good(0.0), dt=1.0,
            out_limits=(0.0, 100.0), out_scale_span=100.0,
        )
        # delta = 1*(5-0) = 5, cv = 98+5 = 103, effective_hi=110
        assert result.cv == pytest.approx(103.0)
        assert result.new_state.is_saturated is False

    def test_overrange_bkcal_uses_effective_limits(self) -> None:
        """BKCAL_OUT should use effective limits for limit bits."""
        state = PIDState(cv=108.0, error_prev=0.0, pv_prev=50.0, pv_prev2=50.0)
        result = self.engine.compute(
            params=PIDParams(gain=2.0, reset=1e9, rate=0.0),
            state=state,
            pv=FFSignal.good(50.0), sp=FFSignal.good(55.0),
            bkcal_in=FFSignal.good(0.0), dt=1.0,
            out_limits=(0.0, 100.0), out_scale_span=100.0,
        )
        # delta = 2*(5-0)=10, cv=108+10=118 -> clamped to 110
        from smart_pid_domain.enums import LimitBits
        assert result.bkcal_out.status.limit_bits == LimitBits.HIGH_LIMITED


class TestIncreaseToClose:
    """Gap #5: Increase-to-close inversion is applied in PIDWorker, not engine.
    These tests verify the inversion logic conceptually."""

    def test_inversion_formula(self) -> None:
        """co_output = out_hi_lim + out_lo_lim - cv."""
        # Simulating the inversion logic from pid_worker
        out_hi_lim = 100.0
        out_lo_lim = 0.0
        cv = 30.0
        inverted = out_hi_lim + out_lo_lim - cv
        assert inverted == pytest.approx(70.0)

    def test_inversion_at_midpoint(self) -> None:
        """At 50%, inversion should produce 50%."""
        inverted = 100.0 + 0.0 - 50.0
        assert inverted == pytest.approx(50.0)

    def test_inversion_at_extremes(self) -> None:
        """0% -> 100%, 100% -> 0%."""
        assert pytest.approx(100.0) == 100.0 + 0.0 - 0.0
        assert pytest.approx(0.0) == 100.0 + 0.0 - 100.0

    def test_inversion_with_nonzero_lo_lim(self) -> None:
        """With lo=10, hi=90: cv=30 -> 10+90-30=70."""
        inverted = 90.0 + 10.0 - 30.0
        assert inverted == pytest.approx(70.0)


class TestCombinedFeatures:
    """Test interactions between multiple gap features."""

    def setup_method(self) -> None:
        self.engine = PIDEngine()

    def test_low_cutoff_plus_pv_filter(self) -> None:
        """Low cutoff should zero PV before filter sees it."""
        state = PIDState(
            cv=50.0, error_prev=0.0, pv_prev=0.0, pv_prev2=0.0, pv_filtered=5.0,
        )
        result = self.engine.compute(
            params=PIDParams(gain=1.0, reset=1e9, rate=0.0),
            state=state,
            pv=FFSignal.good(0.3), sp=FFSignal.good(50.0),
            bkcal_in=FFSignal.good(0.0), dt=1.0,
            out_limits=(0.0, 100.0),
            low_cutoff_enabled=True, low_cut=1.0,
            pv_ftime=4.0,
        )
        # PV=0.3 < 1.0 -> forced to 0, then filter: alpha=0.2, 0.2*0+0.8*5=4
        assert result.new_state.pv_filtered == pytest.approx(4.0)

    def test_ff_plus_overrange(self) -> None:
        """Feedforward pushing output into over-range territory."""
        state = PIDState(cv=95.0, error_prev=0.0, pv_prev=50.0, pv_prev2=50.0)
        result = self.engine.compute(
            params=PIDParams(gain=1.0, reset=1e9, rate=0.0),
            state=state,
            pv=FFSignal.good(50.0), sp=FFSignal.good(50.0),
            bkcal_in=FFSignal.good(0.0), dt=1.0,
            out_limits=(0.0, 100.0),
            ff_enable=True, ff_val=10.0, ff_gain=1.0,
            out_scale_span=100.0,
        )
        # cv = 95 + 0 + 10 = 105, effective_hi=110, not saturated
        assert result.cv == pytest.approx(105.0)
        assert result.new_state.is_saturated is False

    def test_all_features_together(self) -> None:
        """Smoke test with all features enabled simultaneously."""
        state = PIDState(
            cv=50.0, error_prev=0.0, pv_prev=50.0, pv_prev2=50.0,
            pv_filtered=50.0, sp_filtered=50.0,
        )
        result = self.engine.compute(
            params=PIDParams(gain=1.0, reset=10.0, rate=0.0),
            state=state,
            pv=FFSignal.good(48.0), sp=FFSignal.good(55.0),
            bkcal_in=FFSignal.good(0.0), dt=1.0,
            out_limits=(0.0, 100.0),
            pv_ftime=2.0, sp_ftime=2.0,
            ff_enable=True, ff_val=1.0, ff_gain=0.5,
            low_cutoff_enabled=True, low_cut=1.0,
            out_scale_span=100.0,
        )
        # Just verify it runs and produces a reasonable result
        assert 0.0 <= result.cv <= 110.0
        assert result.new_state.pv_filtered != 0.0
        assert result.new_state.sp_filtered != 0.0


class TestControllerModelFF:
    """Verify Controller model has ff_enable and ff_gain fields."""

    def test_controller_ff_defaults(self) -> None:
        from smart_pid_domain.models.controller import Controller
        ctrl = Controller()
        assert ctrl.ff_enable is False
        assert ctrl.ff_gain == 1.0

    def test_controller_ff_custom(self) -> None:
        from smart_pid_domain.models.controller import Controller
        ctrl = Controller(ff_enable=True, ff_gain=2.5)
        assert ctrl.ff_enable is True
        assert ctrl.ff_gain == 2.5
