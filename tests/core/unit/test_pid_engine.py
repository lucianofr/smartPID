"""Unit tests for PID engine velocity form equation."""
from __future__ import annotations

import pytest

from smart_pid_core.domain.services.pid_engine import PIDEngine, PIDState
from smart_pid_domain.enums import InitSubStatus, LimitBits
from smart_pid_domain.models.controller import PIDParams
from smart_pid_domain.models.signal import FFSignal, FFSignalStatus


class TestPIDCompute:
    """Test PID velocity form: delta = G*[(e-e_prev) + dt/Ti*e - Td*(pv-2pv1+pv2)/dt]."""

    def setup_method(self) -> None:
        self.engine = PIDEngine()
        self.params = PIDParams(gain=1.0, reset=10.0, rate=0.0)

    def test_zero_error_produces_zero_delta(self) -> None:
        """With PV == SP and no history, delta_cv should be zero."""
        state = PIDState(cv=50.0, pv_prev=50.0, pv_prev2=50.0)
        result = self.engine.compute(
            params=self.params,
            state=state,
            pv=FFSignal.good(50.0),
            sp=FFSignal.good(50.0),
            bkcal_in=FFSignal.good(0.0),
            dt=1.0,
            out_limits=(0.0, 100.0),
        )
        assert result.delta_cv == pytest.approx(0.0, abs=1e-10)
        assert result.cv == pytest.approx(50.0, abs=1e-10)

    def test_proportional_action_on_error_step(self) -> None:
        """Step change in SP should produce proportional kick (error term)."""
        state = PIDState(cv=50.0, error_prev=0.0, pv_prev=50.0, pv_prev2=50.0)
        result = self.engine.compute(
            params=PIDParams(gain=2.0, reset=1e9, rate=0.0),  # P-only (huge Ti)
            state=state,
            pv=FFSignal.good(50.0),
            sp=FFSignal.good(60.0),  # Step change: error = 10
            bkcal_in=FFSignal.good(0.0),
            dt=1.0,
            out_limits=(0.0, 100.0),
        )
        # delta_cv = G * (e - e_prev) = 2.0 * (10 - 0) = 20.0
        assert result.delta_cv == pytest.approx(20.0, abs=1e-6)
        assert result.cv == pytest.approx(70.0, abs=1e-6)

    def test_integral_action_accumulates(self) -> None:
        """Constant error should produce steady integral accumulation."""
        state = PIDState(cv=50.0, error_prev=10.0, pv_prev=40.0, pv_prev2=40.0)
        result = self.engine.compute(
            params=PIDParams(gain=1.0, reset=10.0, rate=0.0),
            state=state,
            pv=FFSignal.good(40.0),
            sp=FFSignal.good(50.0),  # error = 10
            bkcal_in=FFSignal.good(0.0),
            dt=1.0,
            out_limits=(0.0, 100.0),
        )
        # error unchanged: proportional delta = 0
        # integral delta = G * dt/Ti * e = 1.0 * 1.0/10.0 * 10 = 1.0
        assert result.delta_cv == pytest.approx(1.0, abs=1e-6)

    def test_derivative_action_on_pv_change(self) -> None:
        """Derivative acts on PV change, not error change (derivative on PV)."""
        state = PIDState(cv=50.0, error_prev=10.0, pv_prev=40.0, pv_prev2=40.0)
        result = self.engine.compute(
            params=PIDParams(gain=1.0, reset=1e9, rate=5.0, alpha=1.0),  # D-only
            state=state,
            pv=FFSignal.good(42.0),  # PV changed by 2
            sp=FFSignal.good(50.0),  # error = 8
            bkcal_in=FFSignal.good(0.0),
            dt=1.0,
            out_limits=(0.0, 100.0),
        )
        # proportional delta = G * (8 - 10) = -2.0
        # derivative = -G * Td * (pv - 2*pv_prev + pv_prev2) / dt
        #            = -1.0 * 5.0 * (42 - 80 + 40) / 1.0 = -1.0 * 5.0 * 2.0 = -10.0
        # total delta = -2.0 + 0.0 (no integral) + (-10.0) = -12.0
        assert result.delta_cv == pytest.approx(-12.0, abs=1e-6)

    def test_output_clamped_to_limits(self) -> None:
        """CV must be clamped within out_limits."""
        state = PIDState(cv=98.0, error_prev=0.0, pv_prev=50.0, pv_prev2=50.0)
        result = self.engine.compute(
            params=PIDParams(gain=2.0, reset=1e9, rate=0.0),
            state=state,
            pv=FFSignal.good(50.0),
            sp=FFSignal.good(60.0),
            bkcal_in=FFSignal.good(0.0),
            dt=1.0,
            out_limits=(0.0, 100.0),
        )
        # delta_cv = 20, but 98 + 20 = 118 -> clamped to 100
        assert result.cv == pytest.approx(100.0, abs=1e-6)
        assert result.new_state.is_saturated is True

    def test_direct_acting_reverses_error(self) -> None:
        """Direct acting: increasing PV should increase output."""
        state = PIDState(cv=50.0, error_prev=0.0, pv_prev=50.0, pv_prev2=50.0)
        result = self.engine.compute(
            params=PIDParams(gain=1.0, reset=1e9, rate=0.0),
            state=state,
            pv=FFSignal.good(50.0),
            sp=FFSignal.good(40.0),  # error = -10 (reverse acting) or +10 (direct acting)
            bkcal_in=FFSignal.good(0.0),
            dt=1.0,
            out_limits=(0.0, 100.0),
            direct_acting=True,
        )
        # Direct acting: error = PV - SP = 10
        assert result.delta_cv == pytest.approx(10.0, abs=1e-6)


