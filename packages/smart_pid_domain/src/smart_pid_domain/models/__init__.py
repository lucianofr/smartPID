"""Domain models for the Smart PID platform."""
from __future__ import annotations

from smart_pid_domain.models.alarm import AlarmEvent
from smart_pid_domain.models.alarm_config import AlarmConfig, AlarmTransition
from smart_pid_domain.models.controller import (
    AIConfig,
    Controller,
    ControlOpts,
    IOOpts,
    PIDParams,
    ScaleConfig,
    TagBindings,
)
from smart_pid_domain.models.process_preset import PRESETS, ProcessPreset
from smart_pid_domain.models.telemetry import ControlAction, TelemetryFrame

__all__ = [
    "AIConfig",
    "AlarmConfig",
    "AlarmEvent",
    "AlarmTransition",
    "ControlAction",
    "ControlOpts",
    "Controller",
    "IOOpts",
    "PRESETS",
    "PIDParams",
    "ProcessPreset",
    "ScaleConfig",
    "TagBindings",
    "TelemetryFrame",
]
