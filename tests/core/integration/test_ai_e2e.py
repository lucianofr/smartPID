"""End-to-end test: Simulator -> StatsWorker -> AIWorker (Fuzzy) -> Ki adjustment."""
from __future__ import annotations

import time
import uuid

import msgpack
import pytest

from smart_pid_core.application.event_bus import EventBus
from smart_pid_core.application.workers.ai_worker import AIWorker
from smart_pid_core.application.workers.stats_worker import StatsWorker
from smart_pid_domain.enums import AIEngine, ControlObjective, ProcessSpeed
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
        id=1, name="E2E-Test", scan_rate_s=0.1,
        process_speed=ProcessSpeed.ULTRA_FAST,
        pid_params=PIDParams(gain=1.0, reset=10.0, rate=0.0),
        pv_scale=ScaleConfig(eu_min=0.0, eu_max=100.0),
        ai_config=AIConfig(
            engine=AIEngine.FUZZY,
            objective=ControlObjective.SP_TRACKING,
            dead_time_l=0.1,
            limit_min=0.5,
            limit_max=50.0,
        ),
    )


class TestEndToEndAITuning:
    def test_fuzzy_adjusts_ki_over_time(self, bus, controller):
        """Verify that the fuzzy engine modifies Ki when there is a sustained error.

        Flow: test publishes TELEMETRY (with mode=AUTO) -> AIWorker triggers fuzzy
        computation on its timer and publishes ACTION.AI.
        """
        stats_worker = StatsWorker(bus=bus, controller=controller)
        # SP_TRACKING consumes StatsWorker snapshots (AIWorker._drain_stats),
        # and production publishes STATS only once per 5 s of samples. Shorten
        # both cadences so a full stats -> fuzzy cycle fits the test budget.
        stats_worker._publish_interval = 5  # Override for fast testing
        ai_worker = AIWorker(bus=bus, controller=controller)
        ai_worker._ai_period_s = 0.5  # Override for fast testing

        stats_worker.start()
        ai_worker.start()

        try:
            pub = bus.create_publisher()
            ai_sub = bus.create_subscriber(f"ACTION.AI.{controller.id}".encode())
            time.sleep(0.05)

            # Simulate steady-state error (PV below SP). IAE saturates at
            # _IAE_FULL_SCALE = 20% of span, so a 15% offset is what rule R1
            # (IAE HIGH + OSC STABLE + EFF SMOOTH -> reduce Ti) keys on; the
            # old 5% offset normalises to IAE 0.25 = LOW, which correctly
            # fires R5 "settled" and holds Ti.
            for _ in range(15):
                telem = {"pv": 35.0, "sp": 50.0, "co": 50.0, "mode": "AUTO"}
                pub.send(
                    f"TELEMETRY.{controller.id}".encode(),
                    msgpack.packb(telem),
                )
                time.sleep(0.12)

            # Wait for AI timer cycle
            time.sleep(1.0)

            # Check that ACTION.AI was published
            msg = ai_sub.recv(timeout_ms=3000)
            assert msg is not None, "Expected ACTION.AI message"
            _topic, payload = msg
            data = msgpack.unpackb(payload)
            assert data["engine"] == "FUZZY"
            # gamma may be zero on the first cycle (initial state),
            # drain further messages to find a non-zero adjustment
            gamma = data["gamma"]
            for _ in range(10):
                msg2 = ai_sub.recv(timeout_ms=2000)
                if msg2 is None:
                    break
                d2 = msgpack.unpackb(msg2[1])
                if d2["gamma"] != 0.0:
                    gamma = d2["gamma"]
                    break
            assert gamma != 0.0, "Expected fuzzy to adjust gamma for sustained error"

        finally:
            ai_worker.stop()
            stats_worker.stop()
