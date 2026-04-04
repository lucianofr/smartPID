"""Phase 2 DTOs — shared between core and HMI."""
from smart_pid_domain.dtos.alarms import AlarmAckRequest, AlarmResponse
from smart_pid_domain.dtos.auth import LoginRequest, TokenResponse, UserClaims, UserCreate
from smart_pid_domain.dtos.commands import (
    CommandResponse,
    ModeCommand,
    OutputCommand,
    SetpointCommand,
)
from smart_pid_domain.dtos.controllers import (
    ControllerCreate,
    ControllerResponse,
    ControllerUpdate,
)
from smart_pid_domain.dtos.history import HistoryResponse, TelemetryFrameDTO
from smart_pid_domain.dtos.simulator import (
    ControllerSimStatus,
    SimulatorDisturbanceRequest,
    SimulatorParametersRequest,
    SimulatorPresetRequest,
    SimulatorStatusResponse,
)
from smart_pid_domain.dtos.system import SystemStatusResponse
from smart_pid_domain.dtos.users import UserResponse, UserUpdate

__all__ = [
    "AlarmAckRequest",
    "AlarmResponse",
    "CommandResponse",
    "ControllerCreate",
    "ControllerResponse",
    "ControllerSimStatus",
    "ControllerUpdate",
    "HistoryResponse",
    "LoginRequest",
    "ModeCommand",
    "OutputCommand",
    "SetpointCommand",
    "SimulatorDisturbanceRequest",
    "SimulatorParametersRequest",
    "SimulatorPresetRequest",
    "SimulatorStatusResponse",
    "SystemStatusResponse",
    "TelemetryFrameDTO",
    "TokenResponse",
    "UserClaims",
    "UserCreate",
    "UserResponse",
    "UserUpdate",
]
