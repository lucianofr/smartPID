"""In-memory circular trend buffer — the last 72 hours of PV/SP/CO per loop.

Four parallel ``array('d')`` columns per controller, fed from the TELEMETRY bus
by ``TrendBufferWorker``. Real OPC-UA loops and simulator loops share the same
telemetry pipeline (IOWorker publishes ``TELEMETRY.{cid}`` for both), so a
single subscriber covers every loop registered in the system.

Three rules make it circular and affordable:

* **cadence** — the scan publishes at 10 Hz (``scan_interval_s`` /
  ``simulator_interval_ms`` default to 100 ms) but a *trend* needs one sample
  per second, so a frame closer than ``TREND_INTERVAL_S`` to the newest stored
  sample is dropped on arrival. That guard also subsumes the duplicate and
  out-of-order cases (a non-increasing ``ts`` is never one interval ahead);
* **time** — a sample older than ``RETENTION_S`` relative to the loop's newest
  sample is dropped on append, so the window is always "the last 72 hours of
  process time", never a growing log;
* **count** — ``MAX_SAMPLES_PER_LOOP`` is the hard cap the columns are trimmed
  to, the same contract ``DBWorker._buffer`` already honours. It MUST stay at
  or above ``RETENTION_S / TREND_INTERVAL_S``, otherwise the ring would serve a
  shorter span than ``/trend`` advertises — a chart drawing less than its own
  axis claims, with nothing on screen to say so.

Columns rather than a ``deque`` of sample objects because that is what makes
72 h fit: a boxed 4-float tuple costs a measured 128 B/sample against 32 B for
four ``'d'`` slots, so the full 72 h ring is 8.3 MB/loop instead of 33 MB —
less than the 1 h ring of tuples it replaces. Trimming is one ``del col[:k]``
memmove per evicted sample, measured at 277 us (0.03 % of a core at 1 Hz).

This is deliberately separate from ``Log_Processo`` (7-day SQLite retention):
that table backs exports and long multitrend replays, this buffer backs the
HMI trend charts' "seed the window, then follow live" path via
``GET /trend/{controller_id}``. The chart's *selectable* window is clamped well
below ``RETENTION_S`` by the frontend (``TREND_WINDOW_MAX_S``); the rest of the
ring is the backlog a future pan-to-the-past control will read.
"""
from __future__ import annotations

import threading
import time
from array import array
from bisect import bisect_left
from collections.abc import Iterable
from typing import NamedTuple

#: Window kept per loop, in seconds of process time.
RETENTION_S = 259_200.0  # 72 h

#: Minimum spacing between stored samples — the 10 Hz scan is thinned to this.
TREND_INTERVAL_S = 1.0

#: Window pre-filled from ``Log_Processo`` at startup, so a daemon restart does
#: not blank every chart. Deliberately a slice of ``RETENTION_S``: the bucketed
#: historian scan costs ~0.4 s per loop per 12 h, and this runs before the PID
#: loops start, so hydrating the whole ring would put tens of seconds between
#: boot and control. The rest of the window refills live.
HYDRATE_S = 3_600.0

#: Hard point cap per loop; the columns are trimmed to it. Sized for the full
#: retention window at the ingest cadence, plus headroom.
MAX_SAMPLES_PER_LOOP = 280_000


class TrendSample(NamedTuple):
    """One buffered PV/SP/CO reading; ``ts`` is epoch seconds (UTC)."""

    ts: float
    pv: float
    sp: float
    co: float


#: Per-loop storage: parallel columns of ts, pv, sp, co.
_Columns = tuple["array[float]", "array[float]", "array[float]", "array[float]"]


