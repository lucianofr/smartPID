"""AdapterFactory — centralized DI based on CoreSettings."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from smart_pid_core.config import CoreSettings


class AdapterFactory:
    """Creates and caches adapter instances based on configuration.

    When simulator is enabled, SimulatorAdapter serves as TelemetrySource + ControlWriter.
    Otherwise, OPCUAAdapter serves as TelemetrySource + ControlWriter + TagBrowser.
    """

    def __init__(self, settings: CoreSettings) -> None:
        self._settings = settings
        self._simulator_adapter = None
        self._opcua_adapter = None

        if settings.simulator_enabled:
            from smart_pid_core.adapters.inbound.simulator_adapter import SimulatorAdapter

            self._simulator_adapter = SimulatorAdapter(settings=settings)
        else:
            from smart_pid_core.adapters.outbound.opcua_adapter import OPCUAAdapter

            self._opcua_adapter = OPCUAAdapter(settings=settings)

    @property
    def telemetry_source(self):
        """Return the TelemetrySource adapter."""
        if self._settings.simulator_enabled:
            return self._simulator_adapter
        return self._opcua_adapter

    @property
    def control_writer(self):
        """Return the ControlWriter adapter."""
        if self._settings.simulator_enabled:
            return self._simulator_adapter
        return self._opcua_adapter

    @property
    def tag_browser(self):
        """Return the TagBrowser adapter (OPC-UA only)."""
        if self._opcua_adapter is None:
            raise RuntimeError(
                "TagBrowser only available when OPC-UA is active (simulator disabled)"
            )
        return self._opcua_adapter

    @property
    def simulator_adapter(self):
        """Return the SimulatorAdapter if simulator is enabled, else None."""
        return self._simulator_adapter

    @property
    def opcua_adapter(self):
        """Return the OPCUAAdapter if OPC-UA is active, else None."""
        return self._opcua_adapter
