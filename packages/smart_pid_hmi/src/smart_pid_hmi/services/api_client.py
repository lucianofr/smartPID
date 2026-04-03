"""Sync REST API client using httpx."""
from __future__ import annotations

from typing import TYPE_CHECKING

import httpx

from smart_pid_domain.dtos import (
    CommandResponse,
    ControllerResponse,
    HistoryResponse,
    TokenResponse,
)

if TYPE_CHECKING:
    from datetime import datetime

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

    def _headers(self) -> dict[str, str]:
        return self._session.auth_header

    def login(self, username: str, password: str) -> TokenResponse:
        resp = self._http.post(
            "/auth/login",
            json={"username": username, "password": password},
        )
        resp.raise_for_status()
        return TokenResponse.model_validate(resp.json())

    def list_controllers(self) -> list[ControllerResponse]:
        resp = self._http.get("/controllers", headers=self._headers())
        resp.raise_for_status()
        return [ControllerResponse.model_validate(c) for c in resp.json()]

    def get_controller(self, controller_id: int) -> ControllerResponse:
        resp = self._http.get(f"/controllers/{controller_id}", headers=self._headers())
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

    def close(self) -> None:
        self._http.close()
