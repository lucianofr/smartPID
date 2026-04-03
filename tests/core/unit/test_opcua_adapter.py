"""Unit tests for OPCUAAdapter."""
from __future__ import annotations

from smart_pid_core.config import CoreSettings
from smart_pid_domain.enums import ConnectionState


def _make_settings(**overrides) -> CoreSettings:
    defaults = {"jwt_secret": "test-secret-key-minimum-32-bytes!"}
    defaults.update(overrides)
    return CoreSettings(**defaults)  # type: ignore[call-arg]


class TestOPCUAAdapterInit:
    def test_initial_state_is_offline(self):
        from smart_pid_core.adapters.outbound.opcua_adapter import OPCUAAdapter

        settings = _make_settings(opcua_endpoint="opc.tcp://localhost:4840")
        adapter = OPCUAAdapter(settings=settings)
        assert adapter.state == ConnectionState.OFFLINE
        assert not adapter.is_connected

    def test_endpoint_from_settings(self):
        from smart_pid_core.adapters.outbound.opcua_adapter import OPCUAAdapter

        settings = _make_settings(opcua_endpoint="opc.tcp://10.0.0.1:4840")
        adapter = OPCUAAdapter(settings=settings)
        assert adapter.endpoint == "opc.tcp://10.0.0.1:4840"
