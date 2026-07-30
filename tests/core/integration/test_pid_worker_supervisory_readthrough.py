"""SUPERVISORY status frames must report the monitored controller, not SmartPID.

In SUPERVISORY the DCS runs the loop and SmartPID only observes it — the IO
worker never writes CO (`pid_worker.py`, the ACTION.CTRL comment). So CO in a
STATUS frame is a *measurement* of the DCS controller's output, exactly as PV
is a measurement of the process, and `mode` is the DCS's mode.

Both were wrong. CO was seeded from the first telemetry frame only and never
refreshed; since MAN is the default mode and the one branch that never
reassigns `_last_co`, every STATUS frame published a GOOD 0.0 forever — a dead
CO bar on the operator screen while the twin's valve moved. `mode` published
PIDWorker's own internal mode, which only moves on a REST `set_mode`.

DDC is the other half of the contract and must not change: there SmartPID
computes CO and owns it, so telemetry may only seed it.
"""
from __future__ import annotations

import time
import uuid

import msgpack
import pytest

from smart_pid_core.application.event_bus import EventBus
from smart_pid_core.application.workers.pid_worker import PIDWorker
from smart_pid_core.domain.services.pid_engine import PIDEngine
from smart_pid_core.domain.services.pid_mode_manager import ModeManager
from smart_pid_domain.enums import ControllerMode, ExecutionMode, SignalSeverity
from smart_pid_domain.models.controller import Controller, PIDParams


def _make_bus() -> EventBus:
    bus = EventBus(url_prefix=f"inproc://test_{uuid.uuid4().hex[:8]}")
    bus.start()
    return bus


def _make_worker(
    bus: EventBus, execution_mode: ExecutionMode,
) -> tuple[PIDWorker, Controller]:
    ctrl = Controller(
        id=1, name="T-SUP", scan_rate_s=0.05,
        pid_params=PIDParams(gain=1.0, reset=10.0),
        execution_mode=execution_mode,
    )
    worker = PIDWorker(
        bus=bus, controller=ctrl, engine=PIDEngine(), mode_manager=ModeManager(),
    )
    return worker, ctrl


def _send(pub, **fields: object) -> None:  # noqa: ANN001
    """Publish one TELEMETRY frame, CO carrying full FF signal semantics."""
    data: dict = {"pv": 50.0, "sp": 50.0, **fields}
    pub.send(b"TELEMETRY.1", msgpack.packb(data))


def _last_status(sub, max_frames: int = 40) -> dict | None:  # noqa: ANN001
    """Return the most recent STATUS.1 frame.

    Bounded: the worker republishes every scan, so an unbounded
    drain-until-empty never terminates.
    """
    latest = None
    for _ in range(max_frames):
        msg = sub.recv(timeout_ms=2000 if latest is None else 100)
        if msg is None:
            break
        latest = msgpack.unpackb(msg[1])
    return latest


