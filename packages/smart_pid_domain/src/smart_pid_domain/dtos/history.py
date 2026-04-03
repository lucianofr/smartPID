"""History query DTOs."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class TelemetryFrameDTO(BaseModel):
    timestamp: datetime
    pv: float
    sp: float
    co: float
    mode: str
    status: str


class HistoryResponse(BaseModel):
    controller_id: int
    frames: list[TelemetryFrameDTO]
    count: int
