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
    SLOW = "SLOW"
    MEDIUM = "MEDIUM"
    FAST = "FAST"

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
