"""Unit tests for OPCUAAdapter tuning read/write and external mode methods."""
from __future__ import annotations

import pytest

from smart_pid_core.adapters.outbound.opcua_adapter import OPCUAAdapter
from smart_pid_core.config import CoreSettings


def _make_adapter() -> OPCUAAdapter:
    """Create an OPCUAAdapter without starting it (no OPC-UA server needed)."""
    from smart_pid_core.adapters.outbound.opcua_adapter import OPCUAAdapter

    settings = CoreSettings(
        jwt_secret="test-secret-key-minimum-32-bytes!",
        opcua_endpoint="opc.tcp://localhost:49999",
    )  # type: ignore[call-arg]
    return OPCUAAdapter(settings=settings)


class TestRegisterControllerTuningTags:
    """register_controller() accepts and stores kp/ti/td/mode node IDs."""

    def test_stores_tuning_tags(self) -> None:
        adapter = _make_adapter()
        adapter.register_controller(
            controller_id=1,
            node_id_pv="ns=2;s=PV",
            node_id_sp="ns=2;s=SP",
            node_id_co="ns=2;s=CO",
            node_id_kp="ns=2;s=KP",
            node_id_ti="ns=2;s=TI",
            node_id_td="ns=2;s=TD",
            node_id_mode="ns=2;s=MODE",
        )
        tags = adapter._controllers[1]
        assert tags["kp"] == "ns=2;s=KP"
        assert tags["ti"] == "ns=2;s=TI"
        assert tags["td"] == "ns=2;s=TD"
        assert tags["mode"] == "ns=2;s=MODE"

    def test_tuning_tags_default_to_empty(self) -> None:
        adapter = _make_adapter()
        adapter.register_controller(
            controller_id=2,
            node_id_pv="ns=2;s=PV",
            node_id_sp="ns=2;s=SP",
            node_id_co="ns=2;s=CO",
        )
        tags = adapter._controllers[2]
        assert tags["kp"] == ""
        assert tags["ti"] == ""
        assert tags["td"] == ""
        assert tags["mode"] == ""

    def test_existing_tags_preserved(self) -> None:
        """Existing pv/sp/co/integral/bkcal tags still stored correctly."""
        adapter = _make_adapter()
        adapter.register_controller(
            controller_id=3,
            node_id_pv="ns=2;s=PV",
            node_id_sp="ns=2;s=SP",
            node_id_co="ns=2;s=CO",
            node_id_integral="ns=2;s=INT",
            node_id_bkcal_in="ns=2;s=BKIN",
            node_id_bkcal_out="ns=2;s=BKOUT",
            node_id_kp="ns=2;s=KP",
        )
        tags = adapter._controllers[3]
        assert tags["pv"] == "ns=2;s=PV"
        assert tags["integral"] == "ns=2;s=INT"
        assert tags["bkcal_in"] == "ns=2;s=BKIN"
        assert tags["bkcal_out"] == "ns=2;s=BKOUT"
        assert tags["kp"] == "ns=2;s=KP"


class TestReadPIDParamsNoServer:
    """read_pid_params() returns None when no tuning tags or not connected."""

    def test_returns_none_when_no_tuning_tags(self) -> None:
        adapter = _make_adapter()
        adapter.register_controller(
            controller_id=1,
            node_id_pv="ns=2;s=PV",
            node_id_sp="ns=2;s=SP",
            node_id_co="ns=2;s=CO",
        )
        result = adapter.read_pid_params(1)
        assert result is None

    def test_returns_none_for_unregistered_controller(self) -> None:
        adapter = _make_adapter()
        result = adapter.read_pid_params(999)
        assert result is None

    def test_returns_none_when_not_connected(self) -> None:
        """Even with tuning tags, returns None if adapter is not connected."""
        adapter = _make_adapter()
        adapter.register_controller(
            controller_id=1,
            node_id_pv="ns=2;s=PV",
            node_id_sp="ns=2;s=SP",
            node_id_co="ns=2;s=CO",
            node_id_kp="ns=2;s=KP",
            node_id_ti="ns=2;s=TI",
        )
        # Not started, so not connected — should return None
        result = adapter.read_pid_params(1)
        assert result is None


class TestReadExternalModeNoServer:
    """read_external_mode() returns None when no mode tag or not connected."""

    def test_returns_none_when_no_mode_tag(self) -> None:
        adapter = _make_adapter()
        adapter.register_controller(
            controller_id=1,
            node_id_pv="ns=2;s=PV",
            node_id_sp="ns=2;s=SP",
            node_id_co="ns=2;s=CO",
        )
        result = adapter.read_external_mode(1)
        assert result is None

    def test_returns_none_for_unregistered_controller(self) -> None:
        adapter = _make_adapter()
        result = adapter.read_external_mode(999)
        assert result is None

    def test_returns_none_when_not_connected(self) -> None:
        adapter = _make_adapter()
        adapter.register_controller(
            controller_id=1,
            node_id_pv="ns=2;s=PV",
            node_id_sp="ns=2;s=SP",
            node_id_co="ns=2;s=CO",
            node_id_mode="ns=2;s=MODE",
        )
        result = adapter.read_external_mode(1)
        assert result is None


class TestWritePIDParamsNoServer:
    """write_pid_params() raises ConnectionError when not connected."""

    def test_raises_when_not_connected(self) -> None:
        adapter = _make_adapter()
        adapter.register_controller(
            controller_id=1,
            node_id_pv="ns=2;s=PV",
            node_id_sp="ns=2;s=SP",
            node_id_co="ns=2;s=CO",
            node_id_kp="ns=2;s=KP",
        )
        with pytest.raises(ConnectionError):
            adapter.write_pid_params(controller_id=1, kp=1.5, ti=None, td=None)

    def test_no_op_when_all_none(self) -> None:
        """write_pid_params with all None values should not raise even if not connected."""
        adapter = _make_adapter()
        adapter.register_controller(
            controller_id=1,
            node_id_pv="ns=2;s=PV",
            node_id_sp="ns=2;s=SP",
            node_id_co="ns=2;s=CO",
        )
        # All None + no tag mappings = no pairs = early return, no ConnectionError
        adapter.write_pid_params(controller_id=1, kp=None, ti=None, td=None)

    def test_no_op_when_tags_not_mapped(self) -> None:
        """write_pid_params with values but no tag mappings should not raise."""
        adapter = _make_adapter()
        adapter.register_controller(
            controller_id=1,
            node_id_pv="ns=2;s=PV",
            node_id_sp="ns=2;s=SP",
            node_id_co="ns=2;s=CO",
        )
        # kp=1.0 but no kp tag mapped → pairs is empty → early return
        adapter.write_pid_params(controller_id=1, kp=1.0, ti=None, td=None)
