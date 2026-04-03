"""Tests for AdapterFactory — conditional dependency injection."""
from __future__ import annotations

import pytest

from smart_pid_core.adapters.factory import AdapterFactory
from smart_pid_core.adapters.inbound.simulator_adapter import SimulatorAdapter
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
    def test_creates_simulator_adapter(self, sim_settings: CoreSettings) -> None:
        factory = AdapterFactory(sim_settings)
        adapter = factory.telemetry_source
        assert isinstance(adapter, SimulatorAdapter)

    def test_same_instance_for_both_ports(self, sim_settings: CoreSettings) -> None:
        factory = AdapterFactory(sim_settings)
        assert factory.telemetry_source is factory.control_writer

    def test_simulator_adapter_property(self, sim_settings: CoreSettings) -> None:
        factory = AdapterFactory(sim_settings)
        assert factory.simulator_adapter is not None

    def test_tag_browser_raises_when_simulator(self, sim_settings: CoreSettings) -> None:
        factory = AdapterFactory(sim_settings)
        with pytest.raises(RuntimeError, match="TagBrowser"):
            _ = factory.tag_browser


class TestAdapterFactoryOPCUA:
    def test_telemetry_source_returns_opcua_when_simulator_disabled(self):
        from smart_pid_core.adapters.outbound.opcua_adapter import OPCUAAdapter

        settings = CoreSettings(
            jwt_secret="test-secret-key-minimum-32-bytes!",
            simulator_enabled=False,
        )  # type: ignore[call-arg]
        factory = AdapterFactory(settings)
        source = factory.telemetry_source
        assert isinstance(source, OPCUAAdapter)

    def test_control_writer_returns_opcua_when_simulator_disabled(self):
        from smart_pid_core.adapters.outbound.opcua_adapter import OPCUAAdapter

        settings = CoreSettings(
            jwt_secret="test-secret-key-minimum-32-bytes!",
            simulator_enabled=False,
        )  # type: ignore[call-arg]
        factory = AdapterFactory(settings)
        writer = factory.control_writer
        assert isinstance(writer, OPCUAAdapter)

    def test_tag_browser_returns_opcua(self):
        from smart_pid_core.adapters.outbound.opcua_adapter import OPCUAAdapter

        settings = CoreSettings(
            jwt_secret="test-secret-key-minimum-32-bytes!",
            simulator_enabled=False,
        )  # type: ignore[call-arg]
        factory = AdapterFactory(settings)
        browser = factory.tag_browser
        assert isinstance(browser, OPCUAAdapter)

    def test_opcua_adapter_is_same_instance(self):
        settings = CoreSettings(
            jwt_secret="test-secret-key-minimum-32-bytes!",
            simulator_enabled=False,
        )  # type: ignore[call-arg]
        factory = AdapterFactory(settings)
        assert factory.telemetry_source is factory.control_writer

    def test_simulator_adapter_is_none(self, prod_settings: CoreSettings) -> None:
        factory = AdapterFactory(prod_settings)
        assert factory.simulator_adapter is None

    def test_opcua_adapter_property(self, prod_settings: CoreSettings) -> None:
        factory = AdapterFactory(prod_settings)
        assert factory.opcua_adapter is not None
