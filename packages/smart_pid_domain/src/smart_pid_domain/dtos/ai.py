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
    osc: float = 0.0
    osc_period_s: float = 0.0
    # Excitation context for the same detector: how many samples it was
    # allowed to look at (0 means unmeasured, not calm) and how far the
    # setpoint itself travelled — the scale the amplitude is judged against.
    osc_sample_count: int = 0
    sp_pk_pk: float = 0.0
    overshoot: float = 0.0
    sample_count: int


class AIStatusResponse(BaseModel):
    controller_id: int
    engine: AIEngine
    objective: ControlObjective
    speed: ProcessSpeed
    current_ki: float
    last_gamma: float | None = None
    enabled: bool = True
    # Distinguishes RUN from PAUSE: `enabled` alone cannot express the
    # three-state RUN/PAUSE/STOP lifecycle the HMI drives.
    paused: bool = False


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


class FuzzyMembershipFunction(BaseModel):
    label: str            # e.g. "LOW"
    kind: str              # "tri" | "trap"
    params: list[float]    # 3 values for tri, 4 for trap
    degree: float           # membership degree of the crisp input, 0..1


class FuzzyInputTrace(BaseModel):
    name: str               # e.g. "iae"
    value: float            # crisp input value
    domain_min: float       # plot x-axis lower bound
    domain_max: float       # plot x-axis upper bound
    functions: list[FuzzyMembershipFunction]


class FuzzyRuleTrace(BaseModel):
    index: int                   # position in the strategy rule base, 0-based
    conditions: dict[str, str]   # {"iae": "HIGH", "osc": "STABLE"}
    output: str                  # output level label, e.g. "R"
    strength: float              # firing strength 0..1
    fired: bool                  # strength > 0.0


class FuzzyOutputTrace(BaseModel):
    label: str       # e.g. "R"
    center: float    # singleton centre, e.g. -0.15
    strength: float  # aggregated strength


class FuzzyTraceResponse(BaseModel):
    controller_id: int
    objective: ControlObjective
    timestamp: float                   # unix seconds when infer() ran
    inputs: list[FuzzyInputTrace]
    rules: list[FuzzyRuleTrace]
    outputs: list[FuzzyOutputTrace]
    delta_ti: float                    # defuzzified output
