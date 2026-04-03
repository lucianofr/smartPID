"""System status DTOs."""
from __future__ import annotations

from pydantic import BaseModel


class SystemStatusResponse(BaseModel):
    status: str
    uptime_s: float
    active_controllers: int
    bus_active: bool
    api_version: str
