"""Tests for AdapterFactory — conditional dependency injection."""
from __future__ import annotations

import pytest

from smart_pid_core.adapters.factory import AdapterFactory
from smart_pid_core.adapters.outbound.opcua_adapter import OPCUAAdapter
from smart_pid_core.adapters.outbound.simulator_client import SimulatorClient
from smart_pid_core.config import CoreSettings


@pytest.fixture
def sim_settings() -> CoreSettings:
    return CoreSettings(
        jwt_secret="test-secret-key-minimum-32-bytes!",
        simulator_enabled=True,
        simulator_interval_ms=50,
    )  # type: ignore[call-arg]


@pytest.fixture
def prod_settings() -> CoreSettings:
    return CoreSettings(
        jwt_secret="test-secret-key-minimum-32-bytes!",
        simulator_enabled=False,
    )  # type: ignore[call-arg]


class TestAdapterFactorySimulator:
    def test_telemetry_source_is_opcua(self, sim_settings: CoreSettings) -> None:
        factory = AdapterFactory(sim_settings)
        assert isinstance(factory.telemetry_source, OPCUAAdapter)

    def test_control_writer_is_opcua(self, sim_settings: CoreSettings) -> None:
        factory = AdapterFactory(sim_settings)
        assert isinstance(factory.control_writer, OPCUAAdapter)

    def test_telemetry_and_control_same_instance(self, sim_settings: CoreSettings) -> None:
        factory = AdapterFactory(sim_settings)
        assert factory.telemetry_source is factory.control_writer

    def test_simulator_client_property(self, sim_settings: CoreSettings) -> None:
        factory = AdapterFactory(sim_settings)
        assert factory.simulator_client is not None
        assert isinstance(factory.simulator_client, SimulatorClient)

    def test_opcua_adapter_always_available(self, sim_settings: CoreSettings) -> None:
        factory = AdapterFactory(sim_settings)
        assert factory.opcua_adapter is not None
        assert isinstance(factory.opcua_adapter, OPCUAAdapter)

    def test_opcua_connects_to_simulator_port(self, sim_settings: CoreSettings) -> None:
        factory = AdapterFactory(sim_settings)
        expected = f"opc.tcp://localhost:{sim_settings.simulator_port}"
        assert factory.opcua_adapter._endpoint == expected

    def test_opcua_connects_to_explicit_advertised_endpoint(
        self, sim_settings: CoreSettings,
    ) -> None:
        """simulator_opcua_endpoint, when set, wins over the localhost derivation
        (the twin running in its own container)."""
        settings = sim_settings.model_copy(
            update={"simulator_opcua_endpoint": "opc.tcp://twin-host:4849"}
        )
        factory = AdapterFactory(settings)
        assert factory.opcua_adapter._endpoint == "opc.tcp://twin-host:4849"

    def test_tag_browser_raises_when_simulator(self, sim_settings: CoreSettings) -> None:
        factory = AdapterFactory(sim_settings)
        with pytest.raises(RuntimeError, match="TagBrowser"):
            _ = factory.tag_browser


class TestAdapterFactoryOPCUA:
    def test_telemetry_source_returns_opcua(self, prod_settings: CoreSettings) -> None:
        factory = AdapterFactory(prod_settings)
        assert isinstance(factory.telemetry_source, OPCUAAdapter)

    def test_control_writer_returns_opcua(self, prod_settings: CoreSettings) -> None:
        factory = AdapterFactory(prod_settings)
        assert isinstance(factory.control_writer, OPCUAAdapter)

    def test_tag_browser_returns_opcua(self, prod_settings: CoreSettings) -> None:
        factory = AdapterFactory(prod_settings)
        assert isinstance(factory.tag_browser, OPCUAAdapter)

    def test_opcua_adapter_is_same_instance(self, prod_settings: CoreSettings) -> None:
        factory = AdapterFactory(prod_settings)
        assert factory.telemetry_source is factory.control_writer

    def test_simulator_client_is_none(self, prod_settings: CoreSettings) -> None:
        factory = AdapterFactory(prod_settings)
        assert factory.simulator_client is None

    def test_opcua_adapter_property(self, prod_settings: CoreSettings) -> None:
        factory = AdapterFactory(prod_settings)
        assert factory.opcua_adapter is not None
