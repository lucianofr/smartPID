"""Tests for MonitorWorker — enriches telemetry and publishes STATUS."""
from __future__ import annotations

import time

import msgpack
import pytest

from smart_pid_core.application.event_bus import EventBus
from smart_pid_core.application.workers.monitor_worker import MonitorWorker


def _signal(value: float = 0.0, limit: str = "NONE") -> dict:
    return {
        "value": value,
        "severity": "GOOD",
        "limit_bits": limit,
        "sub_status": "NONE",
    }


def _make_telemetry(
    controller_id: int = 1,
    pv: float = 50.0,
    sp: float = 50.0,
    co: float = 50.0,
    co_limit: str = "NONE",
) -> dict:
    return {
        "controller_id": controller_id,
        "pv": _signal(pv),
        "sp": _signal(sp),
        "co": _signal(co, limit=co_limit),
        "bkcal_in": _signal(0.0),
        "bkcal_out": _signal(0.0),
        "integral_val": 0.0,
        "timestamp": time.time(),
    }


class TestMonitorWorkerEnrich:
    """Unit tests for the static _enrich method (no ZMQ needed)."""

    def test_error_calculation(self) -> None:
        telem = _make_telemetry(pv=55.0, sp=50.0)
        result = MonitorWorker._enrich(telem)
        assert result["error"] == pytest.approx(5.0)
        assert result["saturated"] is False

    def test_negative_error(self) -> None:
        telem = _make_telemetry(pv=45.0, sp=50.0)
        result = MonitorWorker._enrich(telem)
        assert result["error"] == pytest.approx(-5.0)

    def test_zero_error(self) -> None:
        telem = _make_telemetry(pv=50.0, sp=50.0)
        result = MonitorWorker._enrich(telem)
        assert result["error"] == pytest.approx(0.0)

    def test_high_saturation(self) -> None:
        telem = _make_telemetry(co=100.0, co_limit="HIGH_LIMITED")
        result = MonitorWorker._enrich(telem)
        assert result["saturated"] is True

    def test_low_saturation(self) -> None:
        telem = _make_telemetry(co=0.0, co_limit="LOW_LIMITED")
        result = MonitorWorker._enrich(telem)
        assert result["saturated"] is True

    def test_no_saturation(self) -> None:
        telem = _make_telemetry(co=50.0, co_limit="NONE")
        result = MonitorWorker._enrich(telem)
        assert result["saturated"] is False

    def test_preserves_all_fields(self) -> None:
        telem = _make_telemetry(pv=60.0, sp=50.0, co=70.0)
        result = MonitorWorker._enrich(telem)
        assert result["controller_id"] == 1
        assert result["pv"]["value"] == 60.0
        assert result["sp"]["value"] == 50.0
        assert result["co"]["value"] == 70.0
        assert "bkcal_in" in result
        assert "bkcal_out" in result
        assert "integral_val" in result
        assert "timestamp" in result

    def test_missing_bkcal_uses_defaults(self) -> None:
        telem = {
            "controller_id": 1,
            "pv": _signal(50.0),
            "sp": _signal(50.0),
            "co": _signal(50.0),
            "integral_val": 0.0,
            "timestamp": time.time(),
        }
        result = MonitorWorker._enrich(telem)
        assert result["bkcal_in"]["value"] == 0.0
        assert result["bkcal_out"]["value"] == 0.0

    def test_plain_float_signals(self) -> None:
        """Backward compat: plain float values instead of dicts."""
        telem = {
            "controller_id": 1,
            "pv": 55.0,
            "sp": 50.0,
            "co": 75.0,
            "timestamp": time.time(),
        }
        result = MonitorWorker._enrich(telem)
        assert result["error"] == pytest.approx(5.0)
        assert result["saturated"] is False


