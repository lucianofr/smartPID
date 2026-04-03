"""Phase 2 DTOs — shared between core and HMI."""
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
from smart_pid_domain.dtos.system import SystemStatusResponse

__all__ = [
    "CommandResponse",
    "ControllerCreate",
    "ControllerResponse",
    "ControllerUpdate",
    "HistoryResponse",
    "LoginRequest",
    "ModeCommand",
    "OutputCommand",
    "SetpointCommand",
    "SystemStatusResponse",
    "TelemetryFrameDTO",
    "TokenResponse",
    "UserClaims",
    "UserCreate",
]
