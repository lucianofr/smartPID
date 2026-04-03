from __future__ import annotations

import time
from datetime import UTC, datetime

import msgpack

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
