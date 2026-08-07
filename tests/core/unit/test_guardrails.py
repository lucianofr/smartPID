"""Tests for tuning guardrail clamping logic."""
import math

import pytest

from smart_pid_core.domain.services.tuning_guardrails import (
    KP_MIN,
    clamp_tuning_absolute,
    clamp_tuning_change,
)
from smart_pid_domain.enums import ExecutionMode


class TestClampTuningChange:
    def test_no_change(self) -> None:
        result = clamp_tuning_change(current=1.0, recommended=1.0, max_pct=10.0)
        assert result == 1.0

    def test_within_limit(self) -> None:
        result = clamp_tuning_change(current=1.0, recommended=1.05, max_pct=10.0)
        assert result == 1.05

    def test_clamped_high(self) -> None:
        result = clamp_tuning_change(current=1.0, recommended=1.5, max_pct=10.0)
        assert result == pytest.approx(1.1)

    def test_clamped_low(self) -> None:
        result = clamp_tuning_change(current=1.0, recommended=0.5, max_pct=10.0)
        assert result == pytest.approx(0.9)

    def test_negative_current(self) -> None:
        result = clamp_tuning_change(current=-1.0, recommended=-1.5, max_pct=10.0)
        assert result == pytest.approx(-1.1)

    def test_zero_current(self) -> None:
        result = clamp_tuning_change(current=0.0, recommended=0.5, max_pct=10.0)
        assert result == 0.0

    def test_100_pct_allows_doubling(self) -> None:
        result = clamp_tuning_change(current=1.0, recommended=2.5, max_pct=100.0)
        assert result == pytest.approx(2.0)


class TestClampTuningChangeTuple:
    def test_clamp_all_three(self) -> None:
        from smart_pid_core.domain.services.tuning_guardrails import clamp_tuning_params

        kp, ti, td = clamp_tuning_params(
            current_kp=1.0, current_ti=10.0, current_td=0.5,
            rec_kp=2.0, rec_ti=20.0, rec_td=1.0,
            max_pct=10.0,
        )
        assert kp == pytest.approx(1.1)
        assert ti == pytest.approx(11.0)
        assert td == pytest.approx(0.55)


class TestClampTuningAbsolute:
    """The rate clamp above bounds how FAR a value may move per write; these
    bound WHERE it may land. Both are needed: a 10 %/write rate limit still
    walks Kp to zero over enough writes without ever tripping.
    """

    def test_kp_floor_applies_in_both_modes(self) -> None:
        for mode in (ExecutionMode.DDC, ExecutionMode.SUPERVISORY):
            kp, _, _ = clamp_tuning_absolute(
                kp=0.0, ti=None, td=None,
                execution_mode=mode, ti_min=1.0, ti_max=10.0,
            )
            assert kp == pytest.approx(KP_MIN), mode

    def test_negative_kp_raised_to_floor(self) -> None:
        """Kp's sign carries no meaning here — `direct_acting` owns the loop's
        action and PIDEngine takes the error sign from it, so a negative gain
        double-inverts into positive feedback rather than reverse action.
        """
        kp, _, _ = clamp_tuning_absolute(
            kp=-2.0, ti=None, td=None,
            execution_mode=ExecutionMode.DDC, ti_min=1.0, ti_max=10.0,
        )
        assert kp == pytest.approx(KP_MIN)

    def test_kp_above_floor_untouched(self) -> None:
        kp, _, _ = clamp_tuning_absolute(
            kp=2.5, ti=None, td=None,
            execution_mode=ExecutionMode.DDC, ti_min=1.0, ti_max=10.0,
        )
        assert kp == pytest.approx(2.5)

    def test_ddc_allows_ti_zero_to_disable_integral(self) -> None:
        """PIDEngine gates the integral on `reset > 0`, so 0 is the documented
        way to run P-only. DDC keeps that door open.
        """
        _, ti, _ = clamp_tuning_absolute(
            kp=None, ti=0.0, td=None,
            execution_mode=ExecutionMode.DDC, ti_min=1.0, ti_max=10.0,
        )
        assert ti == pytest.approx(0.0)

    def test_supervisory_ti_forced_into_configured_band(self) -> None:
        """The band is the operator's own Ti/Ki Min/Max from the loop's
        optimizer config. The AI worker already honours it; the manual write
        path must not be the way around it.
        """
        _, ti_low, _ = clamp_tuning_absolute(
            kp=None, ti=0.0, td=None,
            execution_mode=ExecutionMode.SUPERVISORY, ti_min=1.0, ti_max=10.0,
        )
        assert ti_low == pytest.approx(1.0)
        _, ti_high, _ = clamp_tuning_absolute(
            kp=None, ti=500.0, td=None,
            execution_mode=ExecutionMode.SUPERVISORY, ti_min=1.0, ti_max=10.0,
        )
        assert ti_high == pytest.approx(10.0)

    def test_supervisory_ti_inside_band_untouched(self) -> None:
        _, ti, _ = clamp_tuning_absolute(
            kp=None, ti=4.0, td=None,
            execution_mode=ExecutionMode.SUPERVISORY, ti_min=1.0, ti_max=10.0,
        )
        assert ti == pytest.approx(4.0)

    def test_td_zero_allowed_in_both_modes(self) -> None:
        for mode in (ExecutionMode.DDC, ExecutionMode.SUPERVISORY):
            _, _, td = clamp_tuning_absolute(
                kp=None, ti=None, td=0.0,
                execution_mode=mode, ti_min=1.0, ti_max=10.0,
            )
            assert td == pytest.approx(0.0), mode

    def test_negative_td_floored_at_zero(self) -> None:
        """A negative rate term differentiates with the wrong sign, which is
        positive feedback on the fastest channel in the loop.
        """
        _, _, td = clamp_tuning_absolute(
            kp=None, ti=None, td=-1.0,
            execution_mode=ExecutionMode.DDC, ti_min=1.0, ti_max=10.0,
        )
        assert td == pytest.approx(0.0)

    def test_negative_ti_floored_at_zero_in_ddc(self) -> None:
        """A negative reset flips the sign of the integral term."""
        _, ti, _ = clamp_tuning_absolute(
            kp=None, ti=-5.0, td=None,
            execution_mode=ExecutionMode.DDC, ti_min=1.0, ti_max=10.0,
        )
        assert ti == pytest.approx(0.0)

    def test_none_passes_through(self) -> None:
        """TuningCommand allows partial writes; an omitted field must stay
        omitted rather than materialise as a floor value.
        """
        assert clamp_tuning_absolute(
            kp=None, ti=None, td=None,
            execution_mode=ExecutionMode.SUPERVISORY, ti_min=1.0, ti_max=10.0,
        ) == (None, None, None)

    def test_inverted_band_does_not_invert_result(self) -> None:
        """`limit_min > limit_max` is reachable: the two UI fields are validated
        independently. A naive min(max()) would return the wrong bound; the
        floor must still win so Ti never lands below the operator's minimum.
        """
        _, ti, _ = clamp_tuning_absolute(
            kp=None, ti=5.0, td=None,
            execution_mode=ExecutionMode.SUPERVISORY, ti_min=10.0, ti_max=1.0,
        )
        assert ti == pytest.approx(10.0)


