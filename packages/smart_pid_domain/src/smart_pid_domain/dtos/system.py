"""System status DTOs."""
from __future__ import annotations

from pydantic import BaseModel


class SystemStatusResponse(BaseModel):
    status: str
    uptime_s: float
    active_controllers: int
    bus_active: bool
    api_version: str
    # Optional: a host without psutil still reports a healthy daemon rather
    # than failing the whole status probe. The HMI renders an em dash.
    cpu_percent: float | None = None
    memory_percent: float | None = None
