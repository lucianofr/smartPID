"""Tests for tuning-related domain events."""
from uuid import UUID, uuid4

from smart_pid_domain.events import TuningApplied, TuningRecommended


class TestTuningRecommended:
    def test_creation(self) -> None:
        evt = TuningRecommended(
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
        assert isinstance(evt.event_id, UUID)
        assert evt.controller_id == 1
        assert evt.recommended_kp == 1.2

    def test_frozen(self) -> None:
        evt = TuningRecommended(
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
            evt.controller_id = 2  # type: ignore[misc]
            raise AssertionError("Should be frozen")
        except AttributeError:
            pass


class TestTuningApplied:
    def test_creation(self) -> None:
        rec_id = uuid4()
        evt = TuningApplied(
            controller_id=1,
            recommendation_id=rec_id,
            applied_kp=1.15,
            applied_ti=9.0,
            applied_td=0.05,
            clamped=True,
            timestamp=1001.0,
        )
        assert isinstance(evt.event_id, UUID)
        assert evt.recommendation_id == rec_id
        assert evt.clamped is True

    def test_frozen(self) -> None:
        evt = TuningApplied(
            controller_id=1,
            recommendation_id=uuid4(),
            applied_kp=1.0,
            applied_ti=10.0,
            applied_td=0.0,
            clamped=False,
            timestamp=0.0,
        )
        try:
            evt.clamped = True  # type: ignore[misc]
            raise AssertionError("Should be frozen")
        except AttributeError:
            pass
