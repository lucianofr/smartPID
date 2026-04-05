"""Tests for tuning and execution mode enums."""
from smart_pid_domain.enums import (
    SystemExecutionMode,
    TuningRecStatus,
    TuningWriteMode,
)


class TestTuningWriteMode:
    def test_values(self) -> None:
        assert TuningWriteMode.AUTO_APPLY == "auto_apply"
        assert TuningWriteMode.APPROVAL_REQUIRED == "approval_required"
        assert TuningWriteMode.DISABLED == "disabled"

    def test_is_strenum(self) -> None:
        assert isinstance(TuningWriteMode.AUTO_APPLY, str)

    def test_member_count(self) -> None:
        assert len(TuningWriteMode) == 3


class TestTuningRecStatus:
    def test_values(self) -> None:
        assert TuningRecStatus.PENDING == "pending"
        assert TuningRecStatus.APPLIED == "applied"
        assert TuningRecStatus.REJECTED == "rejected"
        assert TuningRecStatus.EXPIRED == "expired"

    def test_member_count(self) -> None:
        assert len(TuningRecStatus) == 4


class TestSystemExecutionMode:
    def test_values(self) -> None:
        assert SystemExecutionMode.MONITOR == "monitor"
        assert SystemExecutionMode.EXECUTE == "execute"

    def test_member_count(self) -> None:
        assert len(SystemExecutionMode) == 2