class TestMonitorWorkerIntegration:
    """Integration tests using a real EventBus (XPUB/XSUB proxy)."""

    @pytest.fixture()
    def bus(self):
        """Create and start a unique EventBus for each test."""
        import uuid
        bus = EventBus(url_prefix=f"inproc://test-monitor-{uuid.uuid4().hex[:8]}")
        bus.start()
        yield bus
        bus.stop()

    def test_publishes_status_with_error(self, bus: EventBus) -> None:
        worker = MonitorWorker(bus=bus, controller_id=1, scan_rate_ms=50)
        worker.start()

        pub = bus.create_publisher()
        status_sub = bus.create_subscriber(b"STATUS.1")
        time.sleep(0.05)  # let subscriptions propagate

        pub.send(b"TELEMETRY.1", msgpack.packb(_make_telemetry(pv=55.0, sp=50.0)))

        # Poll for STATUS message
        deadline = time.monotonic() + 2.0
        data = None
        while time.monotonic() < deadline:
            msg = status_sub.recv(timeout_ms=100)
            if msg is not None:
                _topic, payload = msg
                data = msgpack.unpackb(payload)
                break

        worker.stop()
        pub.close()
        status_sub.close()

        assert data is not None, "No STATUS message received within 2s"
        assert data["error"] == pytest.approx(5.0)
        assert data["saturated"] is False
        assert data["controller_id"] == 1

    def test_detects_saturation(self, bus: EventBus) -> None:
        worker = MonitorWorker(bus=bus, controller_id=1, scan_rate_ms=50)
        worker.start()

        pub = bus.create_publisher()
        status_sub = bus.create_subscriber(b"STATUS.1")
        time.sleep(0.05)

        pub.send(
            b"TELEMETRY.1",
            msgpack.packb(_make_telemetry(co=100.0, co_limit="HIGH_LIMITED")),
        )

        deadline = time.monotonic() + 2.0
        data = None
        while time.monotonic() < deadline:
            msg = status_sub.recv(timeout_ms=100)
            if msg is not None:
                _topic, payload = msg
                data = msgpack.unpackb(payload)
                break

        worker.stop()
        pub.close()
        status_sub.close()

        assert data is not None, "No STATUS message received within 2s"
        assert data["saturated"] is True

    def test_drains_to_latest(self, bus: EventBus) -> None:
        """When multiple TELEMETRY messages queue up, only the latest is used."""
        # Use a long scan rate so the worker doesn't process between sends
        worker = MonitorWorker(bus=bus, controller_id=1, scan_rate_ms=2000)
        worker.start()

        pub = bus.create_publisher()
        status_sub = bus.create_subscriber(b"STATUS.1")
        time.sleep(0.1)  # let subscriptions propagate and worker block on first poll

        # Burst multiple telemetry messages — worker should drain to latest
        for pv in [10.0, 20.0, 30.0]:
            pub.send(b"TELEMETRY.1", msgpack.packb(_make_telemetry(pv=pv, sp=50.0)))
        time.sleep(0.05)  # let messages arrive at worker's SUB socket

        # Now stop and restart with fast scan to process
        worker.stop()
        worker = MonitorWorker(bus=bus, controller_id=1, scan_rate_ms=50)
        worker.start()
        time.sleep(0.05)

        # Re-send burst — this time the fast worker will drain them
        for pv in [10.0, 20.0, 30.0]:
            pub.send(b"TELEMETRY.1", msgpack.packb(_make_telemetry(pv=pv, sp=50.0)))

        deadline = time.monotonic() + 2.0
        data = None
        while time.monotonic() < deadline:
            msg = status_sub.recv(timeout_ms=100)
            if msg is not None:
                _topic, payload = msg
                data = msgpack.unpackb(payload)
                break

        worker.stop()
        pub.close()
        status_sub.close()

        assert data is not None, "No STATUS message received within 2s"
        # Should have the latest PV (30.0), error = 30.0 - 50.0 = -20.0
        assert data["error"] == pytest.approx(-20.0)

    def test_stop_is_clean(self, bus: EventBus) -> None:
        worker = MonitorWorker(bus=bus, controller_id=1, scan_rate_ms=50)
        worker.start()
        assert worker.is_alive()
        worker.stop()
        assert not worker.is_alive()
