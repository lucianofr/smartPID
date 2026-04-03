"""AI and statistics request/response DTOs."""
from __future__ import annotations

from pydantic import BaseModel

from smart_pid_domain.enums import AIEngine, ControlObjective, ProcessSpeed  # noqa: TC001


class StatsResponse(BaseModel):
    controller_id: int
    iae: float
    itae: float
    ise: float
    mse: float
    std_dev: float
    total_variation: float
    variability_sp: float
    variability_range: float
    sample_count: int


class AIStatusResponse(BaseModel):
    controller_id: int
    engine: AIEngine
    objective: ControlObjective
    speed: ProcessSpeed
    current_ki: float
    last_gamma: float | None = None


class AIConfigUpdateRequest(BaseModel):
    engine: AIEngine | None = None
    objective: ControlObjective | None = None
    speed: ProcessSpeed | None = None


class AITuningLogEntry(BaseModel):
    id: int
    controller_id: int
    timestamp: str
    motor: str
    ki_antes: float | None
    ki_depois: float | None
    objetivo: str | None
    metrica: float | None
    aprovado: bool


class AIHistoryResponse(BaseModel):
    controller_id: int
    entries: list[AITuningLogEntry]
