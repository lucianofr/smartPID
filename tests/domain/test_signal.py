"""Tests for FF signal enums and value objects."""
from __future__ import annotations

from datetime import UTC, datetime

from smart_pid_domain.enums import InitSubStatus, LimitBits, SignalSeverity
from smart_pid_domain.models.signal import FFSignal, FFSignalStatus


class TestSignalSeverity:
    def test_values(self) -> None:
        assert SignalSeverity.GOOD == "GOOD"
        assert SignalSeverity.UNCERTAIN == "UNCERTAIN"
        assert SignalSeverity.BAD == "BAD"

    def test_is_str_enum(self) -> None:
        assert isinstance(SignalSeverity.GOOD, str)


class TestLimitBits:
    def test_values(self) -> None:
        assert LimitBits.NONE == "NONE"
        assert LimitBits.LOW_LIMITED == "LOW_LIMITED"
        assert LimitBits.HIGH_LIMITED == "HIGH_LIMITED"
        assert LimitBits.CONSTANT == "CONSTANT"


class TestInitSubStatus:
    def test_values(self) -> None:
        assert InitSubStatus.NONE == "NONE"
        assert InitSubStatus.NI == "NI"
        assert InitSubStatus.IR == "IR"
        assert InitSubStatus.IA == "IA"
        assert InitSubStatus.GOOD_CASCADE == "GOOD_CASCADE"


class TestFFSignalStatus:
    def test_default_is_good(self) -> None:
        status = FFSignalStatus()
        assert status.severity == SignalSeverity.GOOD
        assert status.limit_bits == LimitBits.NONE
        assert status.sub_status == InitSubStatus.NONE

    def test_is_good(self) -> None:
        assert FFSignalStatus().is_good is True
        assert FFSignalStatus(severity=SignalSeverity.BAD).is_good is False

    def test_is_bad(self) -> None:
        assert FFSignalStatus(severity=SignalSeverity.BAD).is_bad is True
        assert FFSignalStatus().is_bad is False

    def test_is_high_limited(self) -> None:
        status = FFSignalStatus(limit_bits=LimitBits.HIGH_LIMITED)
        assert status.is_high_limited is True
        assert status.is_low_limited is False

    def test_is_low_limited(self) -> None:
        status = FFSignalStatus(limit_bits=LimitBits.LOW_LIMITED)
        assert status.is_low_limited is True
        assert status.is_high_limited is False

    def test_is_constant(self) -> None:
        status = FFSignalStatus(limit_bits=LimitBits.CONSTANT)
        assert status.is_constant is True

    def test_sub_status_properties(self) -> None:
        assert FFSignalStatus(sub_status=InitSubStatus.NI).is_not_invited is True
        assert FFSignalStatus(sub_status=InitSubStatus.IR).is_init_request is True
        assert FFSignalStatus(sub_status=InitSubStatus.IA).is_init_acknowledge is True
        assert FFSignalStatus(sub_status=InitSubStatus.GOOD_CASCADE).is_good_cascade is True

    def test_frozen(self) -> None:
        import pytest
        status = FFSignalStatus()
        with pytest.raises(AttributeError):
            status.severity = SignalSeverity.BAD  # type: ignore[misc]


class TestFFSignal:
    def test_default_good_status(self) -> None:
        sig = FFSignal(value=42.0)
        assert sig.value == 42.0
        assert sig.status.is_good is True
        assert sig.timestamp is None

    def test_good_factory(self) -> None:
        ts = datetime.now(tz=UTC)
        sig = FFSignal.good(50.0, ts)
        assert sig.value == 50.0
        assert sig.status.is_good is True
        assert sig.timestamp == ts

    def test_bad_factory(self) -> None:
        sig = FFSignal.bad(0.0)
        assert sig.status.is_bad is True
        assert sig.value == 0.0

    def test_with_limits_factory(self) -> None:
        sig = FFSignal.with_limits(75.0, LimitBits.HIGH_LIMITED)
        assert sig.value == 75.0
        assert sig.status.is_high_limited is True
        assert sig.status.is_good is True

    def test_frozen(self) -> None:
        import pytest
        sig = FFSignal(value=1.0)
        with pytest.raises(AttributeError):
            sig.value = 2.0  # type: ignore[misc]

    def test_equality(self) -> None:
        ts = datetime(2026, 1, 1, tzinfo=UTC)
        a = FFSignal.good(10.0, ts)
        b = FFSignal.good(10.0, ts)
        assert a == b
