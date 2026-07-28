"""Integration tests for StatsWorker — bus subscriber."""
from __future__ import annotations

import time
import uuid

import msgpack
import pytest

from smart_pid_core.application.event_bus import EventBus
from smart_pid_core.application.workers.stats_worker import StatsWorker
from smart_pid_domain.enums import ProcessSpeed
from smart_pid_domain.models.controller import Controller, ScaleConfig


@pytest.fixture
def bus():
    b = EventBus(url_prefix=f"inproc://test_stats_{uuid.uuid4().hex[:8]}")
    b.start()
    yield b
    b.stop()


@pytest.fixture
def controller():
    return Controller(
        id=1, name="Test", scan_rate_s=0.1,
        pv_scale=ScaleConfig(eu_min=0.0, eu_max=100.0),
        process_speed=ProcessSpeed.ULTRA_FAST,
    )


class TestStatsWorker:
    def test_publishes_stats_after_samples(self, bus, controller):
        worker = StatsWorker(bus=bus, controller=controller)
        # Production cadence is one STATS per 5 s of samples
        # (_publish_interval = 5.0 / scan_rate_s = 50 ticks here); shorten it
        # so the assertion does not need a 5 s sleep.
        worker._publish_interval = 10
        worker.start()
        try:
            pub = bus.create_publisher()
            sub = bus.create_subscriber(f"STATS.{controller.id}".encode())
            time.sleep(0.05)

            # Send enough samples to trigger publish (window=50, interval=10)
            for i in range(12):
                telem = {"pv": 52.0, "sp": 50.0, "co": 48.0 + i}
                pub.send(
                    f"TELEMETRY.{controller.id}".encode(),
                    msgpack.packb(telem),
                )
                action = {"controller_id": 1, "co": 48.0 + i, "integral_val": 25.0}
                pub.send(
                    f"ACTION.CTRL.{controller.id}".encode(),
                    msgpack.packb(action),
                )
                time.sleep(0.1)

            # Should have published at least one STATS message
            time.sleep(0.2)
            msg = sub.recv(timeout_ms=1000)
            assert msg is not None
            _topic, payload = msg
            data = msgpack.unpackb(payload)
            assert "iae" in data
            assert "total_variation" in data
            assert data["controller_id"] == 1
        finally:
            worker.stop()

    def test_get_current_stats(self, bus, controller):
        worker = StatsWorker(bus=bus, controller=controller)
        worker.start()
        try:
            pub = bus.create_publisher()
            time.sleep(0.05)

            for _ in range(3):
                telem = {"pv": 55.0, "sp": 50.0, "co": 50.0}
                pub.send(
                    f"TELEMETRY.{controller.id}".encode(),
                    msgpack.packb(telem),
                )
                time.sleep(0.15)

            stats = worker.get_current_stats()
            assert stats["iae"] > 0.0
        finally:
            worker.stop()
