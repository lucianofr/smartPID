"""Integration tests for AIWorker — bus subscriber with Fuzzy/RL engine."""
from __future__ import annotations

import time
import uuid

import msgpack
import pytest

from smart_pid_core.application.event_bus import EventBus
from smart_pid_core.application.workers.ai_worker import AIWorker
from smart_pid_domain.enums import AIEngine, ControlObjective, ProcessSpeed
from smart_pid_domain.models.controller import AIConfig, Controller, ScaleConfig


@pytest.fixture
def bus():
    b = EventBus(url_prefix=f"inproc://test_ai_{uuid.uuid4().hex[:8]}")
    b.start()
    yield b
    b.stop()


@pytest.fixture
def controller_fuzzy():
    return Controller(
        id=1, name="TestFuzzy", scan_rate_ms=100,
        process_speed=ProcessSpeed.MEDIUM,
        pv_scale=ScaleConfig(eu_min=0.0, eu_max=100.0),
        ai_config=AIConfig(
            engine=AIEngine.FUZZY,
            objective=ControlObjective.SP_TRACKING,
            dead_time_l=0.1,  # T_cycle = 0.3s for fast testing
            limit_min=0.1,
            limit_max=100.0,
        ),
    )


class TestAIWorkerFuzzy:
    def test_publishes_ai_action(self, bus, controller_fuzzy):
        worker = AIWorker(bus=bus, controller=controller_fuzzy)
        worker.start()
        try:
            pub = bus.create_publisher()
            sub = bus.create_subscriber(f"ACTION.AI.{controller_fuzzy.id}".encode())
            time.sleep(0.05)

            # Send telemetry samples with AUTO mode
            for _ in range(5):
                telem = {"pv": 55.0, "sp": 50.0, "co": 48.0, "mode": "AUTO"}
                pub.send(
                    f"TELEMETRY.{controller_fuzzy.id}".encode(),
                    msgpack.packb(telem),
                )
                time.sleep(0.05)

            # Send STATS to trigger AI evaluation
            stats = {"controller_id": controller_fuzzy.id, "iae": 1.0}
            pub.send(
                f"STATS.{controller_fuzzy.id}".encode(),
                msgpack.packb(stats),
            )

            msg = sub.recv(timeout_ms=2000)
            assert msg is not None
            _topic, payload = msg
            data = msgpack.unpackb(payload)
            assert data["controller_id"] == 1
            assert "gamma" in data
            assert "new_ki" in data
            assert "engine" in data
            assert data["engine"] == "FUZZY"
        finally:
            worker.stop()

    def test_none_engine_does_not_start(self, bus):
        ctrl = Controller(
            id=2, name="TestNone", scan_rate_ms=100,
            ai_config=AIConfig(engine=AIEngine.NONE),
        )
        worker = AIWorker(bus=bus, controller=ctrl)
        worker.start()
        assert not worker.is_alive()  # Should not start with NONE engine
        worker.stop()
