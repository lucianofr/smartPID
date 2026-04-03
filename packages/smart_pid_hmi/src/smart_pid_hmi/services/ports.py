"""Service port protocols — contracts for API client and telemetry source."""
from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from datetime import datetime
    from queue import SimpleQueue

    from smart_pid_domain.dtos import (
        CommandResponse,
        ControllerResponse,
        HistoryResponse,
        TokenResponse,
    )


class TelemetrySourcePort(Protocol):
    """Contract for real-time telemetry data source."""

    def start(self) -> None: ...
    def stop(self) -> None: ...

    @property
    def queue(self) -> SimpleQueue: ...


class APIClientPort(Protocol):
    """Contract for REST API client (sync)."""

    def login(self, username: str, password: str) -> TokenResponse: ...
    def list_controllers(self) -> list[ControllerResponse]: ...
    def get_controller(self, controller_id: int) -> ControllerResponse: ...
    def set_setpoint(self, controller_id: int, value: float) -> CommandResponse: ...
    def set_mode(self, controller_id: int, mode: str) -> CommandResponse: ...
    def set_output(self, controller_id: int, value: float) -> CommandResponse: ...
    def get_history(
        self, controller_id: int, start: datetime, end: datetime
    ) -> HistoryResponse: ...
