"""Typed exception hierarchy for Smart PID."""
from __future__ import annotations


class SmartPIDError(Exception):
    """Base error for entire application."""


class DomainError(SmartPIDError):
    """Errors from domain logic."""


class PIDComputationError(DomainError):
    """Error during PID calculation."""


class InvalidModeTransition(DomainError):
    """Invalid PID mode transition requested."""

    def __init__(self, current: str, target: str, reason: str) -> None:
        super().__init__(f"Cannot transition from {current} to {target}: {reason}")
        self.current = current
        self.target = target
        self.reason = reason


class InfrastructureError(SmartPIDError):
    """Errors from adapters/external systems."""


class OPCUAConnectionError(InfrastructureError):
    """Failed to connect to OPC-UA server."""


class DatabaseError(InfrastructureError):
    """Database operation failed."""


class ProjectError(SmartPIDError):
    """Errors related to project lifecycle."""


class ProjectNotFoundError(ProjectError):
    """Project file (.spid) not found."""