class TrendBuffer:
    """Thread-safe per-loop ring of :class:`TrendSample`.

    The writer is the trend-buffer worker thread; readers are uvicorn
    request handlers, so every public method takes the same lock.
    """

    def __init__(self, retention_s: float = RETENTION_S) -> None:
        self._retention_s = retention_s
        self._rings: dict[int, _Columns] = {}
        #: Earliest epoch already requested from the historian per loop, so a
        #: window the database could not satisfy is not re-queried on every
        #: chart mount. Log_Processo only ever gains NEWER rows, so "we already
        #: asked back to T" stays true for the life of the process.
        self._filled_from: dict[int, float] = {}
        self._lock = threading.Lock()

    def append(self, controller_id: int, ts: float, pv: float, sp: float, co: float) -> bool:
        """Append one sample; returns False when it was dropped.

        Drops are the frontend window buffer's own rules plus the ingest
        cadence: a non-finite ``ts``, or one less than ``TREND_INTERVAL_S``
        past the newest stored sample — which covers duplicate, out-of-order
        and merely faster-than-1-Hz frames alike.
        """
        if ts != ts or ts == float("inf") or ts == float("-inf"):
            return False
        # Coerce BEFORE touching any column. ``array('d').append`` raises on a
        # non-float, and a raise between the four appends would leave the
        # columns at different lengths for good — every later query would walk
        # off the short one and 500 that loop until restart. Failing here makes
        # equal column lengths structural rather than caller discipline.
        pv, sp, co = float(pv), float(sp), float(co)
        with self._lock:
            cols = self._rings.get(controller_id)
            if cols is None:
                cols = (array("d"), array("d"), array("d"), array("d"))
                self._rings[controller_id] = cols
            ts_col, pv_col, sp_col, co_col = cols
            if ts_col and ts - ts_col[-1] < TREND_INTERVAL_S:
                return False
            ts_col.append(ts)
            pv_col.append(pv)
            sp_col.append(sp)
            co_col.append(co)

            # Columns are append-ordered and strictly increasing, so the first
            # in-window index is a bisect, not a scan.
            drop = bisect_left(ts_col, ts - self._retention_s)
            overflow = len(ts_col) - drop - MAX_SAMPLES_PER_LOOP
            if overflow > 0:
                drop += overflow
            if drop:
                del ts_col[:drop]
                del pv_col[:drop]
                del sp_col[:drop]
                del co_col[:drop]
            return True

    def query(self, controller_id: int, seconds: float) -> list[TrendSample]:
        """Newest ``seconds`` of samples for a loop, ascending by ``ts``.

        The right edge is the loop's newest buffered sample, not wall clock:
        a paused loop still returns its last window instead of nothing.
        """
        with self._lock:
            cols = self._rings.get(controller_id)
            if cols is None:
                return []
            ts_col, pv_col, sp_col, co_col = cols
            n = len(ts_col)
            if n == 0:
                return []
            start = bisect_left(ts_col, ts_col[n - 1] - seconds)
            return [
                TrendSample(ts_col[i], pv_col[i], sp_col[i], co_col[i])
                for i in range(start, n)
            ]

    def gap(self, controller_id: int, seconds: float) -> tuple[float, float] | None:
        """Epoch range still missing to serve a ``seconds`` window, or None.

        The ring is pre-filled with only ``HYDRATE_S`` at boot and then grows
        live, so for a while after a restart it holds less than the operator can
        ask for. This reports the ``(start, end)`` a caller should read from the
        historian and hand to :meth:`backfill`; None means the window is already
        covered, or that this depth was already asked for and the database had
        nothing more.

        Recording the attempt is what keeps the slow path rare: the fill happens
        once per loop per depth, not once per chart mount.
        """
        with self._lock:
            cols = self._rings.get(controller_id)
            if cols is None or not cols[0]:
                # Nothing buffered for this loop: the whole window is missing
                # and there is no newest sample, so wall clock is the right edge.
                end = time.time()
                start = end - seconds
            else:
                ts_col = cols[0]
                # Read up to the oldest sample held; the live path owns newer.
                end = ts_col[0]
                start = ts_col[-1] - seconds
            if start >= end - TREND_INTERVAL_S:
                return None
            tried = self._filled_from.get(controller_id)
            if tried is not None and start >= tried - TREND_INTERVAL_S:
                return None
            self._filled_from[controller_id] = start
            return (start, end)

    def backfill(
        self, controller_id: int, samples: Iterable[tuple[float, float, float, float]]
    ) -> int:
        """Insert historian samples at the OLD end; returns how many were kept.

        The counterpart of :meth:`append`, which owns the new end and drops
        anything not newer than what it already holds — so replaying history
        through it would store nothing. The two never contend for the same end
        of the columns.

        Samples are expected ascending; anything newer than the current oldest,
        older than the retention window, or closer than ``TREND_INTERVAL_S`` to
        its kept predecessor is dropped. That last rule is why a bucketed
        historian read does not need to guarantee spacing itself.
        """
        with self._lock:
            cols = self._rings.get(controller_id)
            if cols is None:
                cols = (array("d"), array("d"), array("d"), array("d"))
                self._rings[controller_id] = cols
            ts_col, pv_col, sp_col, co_col = cols
            if ts_col:
                newest_allowed = ts_col[0] - TREND_INTERVAL_S
                floor = ts_col[-1] - self._retention_s
            else:
                newest_allowed = float("inf")
                floor = float("-inf")

            # Build in temporaries: a bad value raises before the ring is
            # touched, so the four columns cannot end up at different lengths.
            new = (array("d"), array("d"), array("d"), array("d"))
            for ts, pv, sp, co in samples:
                if ts != ts or ts == float("inf") or ts == float("-inf"):
                    continue
                if ts > newest_allowed or ts < floor:
                    continue
                if new[0] and ts - new[0][-1] < TREND_INTERVAL_S:
                    continue
                new[0].append(ts)
                new[1].append(float(pv))
                new[2].append(float(sp))
                new[3].append(float(co))
            if not new[0]:
                return 0

            ts_col[:0] = new[0]
            pv_col[:0] = new[1]
            sp_col[:0] = new[2]
            co_col[:0] = new[3]
            overflow = len(ts_col) - MAX_SAMPLES_PER_LOOP
            if overflow > 0:
                del ts_col[:overflow]
                del pv_col[:overflow]
                del sp_col[:overflow]
                del co_col[:overflow]
            return len(new[0])

    def __len__(self) -> int:
        with self._lock:
            return sum(len(cols[0]) for cols in self._rings.values())