class TestAntiWindup:
    """Anti-reset windup: pause integral when output is saturated."""

    def setup_method(self) -> None:
        self.engine = PIDEngine()

    def test_integral_paused_when_saturated_high(self) -> None:
        """When CV hits upper limit, integral should not accumulate further up."""
        state = PIDState(cv=100.0, error_prev=10.0, pv_prev=40.0, pv_prev2=40.0, is_saturated=True)
        result = self.engine.compute(
            params=PIDParams(gain=1.0, reset=10.0, rate=0.0),
            state=state,
            pv=FFSignal.good(40.0),
            sp=FFSignal.good(50.0),
            bkcal_in=FFSignal.good(0.0),
            dt=1.0,
            out_limits=(0.0, 100.0),
        )
        # Proportional delta = 0 (error unchanged)
        # Integral should be suppressed because output is saturated high and error is positive
        assert result.cv == pytest.approx(100.0, abs=1e-6)

    def test_integral_resumes_when_error_reverses(self) -> None:
        """When error direction reverses, integral should resume to bring output back."""
        state = PIDState(cv=100.0, error_prev=-5.0, pv_prev=55.0, pv_prev2=55.0, is_saturated=True)
        result = self.engine.compute(
            params=PIDParams(gain=1.0, reset=10.0, rate=0.0),
            state=state,
            pv=FFSignal.good(55.0),
            sp=FFSignal.good(50.0),  # error = -5
            bkcal_in=FFSignal.good(0.0),
            dt=1.0,
            out_limits=(0.0, 100.0),
        )
        # Error is negative while saturated high -> integral should act to reduce output
        # integral delta = 1.0 * 1.0/10.0 * (-5) = -0.5
        assert result.cv < 100.0


class TestBumplessTransfer:
    """Bumpless transfer recalculates integral on mode change."""

    def setup_method(self) -> None:
        self.engine = PIDEngine()

    def test_bumpless_sets_cv_to_current_co(self) -> None:
        """After bumpless transfer, the PID output should match the current CO."""
        state = PIDState(cv=30.0)
        new_state = self.engine.bumpless_transfer(
            state=state,
            current_pv=45.0,
            current_co=65.0,
            params=PIDParams(gain=1.5, reset=10.0, rate=0.0),
        )
        assert new_state.cv == pytest.approx(65.0, abs=1e-6)
        assert new_state.pv_prev == pytest.approx(45.0, abs=1e-6)
        assert new_state.pv_prev2 == pytest.approx(45.0, abs=1e-6)


class TestSPRamp:
    """SP rate limiting (SP_RATE_UP / SP_RATE_DN)."""

    def setup_method(self) -> None:
        self.engine = PIDEngine()

    def test_ramp_up_limits_sp_increase(self) -> None:
        """SP should increase at most rate_up * dt per scan."""
        result = self.engine.apply_sp_ramp(
            sp_target=100.0,
            sp_current=50.0,
            rate_up=10.0,  # 10 units/second
            rate_dn=10.0,
            dt=1.0,
        )
        assert result == pytest.approx(60.0, abs=1e-6)  # 50 + 10*1

    def test_ramp_down_limits_sp_decrease(self) -> None:
        result = self.engine.apply_sp_ramp(
            sp_target=0.0,
            sp_current=50.0,
            rate_up=10.0,
            rate_dn=5.0,  # 5 units/second
            dt=1.0,
        )
        assert result == pytest.approx(45.0, abs=1e-6)  # 50 - 5*1

    def test_zero_rate_means_immediate(self) -> None:
        """Rate of 0 means no limiting -- SP jumps immediately."""
        result = self.engine.apply_sp_ramp(
            sp_target=100.0,
            sp_current=50.0,
            rate_up=0.0,
            rate_dn=0.0,
            dt=1.0,
        )
        assert result == pytest.approx(100.0, abs=1e-6)


