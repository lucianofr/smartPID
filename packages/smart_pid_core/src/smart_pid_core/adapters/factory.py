"""AdapterFactory — centralized DI based on CoreSettings."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from smart_pid_core.config import CoreSettings


class AdapterFactory:
    """Creates and caches adapter instances based on configuration.

    When simulator is enabled, the same SimulatorAdapter serves as both
    TelemetrySource and ControlWriter.
    """

    def __init__(self, settings: CoreSettings) -> None:
        self._settings = settings
        self._simulator_adapter = None

        if settings.simulator_enabled:
            from smart_pid_core.adapters.inbound.simulator_adapter import SimulatorAdapter

            self._simulator_adapter = SimulatorAdapter(settings=settings)

    @property
    def telemetry_source(self):
        """Return the TelemetrySource adapter."""
        if self._settings.simulator_enabled:
            return self._simulator_adapter
        raise NotImplementedError("OPC-UA client not yet implemented (Phase 3b)")

    @property
    def control_writer(self):
        """Return the ControlWriter adapter."""
        if self._settings.simulator_enabled:
            return self._simulator_adapter
        raise NotImplementedError("OPC-UA writer not yet implemented (Phase 3b)")

    @property
    def simulator_adapter(self):
        """Return the SimulatorAdapter if simulator is enabled, else None."""
        return self._simulator_adapter
