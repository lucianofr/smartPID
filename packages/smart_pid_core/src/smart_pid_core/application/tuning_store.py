"""TuningRecommendationStore — lifecycle-tracked storage for AI tuning recs.

Replaces the ad-hoc ``app.state.tuning_recommendations`` plain dict with
proper lifecycle tracking: timestamp, status, who applied, expiration.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from smart_pid_domain.enums import TuningRecStatus

if TYPE_CHECKING:
    from smart_pid_domain.models.tuning import TuningRecommendation


@dataclass
class TrackedRecommendation:
    """A tuning recommendation with lifecycle metadata."""

    recommendation: TuningRecommendation
    created_at: float = field(default_factory=time.time)
    status: TuningRecStatus = TuningRecStatus.PENDING
    applied_by: int | None = None
    applied_at: float | None = None
    rejected_by: int | None = None
    rejected_at: float | None = None


class TuningRecommendationStore:
    """Thread-safe store for tuning recommendations with lifecycle tracking.

    Producers run in worker threads (``AIWorker``) while consumers run on the
    API event loop, so every accessor holds ``_lock``: the expiry check in
    :meth:`get` is a read-modify-write that would otherwise race a concurrent
    :meth:`put` or :meth:`mark_applied`.

    Parameters
    ----------
    expiry_seconds:
        How long a PENDING recommendation remains valid before it
        transitions to EXPIRED.  Default: 3600 (1 hour).
    """

    def __init__(self, expiry_seconds: float = 3600.0) -> None:
        self._store: dict[int, TrackedRecommendation] = {}
        self._expiry_seconds = expiry_seconds
        self._lock = threading.RLock()

    def put(self, rec: TuningRecommendation) -> TrackedRecommendation:
        """Store a new recommendation, replacing any existing one for the controller."""
        tracked = TrackedRecommendation(recommendation=rec)
        with self._lock:
            self._store[rec.controller_id] = tracked
        return tracked

    def get(self, controller_id: int) -> TrackedRecommendation | None:
        """Return the tracked recommendation, expiring stale entries."""
        with self._lock:
            tracked = self._store.get(controller_id)
            if tracked is None:
                return None
            if (
                tracked.status == TuningRecStatus.PENDING
                and time.time() - tracked.created_at > self._expiry_seconds
            ):
                tracked.status = TuningRecStatus.EXPIRED
            return tracked

    def mark_applied(self, controller_id: int, user_id: int) -> TrackedRecommendation | None:
        """Mark a recommendation as applied by a user."""
        with self._lock:
            tracked = self._store.get(controller_id)
            if tracked is None:
                return None
            tracked.status = TuningRecStatus.APPLIED
            tracked.applied_by = user_id
            tracked.applied_at = time.time()
            return tracked

    def mark_rejected(self, controller_id: int, user_id: int) -> TrackedRecommendation | None:
        """Mark a recommendation as rejected by a user."""
        with self._lock:
            tracked = self._store.get(controller_id)
            if tracked is None:
                return None
            tracked.status = TuningRecStatus.REJECTED
            tracked.rejected_by = user_id
            tracked.rejected_at = time.time()
            return tracked

    def remove(self, controller_id: int) -> None:
        """Remove a recommendation from the store."""
        with self._lock:
            self._store.pop(controller_id, None)

    def pending(self) -> list[TrackedRecommendation]:
        """Return all currently-pending (non-expired) recommendations."""
        now = time.time()
        result: list[TrackedRecommendation] = []
        with self._lock:
            for tracked in self._store.values():
                if tracked.status == TuningRecStatus.PENDING:
                    if now - tracked.created_at > self._expiry_seconds:
                        tracked.status = TuningRecStatus.EXPIRED
                    else:
                        result.append(tracked)
        return result

    def all(self) -> dict[int, TrackedRecommendation]:
        """Return the full store (including expired/applied/rejected)."""
        with self._lock:
            return dict(self._store)
