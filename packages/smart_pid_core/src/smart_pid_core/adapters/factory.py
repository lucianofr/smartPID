"""AdapterFactory — centralized DI based on CoreSettings."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from smart_pid_core.config import CoreSettings


class AdapterFactory:
    """Creates and caches adapter instances based on configuration.

    When simulator is enabled, creates BOTH SimulatorAdapter (process plant + embedded
    OPC-UA server) AND OPCUAAdapter (client connecting to localhost simulator port).
    OPCUAAdapter is the unified I/O path for all modes.
    """

    def __init__(self, settings: CoreSettings) -> None:
        self._settings = settings
        self._simulator_adapter = None

        from smart_pid_core.adapters.outbound.opcua_adapter import OPCUAAdapter

        if settings.simulator_enabled:
            from smart_pid_core.adapters.inbound.simulator_adapter import SimulatorAdapter

            self._simulator_adapter = SimulatorAdapter(settings=settings)
            sim_settings = settings.model_copy(
                update={"opcua_endpoint": f"opc.tcp://localhost:{settings.simulator_port}"},
            )
            self._opcua_adapter = OPCUAAdapter(settings=sim_settings)
        else:
            self._opcua_adapter = OPCUAAdapter(settings=settings)

    @property
    def telemetry_source(self):
        """Return the TelemetrySource adapter (always OPCUAAdapter)."""
        return self._opcua_adapter

    @property
    def control_writer(self):
        """Return the ControlWriter adapter (always OPCUAAdapter)."""
        return self._opcua_adapter

    @property
    def tag_browser(self):
        """Return the TagBrowser adapter (OPC-UA only, not available in simulator mode)."""
        if self._settings.simulator_enabled:
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
        """Return the OPCUAAdapter (always available)."""
        return self._opcua_adapter