class TestDeadband:
    """Integral deadband: stops integral when error is within deadband."""

    def setup_method(self) -> None:
        self.engine = PIDEngine()

    def test_integral_stops_within_deadband(self) -> None:
        """When |error| < deadband, integral term should not accumulate."""
        state = PIDState(cv=50.0, error_prev=0.5, pv_prev=49.5, pv_prev2=49.5)
        result = self.engine.compute(
            params=PIDParams(gain=1.0, reset=10.0, rate=0.0, deadband=2.0),
            state=state,
            pv=FFSignal.good(49.5),
            sp=FFSignal.good(50.0),  # error = 0.5, within deadband of 2.0
            bkcal_in=FFSignal.good(0.0),
            dt=1.0,
            out_limits=(0.0, 100.0),
        )
        # Proportional delta = 0 (error unchanged)
        # Integral should be zero because |error| < deadband
        assert result.delta_cv == pytest.approx(0.0, abs=1e-6)


class TestDirectionalAntiWindup:
    """Anti-windup based on BKCAL_IN limit bits from downstream block."""

    def setup_method(self) -> None:
        self.engine = PIDEngine()

    def test_high_limited_blocks_positive_integration(self) -> None:
        """When downstream is HIGH_LIMITED, positive integral increment is blocked."""
        state = PIDState(cv=60.0, error_prev=10.0, pv_prev=40.0, pv_prev2=40.0)
        bkcal_in = FFSignal.with_limits(60.0, LimitBits.HIGH_LIMITED)
        result = self.engine.compute(
            params=PIDParams(gain=1.0, reset=10.0, rate=0.0),
            state=state,
            pv=FFSignal.good(40.0),
            sp=FFSignal.good(50.0),
            bkcal_in=bkcal_in,
            dt=1.0,
            out_limits=(0.0, 100.0),
        )
        # Error = 10 (positive), integral would be +1.0, but HIGH_LIMITED blocks it
        # Only proportional acts: error unchanged so p_term = 0
        assert result.delta_cv == pytest.approx(0.0, abs=1e-6)

    def test_high_limited_allows_negative_integration(self) -> None:
        """HIGH_LIMITED only blocks positive increment; negative is allowed."""
        state = PIDState(cv=60.0, error_prev=-5.0, pv_prev=55.0, pv_prev2=55.0)
        bkcal_in = FFSignal.with_limits(60.0, LimitBits.HIGH_LIMITED)
        result = self.engine.compute(
            params=PIDParams(gain=1.0, reset=10.0, rate=0.0),
            state=state,
            pv=FFSignal.good(55.0),
            sp=FFSignal.good(50.0),
            bkcal_in=bkcal_in,
            dt=1.0,
            out_limits=(0.0, 100.0),
        )
        # Error = -5, integral = -0.5 (negative) -> allowed despite HIGH_LIMITED
        assert result.delta_cv < 0.0

    def test_low_limited_blocks_negative_integration(self) -> None:
        """When downstream is LOW_LIMITED, negative integral increment is blocked."""
        state = PIDState(cv=40.0, error_prev=-10.0, pv_prev=60.0, pv_prev2=60.0)
        bkcal_in = FFSignal.with_limits(40.0, LimitBits.LOW_LIMITED)
        result = self.engine.compute(
            params=PIDParams(gain=1.0, reset=10.0, rate=0.0),
            state=state,
            pv=FFSignal.good(60.0),
            sp=FFSignal.good(50.0),
            bkcal_in=bkcal_in,
            dt=1.0,
            out_limits=(0.0, 100.0),
        )
        # Error = -10, integral would be -1.0, but LOW_LIMITED blocks it
        # Proportional: error unchanged so p_term = 0
        assert result.delta_cv == pytest.approx(0.0, abs=1e-6)

    def test_constant_blocks_all_integration(self) -> None:
        """CONSTANT limit blocks all integration regardless of direction."""
        state = PIDState(cv=50.0, error_prev=10.0, pv_prev=40.0, pv_prev2=40.0)
        bkcal_in = FFSignal.with_limits(50.0, LimitBits.CONSTANT)
        result = self.engine.compute(
            params=PIDParams(gain=1.0, reset=10.0, rate=0.0),
            state=state,
            pv=FFSignal.good(40.0),
            sp=FFSignal.good(50.0),
            bkcal_in=bkcal_in,
            dt=1.0,
            out_limits=(0.0, 100.0),
        )
        assert result.delta_cv == pytest.approx(0.0, abs=1e-6)

    def test_none_limit_allows_normal_integration(self) -> None:
        """NONE limit bits -- integration is free (normal behavior)."""
        state = PIDState(cv=50.0, error_prev=10.0, pv_prev=40.0, pv_prev2=40.0)
        bkcal_in = FFSignal.good(50.0)
        result = self.engine.compute(
            params=PIDParams(gain=1.0, reset=10.0, rate=0.0),
            state=state,
            pv=FFSignal.good(40.0),
            sp=FFSignal.good(50.0),
            bkcal_in=bkcal_in,
            dt=1.0,
            out_limits=(0.0, 100.0),
        )
        # Normal integral: G * dt/Ti * e = 1.0 * 1.0/10.0 * 10 = 1.0
        assert result.delta_cv == pytest.approx(1.0, abs=1e-6)

    def test_downstream_and_local_arw_most_restrictive_wins(self) -> None:
        """Both local ARW and downstream limit active -- most restrictive wins."""
        state = PIDState(
            cv=100.0, error_prev=10.0, pv_prev=40.0, pv_prev2=40.0, is_saturated=True,
        )
        bkcal_in = FFSignal.good(100.0)  # No downstream limit
        result = self.engine.compute(
            params=PIDParams(gain=1.0, reset=10.0, rate=0.0),
            state=state,
            pv=FFSignal.good(40.0),
            sp=FFSignal.good(50.0),
            bkcal_in=bkcal_in,
            dt=1.0,
            out_limits=(0.0, 100.0),
        )
        # Local ARW blocks positive integration when saturated high
        assert result.cv == pytest.approx(100.0, abs=1e-6)


