"""Unit tests for OPCUAServer wrapper."""
from __future__ import annotations

import socket
import time
from unittest.mock import MagicMock

import pytest


def _get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class TestOPCUAServerInit:
    def test_initial_state_not_running(self) -> None:
        from smart_pid_core.adapters.inbound.opcua_server import OPCUAServer

        server = OPCUAServer(port=_get_free_port())
        assert not server.is_running

    def test_port_stored(self) -> None:
        from smart_pid_core.adapters.inbound.opcua_server import OPCUAServer

        port = _get_free_port()
        server = OPCUAServer(port=port)
        assert server.port == port

    def test_endpoint_format(self) -> None:
        from smart_pid_core.adapters.inbound.opcua_server import OPCUAServer

        port = _get_free_port()
        server = OPCUAServer(port=port)
        assert server.endpoint == f"opc.tcp://0.0.0.0:{port}"

    def test_no_controllers_initially(self) -> None:
        from smart_pid_core.adapters.inbound.opcua_server import OPCUAServer

        server = OPCUAServer(port=_get_free_port())
        assert server.controller_node_ids == {}


class TestOPCUAServerLifecycle:
    def test_start_and_stop(self) -> None:
        from smart_pid_core.adapters.inbound.opcua_server import OPCUAServer

        server = OPCUAServer(port=_get_free_port())
        server.start()
        try:
            assert server.is_running
        finally:
            server.stop()
        assert not server.is_running

    def test_double_start_is_idempotent(self) -> None:
        from smart_pid_core.adapters.inbound.opcua_server import OPCUAServer

        server = OPCUAServer(port=_get_free_port())
        server.start()
        try:
            server.start()  # Should not raise
            assert server.is_running
        finally:
            server.stop()

    def test_stop_when_not_started_is_safe(self) -> None:
        from smart_pid_core.adapters.inbound.opcua_server import OPCUAServer

        server = OPCUAServer(port=_get_free_port())
        server.stop()  # Should not raise


class TestOPCUAServerRegisterController:
    def test_register_before_start_stores_controller(self) -> None:
        from smart_pid_core.adapters.inbound.opcua_server import OPCUAServer

        server = OPCUAServer(port=_get_free_port())
        server.register_controller(1)
        assert 1 in server.controller_node_ids

    def test_register_after_start_creates_nodes(self) -> None:
        from smart_pid_core.adapters.inbound.opcua_server import OPCUAServer

        server = OPCUAServer(port=_get_free_port())
        server.start()
        try:
            node_ids = server.register_controller(1)
            assert "pv" in node_ids
            assert "sp" in node_ids
            assert "co" in node_ids
            assert "mode" in node_ids
            assert "status" in node_ids
            assert all(nid.startswith("ns=") for nid in node_ids.values())
        finally:
            server.stop()

    def test_pre_registered_controllers_get_nodes_after_start(self) -> None:
        from smart_pid_core.adapters.inbound.opcua_server import OPCUAServer

        server = OPCUAServer(port=_get_free_port())
        server.register_controller(1)
        server.start()
        try:
            node_ids = server.controller_node_ids[1]
            assert "pv" in node_ids
            assert all(nid.startswith("ns=") for nid in node_ids.values())
        finally:
            server.stop()

    def test_values_pushed_before_start_survive_node_creation(self) -> None:
        """A config pushed before the loop exists must reach the nodes.

        Nodes are minted with hardcoded defaults (Kp=1.0, Mode=0), and
        update_values used to return early while the loop was down. The
        defaults therefore stayed in the address space, and the initial
        subscribe_data_change notification fed them straight back into the
        twin -- wiping restored tuning on every daemon start.
        """
        import asyncio

        from smart_pid_core.adapters.inbound.opcua_server import OPCUAServer

        server = OPCUAServer(port=_get_free_port())
        server.register_controller(1)
        server.update_values(controller_id=1, values={"kp": 3.25, "mode": 1})
        server.start()
        try:
            nodes = server._controller_nodes[1]

            def _read(key: str) -> float | int:
                return asyncio.run_coroutine_threadsafe(
                    nodes[key].read_value(), server._loop,
                ).result(timeout=5.0)

            assert _read("kp") == pytest.approx(3.25)
            assert _read("mode") == 1
        finally:
            server.stop()

    def test_reregistration_keeps_the_client_reading_live_values(self) -> None:
        """A re-registered controller must keep its node ids.

        Minting a second ``CTRL_{id}`` folder orphans the first: the twin
        ticks the new nodes while a client bound to the old ones freezes on
        the last value it ever saw — the Sim trend and the block diagram then
        disagree because they read different node sets.
        """
        from smart_pid_core.adapters.inbound.opcua_server import OPCUAServer
        from smart_pid_core.adapters.outbound.opcua_adapter import OPCUAAdapter
        from smart_pid_core.config import CoreSettings

        port = _get_free_port()
        server = OPCUAServer(port=port)
        server.start()
        try:
            first = server.register_controller(1)
            settings = CoreSettings(
                jwt_secret="test-secret-key-minimum-32-bytes!",
                opcua_endpoint=f"opc.tcp://localhost:{port}",
            )  # type: ignore[call-arg]
            client = OPCUAAdapter(settings=settings)
            client.register_controller(
                controller_id=1,
                node_id_pv=first["pv"],
                node_id_sp=first["sp"],
                node_id_co=first["co"],
            )
            client.start()
            try:
                assert client.wait_connected(timeout_s=5.0)

                # Delete + re-create the simulator loop for the same id.
                assert server.register_controller(1) == first

                server.update_values(controller_id=1, values={"pv": 61.5})
                time.sleep(0.3)
                assert client.read_telemetry(1).pv.value == pytest.approx(61.5, abs=0.5)
            finally:
                client.stop()
        finally:
            server.stop()


