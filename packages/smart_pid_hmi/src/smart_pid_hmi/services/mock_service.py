"""Mock service implementations for offline dev/test."""
from __future__ import annotations

import base64
import json
import math
import random
import threading
import time
from datetime import UTC, datetime
from queue import SimpleQueue

from smart_pid_domain.dtos import (
    CommandResponse,
    ControllerResponse,
    HistoryResponse,
    SimulatorStatusResponse,
    TelemetryFrameDTO,
    TokenResponse,
)
from smart_pid_domain.dtos.users import UserResponse

# Mock controller definitions
_MOCK_CONTROLLERS = [
    {"id": 1, "name": "FIC-101", "description": "Flow control", "sp": 50.0,
     "sp_hi_lim": 100.0, "sp_lo_lim": 0.0, "out_hi_lim": 100.0, "out_lo_lim": 0.0},
    {"id": 2, "name": "LIC-201", "description": "Level control", "sp": 65.0,
     "sp_hi_lim": 100.0, "sp_lo_lim": 0.0, "out_hi_lim": 100.0, "out_lo_lim": 0.0},
    {"id": 3, "name": "TIC-301", "description": "Temperature control", "sp": 180.0,
     "sp_hi_lim": 300.0, "sp_lo_lim": 0.0, "out_hi_lim": 100.0, "out_lo_lim": 0.0},
]


class MockTelemetrySource:
    """Generates synthetic telemetry frames at a configurable interval."""

    def __init__(self, interval_ms: int = 100) -> None:
        self._interval = interval_ms / 1000.0
        self._queue: SimpleQueue = SimpleQueue()
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._tick = 0

    @property
    def queue(self) -> SimpleQueue:
        return self._queue

    def start(self) -> None:
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        self._thread.join(timeout=2.0)

    def _run(self) -> None:
        while not self._stop_event.is_set():
            for ctrl in _MOCK_CONTROLLERS:
                t = self._tick * self._interval
                sp = ctrl["sp"]
                pv = sp + 5.0 * math.sin(t * 0.5) + random.gauss(0, 0.5)
                co = max(0.0, min(100.0, 50.0 + 10.0 * math.sin(t * 0.3)))

                frame = {
                    "controller_id": ctrl["id"],
                    "pv": round(pv, 2),
                    "sp": round(sp, 2),
                    "co": round(co, 2),
                    "integral_val": 0.0,
                    "timestamp": datetime.now(tz=UTC).isoformat(),
                    "status": "GOOD",
                }
                self._queue.put((f"STATUS.{ctrl['id']}", frame))
            self._tick += 1
            self._stop_event.wait(timeout=self._interval)


