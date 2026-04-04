"""Closed-loop integration test: SimulatorAdapter + OPCUAAdapter via OPC-UA."""
from __future__ import annotations

import time
from typing import Any, Callable

import pytest

from smart_pid_core.adapters.inbound.opcua_server import OPCUAServer
from smart_pid_core.adapters.outbound.opcua_adapter import OPCUAAdapter
from smart_pid_core.config import CoreSettings


def _poll_until(
    predicate: Callable[[], Any],
    timeout_s: float = 2.0,
    interval_s: float = 0.05,
) -> Any:
    """Poll predicate until truthy or timeout. Returns last result."""
    deadline = time.monotonic() + timeout_s
    result = None
    while time.monotonic() < deadline:
        result = predicate()
        if result:
            return result
        time.sleep(interval_s)
    return result

FULLSTACK_PORT = 48470


@pytest.fixture
def opcua_server():
    """Start an embedded OPCUAServer on a unique port."""
    server = OPCUAServer(port=FULLSTACK_PORT)
    server.register_controller(1)
    server.start()
    yield server
    server.stop()


@pytest.fixture
def opcua_client(opcua_server: OPCUAServer):
    """Create and start an OPCUAAdapter client connected to the test server."""
    node_ids = opcua_server.controller_node_ids[1]
    settings = CoreSettings(
        jwt_secret="test-secret-key-minimum-32-bytes!",
        opcua_endpoint=f"opc.tcp://localhost:{FULLSTACK_PORT}",
    )  # type: ignore[call-arg]
    adapter = OPCUAAdapter(settings=settings)
    adapter.register_controller(
        controller_id=1,
        node_id_pv=node_ids["pv"],
        node_id_sp=node_ids["sp"],
        node_id_co=node_ids["co"],
    )
    adapter.start()
    connected = adapter.wait_connected(timeout_s=10.0)
    assert connected, "OPCUAAdapter failed to connect to OPCUAServer"
    yield adapter
    adapter.stop()


@pytest.mark.integration
class TestOPCUAFullStack:
    """Closed-loop tests with real asyncua connections."""

    def test_read_telemetry_from_server(
        self, opcua_server: OPCUAServer, opcua_client: OPCUAAdapter,
    ) -> None:
        """Client can read PV/SP/CO values that the server publishes."""
        opcua_server.update_values(controller_id=1, pv=72.5, sp=75.0, co=45.0)

        def _pv_updated():
            f = opcua_client.read_telemetry(1)
            return f if f.pv.value == pytest.approx(72.5, abs=0.1) else None

        frame = _poll_until(_pv_updated)
        assert frame is not None
        assert frame.controller_id == 1
        assert frame.pv.value == pytest.approx(72.5, abs=0.1)
        assert frame.sp.value == pytest.approx(75.0, abs=0.1)
        assert frame.co.value == pytest.approx(45.0, abs=0.1)

    def test_write_co_back_to_server(
        self, opcua_server: OPCUAServer, opcua_client: OPCUAAdapter,
    ) -> None:
        """Client can write CO value back to the server node."""
        opcua_client.write_output(controller_id=1, co=65.0)

        def _co_updated():
            f = opcua_client.read_telemetry(1)
            return f if f.co.value == pytest.approx(65.0, abs=0.1) else None

        frame = _poll_until(_co_updated)
        assert frame is not None
        assert frame.co.value == pytest.approx(65.0, abs=0.1)

    def test_update_and_read_cycle(
        self, opcua_server: OPCUAServer, opcua_client: OPCUAAdapter,
    ) -> None:
        """Full cycle: server updates PV, client reads it, client writes CO."""
        # Server sets initial process values
        opcua_server.update_values(controller_id=1, pv=50.0, sp=60.0, co=30.0)

        def _pv_set():
            f = opcua_client.read_telemetry(1)
            return f if f.pv.value == pytest.approx(50.0, abs=0.1) else None

        frame1 = _poll_until(_pv_set)
        assert frame1 is not None
        assert frame1.pv.value == pytest.approx(50.0, abs=0.1)
        assert frame1.sp.value == pytest.approx(60.0, abs=0.1)

        # Client writes new CO
        opcua_client.write_output(controller_id=1, co=55.0)

        def _co_set():
            f = opcua_client.read_telemetry(1)
            return f if f.co.value == pytest.approx(55.0, abs=0.1) else None

        frame2 = _poll_until(_co_set)
        assert frame2 is not None
        assert frame2.co.value == pytest.approx(55.0, abs=0.1)

    def test_shutdown_order_client_before_server(
        self, opcua_server: OPCUAServer,
    ) -> None:
        """Verify stopping client before server does not raise."""
        settings = CoreSettings(
            jwt_secret="test-secret-key-minimum-32-bytes!",
            opcua_endpoint=f"opc.tcp://localhost:{FULLSTACK_PORT}",
        )  # type: ignore[call-arg]
        node_ids = opcua_server.controller_node_ids[1]
        client = OPCUAAdapter(settings=settings)
        client.register_controller(
            controller_id=1,
            node_id_pv=node_ids["pv"],
            node_id_sp=node_ids["sp"],
            node_id_co=node_ids["co"],
        )
        client.start()
        assert client.wait_connected(timeout_s=10.0)

        # Stop in correct order — should not raise
        client.stop()
        assert not client.is_connected
