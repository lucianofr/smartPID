"""Integration tests for OPC-UA connection lifecycle."""
from __future__ import annotations

import time

import pytest

from smart_pid_core.adapters.outbound.opcua_adapter import OPCUAAdapter
from smart_pid_core.config import CoreSettings
from smart_pid_domain.enums import ConnectionState
from smart_pid_domain.models.signal import FFSignal
from tests.core.fixtures.opcua_server import OPCUATestServer


@pytest.fixture(scope="module")
def opcua_server():
    server = OPCUATestServer()
    server.start()
    yield server
    server.stop()


def _make_settings(endpoint: str) -> CoreSettings:
    return CoreSettings(
        jwt_secret="test-secret-key-minimum-32-bytes!",
        opcua_endpoint=endpoint,
    )  # type: ignore[call-arg]


@pytest.mark.integration
class TestOPCUAConnection:
    def test_connect_reaches_online(self, opcua_server: OPCUATestServer):
        settings = _make_settings(opcua_server.endpoint)
        adapter = OPCUAAdapter(settings=settings)
        adapter.start()
        try:
            adapter.wait_connected(timeout_s=5.0)
            assert adapter.state == ConnectionState.ONLINE
            assert adapter.is_connected
        finally:
            adapter.stop()
        assert adapter.state == ConnectionState.OFFLINE

    def test_connect_to_bad_endpoint_stays_reconnecting(self):
        settings = _make_settings("opc.tcp://localhost:19999")
        adapter = OPCUAAdapter(settings=settings)
        adapter.start()
        try:
            time.sleep(1.0)
            assert adapter.state in {ConnectionState.CONNECTING, ConnectionState.RECONNECTING}
        finally:
            adapter.stop()


@pytest.mark.integration
class TestOPCUATelemetryRead:
    def test_read_telemetry_returns_frame(self, opcua_server: OPCUATestServer):
        settings = _make_settings(opcua_server.endpoint)
        adapter = OPCUAAdapter(settings=settings)
        adapter.register_controller(
            controller_id=1,
            node_id_pv=opcua_server.node_ids["pv"],
            node_id_sp=opcua_server.node_ids["sp"],
            node_id_co=opcua_server.node_ids["co"],
        )
        adapter.start()
        try:
            adapter.wait_connected(timeout_s=5.0)
            frame = adapter.read_telemetry(controller_id=1)
            assert frame.controller_id == 1
            assert isinstance(frame.pv, FFSignal)
            assert isinstance(frame.sp, FFSignal)
            assert isinstance(frame.co, FFSignal)
            assert frame.pv.value == pytest.approx(50.0, abs=0.1)
            assert frame.sp.value == pytest.approx(50.0, abs=0.1)
        finally:
            adapter.stop()

    def test_read_telemetry_unknown_controller_raises(self, opcua_server: OPCUATestServer):
        settings = _make_settings(opcua_server.endpoint)
        adapter = OPCUAAdapter(settings=settings)
        adapter.start()
        try:
            adapter.wait_connected(timeout_s=5.0)
            with pytest.raises(KeyError):
                adapter.read_telemetry(controller_id=999)
        finally:
            adapter.stop()


@pytest.mark.integration
class TestOPCUAControlWriter:
    def test_write_output_updates_co_node(self, opcua_server: OPCUATestServer):
        settings = _make_settings(opcua_server.endpoint)
        adapter = OPCUAAdapter(settings=settings)
        adapter.register_controller(
            controller_id=1,
            node_id_pv=opcua_server.node_ids["pv"],
            node_id_sp=opcua_server.node_ids["sp"],
            node_id_co=opcua_server.node_ids["co"],
        )
        adapter.start()
        try:
            adapter.wait_connected(timeout_s=5.0)
            adapter.write_output(controller_id=1, co=75.5)
            frame = adapter.read_telemetry(controller_id=1)
            assert frame.co.value == pytest.approx(75.5, abs=0.1)
        finally:
            adapter.stop()

    def test_write_parameter_updates_sp_node(self, opcua_server: OPCUATestServer):
        settings = _make_settings(opcua_server.endpoint)
        adapter = OPCUAAdapter(settings=settings)
        adapter.register_controller(
            controller_id=1,
            node_id_pv=opcua_server.node_ids["pv"],
            node_id_sp=opcua_server.node_ids["sp"],
            node_id_co=opcua_server.node_ids["co"],
        )
        adapter.start()
        try:
            adapter.wait_connected(timeout_s=5.0)
            adapter.write_parameter(controller_id=1, param="sp", value=65.0)
            frame = adapter.read_telemetry(controller_id=1)
            assert frame.sp.value == pytest.approx(65.0, abs=0.1)
        finally:
            adapter.stop()
