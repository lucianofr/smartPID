"""In-memory circular trend buffer — the last hour of PV/SP/CO per loop.

One bounded deque per controller, fed from the TELEMETRY bus by
``TrendBufferWorker``. Real OPC-UA loops and simulator loops share the same
telemetry pipeline (IOWorker publishes ``TELEMETRY.{cid}`` for both), so a
single subscriber covers every loop registered in the system.

Two eviction rules make it circular:

* **time** — a sample older than ``RETENTION_S`` relative to the loop's newest
  sample is dropped on append, so the window is always "the last hour of
  process time", never a growing log;
* **count** — ``deque(maxlen=MAX_SAMPLES_PER_LOOP)`` sheds the oldest samples
  under rates above the sized-for scan cadence, the same contract
  ``DBWorker._buffer`` already honours.

This is deliberately separate from ``Log_Processo`` (7-day SQLite retention):
that table backs exports and long multitrend replays, this buffer backs the
HMI trend charts' "seed the window, then follow live" path via
``GET /trend/{controller_id}``.
"""
from __future__ import annotations

import threading
from collections import deque
from typing import NamedTuple

#: Window kept per loop, in seconds of process time.
RETENTION_S = 3600.0

#: Hard point cap per loop. Sized for a 10 Hz scan over the full retention
#: window plus headroom; the deque sheds oldest beyond it.
MAX_SAMPLES_PER_LOOP = 40_000


class TrendSample(NamedTuple):
    """One buffered PV/SP/CO reading; ``ts`` is epoch seconds (UTC)."""

    ts: float
    pv: float
    sp: float
    co: float


class TrendBuffer:
    """Thread-safe per-loop ring of :class:`TrendSample`.

    The writer is the trend-buffer worker thread; readers are uvicorn
    request handlers, so every public method takes the same lock.
    """

    def __init__(self, retention_s: float = RETENTION_S) -> None:
        self._retention_s = retention_s
        self._rings: dict[int, deque[TrendSample]] = {}
        self._lock = threading.Lock()

    def append(self, controller_id: int, ts: float, pv: float, sp: float, co: float) -> bool:
        """Append one sample; returns False when it was dropped.

        Drops mirror the frontend window buffer: non-finite or non-increasing
        ``ts`` (per loop) is a duplicate/out-of-order frame, not a sample.
        """
        if ts != ts or ts == float("inf") or ts == float("-inf"):
            return False
        with self._lock:
            ring = self._rings.get(controller_id)
            if ring is None:
                ring = deque(maxlen=MAX_SAMPLES_PER_LOOP)
                self._rings[controller_id] = ring
            elif ts <= ring[-1].ts:
                return False
            ring.append(TrendSample(ts, pv, sp, co))
            cutoff = ts - self._retention_s
            while ring and ring[0].ts < cutoff:
                ring.popleft()
            return True

    def query(self, controller_id: int, seconds: float) -> list[TrendSample]:
        """Newest ``seconds`` of samples for a loop, ascending by ``ts``.

        The right edge is the loop's newest buffered sample, not wall clock:
        a paused loop still returns its last hour instead of nothing.
        """
        with self._lock:
            ring = self._rings.get(controller_id)
            if not ring:
                return []
            cutoff = ring[-1].ts - seconds
            # Rings are append-ordered; find the first in-window index.
            start = 0
            n = len(ring)
            while start < n and ring[start].ts < cutoff:
                start += 1
            return [ring[i] for i in range(start, n)]

    def __len__(self) -> int:
        with self._lock:
            return sum(len(r) for r in self._rings.values())
