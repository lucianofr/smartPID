"""Tests for the pure IMC/lambda tuning recommender.

The worked examples below are verified by hand against the IMC-PID formulas
documented in ``tuning_recommender``::

    Kc = (2tau + L) / (2*K*(lambda + L))
    Ti = tau + L/2
    Td = tau*L / (2tau + L)
"""
from __future__ import annotations

import math

import pytest

from smart_pid_core.domain.services.tuning_recommender import (
    FOPDTModel,
    TuningProposal,
    identify_fopdt,
    recommend_pid,
)
from smart_pid_domain.enums import ControlObjective

# Reference plant used across the worked examples: K = 2 %PV/%CO, tau = 20 s,
# L = 4 s.  tss = L + 4*tau = 4 + 80 = 84 s.
_K = 2.0
_TAU = 20.0
_L = 4.0
_TSS = 84.0
_MODEL = FOPDTModel(gain=_K, tau_s=_TAU, dead_time_s=_L)


def _recommend(objective: ControlObjective, **overrides) -> TuningProposal | None:
    kwargs = {
        "model": _MODEL,
        "objective": objective,
        "current_kp": 0.1,
        "current_ti": 200.0,
        "current_td": 0.0,
        "limit_min": 0.1,
        "limit_max": 1000.0,
    }
    kwargs.update(overrides)
    return recommend_pid(**kwargs)  # type: ignore[arg-type]


class TestIdentifyFOPDT:
    """tau is derived from tss and L as tau = (tss - L) / 4."""

    def test_derives_tau_from_settling_time(self) -> None:
        model = identify_fopdt(tss_s=_TSS, dead_time_s=_L, gain=_K)
        assert model is not None
        assert model.tau_s == pytest.approx(20.0)
        assert model.dead_time_s == pytest.approx(4.0)
        assert model.gain == pytest.approx(2.0)

    def test_zero_dead_time_is_identifiable(self) -> None:
        model = identify_fopdt(tss_s=80.0, dead_time_s=0.0, gain=1.0)
        assert model is not None
        assert model.tau_s == pytest.approx(20.0)

    def test_negative_gain_is_kept_signed(self) -> None:
        """Reverse-acting processes are identifiable; direction lives elsewhere."""
        model = identify_fopdt(tss_s=_TSS, dead_time_s=_L, gain=-_K)
        assert model is not None
        assert model.gain == pytest.approx(-2.0)

    @pytest.mark.parametrize(
        ("tss_s", "dead_time_s", "gain"),
        [
            (0.0, 4.0, 2.0),        # no settling time
            (-10.0, 4.0, 2.0),      # negative settling time
            (84.0, -1.0, 2.0),      # negative dead time
            (4.0, 4.0, 2.0),        # dead time consumes the whole tss -> tau = 0
            (3.0, 4.0, 2.0),        # dead time exceeds tss -> tau < 0
            (84.0, 4.0, 0.0),       # zero gain
            (84.0, 4.0, 0.005),     # gain below the invertible floor
            (math.nan, 4.0, 2.0),   # NaN
            (math.inf, 4.0, 2.0),   # inf
            (84.0, 4.0, math.nan),
        ],
    )
    def test_unidentifiable_returns_none(
        self, tss_s: float, dead_time_s: float, gain: float,
    ) -> None:
        assert identify_fopdt(
            tss_s=tss_s, dead_time_s=dead_time_s, gain=gain,
        ) is None


class TestLambdaSelection:
    """lambda = max(factor * tau, 0.8 * L), factor set by the objective."""

    def test_sp_tracking_uses_one_tau(self) -> None:
        prop = _recommend(ControlObjective.SP_TRACKING)
        assert prop is not None
        assert prop.lambda_s == pytest.approx(20.0)

    def test_disturbance_rejection_is_tighter(self) -> None:
        prop = _recommend(ControlObjective.DISTURBANCE_REJECTION)
        assert prop is not None
        assert prop.lambda_s == pytest.approx(20.0 / 3.0)

    def test_surge_level_is_heavily_detuned(self) -> None:
        prop = _recommend(ControlObjective.SURGE_LEVEL)
        assert prop is not None
        assert prop.lambda_s == pytest.approx(60.0)

    def test_ordering_dr_tighter_than_sp_tighter_than_surge(self) -> None:
        dr = _recommend(ControlObjective.DISTURBANCE_REJECTION)
        sp = _recommend(ControlObjective.SP_TRACKING)
        surge = _recommend(ControlObjective.SURGE_LEVEL)
        assert dr is not None and sp is not None and surge is not None
        # Tighter lambda -> higher gain.
        assert dr.kp > sp.kp > surge.kp

    def test_dead_time_floor_overrides_tau_factor(self) -> None:
        """A dead-time dominant loop cannot be tuned below lambda = 0.8*L."""
        # tau = 1 s, L = 20 s -> tau/3 = 0.333 s but 0.8*L = 16 s wins.
        model = FOPDTModel(gain=1.0, tau_s=1.0, dead_time_s=20.0)
        prop = _recommend(ControlObjective.DISTURBANCE_REJECTION, model=model)
        assert prop is not None
        assert prop.lambda_s == pytest.approx(16.0)