class MockAPIClient:
    """Mock REST client returning canned data. Same interface as APIClient."""

    def login(self, username: str, password: str) -> TokenResponse:
        # Fake JWT with long expiry
        header = base64.urlsafe_b64encode(b'{"alg":"HS256"}').rstrip(b"=").decode()
        payload = base64.urlsafe_b64encode(json.dumps({
            "sub": "1", "username": username, "role": "operator",
            "exp": int(time.time()) + 86400,
        }).encode()).rstrip(b"=").decode()
        fake_token = f"{header}.{payload}.mocksig"
        return TokenResponse(access_token=fake_token)

    def list_controllers(self) -> list[ControllerResponse]:
        return [
            ControllerResponse(
                id=c["id"], name=c["name"], description=c["description"],
                mode="AUTO", pv=c["sp"], sp=c["sp"], co=50.0,
                sp_hi_lim=c["sp_hi_lim"], sp_lo_lim=c["sp_lo_lim"],
                out_hi_lim=c["out_hi_lim"], out_lo_lim=c["out_lo_lim"],
            )
            for c in _MOCK_CONTROLLERS
        ]

    def get_controller(self, controller_id: int) -> ControllerResponse:
        for c in _MOCK_CONTROLLERS:
            if c["id"] == controller_id:
                return ControllerResponse(
                    id=c["id"], name=c["name"], description=c["description"],
                    mode="AUTO", pv=c["sp"], sp=c["sp"], co=50.0,
                    sp_hi_lim=c["sp_hi_lim"], sp_lo_lim=c["sp_lo_lim"],
                    out_hi_lim=c["out_hi_lim"], out_lo_lim=c["out_lo_lim"],
                )
        return ControllerResponse(
            id=controller_id, name="UNKNOWN", description="",
            mode="OOS", pv=0.0, sp=0.0, co=0.0,
        )

    def set_setpoint(self, controller_id: int, value: float) -> CommandResponse:
        return CommandResponse(ok=True, controller_id=controller_id,
                               detail=f"SP set to {value}")

    def set_mode(self, controller_id: int, mode: str) -> CommandResponse:
        return CommandResponse(ok=True, controller_id=controller_id,
                               detail=f"Mode set to {mode}")

    def set_output(self, controller_id: int, value: float) -> CommandResponse:
        return CommandResponse(ok=True, controller_id=controller_id,
                               detail=f"Output set to {value}")

    def get_history(
        self, controller_id: int, start: datetime, end: datetime
    ) -> HistoryResponse:
        now = datetime.now(tz=UTC)
        frames = [
            TelemetryFrameDTO(
                timestamp=now, pv=50.0, sp=50.0, co=50.0,
                mode="AUTO", status="GOOD",
            )
        ]
        return HistoryResponse(controller_id=controller_id, frames=frames, count=len(frames))

    def list_users(self) -> list[UserResponse]:
        return [
            UserResponse(
                id=1, username="admin", role="ADMIN", active=True, created_at="2026-01-01",
            ),
            UserResponse(
                id=2, username="operator", role="OPERATOR", active=True, created_at="2026-01-02",
            ),
            UserResponse(
                id=3, username="inactive", role="OPERATOR", active=False, created_at="2026-01-03",
            ),
        ]

    def create_user(self, username: str, password: str, role: str) -> UserResponse:
        return UserResponse(id=99, username=username, role=role, active=True, created_at="")

    def update_user(
        self, user_id: int, role: str | None = None,
        password: str | None = None, active: bool | None = None,
    ) -> UserResponse:
        return UserResponse(
            id=user_id, username="user", role=role or "OPERATOR",
            active=active if active is not None else True, created_at="",
        )

    def deactivate_user(self, user_id: int) -> UserResponse:
        return UserResponse(
            id=user_id, username="user", role="OPERATOR", active=False, created_at="",
        )

    # Alarms
    def get_active_alarms(self, controller_id: int | None = None) -> list[dict]:
        return []

    def ack_alarm(self, alarm_id: int) -> dict:
        return {"ok": True, "alarm_id": alarm_id}

    def ack_all_alarms(self) -> dict:
        return {"ok": True}

    def get_alarm_history(
        self, start: datetime, end: datetime, controller_id: int | None = None,
    ) -> list[dict]:
        return []

    # Simulator
    def get_simulator_status(self) -> SimulatorStatusResponse:
        return SimulatorStatusResponse(enabled=False)

    def set_simulator_preset(
        self, controller_id: int, preset: str,
    ) -> CommandResponse:
        return CommandResponse(ok=True, controller_id=controller_id, detail="mock")

    def set_simulator_parameters(
        self, controller_id: int, gain: float, tau1: float,
        tau2: float | None, dead_time: float,
    ) -> CommandResponse:
        return CommandResponse(ok=True, controller_id=controller_id, detail="mock")

    def inject_simulator_disturbance(
        self, controller_id: int, dist_type: str, amplitude: float,
    ) -> CommandResponse:
        return CommandResponse(ok=True, controller_id=controller_id, detail="mock")

    def clear_simulator_disturbance(self, controller_id: int) -> CommandResponse:
        return CommandResponse(ok=True, controller_id=controller_id, detail="mock")

    # Stats
    def get_controller_stats(self, controller_id: int) -> dict:
        return {"controller_id": controller_id, "iae": 0.0, "ise": 0.0}

    def get_all_stats(self) -> list[dict]:
        return [
            {"controller_id": c["id"], "iae": 0.0, "ise": 0.0}
            for c in _MOCK_CONTROLLERS
        ]

    # Export (stubs)
    def create_export(
        self, controller_id: int, start: str, end: str, fmt: str = "csv",
    ) -> dict:
        return {"export_id": "mock-001", "status": "complete"}

    def get_export_status(self, export_id: str) -> dict:
        return {"export_id": export_id, "status": "complete"}

    def download_export(self, export_id: str, dest_path: object) -> object:
        return dest_path

    def set_base_url(self, url: str) -> None:
        pass

    def close(self) -> None:
        pass
