"""AdapterFactory — centralized DI based on CoreSettings."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from smart_pid_core.adapters.outbound.simulator_client import SimulatorClient
    from smart_pid_core.config import CoreSettings


class AdapterFactory:
    """Creates and caches adapter instances based on configuration.

    When simulator is enabled, creates a SimulatorClient (async RPC to the
    standalone twin process — see ``smart_pid_core.simulator_service``) AND
    an OPCUAAdapter pointed at the twin's OPC-UA endpoint. OPCUAAdapter is
    the unified I/O path for all modes; the twin itself never runs
    in-process, so simulator mode differs from real-DCS mode only in where
    OPCUAAdapter connects and in the presence of SimulatorClient.
    """

    def __init__(self, settings: CoreSettings) -> None:
        self._settings = settings
        self._simulator_client: SimulatorClient | None = None

        from smart_pid_core.adapters.outbound.opcua_adapter import OPCUAAdapter

        if settings.simulator_enabled:
            from smart_pid_core.adapters.outbound.simulator_client import SimulatorClient

            self._simulator_client = SimulatorClient(settings.simulator_url)
            opcua_endpoint = (
                settings.simulator_opcua_endpoint
                or f"opc.tcp://localhost:{settings.simulator_port}"
            )
            sim_settings = settings.model_copy(update={"opcua_endpoint": opcua_endpoint})
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
    def simulator_client(self):
        """Return the SimulatorClient if simulator is enabled, else None."""
        return self._simulator_client

    @property
    def opcua_adapter(self):
        """Return the OPCUAAdapter (always available)."""
        return self._opcua_adapter
