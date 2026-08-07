"""System status DTOs."""
from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, StringConstraints


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


LogLevelName = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class LogLevelsResponse(BaseModel):
    levels: list[LogLevelName]
    available: list[LogLevelName]


class LogLevelsUpdate(BaseModel):
    # Empty list is valid: it lets an operator silence every level (the
    # daemon still keeps emitting CRITICAL-by-policy records the backend
    # writes outside the standard logging pipeline).
    levels: list[LogLevelName]


class FeedbackRequest(BaseModel):
    """Body of ``POST /system/feedback`` — Loops-page message to the developer."""

    message: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)
    ]
