"""Tests for AdapterFactory — conditional dependency injection."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from smart_pid_core.adapters.factory import AdapterFactory
from smart_pid_core.adapters.inbound.simulator_adapter import SimulatorAdapter
from smart_pid_core.adapters.outbound.opcua_adapter import OPCUAAdapter
from smart_pid_core.config import CoreSettings

_MOCK_OPCUA = "smart_pid_core.adapters.inbound.simulator_adapter.OPCUAServer"


def _patch_opcua_server():
    """Patch OPCUAServer to avoid real port binding in tests."""
    from unittest.mock import MagicMock

    mock = MagicMock()
    mock.is_running = False
    mock.controller_node_ids = {}
    return patch(_MOCK_OPCUA, return_value=mock)


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
        with _patch_opcua_server():
            factory = AdapterFactory(sim_settings)
            assert isinstance(factory.telemetry_source, OPCUAAdapter)

    def test_control_writer_is_opcua(self, sim_settings: CoreSettings) -> None:
        with _patch_opcua_server():
            factory = AdapterFactory(sim_settings)
            assert isinstance(factory.control_writer, OPCUAAdapter)

    def test_telemetry_and_control_same_instance(self, sim_settings: CoreSettings) -> None:
        with _patch_opcua_server():
            factory = AdapterFactory(sim_settings)
            assert factory.telemetry_source is factory.control_writer

    def test_simulator_adapter_property(self, sim_settings: CoreSettings) -> None:
        with _patch_opcua_server():
            factory = AdapterFactory(sim_settings)
            assert factory.simulator_adapter is not None
            assert isinstance(factory.simulator_adapter, SimulatorAdapter)

    def test_opcua_adapter_always_available(self, sim_settings: CoreSettings) -> None:
        with _patch_opcua_server():
            factory = AdapterFactory(sim_settings)
            assert factory.opcua_adapter is not None
            assert isinstance(factory.opcua_adapter, OPCUAAdapter)

    def test_opcua_connects_to_simulator_port(self, sim_settings: CoreSettings) -> None:
        with _patch_opcua_server():
            factory = AdapterFactory(sim_settings)
            expected = f"opc.tcp://localhost:{sim_settings.simulator_port}"
            assert factory.opcua_adapter._endpoint == expected

    def test_tag_browser_raises_when_simulator(self, sim_settings: CoreSettings) -> None:
        with _patch_opcua_server():
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

    def test_simulator_adapter_is_none(self, prod_settings: CoreSettings) -> None:
        factory = AdapterFactory(prod_settings)
        assert factory.simulator_adapter is None

    def test_opcua_adapter_property(self, prod_settings: CoreSettings) -> None:
        factory = AdapterFactory(prod_settings)
        assert factory.opcua_adapter is not None
