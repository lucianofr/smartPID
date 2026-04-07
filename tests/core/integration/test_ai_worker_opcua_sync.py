"""Tests for AIWorker OPC-UA synchronization.

Rule: Before each AI inference cycle, the AI worker MUST use the latest
Ti/Ki value from OPC-UA telemetry (not a stale internal accumulator).
Rule: After computing a new Ti/Ki, the IO worker writes it back via OPC-UA.
"""
from __future__ import annotations

import time
import uuid

import msgpack
import pytest

from smart_pid_core.application.event_bus import EventBus
from smart_pid_core.application.workers.ai_worker import AIWorker
from smart_pid_domain.enums import AIEngine, ControlObjective, ProcessSpeed
from smart_pid_domain.models.controller import AIConfig, Controller, ScaleConfig

_TEST_AI_PERIOD = 0.3


@pytest.fixture
def bus():
    b = EventBus(url_prefix=f"inproc://test_ai_sync_{uuid.uuid4().hex[:8]}")
    b.start()
    yield b
    b.stop()


@pytest.fixture
def controller_fuzzy():
    return Controller(
        id=1,
        name="TestSync",
        scan_rate_ms=100,
        process_speed=ProcessSpeed.MEDIUM,
        pv_scale=ScaleConfig(eu_min=0.0, eu_max=100.0),
        ai_config=AIConfig(
            engine=AIEngine.FUZZY,
            objective=ControlObjective.SP_TRACKING,
            dead_time_l=0.1,
            limit_min=0.1,
            limit_max=100.0,
        ),
    )


class TestAIWorkerReadsFreshTi:
    """AI worker must use the latest Ti from telemetry on every cycle."""

    def test_uses_latest_ti_from_telemetry(self, bus, controller_fuzzy):
        """When telemetry carries a new Ti value, AI uses it as ki_current."""
        worker = AIWorker(bus=bus, controller=controller_fuzzy)
        worker._ai_period_s = _TEST_AI_PERIOD
        worker.start()
        try:
            pub = bus.create_publisher()
            sub = bus.create_subscriber(f"ACTION.AI.{controller_fuzzy.id}".encode())
            time.sleep(0.05)

            # Send telemetry with Ti=20.0 (different from default 10.0)
            for _ in range(5):
                telem = {
                    "pv": 55.0, "sp": 50.0, "co": 48.0, "mode": "AUTO",
                    "ti": 20.0, "kp": 1.0, "td": 0.0,
                }
                pub.send(
                    f"TELEMETRY.{controller_fuzzy.id}".encode(),
                    msgpack.packb(telem),
                )
                time.sleep(0.05)

            # Wait for AI cycle
            msg = sub.recv(timeout_ms=2000)
            assert msg is not None
            _topic, payload = msg
            data = msgpack.unpackb(payload)

            # The AI should have used Ti=20.0 as ki_current, so new_ki
            # should be based on 20.0 (not the default 10.0)
            new_ki = data["new_ki"]
            # With error=50-55=-5, the fuzzy engine will adjust from 20.0
            # The key assertion: new_ki should be near 20.0, not near 10.0
            assert new_ki > 15.0, (
                f"new_ki={new_ki} suggests AI used stale default (10.0) "
                f"instead of fresh Ti=20.0 from telemetry"
            )
        finally:
            worker.stop()

    def test_resyncs_ti_every_cycle(self, bus, controller_fuzzy):
        """After first AI cycle produces new_ki, the NEXT cycle must read
        fresh Ti from telemetry again (not use the AI's own output)."""
        worker = AIWorker(bus=bus, controller=controller_fuzzy)
        worker._ai_period_s = _TEST_AI_PERIOD
        worker.start()
        try:
            pub = bus.create_publisher()
            sub = bus.create_subscriber(f"ACTION.AI.{controller_fuzzy.id}".encode())
            time.sleep(0.05)

            # First batch: Ti=20.0
            for _ in range(5):
                telem = {
                    "pv": 55.0, "sp": 50.0, "co": 48.0, "mode": "AUTO",
                    "ti": 20.0, "kp": 1.0, "td": 0.0,
                }
                pub.send(
                    f"TELEMETRY.{controller_fuzzy.id}".encode(),
                    msgpack.packb(telem),
                )
                time.sleep(0.05)

            # Consume first AI action
            msg1 = sub.recv(timeout_ms=2000)
            assert msg1 is not None
            data1 = msgpack.unpackb(msg1[1])
            first_new_ki = data1["new_ki"]

            # Now DCS reports Ti=30.0 (e.g., operator changed it)
            for _ in range(5):
                telem = {
                    "pv": 52.0, "sp": 50.0, "co": 48.0, "mode": "AUTO",
                    "ti": 30.0, "kp": 1.0, "td": 0.0,
                }
                pub.send(
                    f"TELEMETRY.{controller_fuzzy.id}".encode(),
                    msgpack.packb(telem),
                )
                time.sleep(0.05)

            # Second AI cycle should use Ti=30.0, not first_new_ki
            msg2 = sub.recv(timeout_ms=2000)
            assert msg2 is not None
            data2 = msgpack.unpackb(msg2[1])
            second_new_ki = data2["new_ki"]

            # second_new_ki must be based on 30.0, not first_new_ki
            assert second_new_ki > 25.0, (
                f"second_new_ki={second_new_ki} suggests AI used its own "
                f"previous output ({first_new_ki}) instead of fresh Ti=30.0"
            )
        finally:
            worker.stop()


class TestAIWorkerPublishesForWriteBack:
    """ACTION.AI must include integral_type and execution_mode for IO worker."""

    def test_action_ai_includes_integral_type_and_execution_mode(self, bus, controller_fuzzy):
        """ACTION.AI payload must include integral_type and execution_mode."""
        worker = AIWorker(bus=bus, controller=controller_fuzzy)
        worker._ai_period_s = _TEST_AI_PERIOD
        worker.start()
        try:
            pub = bus.create_publisher()
            sub = bus.create_subscriber(f"ACTION.AI.{controller_fuzzy.id}".encode())
            time.sleep(0.05)

            for _ in range(5):
                telem = {
                    "pv": 55.0, "sp": 50.0, "co": 48.0, "mode": "AUTO",
                    "ti": 10.0, "kp": 1.0, "td": 0.0,
                }
                pub.send(
                    f"TELEMETRY.{controller_fuzzy.id}".encode(),
                    msgpack.packb(telem),
                )
                time.sleep(0.05)

            msg = sub.recv(timeout_ms=2000)
            assert msg is not None
            _topic, payload = msg
            data = msgpack.unpackb(payload)
            assert "integral_type" in data, (
                "ACTION.AI must include integral_type for OPC-UA write-back"
            )
            assert data["integral_type"] == "TIME_TI"
            assert "execution_mode" in data, (
                "ACTION.AI must include execution_mode for OPC-UA write-back"
            )
            assert data["execution_mode"] == "SUPERVISORY"
        finally:
            worker.stop()
