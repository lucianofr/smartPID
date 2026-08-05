"""Integration test for main.py adapter wiring."""
from __future__ import annotations

from smart_pid_core.config import CoreSettings


class TestMainAdapterWiring:
    def test_simulator_mode_creates_both_adapters(self) -> None:
        """Verify that in simulator mode, AdapterFactory creates both adapters."""
        settings = CoreSettings(
            jwt_secret="test-secret-key-minimum-32-bytes!",
            simulator_enabled=True,
            simulator_port=48460,
        )  # type: ignore[call-arg]

        from smart_pid_core.adapters.factory import AdapterFactory

        factory = AdapterFactory(settings)
        assert factory.simulator_client is not None
        assert factory.opcua_adapter is not None

    def test_non_simulator_mode_no_simulator(self) -> None:
        """Verify that without simulator, only OPCUAAdapter is created."""
        settings = CoreSettings(
            jwt_secret="test-secret-key-minimum-32-bytes!",
            simulator_enabled=False,
        )  # type: ignore[call-arg]

        from smart_pid_core.adapters.factory import AdapterFactory

        factory = AdapterFactory(settings)
        assert factory.simulator_client is None
        assert factory.opcua_adapter is not None

    def test_simulator_mode_opcua_endpoint_points_to_simulator(self) -> None:
        """Verify OPCUAAdapter endpoint points to simulator port when enabled."""
        settings = CoreSettings(
            jwt_secret="test-secret-key-minimum-32-bytes!",
            simulator_enabled=True,
            simulator_port=48461,
        )  # type: ignore[call-arg]

        from smart_pid_core.adapters.factory import AdapterFactory

        factory = AdapterFactory(settings)
        assert "48461" in factory.opcua_adapter.endpoint
