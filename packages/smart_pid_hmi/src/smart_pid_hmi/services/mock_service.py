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
                    "mode": "AUTO",
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
            "sub": "1", "username": username, "role": "ADMIN",
            "exp": int(time.time()) + 86400,
        }).encode()).rstrip(b"=").decode()
        fake_token = f"{header}.{payload}.mocksig"
        return TokenResponse(access_token=fake_token)

    def create_controller(self, data: dict) -> ControllerResponse:
        new_id = max((c["id"] for c in _MOCK_CONTROLLERS), default=0) + 1
        entry = {
            "id": new_id,
            "name": data.get("name", f"LOOP-{new_id}"),
            "description": data.get("description", ""),
            "sp": 50.0,
            "sp_hi_lim": data.get("sp_hi_lim", 100.0),
            "sp_lo_lim": data.get("sp_lo_lim", 0.0),
            "out_hi_lim": data.get("out_hi_lim", 100.0),
            "out_lo_lim": data.get("out_lo_lim", 0.0),
        }
        _MOCK_CONTROLLERS.append(entry)
        return ControllerResponse(
            id=new_id, name=entry["name"], description=entry["description"],
            mode="AUTO", pv=0.0, sp=entry["sp"], co=0.0,
            sp_hi_lim=entry["sp_hi_lim"], sp_lo_lim=entry["sp_lo_lim"],
            out_hi_lim=entry["out_hi_lim"], out_lo_lim=entry["out_lo_lim"],
        )

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

    def update_controller(self, controller_id: int, data: dict) -> ControllerResponse:
        base = self.get_controller(controller_id)
        merged = base.model_dump()
        merged.update(data)
        merged["id"] = controller_id  # ensure id cannot be overwritten
        return ControllerResponse.model_validate(merged)

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

    def get_ai_history(
        self, start: datetime, end: datetime, controller_id: int | None = None,
    ) -> list[dict]:
        return []

    def get_system_events(
        self, start: datetime, end: datetime,
        source: str | None = None, severity: str | None = None,
    ) -> list[dict]:
        return []

    # Simulator
    def start_simulator(self) -> CommandResponse:
        return CommandResponse(ok=True, detail="mock start")

    def stop_simulator(self) -> CommandResponse:
        return CommandResponse(ok=True, detail="mock stop")

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

    def enable_simulator_pid(
        self, controller_id: int, enabled: bool,
    ) -> CommandResponse:
        return CommandResponse(ok=True, controller_id=controller_id, detail="mock")

    def set_simulator_pid_params(
        self, controller_id: int, kp: float, ti: float, td: float,
    ) -> CommandResponse:
        return CommandResponse(ok=True, controller_id=controller_id, detail="mock")

    def set_simulator_pid_mode(
        self, controller_id: int, mode: str,
    ) -> CommandResponse:
        return CommandResponse(ok=True, controller_id=controller_id, detail="mock")

    def set_simulator_pid_sp(
        self, controller_id: int, sp: float,
    ) -> CommandResponse:
        return CommandResponse(ok=True, controller_id=controller_id, detail="mock")

    def set_simulator_co(
        self, controller_id: int, co: float,
    ) -> CommandResponse:
        return CommandResponse(ok=True, controller_id=controller_id, detail="mock")

    def get_simulator_pid_status(self, controller_id: int) -> dict:
        return {"enabled": False, "kp": 1.0, "ti": 10.0, "td": 0.0, "mode": 0, "cv": 0.0}

    # Stats
    def get_controller_stats(self, controller_id: int) -> dict:
        return {"controller_id": controller_id, "iae": 0.0, "ise": 0.0}

    def get_all_stats(self) -> list[dict]:
        return [
            {"controller_id": c["id"], "iae": 0.0, "ise": 0.0}
            for c in _MOCK_CONTROLLERS
        ]

    # Tuning write
    def write_tuning(
        self, controller_id: int,
        kp: float | None = None, ti: float | None = None, td: float | None = None,
    ) -> dict:
        return {"ok": True, "controller_id": controller_id}

    # AI Optimizer
    def get_ai_status(self, controller_id: int) -> dict:
        return {"controller_id": controller_id, "engine": "NONE"}

    def start_optimizer(self, controller_id: int) -> dict:
        return {"ok": True, "controller_id": controller_id}

    def pause_optimizer(self, controller_id: int) -> dict:
        return {"ok": True, "controller_id": controller_id}

    def stop_optimizer(self, controller_id: int) -> dict:
        return {"ok": True, "controller_id": controller_id}

    # Export (stubs)
    def create_export(
        self, controller_id: int, start: str, end: str, fmt: str = "csv",
    ) -> dict:
        return {"export_id": "mock-001", "status": "complete"}

    def get_export_status(self, export_id: str) -> dict:
        return {"export_id": export_id, "status": "complete"}

    def download_export(self, export_id: str, dest_path: object) -> object:
        return dest_path

    # Project management

    def get_current_project(self) -> dict:
        return {"name": "Mock Project", "path": "mock.spid", "controller_count": 2}

    def list_projects(self) -> list[dict]:
        return [
            {"name": "Mock Project", "controller_count": 2, "size_bytes": 1024},
            {"name": "Test Project", "controller_count": 0, "size_bytes": 512},
        ]

    def new_project(self, name: str) -> dict:
        return {"name": name, "path": f"{name}.spid", "controller_count": 0}

    def open_project(self, name: str) -> dict:
        return {"name": name, "path": f"{name}.spid", "controller_count": 0}

    def import_project(self, name: str, file_path: str) -> dict:
        return {"name": name, "path": f"{name}.spid", "controller_count": 0}

    def download_project(self, save_path: str) -> None:
        pass  # No-op in mock mode

    def delete_project(self, name: str) -> None:
        pass  # No-op in mock mode

    def opcua_client_status(self) -> dict:
        return {"state": "OFFLINE", "endpoint": "opc.tcp://localhost:4840"}

    def opcua_client_connect(self, endpoint: str | None = None) -> dict:
        ep = endpoint or "opc.tcp://localhost:4840"
        return {"state": "ONLINE", "endpoint": ep}

    def opcua_client_disconnect(self) -> dict:
        return {"state": "OFFLINE", "endpoint": "opc.tcp://localhost:4840"}

    def save_opcua_endpoint(self, url: str) -> dict:
        return {"state": "OFFLINE", "endpoint": url}

    def set_base_url(self, url: str) -> None:
        pass

    def close(self) -> None:
        pass
