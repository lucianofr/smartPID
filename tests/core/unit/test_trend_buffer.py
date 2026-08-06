"""Unit tests for the in-memory 72-hour trend ring (application/trend_buffer.py)."""
from __future__ import annotations

import threading
import time

import pytest

from smart_pid_core.application.trend_buffer import (
    HYDRATE_S,
    MAX_SAMPLES_PER_LOOP,
    RETENTION_S,
    TREND_INTERVAL_S,
    TrendBuffer,
)


class TestAppendAndQuery:
    def test_query_returns_newest_window_ascending(self) -> None:
        buf = TrendBuffer()
        for i in range(10):
            assert buf.append(1, 1000.0 + i, float(i), 50.0, 25.0)
        window = buf.query(1, 4.0)
        # Both edges are inclusive — the same predicate eviction uses.
        assert [s.ts for s in window] == [1005.0, 1006.0, 1007.0, 1008.0, 1009.0]
        assert [s.pv for s in window] == [5.0, 6.0, 7.0, 8.0, 9.0]

    def test_query_unknown_loop_is_empty(self) -> None:
        assert TrendBuffer().query(99, 60.0) == []

    def test_rings_are_isolated_per_loop(self) -> None:
        buf = TrendBuffer()
        buf.append(1, 1000.0, 1.0, 2.0, 3.0)
        buf.append(2, 1000.0, 4.0, 5.0, 6.0)
        assert [s.pv for s in buf.query(1, 60.0)] == [1.0]
        assert [s.pv for s in buf.query(2, 60.0)] == [4.0]

    def test_non_increasing_ts_is_dropped(self) -> None:
        buf = TrendBuffer()
        assert buf.append(1, 1000.0, 1.0, 2.0, 3.0)
        assert not buf.append(1, 1000.0, 9.0, 9.0, 9.0)  # duplicate
        assert not buf.append(1, 999.0, 9.0, 9.0, 9.0)  # out of order
        assert len(buf.query(1, 60.0)) == 1

    def test_non_finite_ts_is_dropped(self) -> None:
        buf = TrendBuffer()
        assert not buf.append(1, float("nan"), 1.0, 2.0, 3.0)
        assert not buf.append(1, float("inf"), 1.0, 2.0, 3.0)
        assert buf.query(1, 60.0) == []

    def test_non_numeric_value_leaves_the_ring_intact(self) -> None:
        """The four columns must never desync: a rejected sample writes none.

        Not hypothetical bookkeeping — a half-written sample would make every
        later query for this loop index past the end of the short column.
        """
        buf = TrendBuffer()
        assert buf.append(1, 1.0, 10.0, 0.0, 0.0)
        with pytest.raises(TypeError):
            buf.append(1, 2.0, None, 0.0, 0.0)  # type: ignore[arg-type]
        assert buf.append(1, 3.0, 30.0, 0.0, 0.0)
        assert [(s.ts, s.pv) for s in buf.query(1, 60.0)] == [(1.0, 10.0), (3.0, 30.0)]


class TestCircularEviction:
    def test_samples_older_than_retention_are_evicted(self) -> None:
        buf = TrendBuffer()
        assert buf.append(1, 0.0, 1.0, 2.0, 3.0)
        # 72 h later: the first sample falls out of the window.
        assert buf.append(1, RETENTION_S + 1.0, 4.0, 5.0, 6.0)
        window = buf.query(1, RETENTION_S)
        assert len(window) == 1
        assert window[0].pv == 4.0

    def test_retention_is_relative_to_newest_sample(self) -> None:
        buf = TrendBuffer(retention_s=100.0)
        for i in range(5):
            buf.append(1, float(i * 40), float(i), 0.0, 0.0)  # 0, 40, 80, 120, 160
        # Newest is 160; cutoff 60 → samples at 80, 120, 160 survive.
        assert [s.ts for s in buf.query(1, 100.0)] == [80.0, 120.0, 160.0]

    def test_maxlen_sheds_oldest(self) -> None:
        buf = TrendBuffer(retention_s=float("inf"))
        for i in range(MAX_SAMPLES_PER_LOOP + 10):
            assert buf.append(1, float(i), float(i), 0.0, 0.0)
        window = buf.query(1, float("inf"))
        assert len(window) == MAX_SAMPLES_PER_LOOP
        assert window[0].ts == 10.0  # the first 10 were shed

    def test_concurrent_append_and_query(self) -> None:
        buf = TrendBuffer()

        def writer() -> None:
            for i in range(2000):
                buf.append(1, float(i), float(i), 0.0, 0.0)

        t = threading.Thread(target=writer)
        t.start()
        for _ in range(100):
            buf.query(1, 60.0)
        t.join()
        assert buf.query(1, 60.0)[-1].ts == 1999.0


