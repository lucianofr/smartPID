"""Tests for tuning domain models."""
from uuid import UUID, uuid4

from smart_pid_domain.enums import TuningRecStatus
from smart_pid_domain.models.tuning import PIDParamsRead, TuningRecommendation


class TestPIDParamsRead:
    def test_creation_all_values(self) -> None:
        p = PIDParamsRead(kp=1.5, ti=10.0, td=0.5, timestamp=1000.0)
        assert p.kp == 1.5
        assert p.ti == 10.0
        assert p.td == 0.5
        assert p.timestamp == 1000.0

    def test_creation_partial_none(self) -> None:
        p = PIDParamsRead(kp=1.5, ti=None, td=None, timestamp=1000.0)
        assert p.kp == 1.5
        assert p.ti is None
        assert p.td is None

    def test_frozen(self) -> None:
        p = PIDParamsRead(kp=1.0, ti=10.0, td=0.0, timestamp=1000.0)
        try:
            p.kp = 2.0  # type: ignore[misc]
            raise AssertionError("Should be frozen")
        except AttributeError:
            pass


class TestTuningRecommendation:
    def test_creation(self) -> None:
        rec_id = uuid4()
        rec = TuningRecommendation(
            id=rec_id,
            controller_id=1,
            current_kp=1.0,
            current_ti=10.0,
            current_td=0.0,
            recommended_kp=1.2,
            recommended_ti=8.0,
            recommended_td=0.1,
            reason="fuzzy_sp_tracking",
            timestamp=1000.0,
        )
        assert rec.id == rec_id
        assert rec.status == TuningRecStatus.PENDING
        assert rec.recommended_kp == 1.2

    def test_default_status_pending(self) -> None:
        rec = TuningRecommendation(
            id=uuid4(),
            controller_id=1,
            current_kp=1.0,
            current_ti=10.0,
            current_td=0.0,
            recommended_kp=1.0,
            recommended_ti=10.0,
            recommended_td=0.0,
            reason="test",
            timestamp=0.0,
        )
        assert rec.status == TuningRecStatus.PENDING

    def test_frozen(self) -> None:
        rec = TuningRecommendation(
            id=uuid4(),
            controller_id=1,
            current_kp=1.0,
            current_ti=10.0,
            current_td=0.0,
            recommended_kp=1.0,
            recommended_ti=10.0,
            recommended_td=0.0,
            reason="test",
            timestamp=0.0,
        )
        try:
            rec.status = TuningRecStatus.APPLIED  # type: ignore[misc]
            raise AssertionError("Should be frozen")
        except AttributeError:
            pass
