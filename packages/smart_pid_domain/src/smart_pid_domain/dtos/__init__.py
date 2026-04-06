"""Phase 2+ DTOs — shared between core and HMI."""
from smart_pid_domain.dtos.ai import (
    AIConfigUpdateRequest,
    AIHistoryResponse,
    AIStatusResponse,
    AITuningLogEntry,
    StatsResponse,
)
from smart_pid_domain.dtos.alarms import AlarmAckRequest, AlarmResponse
from smart_pid_domain.dtos.auth import LoginRequest, TokenResponse, UserClaims, UserCreate
from smart_pid_domain.dtos.commands import (
    CommandResponse,
    ModeCommand,
    OutputCommand,
    SetpointCommand,
)
from smart_pid_domain.dtos.config import (
    PIDTuningResponse,
    PIDTuningUpdate,
    TagBindingsResponse,
    TagBindingsUpdate,
)
from smart_pid_domain.dtos.controllers import (
    AIConfigDTO,
    ControllerCreate,
    ControllerResponse,
    ControllerUpdate,
    ControlOptsDTO,
    IOOptsDTO,
    PIDParamsDTO,
    ScaleConfigDTO,
    TagBindingsDTO,
)
from smart_pid_domain.dtos.export import ExportJob, ExportRequest
from smart_pid_domain.dtos.history import HistoryResponse, TelemetryFrameDTO
from smart_pid_domain.dtos.opcua import (
    OPCUABrowseResponse,
    OPCUANodeInfo,
    OPCUASearchResponse,
    OPCUAStatusResponse,
)
from smart_pid_domain.dtos.project import (
    ProjectCreate,
    ProjectOpen,
    ProjectResponse,
    ProjectSaveAs,
)
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
    "AIConfigDTO",
    "AIConfigUpdateRequest",
    "AIHistoryResponse",
    "AIStatusResponse",
    "AITuningLogEntry",
    "AlarmAckRequest",
    "AlarmResponse",
    "CommandResponse",
    "ControlOptsDTO",
    "ControllerCreate",
    "ControllerResponse",
    "ControllerSimStatus",
    "ControllerUpdate",
    "ExportJob",
    "ExportRequest",
    "IOOptsDTO",
    "HistoryResponse",
    "LoginRequest",
    "ModeCommand",
    "OPCUABrowseResponse",
    "OPCUANodeInfo",
    "OPCUASearchResponse",
    "OPCUAStatusResponse",
    "OutputCommand",
    "PIDParamsDTO",
    "PIDTuningResponse",
    "PIDTuningUpdate",
    "ProjectCreate",
    "ProjectOpen",
    "ProjectResponse",
    "ProjectSaveAs",
    "SetpointCommand",
    "SimulatorDisturbanceRequest",
    "SimulatorParametersRequest",
    "ScaleConfigDTO",
    "SimulatorPresetRequest",
    "SimulatorStatusResponse",
    "StatsResponse",
    "SystemStatusResponse",
    "TagBindingsDTO",
    "TagBindingsResponse",
    "TagBindingsUpdate",
    "TelemetryFrameDTO",
    "TokenResponse",
    "UserClaims",
    "UserCreate",
    "UserResponse",
    "UserUpdate",
]
