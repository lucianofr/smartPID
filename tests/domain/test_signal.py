"""Tests for FF signal enums and value objects."""
from __future__ import annotations

from smart_pid_domain.enums import InitSubStatus, LimitBits, SignalSeverity


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
