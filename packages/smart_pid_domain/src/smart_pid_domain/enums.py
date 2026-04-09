"""All shared enumerations for the Smart PID platform."""
from __future__ import annotations

from enum import StrEnum


class ControllerMode(StrEnum):
    """Operating modes for the PID block."""
    OOS = "OOS"
    IMAN = "IMAN"
    LO = "LO"
    MAN = "MAN"
    AUTO = "AUTO"
    CAS = "CAS"
    RCAS = "RCAS"
    ROUT = "ROUT"
    BYPASS = "BYPASS"

class ExecutionMode(StrEnum):
    SUPERVISORY = "SUPERVISORY"
    DDC = "DDC"

class PIDStructure(StrEnum):
    ISA = "ISA"
    PARALLEL = "PARALLEL"
    SERIES = "SERIES"

class IntegralType(StrEnum):
    GAIN_KI = "GAIN_KI"
    TIME_TI = "TIME_TI"

class AIEngine(StrEnum):
    NONE = "NONE"
    FUZZY = "FUZZY"
    RL = "RL"

class ControlObjective(StrEnum):
    SP_TRACKING = "SP_TRACKING"
    DISTURBANCE_REJECTION = "DISTURBANCE_REJECTION"
    SURGE_LEVEL = "SURGE_LEVEL"

class ProcessSpeed(StrEnum):
    """Process dynamics speed — determines stats window and AI speed factor."""

    ULTRA_FAST = "ULTRA_FAST"
    FAST = "FAST"
    MEDIUM = "MEDIUM"
    SLOW = "SLOW"

    @property
    def stats_window_s(self) -> int:
        """Default statistics sliding window in seconds."""
        return _STATS_WINDOWS[self]

    @property
    def speed_factor(self) -> float:
        """AI tuning aggressiveness factor (Sv)."""
        return _SPEED_FACTORS[self]

    @property
    def ai_period_s(self) -> int:
        """AI optimization cycle period in seconds."""
        return _AI_PERIODS[self]

    @property
    def label(self) -> str:
        """Human-readable label with process examples for UI."""
        return _LABELS[self]


_STATS_WINDOWS: dict[ProcessSpeed, int] = {
    ProcessSpeed.ULTRA_FAST: 5,
    ProcessSpeed.FAST: 60,
    ProcessSpeed.MEDIUM: 1200,
    ProcessSpeed.SLOW: 7200,
}

_SPEED_FACTORS: dict[ProcessSpeed, float] = {
    ProcessSpeed.ULTRA_FAST: 0.50,
    ProcessSpeed.FAST: 0.30,
    ProcessSpeed.MEDIUM: 0.15,
    ProcessSpeed.SLOW: 0.08,
}

_AI_PERIODS: dict[ProcessSpeed, int] = {
    ProcessSpeed.ULTRA_FAST: 30,
    ProcessSpeed.FAST: 180,
    ProcessSpeed.MEDIUM: 1800,
    ProcessSpeed.SLOW: 14400,
}

_LABELS: dict[ProcessSpeed, str] = {
    ProcessSpeed.ULTRA_FAST: "Ultra Fast — Motors / Converters",
    ProcessSpeed.FAST: "Fast — Flow / Pressure",
    ProcessSpeed.MEDIUM: "Medium — Level / Heat Exchangers",
    ProcessSpeed.SLOW: "Slow — Furnaces / Distillation",
}

class ConnectionState(StrEnum):
    OFFLINE = "OFFLINE"
    CONNECTING = "CONNECTING"
    ONLINE = "ONLINE"
    RECONNECTING = "RECONNECTING"

class SignalSeverity(StrEnum):
    """OPC-UA StatusCode severity (bits 31:30)."""
    GOOD = "GOOD"
    UNCERTAIN = "UNCERTAIN"
    BAD = "BAD"


# Backward compatibility alias — will be removed in a future version
SignalStatus = SignalSeverity