class TestSupervisoryCOReadThrough:
    def test_co_follows_every_frame_not_just_the_first(self) -> None:
        """The reported bug: first frame 0.0, then the twin's output moves.

        Pre-fix `_last_co` was frozen at the seed, so STATUS.co stayed 0.0.
        """
        bus = _make_bus()
        worker, _ = _make_worker(bus, ExecutionMode.SUPERVISORY)
        try:
            worker.start()
            pub = bus.create_publisher()
            sub = bus.create_subscriber(b"STATUS.1")
            time.sleep(0.05)

            _send(pub, co=0.0)      # startup: twin's last_co is 0.0
            time.sleep(0.15)
            _send(pub, co=100.0)    # twin's controller drives the valve open
            time.sleep(0.2)

            status = _last_status(sub)
            assert status is not None
            assert status["co"]["value"] == pytest.approx(100.0, abs=0.1)
        finally:
            worker.stop()
            bus.stop()

    def test_integral_val_tracks_co(self) -> None:
        """MAN seeds PID state from _last_co, so a frozen CO froze this too."""
        bus = _make_bus()
        worker, _ = _make_worker(bus, ExecutionMode.SUPERVISORY)
        try:
            worker.start()
            pub = bus.create_publisher()
            sub = bus.create_subscriber(b"STATUS.1")
            time.sleep(0.05)

            _send(pub, co=0.0)
            time.sleep(0.15)
            _send(pub, co=64.0)
            time.sleep(0.2)

            status = _last_status(sub)
            assert status is not None
            assert status["integral_val"] == pytest.approx(64.0, abs=0.5)
        finally:
            worker.stop()
            bus.stop()

    def test_bad_quality_propagates_from_the_source(self) -> None:
        """A read-through of a measurement must carry its quality, not launder it."""
        bus = _make_bus()
        worker, _ = _make_worker(bus, ExecutionMode.SUPERVISORY)
        try:
            worker.start()
            pub = bus.create_publisher()
            sub = bus.create_subscriber(b"STATUS.1")
            time.sleep(0.05)

            _send(pub, co={"value": 42.0, "severity": SignalSeverity.BAD.value})
            time.sleep(0.2)

            status = _last_status(sub)
            assert status is not None
            assert status["co"]["severity"] == SignalSeverity.BAD.value
        finally:
            worker.stop()
            bus.stop()

    def test_ddc_keeps_seed_only_ownership(self) -> None:
        """The other half of the contract: in DDC SmartPID owns CO.

        Guards against the read-through being applied unconditionally, which
        would let a stale PLC CO node clobber the operator's set_output.
        """
        bus = _make_bus()
        worker, _ = _make_worker(bus, ExecutionMode.DDC)
        try:
            worker.start()
            pub = bus.create_publisher()
            sub = bus.create_subscriber(b"STATUS.1")
            time.sleep(0.05)

            _send(pub, co=10.0)
            time.sleep(0.15)
            worker.set_output(42.0)
            _send(pub, co=99.0)     # must NOT win
            time.sleep(0.2)

            status = _last_status(sub)
            assert status is not None
            assert status["co"]["value"] == pytest.approx(42.0, abs=0.1)
        finally:
            worker.stop()
            bus.stop()


class TestSupervisoryModeReporting:
    def test_status_reports_the_monitored_controllers_mode(self) -> None:
        """Pre-fix this was PIDWorker's internal mode — MAN, always."""
        bus = _make_bus()
        worker, _ = _make_worker(bus, ExecutionMode.SUPERVISORY)
        try:
            worker.start()
            pub = bus.create_publisher()
            sub = bus.create_subscriber(b"STATUS.1")
            time.sleep(0.05)

            _send(pub, co=50.0, mode="AUTO")
            time.sleep(0.2)

            status = _last_status(sub)
            assert status is not None
            assert status["mode"] == "AUTO"
        finally:
            worker.stop()
            bus.stop()

    def test_falls_back_to_internal_mode_when_producer_supplies_none(self) -> None:
        """No mode in telemetry is not evidence the DCS is in MAN."""
        bus = _make_bus()
        worker, _ = _make_worker(bus, ExecutionMode.SUPERVISORY)
        try:
            worker.set_mode(ControllerMode.AUTO)
            worker.start()
            pub = bus.create_publisher()
            sub = bus.create_subscriber(b"STATUS.1")
            time.sleep(0.05)

            _send(pub, co=50.0)  # no "mode" key
            time.sleep(0.2)

            status = _last_status(sub)
            assert status is not None
            assert status["mode"] == ControllerMode.AUTO.value
        finally:
            worker.stop()
            bus.stop()

    def test_ddc_reports_smartpids_own_mode(self) -> None:
        """In DDC SmartPID owns the loop, so its mode is the one that matters."""
        bus = _make_bus()
        worker, _ = _make_worker(bus, ExecutionMode.DDC)
        try:
            worker.start()
            pub = bus.create_publisher()
            sub = bus.create_subscriber(b"STATUS.1")
            time.sleep(0.05)

            _send(pub, co=50.0, mode="AUTO")  # the PLC's mode is not ours
            time.sleep(0.2)

            status = _last_status(sub)
            assert status is not None
            assert status["mode"] == ControllerMode.MAN.value
        finally:
            worker.stop()
            bus.stop()
