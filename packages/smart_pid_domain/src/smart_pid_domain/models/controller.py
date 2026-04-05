"""Controller configuration and PID parameter models."""
from __future__ import annotations

from dataclasses import dataclass, field

from smart_pid_domain.enums import (
    AIEngine,
    ControllerMode,
    ControlObjective,
    ExecutionMode,
    IntegralType,
    PIDStructure,
    ProcessSpeed,
    TuningWriteMode,
)


@dataclass
class ScaleConfig:
    """Engineering unit scale definition."""

    eu_min: float
    eu_max: float
    unit: str = ""

    def __post_init__(self) -> None:
        if self.eu_min >= self.eu_max:
            msg = f"eu_min ({self.eu_min}) must be less than eu_max ({self.eu_max})"
            raise ValueError(msg)

    @property
    def span(self) -> float:
        return self.eu_max - self.eu_min


@dataclass
class PIDParams:
    """PID tuning parameters."""

    gain: float = 1.0             # Kp (proportional gain)
    reset: float = 10.0           # Ti (integral time, seconds/repeat)
    rate: float = 0.0             # Td (derivative time, seconds)
    alpha: float = 0.125          # Derivative filter factor (Rate/8)
    deadband: float = 0.0         # Integral deadband (engineering units)


@dataclass
class AIConfig:
    """AI optimization configuration."""

    engine: AIEngine = AIEngine.NONE
    objective: ControlObjective = ControlObjective.DISTURBANCE_REJECTION
    process_speed: ProcessSpeed = ProcessSpeed.MEDIUM
    dead_time_l: float = 1.0      # Estimated dead time (seconds)
    limit_min: float = 0.1        # Ki/Ti minimum clamp
    limit_max: float = 100.0      # Ki/Ti maximum clamp


@dataclass
class TagBindings:
    """OPC-UA NodeID mappings for a controller."""

    node_id_pv: str = ""
    node_id_sp: str = ""
    node_id_co: str = ""
    node_id_integral: str = ""
    node_id_bkcal_in: str = ""
    node_id_bkcal_out: str = ""
    node_id_kp: str = ""
    node_id_ti: str = ""
    node_id_td: str = ""
    node_id_mode: str = ""


@dataclass
class ControlOpts:
    """Control strategy options (CONTROL_OPTS from bloco_pid.md).

    Note: ``sp_pv_track_in_lo_or_iman`` and ``sp_pv_track_in_man`` also appear
    in ``IOOpts``.  Per ISA / bloco_pid.md these are independent bits in separate
    option words (CONTROL_OPTS vs IO_OPTS) and must remain separate.
    """

    no_out_limits_in_manual: bool = False
    obey_sp_limits_if_cas: bool = False
    track_in_manual: bool = False
    track_enable: bool = False
    direct_acting: bool = False
    sp_track_retained_target: bool = False
    sp_pv_track_in_lo_or_iman: bool = False
    sp_pv_track_in_rout: bool = False
    sp_pv_track_in_man: bool = False


@dataclass
class IOOpts:
    """I/O processing options (IO_OPTS from bloco_pid.md).

    Note: ``sp_pv_track_in_lo_or_iman`` and ``sp_pv_track_in_man`` also appear
    in ``ControlOpts``.  Per ISA / bloco_pid.md these are independent bits in
    separate option words and must remain separate.
    """

    low_cutoff: bool = False
    target_to_man_if_fault: bool = False
    fault_state_to_value: bool = False  # False=freeze, True=go to value
    increase_to_close: bool = False
    sp_pv_track_in_lo_or_iman: bool = False
    sp_pv_track_in_man: bool = False


@dataclass
class Controller:
    """Complete configuration for a single PID control loop."""

    id: int = 0
    name: str = ""
    description: str = ""
    execution_mode: ExecutionMode = ExecutionMode.DDC
    scan_rate_ms: int = 1000
    pid_params: PIDParams = field(default_factory=PIDParams)
    pid_structure: PIDStructure = PIDStructure.ISA
    integral_type: IntegralType = IntegralType.TIME_TI
    pv_scale: ScaleConfig = field(default_factory=lambda: ScaleConfig(0.0, 100.0))
    out_scale: ScaleConfig = field(default_factory=lambda: ScaleConfig(0.0, 100.0))
    tag_bindings: TagBindings = field(default_factory=TagBindings)
    control_opts: ControlOpts = field(default_factory=ControlOpts)
    io_opts: IOOpts = field(default_factory=IOOpts)
    ai_config: AIConfig = field(default_factory=AIConfig)
    tuning_write_mode: TuningWriteMode = TuningWriteMode.APPROVAL_REQUIRED
    max_tuning_change_pct: float = 10.0
    permitted_modes: set[ControllerMode] = field(
        default_factory=lambda: {ControllerMode.MAN, ControllerMode.AUTO}
    )
    mode_normal: ControllerMode = ControllerMode.AUTO

    # SP limits
    sp_hi_lim: float = 100.0
    sp_lo_lim: float = 0.0
    sp_rate_up: float = 0.0       # 0 = immediate
    sp_rate_dn: float = 0.0       # 0 = immediate

    # Output limits
    out_hi_lim: float = 100.0
    out_lo_lim: float = 0.0

    # Anti-reset windup limits
    arw_hi_lim: float = 100.0
    arw_lo_lim: float = 0.0

    # Filter time constants
    pv_ftime: float = 0.0         # PV filter (seconds)
    sp_ftime: float = 0.0         # SP filter (seconds)

    # Low cutoff
    low_cut: float = 0.0

    # Shed (connection loss)
    shed_opt: ControllerMode = ControllerMode.MAN
    shed_time_s: float = 10.0
