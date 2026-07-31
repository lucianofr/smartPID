"""Anti-windup band bounds and reset-recovery gain.

Both defend control-safety behaviour that was previously implicit:

* the ARW band is clamped into the output range, so an ARW limit configured
  wider than the output limits cannot silently disable the anti-windup gate;
* the reset-recovery multiplier is a per-engine setting rather than a literal.
"""
from __future__ import annotations

import pytest

from smart_pid_core.domain.services.pid_engine import (
    DEFAULT_RESET_RECOVERY_GAIN,
    PIDEngine,
    PIDState,
)
from smart_pid_domain.models.controller import PIDParams
from smart_pid_domain.models.signal import FFSignal

OUT_LIMITS = (0.0, 100.0)


def _integrating_params() -> PIDParams:
    """P-neutral, integral-only: delta_cv is then purely the integral term."""
    return PIDParams(gain=1.0, reset=10.0, rate=0.0)


class TestARWWiderThanOutputLimits:
    """An ARW limit outside the output range must not disable the gate.

    CV is clamped to the output limits, so with ``arw_hi`` above ``out_hi`` the
    gate condition ``cv >= arw_hi`` can never be true and the integral keeps
    accumulating while the output sits pinned at saturation.
    """

    def test_windup_blocked_when_arw_hi_exceeds_out_hi(self) -> None:
        engine = PIDEngine()
        # Saturated high, error still positive => integral must be suppressed.
        state = PIDState(cv=100.0, error_prev=10.0, is_saturated=True)
        result = engine.compute(
            params=_integrating_params(),
            state=state,
            pv=FFSignal.good(40.0),
            sp=FFSignal.good(50.0),  # error = +10, drives further into the limit
            bkcal_in=FFSignal.good(100.0),
            dt=1.0,
            out_limits=OUT_LIMITS,
            arw_limits=(-50.0, 150.0),  # wider than the output range
        )
        assert result.delta_cv == pytest.approx(0.0, abs=1e-9)
        assert result.cv == pytest.approx(100.0, abs=1e-9)

    def test_windup_blocked_when_arw_lo_below_out_lo(self) -> None:
        engine = PIDEngine()
        state = PIDState(cv=0.0, error_prev=-10.0, is_saturated=True)
        result = engine.compute(
            params=_integrating_params(),
            state=state,
            pv=FFSignal.good(60.0),
            sp=FFSignal.good(50.0),  # error = -10, drives further down
            bkcal_in=FFSignal.good(0.0),
            dt=1.0,
            out_limits=OUT_LIMITS,
            arw_limits=(-50.0, 150.0),
        )
        assert result.delta_cv == pytest.approx(0.0, abs=1e-9)
        assert result.cv == pytest.approx(0.0, abs=1e-9)

    def test_wide_arw_matches_the_default_none_behaviour(self) -> None:
        """Clamping makes an over-wide band equivalent to passing none at all."""
        engine = PIDEngine()

        def run(arw: tuple[float, float] | None) -> float:
            return engine.compute(
                params=_integrating_params(),
                state=PIDState(cv=100.0, error_prev=10.0, is_saturated=True),
                pv=FFSignal.good(40.0),
                sp=FFSignal.good(50.0),
                bkcal_in=FFSignal.good(100.0),
                dt=1.0,
                out_limits=OUT_LIMITS,
                arw_limits=arw,
            ).delta_cv

        assert run((-50.0, 150.0)) == pytest.approx(run(None), abs=1e-9)


class TestARWNarrowerThanOutputLimits:
    """The useful case must survive clamping: a tighter band still bites."""

    def test_narrow_arw_still_blocks_below_the_output_limit(self) -> None:
        engine = PIDEngine()
        # CV is at 80 — inside the output range, but at the ARW ceiling.
        state = PIDState(cv=80.0, error_prev=10.0, is_saturated=True)
        result = engine.compute(
            params=_integrating_params(),
            state=state,
            pv=FFSignal.good(40.0),
            sp=FFSignal.good(50.0),  # error = +10
            bkcal_in=FFSignal.good(80.0),
            dt=1.0,
            out_limits=OUT_LIMITS,
            arw_limits=(20.0, 80.0),
        )
        assert result.delta_cv == pytest.approx(0.0, abs=1e-9)

    def test_same_state_integrates_without_the_narrow_band(self) -> None:
        """Control: at CV 80 the default band does not block, so the narrow
        band above is doing real work rather than passing vacuously."""
        engine = PIDEngine()
        result = engine.compute(
            params=_integrating_params(),
            state=PIDState(cv=80.0, error_prev=10.0, is_saturated=True),
            pv=FFSignal.good(40.0),
            sp=FFSignal.good(50.0),
            bkcal_in=FFSignal.good(80.0),
            dt=1.0,
            out_limits=OUT_LIMITS,
        )
        assert result.delta_cv == pytest.approx(1.0, abs=1e-9)


class TestResetRecoveryGain:
    """The 16x unwind multiplier is configurable per engine instance."""

    @staticmethod
    def _recovering(engine: PIDEngine) -> float:
        """Saturated high with the error reversed: the integral is unwinding,
        so the recovery multiplier applies."""
        return engine.compute(
            params=_integrating_params(),
            state=PIDState(cv=100.0, error_prev=-5.0, is_saturated=True),
            pv=FFSignal.good(55.0),
            sp=FFSignal.good(50.0),  # error = -5 => integral drives CV down
            bkcal_in=FFSignal.good(100.0),
            dt=1.0,
            out_limits=OUT_LIMITS,
        ).delta_cv

    def test_default_gain_is_applied(self) -> None:
        # Unaccelerated integral = gain * dt/reset * error = 1 * 0.1 * -5 = -0.5
        expected = -0.5 * DEFAULT_RESET_RECOVERY_GAIN
        assert self._recovering(PIDEngine()) == pytest.approx(expected, abs=1e-9)

    def test_default_constant_matches_shipped_behaviour(self) -> None:
        assert DEFAULT_RESET_RECOVERY_GAIN == 16.0

    def test_custom_gain_overrides_the_default(self) -> None:
        assert self._recovering(PIDEngine(reset_recovery_gain=2.0)) == pytest.approx(
            -1.0, abs=1e-9,
        )

    def test_gain_of_one_disables_acceleration(self) -> None:
        assert self._recovering(PIDEngine(reset_recovery_gain=1.0)) == pytest.approx(
            -0.5, abs=1e-9,
        )
