"""Controller CRUD DTOs — full 30+ field coverage."""
from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

#: Controller tag names are shown in the HMI, embedded in OPC-UA node paths and
#: stored in every log row, so they are bounded at the API boundary rather than
#: left to the database to truncate or the UI to overflow.
MAX_CONTROLLER_NAME_LEN = 128

# ── Nested sub-model DTOs ────────────────────────────────────────────────────


class PIDParamsDTO(BaseModel):
    """PID tuning parameters (mirrors domain PIDParams)."""

    gain: float = 1.0
    reset: float = 10.0
    rate: float = 0.0
    alpha: float = 0.125
    deadband: float = 0.0


class ScaleConfigDTO(BaseModel):
    """Engineering-unit scale (mirrors domain ScaleConfig)."""

    eu_min: float = 0.0
    eu_max: float = 100.0
    unit: str = ""


class AIConfigDTO(BaseModel):
    """AI optimization config (mirrors domain AIConfig)."""

    engine: str = "NONE"
    objective: str = "DISTURBANCE_REJECTION"
    dead_time_l: float = 1.0
    limit_min: float = 1.0
    limit_max: float = 10.0
    rl_fallback_kp: float = 0.6
    rl_fallback_kd: float = 0.2
    rl_learning_rate: float = 3e-4
    rl_train_interval: int = 32
    # Surge Level tuning band — see domain AIConfig for semantics.
    sl_band_lo_pct: float | None = None
    sl_band_hi_pct: float | None = None
    sl_error_small_pct: float = 5.0
    sl_co_ramp_max_pct_min: float = 10.0

    @model_validator(mode="after")
    def _check_surge_level_params(self) -> AIConfigDTO:
        for name in ("sl_band_lo_pct", "sl_band_hi_pct"):
            pct = getattr(self, name)
            if pct is not None and not 0.0 <= pct <= 100.0:
                msg = f"{name} must be between 0 and 100 % of span"
                raise ValueError(msg)
        lo, hi = self.sl_band_lo_pct, self.sl_band_hi_pct
        if lo is not None and hi is not None and lo >= hi:
            msg = "sl_band_lo_pct must be strictly below sl_band_hi_pct"
            raise ValueError(msg)
        if self.sl_error_small_pct <= 0.0:
            msg = "sl_error_small_pct must be greater than 0"
            raise ValueError(msg)
        if self.sl_co_ramp_max_pct_min < 0.0:
            msg = "sl_co_ramp_max_pct_min must not be negative"
            raise ValueError(msg)
        return self


class TagBindingsDTO(BaseModel):
    """OPC-UA NodeID mappings (mirrors domain TagBindings)."""

    node_id_pv: str = ""
    node_id_sp: str = ""
    node_id_co: str = ""
    node_id_integral: str = ""
    node_id_bkcal_in: str = ""
    node_id_bkcal_out: str = ""
    node_id_kp: str = ""
    node_id_ti: str = ""
    node_id_td: str = ""
    node_id_mode_target: str = ""
    node_id_mode_actual: str = ""
    node_id_enabled: str = ""
    mode_int_map: dict[str, int] = {}

    @model_validator(mode="after")
    def _no_duplicate_int_values(self) -> TagBindingsDTO:
        vals = list(self.mode_int_map.values())
        if len(vals) != len(set(vals)):
            msg = "Duplicate integer values in mode_int_map"
            raise ValueError(msg)
        return self


class ControlOptsDTO(BaseModel):
    """Control strategy options (mirrors domain ControlOpts)."""

    no_out_limits_in_manual: bool = False
    obey_sp_limits_if_cas: bool = False
    track_in_manual: bool = False
    track_enable: bool = False
    direct_acting: bool = False
    sp_track_retained_target: bool = False
    sp_pv_track_in_lo_or_iman: bool = False
    sp_pv_track_in_rout: bool = False
    sp_pv_track_in_man: bool = False
    use_pv_for_bkcal_out: bool = False


class IOOptsDTO(BaseModel):
    """I/O processing options (mirrors domain IOOpts)."""

    low_cutoff: bool = False
    target_to_man_if_fault: bool = False
    fault_state_to_value: bool = False
    increase_to_close: bool = False
    sp_pv_track_in_lo_or_iman: bool = False
    sp_pv_track_in_man: bool = False


# ── CRUD DTOs ────────────────────────────────────────────────────────────────


