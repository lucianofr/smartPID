from __future__ import annotations

import time
import uuid
from datetime import UTC, datetime

import msgpack
import pytest

from smart_pid_core.application.event_bus import EventBus
from smart_pid_core.application.workers.pid_worker import PIDWorker
from smart_pid_core.domain.services.pid_engine import PIDEngine
from smart_pid_core.domain.services.pid_mode_manager import ModeManager
from smart_pid_domain.enums import ControllerMode
from smart_pid_domain.models.controller import Controller, PIDParams


class TestPIDWorker:
    def test_publishes_control_action(self) -> None:
        bus = EventBus()
        bus.start()
        try:
            controller = Controller(
                id=1, name="TIC-101",
                pid_params=PIDParams(gain=1.0, reset=10.0, rate=0.0),
                scan_rate_ms=100,
            )
            worker = PIDWorker(
                bus=bus, controller=controller, engine=PIDEngine(), mode_manager=ModeManager()
            )
            worker.set_mode(ControllerMode.AUTO)
            worker.start()

            sub = bus.create_subscriber(b"ACTION.CTRL.1")
            pub = bus.create_publisher()
            time.sleep(0.05)

            now = datetime.now(tz=UTC)
            frame_data = {
                "controller_id": 1, "pv": 40.0, "sp": 50.0, "co": 0.0,
                "integral_val": 0.0, "timestamp": now.isoformat(), "status": "GOOD",
            }
            pub.send(b"TELEMETRY.1", msgpack.packb(frame_data))

            msg = sub.recv(timeout_ms=2000)
            assert msg is not None
            topic, payload = msg
            assert topic == b"ACTION.CTRL.1"
            action = msgpack.unpackb(payload)
            assert "co" in action
            assert "integral_val" in action
        finally:
            worker.stop()
            bus.stop()

    def test_worker_survives_missing_telemetry(self) -> None:
        bus = EventBus()
        bus.start()
        try:
            controller = Controller(id=2, name="FIC-201", scan_rate_ms=100)
            worker = PIDWorker(
                bus=bus, controller=controller, engine=PIDEngine(), mode_manager=ModeManager()
            )
            worker.start()
            time.sleep(0.3)
            assert worker.is_alive()
        finally:
            worker.stop()
            bus.stop()


class TestPIDWorkerAIIntegration:
    def test_applies_ki_from_ai_action(self):
        bus = EventBus(url_prefix=f"inproc://test_pid_ai_{uuid.uuid4().hex[:8]}")
        bus.start()
        try:
            sample_controller = Controller(
                id=1, name="TIC-AI", scan_rate_ms=100,
                pid_params=PIDParams(gain=1.0, reset=10.0, rate=0.0),
            )
            engine = PIDEngine()
            mode_manager = ModeManager()
            worker = PIDWorker(
                bus=bus, controller=sample_controller,
                engine=engine, mode_manager=mode_manager,
            )
            worker.set_mode(ControllerMode.AUTO)
            worker.start()

            pub = bus.create_publisher()
            time.sleep(0.05)

            # Send telemetry
            telem = {"pv": 50.0, "sp": 50.0, "co": 50.0}
            pub.send(
                f"TELEMETRY.{sample_controller.id}".encode(),
                msgpack.packb(telem),
            )
            time.sleep(0.2)

            # Send AI action with new Ki
            ai_action = {
                "controller_id": sample_controller.id,
                "new_ki": 15.0,
                "gamma": 0.5,
            }
            pub.send(
                f"ACTION.AI.{sample_controller.id}".encode(),
                msgpack.packb(ai_action),
            )
            time.sleep(0.3)

            # Verify Ki was updated
            assert sample_controller.pid_params.reset == pytest.approx(15.0)
        finally:
            worker.stop()
            bus.stop()
