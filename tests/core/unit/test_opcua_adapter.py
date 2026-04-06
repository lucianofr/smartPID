"""Unit tests for OPCUAAdapter."""
from __future__ import annotations

from smart_pid_core.config import CoreSettings
from smart_pid_domain.enums import ConnectionState, ControllerMode


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


class TestOPCUAAdapterBackoff:
    def test_backoff_max_from_settings(self):
        from smart_pid_core.adapters.outbound.opcua_adapter import OPCUAAdapter

        settings = _make_settings(opcua_retry_max_s=15.0)
        adapter = OPCUAAdapter(settings=settings)
        assert adapter._backoff_max_s == 15.0

    def test_backoff_max_default(self):
        from smart_pid_core.adapters.outbound.opcua_adapter import OPCUAAdapter

        settings = _make_settings()
        adapter = OPCUAAdapter(settings=settings)
        assert adapter._backoff_max_s == 30.0


class TestOPCUAAdapterModeRegistration:
    def test_register_controller_stores_mode_fields(self):
        from smart_pid_core.adapters.outbound.opcua_adapter import OPCUAAdapter

        settings = _make_settings()
        adapter = OPCUAAdapter(settings=settings)
        adapter.register_controller(
            controller_id=1,
            node_id_pv="ns=2;s=PV",
            node_id_sp="ns=2;s=SP",
            node_id_co="ns=2;s=CO",
            node_id_mode_target="ns=2;s=MODE_TGT",
            node_id_mode_actual="ns=2;s=MODE_ACT",
            mode_int_map={"MAN": 1, "AUTO": 2, "CAS": 4},
        )
        tags = adapter._controllers[1]
        assert tags["mode_target"] == "ns=2;s=MODE_TGT"
        assert tags["mode_actual"] == "ns=2;s=MODE_ACT"
        assert tags["mode_int_map"] == {"MAN": 1, "AUTO": 2, "CAS": 4}
        assert tags["mode_int_map_inv"] == {1: "MAN", 2: "AUTO", 4: "CAS"}

    def test_register_controller_no_old_mode_key(self):
        from smart_pid_core.adapters.outbound.opcua_adapter import OPCUAAdapter

        settings = _make_settings()
        adapter = OPCUAAdapter(settings=settings)
        adapter.register_controller(
            controller_id=1,
            node_id_pv="ns=2;s=PV",
            node_id_sp="ns=2;s=SP",
            node_id_co="ns=2;s=CO",
        )
        assert "mode" not in adapter._controllers[1]

    def test_read_actual_mode_returns_none_when_offline(self):
        from smart_pid_core.adapters.outbound.opcua_adapter import OPCUAAdapter

        settings = _make_settings()
        adapter = OPCUAAdapter(settings=settings)
        adapter.register_controller(
            controller_id=1,
            node_id_pv="ns=2;s=PV",
            node_id_sp="ns=2;s=SP",
            node_id_co="ns=2;s=CO",
            node_id_mode_actual="ns=2;s=MODE_ACT",
            mode_int_map={"MAN": 1, "AUTO": 2},
        )
        result = adapter.read_actual_mode(1)
        assert result is None

    def test_read_actual_mode_returns_none_when_no_actual_node(self):
        from smart_pid_core.adapters.outbound.opcua_adapter import OPCUAAdapter

        settings = _make_settings()
        adapter = OPCUAAdapter(settings=settings)
        adapter.register_controller(
            controller_id=1,
            node_id_pv="ns=2;s=PV",
            node_id_sp="ns=2;s=SP",
            node_id_co="ns=2;s=CO",
        )
        result = adapter.read_actual_mode(1)
        assert result is None

    def test_write_target_mode_returns_false_when_offline(self):
        from smart_pid_core.adapters.outbound.opcua_adapter import OPCUAAdapter

        settings = _make_settings()
        adapter = OPCUAAdapter(settings=settings)
        adapter.register_controller(
            controller_id=1,
            node_id_pv="ns=2;s=PV",
            node_id_sp="ns=2;s=SP",
            node_id_co="ns=2;s=CO",
            node_id_mode_target="ns=2;s=MODE_TGT",
            mode_int_map={"MAN": 1, "AUTO": 2},
        )
        result = adapter.write_target_mode(1, ControllerMode.AUTO)
        assert result is False

    def test_write_target_mode_returns_false_when_mode_not_in_map(self):
        from smart_pid_core.adapters.outbound.opcua_adapter import OPCUAAdapter

        settings = _make_settings()
        adapter = OPCUAAdapter(settings=settings)
        adapter.register_controller(
            controller_id=1,
            node_id_pv="ns=2;s=PV",
            node_id_sp="ns=2;s=SP",
            node_id_co="ns=2;s=CO",
            node_id_mode_target="ns=2;s=MODE_TGT",
            mode_int_map={"MAN": 1},
        )
        result = adapter.write_target_mode(1, ControllerMode.CAS)
        assert result is False
