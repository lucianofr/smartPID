"""Tests for TwinTelemetry — telemetry for simulator loops no malha owns.

The bug this guards: a twin loop without a project controller reached no
consumer at all (empty /trend ring, no realtime frame), so every trend chart on
the Sim page stayed blank on a simulator-only deployment.
"""
from __future__ import annotations

import time
import uuid

import msgpack
import pytest

from smart_pid_core.application.event_bus import EventBus
from smart_pid_core.application.twin_telemetry import TwinTelemetry


class _FakeIOWorker:
    def __init__(self, controller_ids: list[int] | None = None) -> None:
        self.controller_ids = list(controller_ids or [])

    def add_controller(self, controller_id: int) -> None:
        if controller_id not in self.controller_ids:
            self.controller_ids.append(controller_id)

    def remove_controller(self, controller_id: int) -> None:
        if controller_id in self.controller_ids:
            self.controller_ids.remove(controller_id)


class _FakeLoopManager:
    def __init__(self, running: set[int] | None = None) -> None:
        self.running = set(running or ())

    def is_loop_running(self, controller_id: int) -> bool:
        return controller_id in self.running


class _FakeTwin:
    def __init__(self, ids: list[int]) -> None:
        self.ids = list(ids)

    def controller_ids(self) -> list[int]:
        return list(self.ids)


@pytest.fixture()
def bus():
    bus = EventBus(url_prefix=f"inproc://test-twin-{uuid.uuid4().hex[:8]}")
    bus.start()
    yield bus
    bus.stop()


def _telemetry(controller_id: int, pv: float, sp: float) -> bytes:
    signal = {"severity": "GOOD", "limit_bits": "NONE", "sub_status": "NONE"}
    return msgpack.packb({
        "controller_id": controller_id,
        "pv": {"value": pv, **signal},
        "sp": {"value": sp, **signal},
        "co": {"value": 0.0, **signal},
        "timestamp": time.time(),
    })


def test_unowned_twin_loop_gets_scanned_and_publishes_status(bus: EventBus) -> None:
    """The whole point: an unowned loop must reach the IO scan AND STATUS."""
    io = _FakeIOWorker()
    telemetry = TwinTelemetry(
        bus=bus,
        io_worker=io,
        loop_manager=_FakeLoopManager(),
        simulator_adapter=_FakeTwin([7]),
        scan_rate_s=0.05,
    )
    telemetry.reconcile()

    assert io.controller_ids == [7], "twin loop must join the IO scan"
    assert telemetry.attached_ids == frozenset({7})

    pub = bus.create_publisher()
    status_sub = bus.create_subscriber(b"STATUS.7")
    time.sleep(0.05)
    pub.send(b"TELEMETRY.7", _telemetry(7, pv=55.0, sp=50.0))

    deadline = time.monotonic() + 2.0
    data = None
    while time.monotonic() < deadline:
        msg = status_sub.recv(timeout_ms=100)
        if msg is not None:
            data = msgpack.unpackb(msg[1])
            break

    telemetry.stop_all()
    pub.close()
    status_sub.close()

    assert data is not None, "no STATUS published for the unowned twin loop"
    assert data["controller_id"] == 7
    assert data["error"] == pytest.approx(5.0)


def test_owned_loop_is_left_to_its_control_worker(bus: EventBus) -> None:
    """A malha's PID/Monitor worker already owns STATUS — never double up."""
    io = _FakeIOWorker([3])
    telemetry = TwinTelemetry(
        bus=bus,
        io_worker=io,
        loop_manager=_FakeLoopManager({3}),
        simulator_adapter=_FakeTwin([3]),
    )
    telemetry.reconcile()

    assert telemetry.attached_ids == frozenset()
    assert io.controller_ids == [3], "the malha's own IO registration must survive"


def test_malha_takeover_releases_status_but_keeps_the_scan(bus: EventBus) -> None:
    """Creating a malha for an attached twin id hands the loop over intact."""
    io = _FakeIOWorker()
    loops = _FakeLoopManager()
    telemetry = TwinTelemetry(
        bus=bus,
        io_worker=io,
        loop_manager=loops,
        simulator_adapter=_FakeTwin([5]),
        scan_rate_s=0.05,
    )
    telemetry.reconcile()
    assert telemetry.attached_ids == frozenset({5})

    loops.running.add(5)  # POST /controllers started a control loop for id 5
    telemetry.reconcile()

    assert telemetry.attached_ids == frozenset()
    assert io.controller_ids == [5], "the loop still needs TELEMETRY for its PID"


def test_deleted_twin_loop_drops_out_of_the_scan(bus: EventBus) -> None:
    io = _FakeIOWorker()
    twin = _FakeTwin([9])
    telemetry = TwinTelemetry(
        bus=bus,
        io_worker=io,
        loop_manager=_FakeLoopManager(),
        simulator_adapter=twin,
        scan_rate_s=0.05,
    )
    telemetry.reconcile()
    assert io.controller_ids == [9]

    twin.ids.clear()  # DELETE /simulator/loops/9
    telemetry.reconcile()

    assert telemetry.attached_ids == frozenset()
    assert io.controller_ids == [], "nothing left to scan for a loop that is gone"


def test_reconcile_is_idempotent(bus: EventBus) -> None:
    io = _FakeIOWorker()
    telemetry = TwinTelemetry(
        bus=bus,
        io_worker=io,
        loop_manager=_FakeLoopManager(),
        simulator_adapter=_FakeTwin([2]),
        scan_rate_s=0.05,
    )
    telemetry.reconcile()
    first = telemetry.attached_ids
    telemetry.reconcile()
    telemetry.reconcile()

    assert telemetry.attached_ids == first
    assert io.controller_ids == [2], "repeated reconciles must not stack registrations"
    telemetry.stop_all()
