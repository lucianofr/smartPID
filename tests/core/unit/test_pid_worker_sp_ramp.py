"""SP rate limiting (SP_WRK) and the `sp_ramping` flag on STATUS.

`sp_rate_up` / `sp_rate_dn` were persisted, exposed over REST and editable in
the HMI, but no worker ever called ``PIDEngine.apply_sp_ramp`` -- so the ramp
never happened and ``STATUS.{id}`` never carried ``sp_ramping``. AlarmWorker
reads that key to suppress deviation alarms during a ramp (alarm_engine.py),
so its absence also made the suppression dead code.
"""
from __future__ import annotations

import msgpack

from smart_pid_core.application.workers.pid_worker import PIDWorker
from smart_pid_core.domain.services.pid_engine import PIDEngine
from smart_pid_core.domain.services.pid_mode_manager import ModeManager
from smart_pid_domain.enums import ControllerMode
from smart_pid_domain.models.controller import Controller, PIDParams
from smart_pid_domain.models.signal import FFSignal

SCAN_S = 0.05


class _RecordingEngine(PIDEngine):
    """Captures the SP the PID actually chased on each scan."""

    def __init__(self) -> None:
        super().__init__()
        self.seen_sp: list[float] = []

    def compute(self, *args, **kwargs):  # noqa: ANN002, ANN003, ANN201
        self.seen_sp.append(kwargs["sp"].value)
        return super().compute(*args, **kwargs)


class _NullSub:
    @staticmethod
    def recv(timeout_ms: int = 0) -> None:  # noqa: ARG004
        return None


class _CapturingPub:
    """Collects published frames and stops the loop after N STATUS frames."""

    def __init__(self, worker: PIDWorker, scans: int) -> None:
        self._worker = worker
        self._scans = scans
        self.status: list[dict] = []

    def send(self, topic: bytes, payload: bytes) -> None:
        if topic.startswith(b"STATUS."):
            self.status.append(msgpack.unpackb(payload))
            if len(self.status) >= self._scans:
                self._worker._stop_event.set()


def _worker(rate_up: float = 0.0, rate_dn: float = 0.0) -> PIDWorker:
    controller = Controller(
        id=1,
        name="TIC-101",
        pid_params=PIDParams(gain=1.0, reset=10.0, rate=0.0),
        scan_rate_s=SCAN_S,
        # The shed watchdog would force MAN before the first scan otherwise:
        # _last_telem_time is 0.0 on a worker fed by hand.
        shed_time_s=0.0,
        sp_rate_up=rate_up,
        sp_rate_dn=rate_dn,
    )
    worker = PIDWorker(
        bus=None,
        controller=controller,
        engine=_RecordingEngine(),
        mode_manager=ModeManager(),
    )
    worker._mode = ControllerMode.AUTO
    worker._has_telemetry = True
    worker._last_pv = FFSignal.good(50.0)
    worker._last_sp = FFSignal.good(50.0)
    return worker


def _run(worker: PIDWorker, scans: int) -> _CapturingPub:
    pub = _CapturingPub(worker, scans)
    sub = _NullSub()
    worker._loop(sub, sub, sub, pub, scan_s=SCAN_S)
    return pub


def _step_sp(worker: PIDWorker, target: float) -> None:
    """Settle one scan in AUTO (seeds SP_WRK at the SP in force), then step.

    Entering a closed-loop mode must NOT ramp: the seed is the setpoint that
    is already in force. Only a step written afterwards travels.
    """
    _run(worker, scans=1)
    assert worker._sp_working == worker._last_sp.value, "mode entry must not ramp"
    worker._engine.seen_sp.clear()
    worker._stop_event.clear()
    worker._last_sp = FFSignal.good(target)



def test_ramp_walks_the_setpoint_and_flags_the_travel() -> None:
    # 20 EU/s over a 0.05 s scan = 1.0 EU per scan: 50 -> 51 -> 52 (arrived).
    worker = _worker(rate_up=20.0)
    _step_sp(worker, 52.0)
    pub = _run(worker, scans=2)

    assert [f["sp_ramping"] for f in pub.status] == [True, False]
    assert worker._engine.seen_sp == [51.0, 52.0]
    assert worker._sp_working == 52.0
    # The TARGET is what STATUS reports and what the next scan ramps toward;
    # feeding the working value back would collapse the ramp to one scan.
    assert [f["sp"]["value"] for f in pub.status] == [52.0, 52.0]


def test_ramp_down_is_rate_limited_too() -> None:
    worker = _worker(rate_dn=20.0)
    _step_sp(worker, 48.0)
    pub = _run(worker, scans=2)

    assert [f["sp_ramping"] for f in pub.status] == [True, False]
    assert worker._engine.seen_sp == [49.0, 48.0]


def test_zero_rate_is_an_immediate_setpoint_and_never_flags() -> None:
    worker = _worker()  # both rates 0 = no limiting (the default loop)
    _step_sp(worker, 52.0)
    pub = _run(worker, scans=1)

    assert pub.status[0]["sp_ramping"] is False
    assert worker._engine.seen_sp == [52.0]


def test_leaving_closed_loop_rearms_the_ramp() -> None:
    """A stale SP_WRK captured before MAN must not resume the old travel."""
    worker = _worker(rate_up=20.0)
    _step_sp(worker, 52.0)
    _run(worker, scans=1)
    assert worker._sp_working == 51.0

    worker._mode = ControllerMode.MAN
    worker._stop_event.clear()
    _run(worker, scans=1)

    assert worker._sp_working is None