class TestIngestCadence:
    """The ring is fed by a 10 Hz scan but stores one sample per second."""

    def test_faster_than_one_hz_is_thinned(self) -> None:
        buf = TrendBuffer()
        # 10 s of a 10 Hz feed: 100 frames in, 10 samples kept.
        for i in range(100):
            buf.append(1, 1000.0 + i * 0.1, float(i), 0.0, 0.0)
        window = buf.query(1, 60.0)
        assert [s.ts for s in window] == [1000.0 + i for i in range(10)]
        # The sample kept per second is the FIRST of that second, not the last:
        # a stored sample is never rewritten.
        assert [s.pv for s in window] == [float(i * 10) for i in range(10)]

    def test_frame_exactly_one_interval_later_is_kept(self) -> None:
        buf = TrendBuffer()
        assert buf.append(1, 1000.0, 1.0, 0.0, 0.0)
        assert buf.append(1, 1000.0 + TREND_INTERVAL_S, 2.0, 0.0, 0.0)
        assert len(buf.query(1, 60.0)) == 2

    def test_thinning_returns_false_for_the_dropped_frame(self) -> None:
        buf = TrendBuffer()
        assert buf.append(1, 1000.0, 1.0, 0.0, 0.0)
        assert not buf.append(1, 1000.5, 2.0, 0.0, 0.0)


class TestSizing:
    """The count cap must not silently truncate the advertised time window.

    A cap below ``RETENTION_S / TREND_INTERVAL_S`` is the bug the frontend's
    own window buffer once shipped with: the chart drew a shorter span than
    its axis claimed, and nothing on screen said so.
    """

    def test_count_cap_covers_the_full_retention_window(self) -> None:
        assert MAX_SAMPLES_PER_LOOP >= RETENTION_S / TREND_INTERVAL_S

    def test_hydration_window_is_a_slice_of_retention(self) -> None:
        # Startup pre-fill is deliberately shorter than the ring: a 72 h
        # historian scan per loop would delay the PID loops starting.
        assert 0.0 < HYDRATE_S < RETENTION_S

    def test_retention_is_seventy_two_hours(self) -> None:
        assert RETENTION_S == 72 * 3600.0


