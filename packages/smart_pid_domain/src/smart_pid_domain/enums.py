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
    ONLINE = "ONLINE"
    RECONNECTING = "RECONNECTING"

class SignalStatus(StrEnum):
    GOOD = "GOOD"
    BAD = "BAD"
    UNCERTAIN = "UNCERTAIN"

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