class TestOPCUAServerUpdateValues:
    def test_update_values_readable_by_client(self) -> None:
        from smart_pid_core.adapters.inbound.opcua_server import OPCUAServer
        from smart_pid_core.adapters.outbound.opcua_adapter import OPCUAAdapter
        from smart_pid_core.config import CoreSettings

        port = _get_free_port()
        server = OPCUAServer(port=port)
        server.register_controller(1)
        server.start()
        try:
            node_ids = server.controller_node_ids[1]

            settings = CoreSettings(
                jwt_secret="test-secret-key-minimum-32-bytes!",
                opcua_endpoint=f"opc.tcp://localhost:{port}",
            )  # type: ignore[call-arg]
            client = OPCUAAdapter(settings=settings)
            client.register_controller(
                controller_id=1,
                node_id_pv=node_ids["pv"],
                node_id_sp=node_ids["sp"],
                node_id_co=node_ids["co"],
            )
            client.start()
            try:
                assert client.wait_connected(timeout_s=5.0)

                server.update_values(
                    controller_id=1,
                    values={"pv": 72.5, "sp": 75.0, "co": 45.0, "mode": 4, "status": 0},
                )
                time.sleep(0.3)  # Allow async write to propagate

                frame = client.read_telemetry(1)
                assert frame.pv.value == pytest.approx(72.5, abs=0.5)
                assert frame.sp.value == pytest.approx(75.0, abs=0.5)
                assert frame.co.value == pytest.approx(45.0, abs=0.5)
            finally:
                client.stop()
        finally:
            server.stop()