class TestWorkedIMCExample:
    """K=2, tau=20, L=4 verified against the formulas by hand."""

    def test_sp_tracking_numbers(self) -> None:
        # lambda = max(20, 3.2) = 20
        # Kc = (2*20 + 4) / (2*2*(20 + 4)) = 44 / 96 = 0.4583333...
        # Ti = 20 + 4/2 = 22
        # Td = 20*4 / 44 = 80/44 = 1.8181818...
        prop = _recommend(ControlObjective.SP_TRACKING)
        assert prop is not None
        assert prop.kp == pytest.approx(44.0 / 96.0)
        assert prop.kp == pytest.approx(0.4583333333, abs=1e-9)
        assert prop.ti == pytest.approx(22.0)
        assert prop.td == pytest.approx(80.0 / 44.0)
        assert prop.td == pytest.approx(1.8181818182, abs=1e-9)

    def test_disturbance_rejection_numbers(self) -> None:
        # lambda = max(20/3, 3.2) = 6.6666...
        # Kc = 44 / (4 * (6.66667 + 4)) = 44 / 42.66667 = 1.03125 exactly
        prop = _recommend(ControlObjective.DISTURBANCE_REJECTION)
        assert prop is not None
        assert prop.kp == pytest.approx(1.03125)
        assert prop.ti == pytest.approx(22.0)
        assert prop.td == pytest.approx(80.0 / 44.0)

    def test_surge_level_numbers(self) -> None:
        # lambda = max(60, 3.2) = 60
        # Kc = 44 / (4 * 64) = 44 / 256 = 0.171875 exactly
        prop = _recommend(ControlObjective.SURGE_LEVEL)
        assert prop is not None
        assert prop.kp == pytest.approx(0.171875)

    def test_ti_and_td_are_lambda_independent(self) -> None:
        """Only Kc depends on lambda in the IMC-PID FOPDT rule."""
        props = [
            _recommend(obj)
            for obj in (
                ControlObjective.SP_TRACKING,
                ControlObjective.DISTURBANCE_REJECTION,
                ControlObjective.SURGE_LEVEL,
            )
        ]
        assert all(p is not None for p in props)
        assert {round(p.ti, 9) for p in props if p} == {22.0}
        assert len({round(p.td, 9) for p in props if p}) == 1

    def test_gain_sign_does_not_flip_kp(self) -> None:
        reverse = FOPDTModel(gain=-_K, tau_s=_TAU, dead_time_s=_L)
        prop = _recommend(ControlObjective.SP_TRACKING, model=reverse)
        assert prop is not None
        assert prop.kp == pytest.approx(44.0 / 96.0)

    def test_reason_names_method_and_lambda(self) -> None:
        prop = _recommend(ControlObjective.SP_TRACKING)
        assert prop is not None
        assert "IMC" in prop.reason
        assert "FOPDT" in prop.reason
        assert "lambda=20 s" in prop.reason
        assert "SP_TRACKING" in prop.reason

    def test_reason_survives_sub_second_time_constants(self) -> None:
        """A fast loop must not have its model printed away as "0.0 s"."""
        fast = FOPDTModel(gain=1.5, tau_s=0.04, dead_time_s=0.04)
        prop = _recommend(ControlObjective.SP_TRACKING, model=fast)
        assert prop is not None
        assert "tau=0.04 s" in prop.reason
        assert "L=0.04 s" in prop.reason
        assert "lambda=0.04 s" in prop.reason


