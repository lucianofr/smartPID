"""Tests for TuningRecommendationStore — Gap #54."""
from __future__ import annotations

import time
from uuid import uuid4

from smart_pid_core.application.tuning_store import (
    TuningRecommendationStore,
)
from smart_pid_domain.enums import TuningRecStatus
from smart_pid_domain.models.tuning import TuningRecommendation


def _make_rec(controller_id: int = 1) -> TuningRecommendation:
    return TuningRecommendation(
        id=uuid4(),
        controller_id=controller_id,
        current_kp=1.0,
        current_ti=10.0,
        current_td=0.5,
        recommended_kp=1.2,
        recommended_ti=8.0,
        recommended_td=0.6,
        reason="fuzzy suggestion",
        timestamp=time.time(),
    )


class TestTuningRecommendationStore:
    def test_put_and_get(self) -> None:
        store = TuningRecommendationStore()
        rec = _make_rec()
        tracked = store.put(rec)
        assert tracked.status == TuningRecStatus.PENDING
        assert tracked.recommendation is rec

        retrieved = store.get(1)
        assert retrieved is tracked

    def test_get_nonexistent_returns_none(self) -> None:
        store = TuningRecommendationStore()
        assert store.get(999) is None

    def test_mark_applied(self) -> None:
        store = TuningRecommendationStore()
        store.put(_make_rec())
        tracked = store.mark_applied(1, user_id=42)
        assert tracked is not None
        assert tracked.status == TuningRecStatus.APPLIED
        assert tracked.applied_by == 42
        assert tracked.applied_at is not None

    def test_mark_rejected(self) -> None:
        store = TuningRecommendationStore()
        store.put(_make_rec())
        tracked = store.mark_rejected(1, user_id=7)
        assert tracked is not None
        assert tracked.status == TuningRecStatus.REJECTED
        assert tracked.rejected_by == 7
        assert tracked.rejected_at is not None

    def test_expiration(self) -> None:
        store = TuningRecommendationStore(expiry_seconds=0.0)
        store.put(_make_rec())
        # After 0 seconds, it should be expired
        tracked = store.get(1)
        assert tracked is not None
        assert tracked.status == TuningRecStatus.EXPIRED

    def test_remove(self) -> None:
        store = TuningRecommendationStore()
        store.put(_make_rec())
        store.remove(1)
        assert store.get(1) is None

    def test_pending_excludes_expired(self) -> None:
        store = TuningRecommendationStore(expiry_seconds=0.0)
        store.put(_make_rec(1))
        store.put(_make_rec(2))
        assert len(store.pending()) == 0

    def test_pending_includes_fresh(self) -> None:
        store = TuningRecommendationStore(expiry_seconds=3600)
        store.put(_make_rec(1))
        store.put(_make_rec(2))
        assert len(store.pending()) == 2

    def test_replace_existing(self) -> None:
        store = TuningRecommendationStore()
        rec1 = _make_rec()
        rec2 = _make_rec()
        store.put(rec1)
        store.put(rec2)
        tracked = store.get(1)
        assert tracked is not None
        assert tracked.recommendation is rec2

    def test_all_returns_full_store(self) -> None:
        store = TuningRecommendationStore()
        store.put(_make_rec(1))
        store.put(_make_rec(2))
        store.mark_applied(1, user_id=1)
        result = store.all()
        assert len(result) == 2
        assert result[1].status == TuningRecStatus.APPLIED
        assert result[2].status == TuningRecStatus.PENDING
