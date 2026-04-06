"""Sync REST API client using httpx."""
from __future__ import annotations

from typing import TYPE_CHECKING

import httpx

from smart_pid_domain.dtos import (
    CommandResponse,
    ControllerResponse,
    HistoryResponse,
    SimulatorStatusResponse,
    TokenResponse,
)
from smart_pid_domain.dtos.users import UserResponse

if TYPE_CHECKING:
    from datetime import datetime
    from pathlib import Path

    from smart_pid_hmi.services.session import Session


class APIClient:
    """Synchronous REST client for the Smart PID backend."""

    def __init__(
        self,
        base_url: str,
        session: Session,
        transport: httpx.BaseTransport | None = None,
        timeout: float = 5.0,
    ) -> None:
        self._session = session
        kwargs: dict = {"base_url": base_url, "timeout": timeout}
        if transport is not None:
            kwargs["transport"] = transport
        self._http = httpx.Client(**kwargs)

    def set_base_url(self, url: str) -> None:
        """Replace the HTTP client with a new base URL (from connection page)."""
        old = self._http
        self._http = httpx.Client(base_url=url, timeout=old.timeout)
        old.close()

    def _headers(self) -> dict[str, str]:
        return self._session.auth_header

    def login(self, username: str, password: str) -> TokenResponse:
        resp = self._http.post(
            "/auth/login",
            json={"username": username, "password": password},
        )
        resp.raise_for_status()
        return TokenResponse.model_validate(resp.json())

    def refresh_token(self) -> TokenResponse:
        """Refresh the current access token before it expires."""
        resp = self._http.post("/auth/refresh", headers=self._headers())
        resp.raise_for_status()
        token_resp = TokenResponse.model_validate(resp.json())
        self._session.store_token(token_resp.access_token)
        return token_resp

    def create_controller(self, data: dict) -> ControllerResponse:
        resp = self._http.post("/controllers", json=data, headers=self._headers())
        resp.raise_for_status()
        return ControllerResponse.model_validate(resp.json())

    def list_controllers(self) -> list[ControllerResponse]:
        resp = self._http.get("/controllers", headers=self._headers())
        resp.raise_for_status()
        return [ControllerResponse.model_validate(c) for c in resp.json()]

    def get_controller(self, controller_id: int) -> ControllerResponse:
        resp = self._http.get(f"/controllers/{controller_id}", headers=self._headers())
        resp.raise_for_status()
        return ControllerResponse.model_validate(resp.json())

    def update_controller(self, controller_id: int, data: dict) -> ControllerResponse:
        resp = self._http.put(
            f"/controllers/{controller_id}", json=data, headers=self._headers(),
        )
        resp.raise_for_status()
        return ControllerResponse.model_validate(resp.json())

    def set_setpoint(self, controller_id: int, value: float) -> CommandResponse:
        resp = self._http.post(
            "/commands/setpoint",
            json={"controller_id": controller_id, "value": value},
            headers=self._headers(),
        )
        resp.raise_for_status()
        return CommandResponse.model_validate(resp.json())

    def set_mode(self, controller_id: int, mode: str) -> CommandResponse:
        resp = self._http.post(
            "/commands/mode",
            json={"controller_id": controller_id, "mode": mode},
            headers=self._headers(),
        )
        resp.raise_for_status()
        return CommandResponse.model_validate(resp.json())

    def set_output(self, controller_id: int, value: float) -> CommandResponse:
        resp = self._http.post(
            "/commands/output",
            json={"controller_id": controller_id, "value": value},
            headers=self._headers(),
        )
        resp.raise_for_status()
        return CommandResponse.model_validate(resp.json())

    def get_history(
        self, controller_id: int, start: datetime, end: datetime
    ) -> HistoryResponse:
        resp = self._http.get(
            f"/history/{controller_id}",
            params={"start": start.isoformat(), "end": end.isoformat()},
            headers=self._headers(),
        )
        resp.raise_for_status()
        return HistoryResponse.model_validate(resp.json())

    # OPC-UA Browse
    def browse_opcua(self, node_id: str) -> list[dict]:
        resp = self._http.get(
            f"/opcua/browse/{node_id}", headers=self._headers(),
        )
        resp.raise_for_status()
        return resp.json().get("children", [])

    def search_opcua(self, query: str) -> list[dict]:
        resp = self._http.get(
            "/opcua/search", params={"q": query}, headers=self._headers(),
        )
        resp.raise_for_status()
        return resp.json().get("results", [])

    def start_simulator(self) -> CommandResponse:
        resp = self._http.post("/simulator/start", headers=self._headers())
        resp.raise_for_status()
        return CommandResponse.model_validate(resp.json())

    def stop_simulator(self) -> CommandResponse:
        resp = self._http.post("/simulator/stop", headers=self._headers())
        resp.raise_for_status()
        return CommandResponse.model_validate(resp.json())

    def get_simulator_status(self) -> SimulatorStatusResponse:
        resp = self._http.get("/simulator/status", headers=self._headers())
        resp.raise_for_status()
        return SimulatorStatusResponse.model_validate(resp.json())

    def set_simulator_preset(self, controller_id: int, preset: str) -> CommandResponse:
        resp = self._http.post(
            "/simulator/preset",
            json={"controller_id": controller_id, "preset": preset},
            headers=self._headers(),
        )
        resp.raise_for_status()
        return CommandResponse.model_validate(resp.json())

    def set_simulator_parameters(
        self, controller_id: int, gain: float, tau1: float,
        tau2: float | None, dead_time: float,
    ) -> CommandResponse:
        resp = self._http.put(
            "/simulator/parameters",
            json={
                "controller_id": controller_id, "gain": gain,
                "tau1": tau1, "tau2": tau2, "dead_time": dead_time,
            },
            headers=self._headers(),
        )
        resp.raise_for_status()
        return CommandResponse.model_validate(resp.json())

    def inject_simulator_disturbance(
        self, controller_id: int, dist_type: str, amplitude: float,
    ) -> CommandResponse:
        resp = self._http.post(
            "/simulator/disturbance",
            json={"controller_id": controller_id, "type": dist_type, "amplitude": amplitude},
            headers=self._headers(),
        )
        resp.raise_for_status()
        return CommandResponse.model_validate(resp.json())

    def clear_simulator_disturbance(self, controller_id: int) -> CommandResponse:
        resp = self._http.delete(
            f"/simulator/disturbance/{controller_id}",
            headers=self._headers(),
        )
        resp.raise_for_status()
        return CommandResponse.model_validate(resp.json())

    def enable_simulator_pid(
        self, controller_id: int, enabled: bool,
    ) -> CommandResponse:
        resp = self._http.post(
            f"/simulator/{controller_id}/pid/enable",
            json={"controller_id": controller_id, "enabled": enabled},
            headers=self._headers(),
        )
        resp.raise_for_status()
        return CommandResponse.model_validate(resp.json())

    def set_simulator_pid_params(
        self, controller_id: int, kp: float, ti: float, td: float,
    ) -> CommandResponse:
        resp = self._http.post(
            f"/simulator/{controller_id}/pid/params",
            json={"controller_id": controller_id, "kp": kp, "ti": ti, "td": td},
            headers=self._headers(),
        )
        resp.raise_for_status()
        return CommandResponse.model_validate(resp.json())

    def set_simulator_pid_mode(
        self, controller_id: int, mode: str,
    ) -> CommandResponse:
        resp = self._http.post(
            f"/simulator/{controller_id}/pid/mode",
            json={"controller_id": controller_id, "mode": mode},
            headers=self._headers(),
        )
        resp.raise_for_status()
        return CommandResponse.model_validate(resp.json())

    def set_simulator_pid_sp(
        self, controller_id: int, sp: float,
    ) -> CommandResponse:
        resp = self._http.post(
            f"/simulator/{controller_id}/pid/sp",
            json={"controller_id": controller_id, "sp": sp},
            headers=self._headers(),
        )
        resp.raise_for_status()
        return CommandResponse.model_validate(resp.json())

    def get_simulator_pid_status(self, controller_id: int) -> dict:
        resp = self._http.get(
            f"/simulator/{controller_id}/pid/status",
            headers=self._headers(),
        )
        resp.raise_for_status()
        return resp.json()

    def set_simulator_auto_sp(
        self,
        controller_id: int,
        enabled: bool,
        sp_min_pct: float,
        sp_max_pct: float,
    ) -> dict:
        resp = self._http.put(
            f"/simulator/{controller_id}/auto-sp",
            json={"enabled": enabled, "sp_min_pct": sp_min_pct, "sp_max_pct": sp_max_pct},
            headers=self._headers(),
        )
        resp.raise_for_status()
        return resp.json()

    def set_simulator_auto_disturbance(
        self,
        controller_id: int,
        enabled: bool,
        max_amplitude_pct: float,
    ) -> dict:
        resp = self._http.put(
            f"/simulator/{controller_id}/auto-disturbance",
            json={"enabled": enabled, "max_amplitude_pct": max_amplitude_pct},
            headers=self._headers(),
        )
        resp.raise_for_status()
        return resp.json()

    def get_active_alarms(self, controller_id: int | None = None) -> list[dict]:
        params: dict = {}
        if controller_id is not None:
            params["controller_id"] = controller_id
        resp = self._http.get("/alarms/active", params=params, headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    def ack_alarm(self, alarm_id: int) -> dict:
        resp = self._http.post(f"/alarms/{alarm_id}/ack", headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    def ack_all_alarms(self) -> dict:
        resp = self._http.post("/alarms/ack-all", headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    def get_alarm_history(
        self, start: datetime, end: datetime, controller_id: int | None = None,
    ) -> list[dict]:
        params: dict = {"start": start.isoformat(), "end": end.isoformat()}
        if controller_id is not None:
            params["controller_id"] = controller_id
        resp = self._http.get("/alarms/history", params=params, headers=self._headers())
        resp.raise_for_status()
        return resp.json()



    def create_export(
        self, controller_id: int, start: str, end: str, fmt: str = "csv",
    ) -> dict:
        """Create a new export job."""
        resp = self._http.post(
            "/export",
            json={
                "controller_id": controller_id,
                "start": start,
                "end": end,
                "format": fmt,
            },
            headers=self._headers(),
        )
        resp.raise_for_status()
        return resp.json()

    def get_export_status(self, export_id: str) -> dict:
        """Get the status of an export job."""
        resp = self._http.get(f"/export/{export_id}", headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    def download_export(self, export_id: str, dest_path: Path) -> Path:
        """Download a completed export file to dest_path."""
        resp = self._http.get(
            f"/export/{export_id}/download", headers=self._headers(),
        )
        resp.raise_for_status()
        dest_path.write_bytes(resp.content)
        return dest_path

    def get_controller_stats(self, controller_id: int) -> dict:
        """Get performance stats for a single controller."""
        resp = self._http.get(
            f"/controllers/{controller_id}/stats",
            headers=self._headers(),
        )
        resp.raise_for_status()
        return resp.json()

    def get_all_stats(self) -> list[dict]:
        """Get performance stats for all controllers."""
        resp = self._http.get("/controllers/stats", headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    def list_users(self) -> list[UserResponse]:
        resp = self._http.get("/users", headers=self._headers())
        resp.raise_for_status()
        return [UserResponse.model_validate(u) for u in resp.json()]

    def create_user(self, username: str, password: str, role: str) -> UserResponse:
        resp = self._http.post(
            "/users",
            json={"username": username, "password": password, "role": role},
            headers=self._headers(),
        )
        resp.raise_for_status()
        return UserResponse.model_validate(resp.json())

    def update_user(
        self, user_id: int, role: str | None = None,
        password: str | None = None, active: bool | None = None,
    ) -> UserResponse:
        body: dict = {}
        if role is not None:
            body["role"] = role
        if password is not None:
            body["password"] = password
        if active is not None:
            body["active"] = active
        resp = self._http.put(
            f"/users/{user_id}", json=body, headers=self._headers(),
        )
        resp.raise_for_status()
        return UserResponse.model_validate(resp.json())

    def deactivate_user(self, user_id: int) -> UserResponse:
        resp = self._http.delete(f"/users/{user_id}", headers=self._headers())
        resp.raise_for_status()
        return UserResponse.model_validate(resp.json())

    # Project management

    def get_current_project(self) -> dict:
        resp = self._http.get("/project/current", headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    def new_project(self, name: str, path: str) -> dict:
        resp = self._http.post(
            "/project/new", json={"name": name, "path": path}, headers=self._headers(),
        )
        resp.raise_for_status()
        return resp.json()

    def open_project(self, path: str) -> dict:
        resp = self._http.post(
            "/project/open", json={"path": path}, headers=self._headers(),
        )
        resp.raise_for_status()
        return resp.json()

    def save_as_project(self, path: str) -> dict:
        resp = self._http.post(
            "/project/save-as", json={"path": path}, headers=self._headers(),
        )
        resp.raise_for_status()
        return resp.json()

    def close(self) -> None:
        self._http.close()
