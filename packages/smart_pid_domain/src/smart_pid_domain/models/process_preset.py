"""Process model presets — shared between core (ProcessModel) and HMI (SimulatorPage)."""
from __future__ import annotations

from dataclasses import dataclass

from smart_pid_domain.enums import ProcessPresetName


@dataclass(frozen=True)
class ProcessPreset:
    """Immutable process model parameters for a simulator preset."""

    name: ProcessPresetName
    gain: float
    tau1: float
    tau2: float | None
    dead_time: float


PRESETS: dict[ProcessPresetName, ProcessPreset] = {
    ProcessPresetName.FLOW: ProcessPreset(
        name=ProcessPresetName.FLOW, gain=1.2, tau1=3.0, tau2=None, dead_time=1.0,
    ),
    ProcessPresetName.PRESSURE: ProcessPreset(
        name=ProcessPresetName.PRESSURE, gain=0.8, tau1=10.0, tau2=None, dead_time=2.0,
    ),
    ProcessPresetName.LEVEL: ProcessPreset(
        name=ProcessPresetName.LEVEL, gain=2.0, tau1=30.0, tau2=15.0, dead_time=5.0,
    ),
    ProcessPresetName.TEMPERATURE: ProcessPreset(
        name=ProcessPresetName.TEMPERATURE, gain=1.5, tau1=60.0, tau2=20.0, dead_time=10.0,
    ),
}
