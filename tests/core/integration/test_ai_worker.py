"""Integration tests for AIWorker — bus subscriber with Fuzzy/RL engine."""
from __future__ import annotations

import time
import uuid

import msgpack
import pytest

from smart_pid_core.application.event_bus import EventBus
from smart_pid_core.application.workers.ai_worker import AIWorker
from smart_pid_domain.enums import (
    AIEngine,
    ControlObjective,
    IntegralType,
    ProcessSpeed,
)
from smart_pid_domain.models.controller import (
    AIConfig,
    Controller,
    PIDParams,
    ScaleConfig,
)


@pytest.fixture
def bus():
    b = EventBus(url_prefix=f"inproc://test_ai_{uuid.uuid4().hex[:8]}")
    b.start()
    yield b
    b.stop()


@pytest.fixture
def controller_fuzzy():
    return Controller(
        id=1, name="TestFuzzy", scan_rate_s=0.1,
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


class TestAIWorkerFuzzy:
    def test_publishes_ai_action(self, bus, controller_fuzzy):
        worker = AIWorker(bus=bus, controller=controller_fuzzy)
        worker._ai_period_s = 0.3  # Override for fast testing
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

            # Wait for timer-based AI cycle
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
            id=2, name="TestNone", scan_rate_s=0.1,
            ai_config=AIConfig(engine=AIEngine.NONE),
        )
        worker = AIWorker(bus=bus, controller=ctrl)
        worker.start()
        assert not worker.is_alive()  # Should not start with NONE engine
        worker.stop()


class _FixedDecisionEngine:
    """Engine stub that always asks for the same Δ_Ti.

    Lets the worker's Ti→Ki inversion be asserted exactly, without depending
    on what the fuzzy rule base happens to conclude for a given sample run.
    """

    def __init__(self, delta_ti: float) -> None:
        from smart_pid_core.domain.services.fuzzy_engine_v2 import AIDecisionV2
        self._decision = AIDecisionV2(
            delta_ti=delta_ti,
            new_ti=0.0,       # unused on the GAIN_KI path
            inputs={},
            reasoning="stub",
            membership_values={},
        )

    def update_sample(self, *args, **kwargs) -> None:
        return None

    def compute_adjustment(self, **kwargs):
        return self._decision

    def compute_adjustment_from_stats(self, **kwargs):
        return self._decision


def _gain_ki_controller(cid: int, ki: float, limit_min: float) -> Controller:
    return Controller(
        id=cid, name="TestGainKi", scan_rate_s=0.1,
        process_speed=ProcessSpeed.MEDIUM,
        integral_type=IntegralType.GAIN_KI,
        pv_scale=ScaleConfig(eu_min=0.0, eu_max=100.0),
        pid_params=PIDParams(reset=ki),
        ai_config=AIConfig(
            engine=AIEngine.FUZZY,
            objective=ControlObjective.SP_TRACKING,
            dead_time_l=0.1,
            limit_min=limit_min,
            limit_max=100.0,
        ),
    )


def _first_ai_action(bus, worker, controller):
    """Run one AI cycle and return the decoded ACTION.AI payload."""
    worker._ai_period_s = 0.3
    worker.start()
    try:
        pub = bus.create_publisher()
        sub = bus.create_subscriber(f"ACTION.AI.{controller.id}".encode())
        time.sleep(0.05)
        for _ in range(5):
            telem = {"pv": 55.0, "sp": 50.0, "co": 48.0, "mode": "AUTO"}
            pub.send(
                f"TELEMETRY.{controller.id}".encode(), msgpack.packb(telem),
            )
            time.sleep(0.05)
        msg = sub.recv(timeout_ms=2000)
        assert msg is not None
        return msgpack.unpackb(msg[1])
    finally:
        worker.stop()


class TestAIWorkerGainKiInversion:
    """T-A4 — Ki = 1/Ti, so a Δ_Ti the engine means as "relax" must divide
    Ki, never multiply it. Getting the sense wrong here doubles the integral
    gain exactly when the engine asked to halve it."""

    def test_positive_delta_ti_divides_ki(self, bus):
        ctrl = _gain_ki_controller(cid=11, ki=9.0, limit_min=0.1)
        worker = AIWorker(bus=bus, controller=ctrl)
        worker._engine = _FixedDecisionEngine(delta_ti=0.5)
        data = _first_ai_action(bus, worker, ctrl)
        assert data["new_ki"] == pytest.approx(9.0 / 1.5)  # 6.0, not 13.5

    def test_negative_delta_ti_multiplies_ki(self, bus):
        ctrl = _gain_ki_controller(cid=12, ki=4.0, limit_min=0.1)
        worker = AIWorker(bus=bus, controller=ctrl)
        worker._engine = _FixedDecisionEngine(delta_ti=-0.5)
        data = _first_ai_action(bus, worker, ctrl)
        assert data["new_ki"] == pytest.approx(4.0 / 0.5)  # 8.0

    def test_inverted_ki_is_clamped_to_limit_min(self, bus):
        ctrl = _gain_ki_controller(cid=13, ki=0.6, limit_min=0.5)
        worker = AIWorker(bus=bus, controller=ctrl)
        worker._engine = _FixedDecisionEngine(delta_ti=0.5)
        data = _first_ai_action(bus, worker, ctrl)
        assert data["new_ki"] == pytest.approx(0.5)  # 0.4 clamped up