class TestIntegralClamping:
    def test_ti_clamped_to_limit_max(self) -> None:
        prop = _recommend(ControlObjective.SP_TRACKING, limit_max=15.0)
        assert prop is not None
        assert prop.ti == pytest.approx(15.0)

    def test_ti_clamped_to_limit_min(self) -> None:
        prop = _recommend(ControlObjective.SP_TRACKING, limit_min=30.0, limit_max=1000.0)
        assert prop is not None
        assert prop.ti == pytest.approx(30.0)

    def test_inverted_window_is_normalised(self) -> None:
        """limit_min > limit_max must not push Ti outside the intended band."""
        prop = _recommend(ControlObjective.SP_TRACKING, limit_min=15.0, limit_max=5.0)
        assert prop is not None
        assert 5.0 <= prop.ti <= 15.0
        assert prop.ti == pytest.approx(15.0)

    def test_clamping_does_not_touch_kp_or_td(self) -> None:
        prop = _recommend(ControlObjective.SP_TRACKING, limit_max=15.0)
        assert prop is not None
        assert prop.kp == pytest.approx(44.0 / 96.0)
        assert prop.td == pytest.approx(80.0 / 44.0)


class TestMaterialDifferenceGate:
    def test_identical_tuning_returns_none(self) -> None:
        assert _recommend(
            ControlObjective.SP_TRACKING,
            current_kp=44.0 / 96.0,
            current_ti=22.0,
            current_td=80.0 / 44.0,
        ) is None

    def test_sub_threshold_drift_returns_none(self) -> None:
        """All three parameters within 10 % -> not worth an operator's attention."""
        assert _recommend(
            ControlObjective.SP_TRACKING,
            current_kp=(44.0 / 96.0) * 1.05,
            current_ti=22.0 * 0.95,
            current_td=(80.0 / 44.0) * 1.08,
        ) is None

    def test_threshold_is_reached_on_a_single_parameter(self) -> None:
        """Kp alone moving 12 % is enough."""
        prop = _recommend(
            ControlObjective.SP_TRACKING,
            current_kp=(44.0 / 96.0) / 0.88,
            current_ti=22.0,
            current_td=80.0 / 44.0,
        )
        assert prop is not None

    def test_switching_derivative_on_is_material(self) -> None:
        """Td 0 -> 1.82 s scores 1.0 on the symmetric measure."""
        prop = _recommend(
            ControlObjective.SP_TRACKING,
            current_kp=44.0 / 96.0,
            current_ti=22.0,
            current_td=0.0,
        )
        assert prop is not None

    def test_both_td_zero_is_not_a_change(self) -> None:
        """A zero-dead-time plant keeps Td = 0; that must not read as material."""
        model = FOPDTModel(gain=1.0, tau_s=20.0, dead_time_s=0.0)
        # Kc = 40 / (2*1*20) = 1.0 ; Ti = 20 ; Td = 0
        assert _recommend(
            ControlObjective.SP_TRACKING,
            model=model,
            current_kp=1.0,
            current_ti=20.0,
            current_td=0.0,
        ) is None

    def test_self_comparison_of_a_proposal_returns_none(self) -> None:
        """The anti-churn idiom: re-running against the last proposal yields None."""
        first = _recommend(ControlObjective.SP_TRACKING)
        assert first is not None
        again = _recommend(
            ControlObjective.SP_TRACKING,
            current_kp=first.kp,
            current_ti=first.ti,
            current_td=first.td,
        )
        assert again is None


class TestRecommendGuards:
    def test_degenerate_model_returns_none(self) -> None:
        assert _recommend(
            ControlObjective.SP_TRACKING,
            model=FOPDTModel(gain=2.0, tau_s=0.0, dead_time_s=4.0),
        ) is None

    def test_tiny_gain_returns_none(self) -> None:
        assert _recommend(
            ControlObjective.SP_TRACKING,
            model=FOPDTModel(gain=1e-6, tau_s=20.0, dead_time_s=4.0),
        ) is None

    def test_non_finite_current_tuning_returns_none(self) -> None:
        assert _recommend(ControlObjective.SP_TRACKING, current_kp=math.nan) is None

    def test_non_finite_limits_return_none(self) -> None:
        assert _recommend(ControlObjective.SP_TRACKING, limit_max=math.inf) is None


class TestPurity:
    def test_deterministic_across_calls(self) -> None:
        a = _recommend(ControlObjective.SP_TRACKING)
        b = _recommend(ControlObjective.SP_TRACKING)
        assert a == b

    def test_dataclasses_are_frozen(self) -> None:
        model = FOPDTModel(gain=1.0, tau_s=1.0, dead_time_s=1.0)
        with pytest.raises(AttributeError):
            model.gain = 2.0  # type: ignore[misc]
        prop = _recommend(ControlObjective.SP_TRACKING)
        assert prop is not None
        with pytest.raises(AttributeError):
            prop.kp = 2.0  # type: ignore[misc]
