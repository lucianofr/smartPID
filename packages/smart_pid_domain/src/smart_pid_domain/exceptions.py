"""Typed exception hierarchy for the Smart PID platform."""
from __future__ import annotations

class SmartPIDError(Exception):
    """Base exception for all Smart PID errors."""

class DomainError(SmartPIDError):
    pass

class PIDComputationError(DomainError):
    pass

class InvalidModeTransition(DomainError):
    def __init__(self, current: str, target: str, reason: str) -> None:
        self.current = current
        self.target = target
        self.reason = reason
        super().__init__(f"Cannot transition from {current} to {target}: {reason}")

class AIInferenceError(DomainError):
    pass

class AlarmConfigError(DomainError):
    pass

class InfrastructureError(SmartPIDError):
    pass

class OPCUAConnectionError(InfrastructureError):
    pass

class OPCUAReadError(InfrastructureError):
    pass

class OPCUAWriteError(InfrastructureError):
    pass

class DatabaseError(InfrastructureError):
    pass

class ExportError(InfrastructureError):
    pass

class CommunicationError(SmartPIDError):
    pass

class APIConnectionError(CommunicationError):
    pass

class APIAuthError(CommunicationError):
    pass

class APITimeoutError(CommunicationError):
    pass

class TelemetryStreamError(CommunicationError):
    pass

class ProjectError(SmartPIDError):
    pass

class ProjectNotFoundError(ProjectError):
    pass

class ProjectCorruptedError(ProjectError):
    pass

class AuthenticationError(SmartPIDError):
    pass

class AuthorizationError(SmartPIDError):
    pass