class TestIMANTracking:
    """IMAN mode: force CV to match BKCAL_IN value for cascade handshake."""

    def setup_method(self) -> None:
        self.engine = PIDEngine()

    def test_cv_matches_bkcal_in_value(self) -> None:
        """Output must exactly match BKCAL_IN value during tracking."""
        state = PIDState(cv=50.0, pv_prev=45.0, pv_prev2=45.0)
        bkcal_in = FFSignal(
            value=72.5,
            status=FFSignalStatus(sub_status=InitSubStatus.IR),
        )
        result = self.engine.compute_iman_tracking(
            state=state,
            pv=FFSignal.good(45.0),
            sp=FFSignal.good(50.0),
            bkcal_in=bkcal_in,
        )
        assert result.cv == pytest.approx(72.5, abs=1e-10)
        assert result.delta_cv == 0.0

    def test_bkcal_out_has_ia_substatus(self) -> None:
        """BKCAL_OUT must carry IA sub-status to acknowledge initialization."""
        state = PIDState(cv=50.0, pv_prev=45.0, pv_prev2=45.0)
        bkcal_in = FFSignal(
            value=72.5,
            status=FFSignalStatus(sub_status=InitSubStatus.IR),
        )
        result = self.engine.compute_iman_tracking(
            state=state,
            pv=FFSignal.good(45.0),
            sp=FFSignal.good(50.0),
            bkcal_in=bkcal_in,
        )
        assert result.bkcal_out.value == pytest.approx(72.5, abs=1e-10)
        assert result.bkcal_out.status.sub_status == InitSubStatus.IA

    def test_pv_history_updated(self) -> None:
        """PV history must be updated to prevent derivative kick on return."""
        state = PIDState(cv=50.0, pv_prev=40.0, pv_prev2=38.0)
        result = self.engine.compute_iman_tracking(
            state=state,
            pv=FFSignal.good(45.0),
            sp=FFSignal.good(50.0),
            bkcal_in=FFSignal.good(72.5),
        )
        assert result.new_state.pv_prev == pytest.approx(45.0)
        assert result.new_state.pv_prev2 == pytest.approx(40.0)
        assert result.new_state.derivative_filtered == 0.0

    def test_state_cv_set_to_tracking_value(self) -> None:
        """State CV must be set to BKCAL_IN value for seamless transition."""
        state = PIDState(cv=30.0)
        result = self.engine.compute_iman_tracking(
            state=state,
            pv=FFSignal.good(45.0),
            sp=FFSignal.good(50.0),
            bkcal_in=FFSignal.good(80.0),
        )
        assert result.new_state.cv == pytest.approx(80.0)
