"""AI and statistics request/response DTOs."""
from __future__ import annotations

from pydantic import BaseModel

from smart_pid_domain.enums import (  # noqa: TC001
    AIEngine,
    ControlObjective,
    ProcessSpeed,
    TuningRecStatus,
)


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
    # Raw metrics used by the fuzzy OSC detector — published for live
    # inspection in the HMI so the operator can see why OSC is (or is
    # not) firing.
    mean_abs_error: float = 0.0
    pk_pk_error: float = 0.0
    reversals: int = 0
    zero_crossings: int = 0
    recent_pk_pk_error: float = 0.0
    recent_reversals: int = 0
    tv_per_sample: float = 0.0
    sample_count: int


class AIStatusResponse(BaseModel):
    controller_id: int
    engine: AIEngine
    objective: ControlObjective
    speed: ProcessSpeed
    current_ki: float
    last_gamma: float | None = None
    enabled: bool = True


class AIConfigUpdateRequest(BaseModel):
    engine: AIEngine | None = None
    objective: ControlObjective | None = None
    speed: ProcessSpeed | None = None


class AITuningLogEntry(BaseModel):
    id: int
    controller_id: int
    timestamp: str
    engine: str
    ki_before: float | None
    ki_after: float | None
    objective: str | None
    metric: float | None
    approved: bool


class AIHistoryResponse(BaseModel):
    controller_id: int
    entries: list[AITuningLogEntry]


class TuningRecommendationResponse(BaseModel):
    controller_id: int
    current_kp: float
    current_ti: float
    current_td: float
    recommended_kp: float
    recommended_ti: float
    recommended_td: float
    reason: str
    timestamp: float
    status: TuningRecStatus
    source: str | None = None
