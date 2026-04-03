"""End-to-end test: Simulator -> PID -> AIWorker (Fuzzy) -> Ki adjustment."""
from __future__ import annotations

import time
import uuid

import msgpack
import pytest

from smart_pid_core.application.event_bus import EventBus
from smart_pid_core.application.workers.ai_worker import AIWorker
from smart_pid_core.application.workers.pid_worker import PIDWorker
from smart_pid_core.application.workers.stats_worker import StatsWorker
from smart_pid_core.domain.services.pid_engine import PIDEngine
from smart_pid_core.domain.services.pid_mode_manager import ModeManager
from smart_pid_domain.enums import AIEngine, ControllerMode, ControlObjective, ProcessSpeed
from smart_pid_domain.models.controller import AIConfig, Controller, PIDParams, ScaleConfig


@pytest.fixture
def bus():
    b = EventBus(url_prefix=f"inproc://test_e2e_{uuid.uuid4().hex[:8]}")
    b.start()
    yield b
    b.stop()


@pytest.fixture
def controller():
    return Controller(
        id=1, name="E2E-Test", scan_rate_ms=100,
        pid_params=PIDParams(gain=1.0, reset=10.0, rate=0.0),
        pv_scale=ScaleConfig(eu_min=0.0, eu_max=100.0),
        ai_config=AIConfig(
            engine=AIEngine.FUZZY,
            objective=ControlObjective.SP_TRACKING,
            process_speed=ProcessSpeed.MEDIUM,
            dead_time_l=0.1,
            limit_min=0.5,
            limit_max=50.0,
        ),
    )


class TestEndToEndAITuning:
    def test_fuzzy_adjusts_ki_over_time(self, bus, controller):
        """Verify that the fuzzy engine modifies Ki when there is a sustained error."""
        engine = PIDEngine()
        mode_manager = ModeManager()
        pid_worker = PIDWorker(
            bus=bus, controller=controller, engine=engine, mode_manager=mode_manager,
        )
        stats_worker = StatsWorker(bus=bus, controller=controller)
        ai_worker = AIWorker(bus=bus, controller=controller)

        pid_worker.set_mode(ControllerMode.AUTO)
        pid_worker.start()
        stats_worker.start()
        ai_worker.start()

        try:
            pub = bus.create_publisher()
            ai_sub = bus.create_subscriber(f"ACTION.AI.{controller.id}".encode())
            time.sleep(0.05)

            # Simulate steady-state error (PV below SP)
            for _ in range(20):
                telem = {"pv": 45.0, "sp": 50.0, "co": 50.0}
                pub.send(
                    f"TELEMETRY.{controller.id}".encode(),
                    msgpack.packb(telem),
                )
                time.sleep(0.1)

            # Wait for AI cycle
            time.sleep(1.0)

            # Check that ACTION.AI was published
            msg = ai_sub.recv(timeout_ms=2000)
            assert msg is not None, "Expected ACTION.AI message"
            _topic, payload = msg
            data = msgpack.unpackb(payload)
            assert data["engine"] == "FUZZY"
            assert data["gamma"] != 0.0  # Should have adjusted

        finally:
            ai_worker.stop()
            stats_worker.stop()
            pid_worker.stop()
