"""Unit tests for PID engine velocity form equation."""
from __future__ import annotations

import pytest

from smart_pid_core.domain.services.pid_engine import PIDEngine, PIDState
from smart_pid_domain.models.controller import PIDParams


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
            pv=50.0,
            sp=50.0,
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
            pv=50.0,
            sp=60.0,  # Step change: error = 10
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
            pv=40.0,
            sp=50.0,  # error = 10
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
            pv=42.0,  # PV changed by 2
            sp=50.0,  # error = 8
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
            pv=50.0,
            sp=60.0,
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
            pv=50.0,
            sp=40.0,  # error = -10 (reverse acting) or +10 (direct acting)
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
            pv=40.0,
            sp=50.0,
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
            pv=55.0,
            sp=50.0,  # error = -5
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
        """Rate of 0 means no limiting — SP jumps immediately."""
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
            pv=49.5,
            sp=50.0,  # error = 0.5, within deadband of 2.0
            dt=1.0,
            out_limits=(0.0, 100.0),
        )
        # Proportional delta = 0 (error unchanged)
        # Integral should be zero because |error| < deadband
        assert result.delta_cv == pytest.approx(0.0, abs=1e-6)
