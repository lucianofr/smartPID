"""Unit tests for the in-memory 1-hour trend ring (application/trend_buffer.py)."""
from __future__ import annotations

import threading

from smart_pid_core.application.trend_buffer import (
    MAX_SAMPLES_PER_LOOP,
    RETENTION_S,
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


class TestCircularEviction:
    def test_samples_older_than_retention_are_evicted(self) -> None:
        buf = TrendBuffer()
        assert buf.append(1, 0.0, 1.0, 2.0, 3.0)
        # One hour later: the first sample falls out of the window.
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