class TestLazyFill:
    """``gap`` reports what the historian must supply; ``backfill`` inserts it.

    Only ``HYDRATE_S`` is loaded at boot, so a window wider than the ring holds
    is filled on demand from the old end while the live feed keeps writing the
    new end.
    """

    def test_gap_is_none_when_the_window_is_already_covered(self) -> None:
        buf = TrendBuffer()
        for i in range(100):
            buf.append(1, 1000.0 + i, float(i), 0.0, 0.0)
        assert buf.gap(1, 50.0) is None

    def test_gap_spans_from_the_wanted_start_to_the_oldest_held(self) -> None:
        buf = TrendBuffer()
        for i in range(10):
            buf.append(1, 1000.0 + i, float(i), 0.0, 0.0)
        # Newest is 1009, oldest 1000; a 100 s window reaches back to 909.
        assert buf.gap(1, 100.0) == (909.0, 1000.0)

    def test_gap_for_an_empty_loop_uses_wall_clock(self) -> None:
        buf = TrendBuffer()
        before = time.time()
        missing = buf.gap(7, 600.0)
        assert missing is not None
        start, end = missing
        assert end >= before
        assert end - start == 600.0

    def test_gap_is_asked_once_per_depth(self) -> None:
        """A database that cannot satisfy the window must not be re-queried.

        Otherwise every chart mount pays the slow path forever.
        """
        buf = TrendBuffer()
        for i in range(10):
            buf.append(1, 1000.0 + i, float(i), 0.0, 0.0)
        assert buf.gap(1, 100.0) == (909.0, 1000.0)
        assert buf.gap(1, 100.0) is None
        # A deeper window is a new question, so it is asked.
        assert buf.gap(1, 200.0) == (809.0, 1000.0)

    def test_backfill_prepends_and_query_spans_both_halves(self) -> None:
        buf = TrendBuffer()
        for i in range(5):
            buf.append(1, 1000.0 + i, 100.0 + i, 0.0, 0.0)
        stored = buf.backfill(1, [(990.0 + i, float(i), 1.0, 2.0) for i in range(8)])
        assert stored == 8  # 990..997, all older than the held 1000
        window = buf.query(1, 100.0)
        assert [s.ts for s in window] == [990.0 + i for i in range(8)] + [
            1000.0 + i for i in range(5)
        ]
        assert window[0].pv == 0.0
        assert window[-1].pv == 104.0

    def test_backfill_drops_samples_the_live_end_already_owns(self) -> None:
        buf = TrendBuffer()
        buf.append(1, 1000.0, 50.0, 0.0, 0.0)
        # 999.5 is inside one interval of the oldest held sample, 1000+ is newer.
        assert buf.backfill(1, [(999.5, 1.0, 0.0, 0.0), (1000.0, 2.0, 0.0, 0.0)]) == 0
        assert [s.pv for s in buf.query(1, 60.0)] == [50.0]

    def test_backfill_thins_a_feed_denser_than_the_ring_cadence(self) -> None:
        """The bucketed historian read does not guarantee spacing — this does."""
        buf = TrendBuffer()
        buf.append(1, 1000.0, 50.0, 0.0, 0.0)
        dense = [(900.0 + i * 0.1, float(i), 0.0, 0.0) for i in range(300)]
        stored = buf.backfill(1, dense)
        window = buf.query(1, 200.0)
        assert stored == 30
        assert [s.ts for s in window[:-1]] == [900.0 + i for i in range(30)]

    def test_backfill_respects_the_retention_window(self) -> None:
        buf = TrendBuffer(retention_s=100.0)
        buf.append(1, 1000.0, 50.0, 0.0, 0.0)
        # 850 is outside the 100 s window measured from the newest sample.
        assert buf.backfill(1, [(850.0, 1.0, 0.0, 0.0), (950.0, 2.0, 0.0, 0.0)]) == 1
        assert [s.ts for s in buf.query(1, 100.0)] == [950.0, 1000.0]

    def test_backfill_into_an_empty_loop(self) -> None:
        buf = TrendBuffer()
        assert buf.backfill(4, [(1000.0 + i, float(i), 0.0, 0.0) for i in range(5)]) == 5
        assert [s.ts for s in buf.query(4, 60.0)] == [1000.0 + i for i in range(5)]

    def test_backfill_rejects_non_numeric_without_touching_the_ring(self) -> None:
        buf = TrendBuffer()
        buf.append(1, 1000.0, 50.0, 0.0, 0.0)
        with pytest.raises(TypeError):
            buf.backfill(1, [(900.0, None, 0.0, 0.0)])  # type: ignore[list-item]
        assert [s.pv for s in buf.query(1, 200.0)] == [50.0]

    def test_live_appends_still_land_after_a_backfill(self) -> None:
        buf = TrendBuffer()
        buf.append(1, 1000.0, 50.0, 0.0, 0.0)
        buf.backfill(1, [(900.0 + i, float(i), 0.0, 0.0) for i in range(10)])
        assert buf.append(1, 1001.0, 51.0, 0.0, 0.0)
        window = buf.query(1, 200.0)
        assert window[-1].ts == 1001.0
        assert [s.ts for s in window] == sorted(s.ts for s in window)
