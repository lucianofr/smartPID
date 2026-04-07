"""Tests for AIWorker mode guard and timer-driven cadence.

Rule 1: Fuzzy/RL must only execute when loop mode is AUTO, CAS, or RCAS.
Rule 2: AI evaluation runs on a fixed timer (ProcessSpeed.ai_period_s).
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

# Modes where AI MUST NOT run
NON_AUTO_MODES = ["MAN", "OOS", "LO", "IMAN", "ROUT"]
# Modes where AI MUST run
AUTO_MODES = ["AUTO", "CAS", "RCAS"]

_TEST_AI_PERIOD = 0.3  # 300ms for fast testing


@pytest.fixture
def bus():
    b = EventBus(url_prefix=f"inproc://test_ai_mode_{uuid.uuid4().hex[:8]}")
    b.start()
    yield b
    b.stop()


@pytest.fixture
def controller_fuzzy():
    return Controller(
        id=1,
        name="TestFuzzy",
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


class TestAIWorkerModeGuard:
    """AI must skip computation when loop is NOT in an automatic mode."""

    @pytest.mark.parametrize("mode", NON_AUTO_MODES)
    def test_skips_non_auto_modes(self, bus, controller_fuzzy, mode):
        """When telemetry reports a non-auto mode, no ACTION.AI is published."""
        worker = AIWorker(bus=bus, controller=controller_fuzzy)
        worker._ai_period_s = _TEST_AI_PERIOD
        worker.start()
        try:
            pub = bus.create_publisher()
            sub = bus.create_subscriber(f"ACTION.AI.{controller_fuzzy.id}".encode())
            time.sleep(0.05)

            # Send telemetry with non-auto mode
            for _ in range(5):
                telem = {"pv": 55.0, "sp": 50.0, "co": 48.0, "mode": mode}
                pub.send(
                    f"TELEMETRY.{controller_fuzzy.id}".encode(),
                    msgpack.packb(telem),
                )
                time.sleep(0.05)

            # Wait for at least one AI cycle
            time.sleep(_TEST_AI_PERIOD + 0.5)

            # AI should NOT have published any action
            msg = sub.recv(timeout_ms=500)
            assert msg is None, f"AI should not run in mode={mode}, but got ACTION.AI"
        finally:
            worker.stop()

    @pytest.mark.parametrize("mode", AUTO_MODES)
    def test_runs_in_auto_modes(self, bus, controller_fuzzy, mode):
        """When telemetry reports an auto mode, AI computes and publishes ACTION.AI."""
        worker = AIWorker(bus=bus, controller=controller_fuzzy)
        worker._ai_period_s = _TEST_AI_PERIOD
        worker.start()
        try:
            pub = bus.create_publisher()
            sub = bus.create_subscriber(f"ACTION.AI.{controller_fuzzy.id}".encode())
            time.sleep(0.05)

            # Send telemetry with auto mode
            for _ in range(5):
                telem = {"pv": 55.0, "sp": 50.0, "co": 48.0, "mode": mode}
                pub.send(
                    f"TELEMETRY.{controller_fuzzy.id}".encode(),
                    msgpack.packb(telem),
                )
                time.sleep(0.05)

            # Wait for timer-based AI cycle
            msg = sub.recv(timeout_ms=2000)
            assert msg is not None, f"AI should run in mode={mode}"
            _topic, payload = msg
            data = msgpack.unpackb(payload)
            assert data["controller_id"] == controller_fuzzy.id
            assert data["engine"] == "FUZZY"
        finally:
            worker.stop()


class TestAIWorkerTimerCadence:
    """AI runs on its own timer, independent of STATS."""

    def test_fires_on_timer_without_stats(self, bus, controller_fuzzy):
        """AI fires based on its timer, no STATS message needed."""
        worker = AIWorker(bus=bus, controller=controller_fuzzy)
        worker._ai_period_s = _TEST_AI_PERIOD
        worker.start()
        try:
            pub = bus.create_publisher()
            sub = bus.create_subscriber(f"ACTION.AI.{controller_fuzzy.id}".encode())
            time.sleep(0.05)

            # Send telemetry (with AUTO mode) — no STATS needed
            for _ in range(3):
                telem = {"pv": 55.0, "sp": 50.0, "co": 48.0, "mode": "AUTO"}
                pub.send(
                    f"TELEMETRY.{controller_fuzzy.id}".encode(),
                    msgpack.packb(telem),
                )
                time.sleep(0.05)

            # Wait for the timer to fire
            msg = sub.recv(timeout_ms=2000)
            assert msg is not None, "AI should fire on its timer without STATS"
        finally:
            worker.stop()

    def test_no_telemetry_no_action(self, bus, controller_fuzzy):
        """Even after timer fires, if no telemetry was received, no ACTION.AI."""
        worker = AIWorker(bus=bus, controller=controller_fuzzy)
        worker._ai_period_s = _TEST_AI_PERIOD
        worker.start()
        try:
            sub = bus.create_subscriber(f"ACTION.AI.{controller_fuzzy.id}".encode())
            time.sleep(0.05)

            # Wait for at least one AI cycle — no telemetry sent
            time.sleep(_TEST_AI_PERIOD + 0.5)

            msg = sub.recv(timeout_ms=500)
            assert msg is None, "AI should not fire without telemetry data"
        finally:
            worker.stop()