class ControllerCreate(BaseModel):
    """Payload for creating a new controller (all fields have defaults except name)."""

    name: str = Field(min_length=1, max_length=MAX_CONTROLLER_NAME_LEN)
    description: str = ""
    execution_mode: str = "SUPERVISORY"
    scan_rate_s: float = 1.0
    tss_s: float = 60.0
    process_speed: str = "MEDIUM"

    # Nested config groups
    pid_params: PIDParamsDTO = PIDParamsDTO()
    pid_structure: str = "ISA"
    integral_type: str = "TIME_TI"
    pv_scale: ScaleConfigDTO = ScaleConfigDTO()
    out_scale: ScaleConfigDTO = ScaleConfigDTO()
    tag_bindings: TagBindingsDTO = TagBindingsDTO()
    control_opts: ControlOptsDTO = ControlOptsDTO()
    io_opts: IOOptsDTO = IOOptsDTO()
    ai_config: AIConfigDTO = AIConfigDTO()

    # Tuning write policy
    tuning_write_mode: str = "approval_required"
    max_tuning_change_pct: float = 10.0
    stability_band_pct: float | None = None

    # Mode config
    mode_normal: str = "AUTO"
    permitted_modes: list[str] = ["MAN", "AUTO"]

    # SP limits
    sp_hi_lim: float = 100.0
    sp_lo_lim: float = 0.0
    sp_rate_up: float = 0.0
    sp_rate_dn: float = 0.0

    # Output limits
    out_hi_lim: float = 100.0
    out_lo_lim: float = 0.0

    # Anti-reset windup limits
    arw_hi_lim: float = 100.0
    arw_lo_lim: float = 0.0

    # Filter time constants
    pv_ftime: float = 0.0
    sp_ftime: float = 0.0

    # Low cutoff
    low_cut: float = 0.0

    # Feedforward
    ff_enable: bool = False
    ff_gain: float = 1.0

    # Shed (connection loss)
    shed_opt: str = "MAN"
    shed_time_s: float = 10.0


class ControllerUpdate(BaseModel):
    """Patch payload — all fields optional."""

    name: str | None = Field(default=None, min_length=1, max_length=MAX_CONTROLLER_NAME_LEN)
    description: str | None = None
    execution_mode: str | None = None
    scan_rate_s: float | None = None
    tss_s: float | None = None
    process_speed: str | None = None

    pid_params: PIDParamsDTO | None = None
    pid_structure: str | None = None
    integral_type: str | None = None
    pv_scale: ScaleConfigDTO | None = None
    out_scale: ScaleConfigDTO | None = None
    tag_bindings: TagBindingsDTO | None = None
    control_opts: ControlOptsDTO | None = None
    io_opts: IOOptsDTO | None = None
    ai_config: AIConfigDTO | None = None

    tuning_write_mode: str | None = None
    max_tuning_change_pct: float | None = None
    stability_band_pct: float | None = None

    mode_normal: str | None = None
    permitted_modes: list[str] | None = None

    sp_hi_lim: float | None = None
    sp_lo_lim: float | None = None
    sp_rate_up: float | None = None
    sp_rate_dn: float | None = None

    out_hi_lim: float | None = None
    out_lo_lim: float | None = None

    arw_hi_lim: float | None = None
    arw_lo_lim: float | None = None

    pv_ftime: float | None = None
    sp_ftime: float | None = None

    low_cut: float | None = None

    ff_enable: bool | None = None
    ff_gain: float | None = None

    shed_opt: str | None = None
    shed_time_s: float | None = None


class ControllerResponse(BaseModel):
    """Full controller state returned by the API."""

    id: int
    name: str
    description: str
    mode: str
    pv: float
    sp: float
    co: float

    execution_mode: str = "SUPERVISORY"
    scan_rate_s: float = 1.0
    tss_s: float = 60.0
    process_speed: str = "MEDIUM"

    pid_params: PIDParamsDTO = PIDParamsDTO()
    pid_structure: str = "ISA"
    integral_type: str = "TIME_TI"
    pv_scale: ScaleConfigDTO = ScaleConfigDTO()
    out_scale: ScaleConfigDTO = ScaleConfigDTO()
    tag_bindings: TagBindingsDTO = TagBindingsDTO()
    control_opts: ControlOptsDTO = ControlOptsDTO()
    io_opts: IOOptsDTO = IOOptsDTO()
    ai_config: AIConfigDTO = AIConfigDTO()

    optimization_enabled: bool = True

    tuning_write_mode: str = "approval_required"
    max_tuning_change_pct: float = 10.0
    stability_band_pct: float | None = None

    mode_normal: str = "AUTO"
    permitted_modes: list[str] = ["MAN", "AUTO"]

    sp_hi_lim: float = 100.0
    sp_lo_lim: float = 0.0
    sp_rate_up: float = 0.0
    sp_rate_dn: float = 0.0

    out_hi_lim: float = 100.0
    out_lo_lim: float = 0.0

    arw_hi_lim: float = 100.0
    arw_lo_lim: float = 0.0

    pv_ftime: float = 0.0
    sp_ftime: float = 0.0

    low_cut: float = 0.0

    ff_enable: bool = False
    ff_gain: float = 1.0

    shed_opt: str = "MAN"
    shed_time_s: float = 10.0