class LimitBits(StrEnum):
    """OPC-UA StatusCode limit bits (bits 9:8) for directional anti-windup."""
    NONE = "NONE"
    LOW_LIMITED = "LOW_LIMITED"
    HIGH_LIMITED = "HIGH_LIMITED"
    CONSTANT = "CONSTANT"


class InitSubStatus(StrEnum):
    """FF cascade handshake sub-status."""
    NONE = "NONE"
    NI = "NI"
    IR = "IR"
    IA = "IA"
    GOOD_CASCADE = "GOOD_CASCADE"

class OptimizerState(StrEnum):
    RUN = "RUN"
    PAUSE = "PAUSE"
    STOP = "STOP"

class UserRole(StrEnum):
    ADMIN = "ADMIN"
    SUPERVISOR = "SUPERVISOR"
    OPERATOR = "OPERATOR"

class AlarmPriority(StrEnum):
    CRITICAL = "CRITICAL"
    WARNING = "WARNING"
    ADVISORY = "ADVISORY"
    LOG = "LOG"

class AlarmType(StrEnum):
    HIHI = "HIHI"
    HI = "HI"
    LO = "LO"
    LOLO = "LOLO"
    DV_HI = "DV_HI"
    DV_LO = "DV_LO"

class AlarmState(StrEnum):
    """ISA-18.2 alarm states for ACK workflow."""
    UNACKNOWLEDGED = "UNACKNOWLEDGED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    CLEARED_UNACK = "CLEARED_UNACK"


class AuditAction(StrEnum):
    """Audit trail action types."""
    LOGIN = "LOGIN"
    LOGOUT = "LOGOUT"
    SP_CHANGE = "SP_CHANGE"
    MODE_CHANGE = "MODE_CHANGE"
    OUTPUT_CHANGE = "OUTPUT_CHANGE"
    ACK_ALARM = "ACK_ALARM"
    ACK_ALARM_ALL = "ACK_ALARM_ALL"
    TUNE_PID = "TUNE_PID"
    CONFIG_AI = "CONFIG_AI"
    CONFIG_ALARM = "CONFIG_ALARM"
    CREATE_CONTROLLER = "CREATE_CONTROLLER"
    UPDATE_CONTROLLER = "UPDATE_CONTROLLER"
    DELETE_CONTROLLER = "DELETE_CONTROLLER"
    CREATE_USER = "CREATE_USER"
    UPDATE_USER = "UPDATE_USER"
    DEACTIVATE_USER = "DEACTIVATE_USER"
    SIMULATOR_CONFIG = "SIMULATOR_CONFIG"
    OPCUA_CONFIG = "OPCUA_CONFIG"


class ProcessPresetName(StrEnum):
    """Simulator process model presets."""
    FLOW = "FLOW"
    PRESSURE = "PRESSURE"
    LEVEL = "LEVEL"
    TEMPERATURE = "TEMPERATURE"
    CUSTOM = "CUSTOM"


class TuningWriteMode(StrEnum):
    """How AI tuning recommendations are applied to PID parameters."""
    AUTO_APPLY = "auto_apply"
    APPROVAL_REQUIRED = "approval_required"
    DISABLED = "disabled"


class TuningRecStatus(StrEnum):
    """Lifecycle status of an AI tuning recommendation."""
    PENDING = "pending"
    APPLIED = "applied"
    REJECTED = "rejected"
    EXPIRED = "expired"


class SystemExecutionMode(StrEnum):
    """System-wide execution mode: monitor-only or full execute."""
    MONITOR = "monitor"
    EXECUTE = "execute"


class ProcessType(StrEnum):
    """Informational: process dynamics classification for AI engine."""
    SELF_REGULATING = "SELF_REGULATING"
    INTEGRATING = "INTEGRATING"


class TrackOpt(StrEnum):
    """TRK_IN_D behavior when signal quality is BAD."""
    ALWAYS_USE_VALUE = "ALWAYS_USE_VALUE"
    USE_LAST_GOOD = "USE_LAST_GOOD"
    TRACK_IF_BAD = "TRACK_IF_BAD"
