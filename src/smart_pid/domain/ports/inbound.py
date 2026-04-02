"""Inbound port interfaces (external world -> domain)."""
from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from smart_pid.domain.models.telemetry import TelemetryFrame


class TelemetrySource(Protocol):
    """Reads process values from an external source (OPC-UA or Simulator)."""

    async def read_telemetry(self, controller_id: int) -> TelemetryFrame: ...

    async def connect(self, endpoint: str) -> None: ...

    async def disconnect(self) -> None: ...
