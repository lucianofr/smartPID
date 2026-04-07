"""Tests for BusBridge — QTimer drains SimpleQueue -> Qt signals."""
from queue import SimpleQueue

import pytest

from smart_pid_hmi.bus_bridge import BusBridge


@pytest.fixture
def bridge(qtbot):
    q = SimpleQueue()
    b = BusBridge(queue=q, refresh_ms=10)
    yield b
    b.stop()


def test_emits_telemetry_signal(bridge, qtbot):
    frame = {
        "controller_id": 1, "pv": 45.0, "sp": 50.0,
        "co": 62.0, "integral_val": 0.5,
        "timestamp": "2026-04-03T10:00:00", "status": "GOOD",
    }
    bridge._queue.put(("STATUS.1", frame))
    bridge.start()

    with qtbot.waitSignal(bridge.telemetry_received, timeout=500) as sig:
        pass
    assert sig.args[0] == 1  # controller_id
    assert sig.args[1]["pv"] == 45.0


def test_batches_same_controller(bridge, qtbot):
    """Multiple frames for same controller in one tick -> only last emitted."""
    for pv in [10.0, 20.0, 30.0]:
        frame = {
            "controller_id": 1, "pv": pv, "sp": 50.0,
            "co": 50.0, "integral_val": 0.0,
            "timestamp": "2026-04-03T10:00:00", "status": "GOOD",
        }
        bridge._queue.put(("STATUS.1", frame))

    received = []
    bridge.telemetry_received.connect(lambda cid, f: received.append(f["pv"]))
    bridge.start()
    qtbot.wait(100)

    # Should receive only the last value (30.0) for controller 1
    assert len(received) == 1
    assert received[0] == 30.0


def test_connection_lost_after_timeout(qtbot):
    q = SimpleQueue()
    b = BusBridge(queue=q, refresh_ms=10, heartbeat_timeout_s=0.1)
    b.start()
    # Put one frame to start heartbeat, then wait for timeout
    frame = {
        "controller_id": 1, "pv": 45.0, "sp": 50.0,
        "co": 62.0, "integral_val": 0.0,
        "timestamp": "2026-04-03T10:00:00", "status": "GOOD",
    }
    q.put(("STATUS.1", frame))
    qtbot.wait(50)

    with qtbot.waitSignal(b.connection_lost, timeout=1000):
        pass
    b.stop()


def test_normalizes_ff_signal_dicts_to_floats(bridge, qtbot):
    """FFSignal dicts from backend must be flattened to plain floats."""
    frame = {
        "controller_id": 1,
        "pv": {"value": 58.23, "severity": "GOOD", "limit_bits": "NONE", "sub_status": "NONE"},
        "sp": {"value": 60.0, "severity": "GOOD", "limit_bits": "NONE", "sub_status": "NONE"},
        "co": {"value": 48.88, "severity": "GOOD", "limit_bits": "NONE", "sub_status": "NONE"},
        "integral_val": 0.5,
        "timestamp": "2026-04-03T10:00:00",
    }
    bridge._queue.put(("STATUS.1", frame))
    bridge.start()

    with qtbot.waitSignal(bridge.telemetry_received, timeout=500) as sig:
        pass
    assert sig.args[0] == 1
    assert sig.args[1]["pv"] == 58.23
    assert sig.args[1]["sp"] == 60.0
    assert sig.args[1]["co"] == 48.88
    assert isinstance(sig.args[1]["pv"], float)


def test_latest_property(bridge, qtbot):
    frame = {
        "controller_id": 1, "pv": 45.0, "sp": 50.0,
        "co": 62.0, "integral_val": 0.5,
        "timestamp": "2026-04-03T10:00:00", "status": "GOOD",
    }
    bridge._queue.put(("STATUS.1", frame))
    bridge.start()
    qtbot.wait(100)

    latest = bridge.latest(1)
    assert latest is not None
    assert latest["pv"] == 45.0


def test_bus_bridge_has_system_event_signal():
    """BusBridge must have a system_event_received signal."""
    q = SimpleQueue()
    b = BusBridge(q)
    assert hasattr(b, "system_event_received")


def test_bus_bridge_routes_system_events(qtbot):
    """EVENT.SYSTEM messages should emit system_event_received."""
    q = SimpleQueue()
    b = BusBridge(q, refresh_ms=10)

    received = []
    b.system_event_received.connect(lambda data: received.append(data))

    q.put(("EVENT.SYSTEM", {
        "source": "BACKEND", "severity": "INFO",
        "message": "Started", "timestamp": "2026-04-07T12:00:00",
    }))

    b._drain()

    assert len(received) == 1
    assert received[0]["source"] == "BACKEND"