def _wait_for_value(
    received: list[tuple[int, str, float]],
    param: str,
    expected: float,
    timeout: float = 5.0,
) -> bool:
    """Poll received list until a matching (param, ~expected) entry appears."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        matches = [v for _, p, v in received if p == param and abs(v - expected) < 1.0]
        if matches:
            return True
        time.sleep(0.1)
    return False


class TestOPCUAServerWriteCallback:
    def test_on_write_fires_when_client_writes_co(self) -> None:
        from smart_pid_core.adapters.inbound.opcua_server import OPCUAServer
        from smart_pid_core.adapters.outbound.opcua_adapter import OPCUAAdapter
        from smart_pid_core.config import CoreSettings

        received: list[tuple[int, str, float]] = []

        def on_write(controller_id: int, param: str, value: float) -> None:
            received.append((controller_id, param, value))

        port = _get_free_port()
        server = OPCUAServer(port=port)
        server.set_on_write(on_write)
        server.register_controller(1)
        server.start()
        try:
            node_ids = server.controller_node_ids[1]

            settings = CoreSettings(
                jwt_secret="test-secret-key-minimum-32-bytes!",
                opcua_endpoint=f"opc.tcp://localhost:{port}",
            )  # type: ignore[call-arg]
            client = OPCUAAdapter(settings=settings)
            client.register_controller(
                controller_id=1,
                node_id_pv=node_ids["pv"],
                node_id_sp=node_ids["sp"],
                node_id_co=node_ids["co"],
            )
            client.start()
            try:
                assert client.wait_connected(timeout_s=5.0)
                # Wait for initial subscription notifications to settle
                time.sleep(0.5)

                client.write_output(controller_id=1, co=88.0)
                assert _wait_for_value(received, "co", 88.0), (
                    f"on_write callback was not called with co=88.0, got: {received}"
                )

                co_writes = [v for _, p, v in received if p == "co" and abs(v - 88.0) < 1.0]
                assert len(co_writes) >= 1
                assert co_writes[-1] == pytest.approx(88.0, abs=0.5)
            finally:
                client.stop()
        finally:
            server.stop()

    def test_on_write_fires_when_client_writes_sp(self) -> None:
        from smart_pid_core.adapters.inbound.opcua_server import OPCUAServer
        from smart_pid_core.adapters.outbound.opcua_adapter import OPCUAAdapter
        from smart_pid_core.config import CoreSettings

        received: list[tuple[int, str, float]] = []

        def on_write(controller_id: int, param: str, value: float) -> None:
            received.append((controller_id, param, value))

        port = _get_free_port()
        server = OPCUAServer(port=port)
        server.set_on_write(on_write)
        server.register_controller(1)
        server.start()
        try:
            node_ids = server.controller_node_ids[1]

            settings = CoreSettings(
                jwt_secret="test-secret-key-minimum-32-bytes!",
                opcua_endpoint=f"opc.tcp://localhost:{port}",
            )  # type: ignore[call-arg]
            client = OPCUAAdapter(settings=settings)
            client.register_controller(
                controller_id=1,
                node_id_pv=node_ids["pv"],
                node_id_sp=node_ids["sp"],
                node_id_co=node_ids["co"],
            )
            client.start()
            try:
                assert client.wait_connected(timeout_s=5.0)
                time.sleep(0.5)

                client.write_parameter(controller_id=1, param="sp", value=60.0)
                assert _wait_for_value(received, "sp", 60.0), (
                    f"on_write callback was not called with sp=60.0, got: {received}"
                )

                sp_writes = [v for _, p, v in received if p == "sp" and abs(v - 60.0) < 1.0]
                assert len(sp_writes) >= 1
                assert sp_writes[-1] == pytest.approx(60.0, abs=0.5)
            finally:
                client.stop()
        finally:
            server.stop()


class TestOPCUAServerPIDWriteHandler:
    """Test that _WriteHandler resolves PID param nodes correctly."""

    def test_write_handler_resolves_kp(self) -> None:
        from smart_pid_core.adapters.inbound.opcua_server import _WriteHandler

        kp_node = MagicMock()
        kp_node.nodeid.to_string.return_value = "ns=2;s=Kp_1"
        controller_nodes = {
            1: {"kp": kp_node, "ti": MagicMock(), "td": MagicMock()},
        }
        callback = MagicMock()
        handler = _WriteHandler(callback, controller_nodes)
        result = handler._resolve_node("ns=2;s=Kp_1")
        assert result == (1, "kp")

    def test_write_handler_resolves_ti(self) -> None:
        from smart_pid_core.adapters.inbound.opcua_server import _WriteHandler

        ti_node = MagicMock()
        ti_node.nodeid.to_string.return_value = "ns=2;s=Ti_1"
        controller_nodes = {
            1: {"ti": ti_node, "kp": MagicMock(), "td": MagicMock()},
        }
        callback = MagicMock()
        handler = _WriteHandler(callback, controller_nodes)
        result = handler._resolve_node("ns=2;s=Ti_1")
        assert result == (1, "ti")

    def test_write_handler_resolves_td(self) -> None:
        from smart_pid_core.adapters.inbound.opcua_server import _WriteHandler

        td_node = MagicMock()
        td_node.nodeid.to_string.return_value = "ns=2;s=Td_1"
        controller_nodes = {
            1: {"td": td_node, "kp": MagicMock(), "ti": MagicMock()},
        }
        callback = MagicMock()
        handler = _WriteHandler(callback, controller_nodes)
        result = handler._resolve_node("ns=2;s=Td_1")
        assert result == (1, "td")

    def test_write_handler_resolves_mode(self) -> None:
        from smart_pid_core.adapters.inbound.opcua_server import _WriteHandler

        mode_node = MagicMock()
        mode_node.nodeid.to_string.return_value = "ns=2;s=Mode_1"
        controller_nodes = {
            1: {"mode": mode_node},
        }
        callback = MagicMock()
        handler = _WriteHandler(callback, controller_nodes)
        result = handler._resolve_node("ns=2;s=Mode_1")
        assert result == (1, "mode")

    def test_write_handler_resolves_pid_sp(self) -> None:
        from smart_pid_core.adapters.inbound.opcua_server import _WriteHandler

        sp_node = MagicMock()
        sp_node.nodeid.to_string.return_value = "ns=2;s=PIDSP_1"
        controller_nodes = {
            1: {"pid_sp": sp_node},
        }
        callback = MagicMock()
        handler = _WriteHandler(callback, controller_nodes)
        result = handler._resolve_node("ns=2;s=PIDSP_1")
        assert result == (1, "pid_sp")

    def test_write_handler_calls_callback_on_datachange(self) -> None:
        from smart_pid_core.adapters.inbound.opcua_server import _WriteHandler

        kp_node = MagicMock()
        kp_node.nodeid.to_string.return_value = "ns=2;s=Kp_1"
        controller_nodes = {1: {"kp": kp_node}}
        callback = MagicMock()
        handler = _WriteHandler(callback, controller_nodes)
        handler.datachange_notification(kp_node, 3.5, None)
        callback.assert_called_once_with(1, "kp", 3.5)

    def test_register_after_start_creates_pid_nodes(self) -> None:
        from smart_pid_core.adapters.inbound.opcua_server import OPCUAServer

        server = OPCUAServer(port=_get_free_port())
        server.start()
        try:
            node_ids = server.register_controller(1)
            assert "kp" in node_ids
            assert "ti" in node_ids
            assert "td" in node_ids
            assert "mode" in node_ids
            assert "pid_structure" in node_ids
            assert "pid_sp" in node_ids
        finally:
            server.stop()
