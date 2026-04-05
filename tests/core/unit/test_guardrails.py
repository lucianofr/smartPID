"""Tests for tuning guardrail clamping logic."""
import pytest

from smart_pid_core.domain.services.tuning_guardrails import clamp_tuning_change


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