class TestClampTuningAbsoluteNeverEmitsNonFinite:
    """This function is the last thing between a tuning value and a DCS block,
    so it must not trust anything it is handed — neither the value nor the bounds.

    Both arrive from persisted configuration. The DTO guard stops new non-finite
    rows, but the read path is deliberately left open so pre-existing rows still
    load, and this is the code that consumes them on every tuning write. The Kp
    and Td floors happen to survive by argument order (the constant is the first
    operand, so min/max discard a nan operand); the Ti band does not, because its
    data-controlled bound comes first.

    A non-finite Ti can also arrive without any non-finite bound: `write_tuning`
    feeds this the output of `clamp_tuning_change(current.reset, ...)`, and with a
    legacy `current.reset` of inf that computes `inf + -inf`, which is nan.
    """

    _BAD = (float("nan"), float("inf"), float("-inf"))

    @pytest.mark.parametrize("bad", _BAD)
    def test_poisoned_ti_min_does_not_propagate(self, bad: float) -> None:
        _, ti, _ = clamp_tuning_absolute(
            kp=None, ti=5.0, td=None,
            execution_mode=ExecutionMode.SUPERVISORY, ti_min=bad, ti_max=10.0,
        )
        assert ti is not None
        assert math.isfinite(ti), f"ti_min={bad} produced {ti}"
        assert ti >= 0.0

    @pytest.mark.parametrize("bad", _BAD)
    def test_poisoned_ti_max_does_not_propagate(self, bad: float) -> None:
        _, ti, _ = clamp_tuning_absolute(
            kp=None, ti=5.0, td=None,
            execution_mode=ExecutionMode.SUPERVISORY, ti_min=1.0, ti_max=bad,
        )
        assert ti is not None
        assert math.isfinite(ti), f"ti_max={bad} produced {ti}"

    def test_both_bounds_poisoned_falls_back_to_physical_floor(self) -> None:
        """With no usable band left, SUPERVISORY degrades to the DDC rule rather
        than inventing a bound: Ti keeps its value if non-negative.
        """
        _, ti, _ = clamp_tuning_absolute(
            kp=None, ti=5.0, td=None,
            execution_mode=ExecutionMode.SUPERVISORY,
            ti_min=float("nan"), ti_max=float("nan"),
        )
        assert ti == pytest.approx(5.0)

    def test_usable_side_of_a_half_poisoned_band_still_applies(self) -> None:
        """Losing one bound must not discard the other."""
        _, ti, _ = clamp_tuning_absolute(
            kp=None, ti=0.5, td=None,
            execution_mode=ExecutionMode.SUPERVISORY,
            ti_min=2.0, ti_max=float("nan"),
        )
        assert ti == pytest.approx(2.0)

    @pytest.mark.parametrize("bad", _BAD)
    @pytest.mark.parametrize("mode", [ExecutionMode.DDC, ExecutionMode.SUPERVISORY])
    def test_non_finite_inputs_never_reach_the_output(
        self, bad: float, mode: ExecutionMode,
    ) -> None:
        kp, ti, td = clamp_tuning_absolute(
            kp=bad, ti=bad, td=bad,
            execution_mode=mode, ti_min=1.0, ti_max=10.0,
        )
        assert kp is not None and math.isfinite(kp), f"kp={bad} produced {kp}"
        assert ti is not None and math.isfinite(ti), f"ti={bad} produced {ti}"
        assert td is not None and math.isfinite(td), f"td={bad} produced {td}"
        assert kp >= KP_MIN
        assert td >= 0.0

    def test_finite_values_and_bounds_are_untouched(self) -> None:
        """The hardening must not disturb the ordinary case."""
        assert clamp_tuning_absolute(
            kp=2.5, ti=4.0, td=0.5,
            execution_mode=ExecutionMode.SUPERVISORY, ti_min=1.0, ti_max=10.0,
        ) == (pytest.approx(2.5), pytest.approx(4.0), pytest.approx(0.5))
