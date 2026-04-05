"""Integration tests for OPC-UA tag browsing."""
from __future__ import annotations

import pytest

from smart_pid_core.adapters.outbound.opcua_adapter import OPCUAAdapter
from smart_pid_core.config import CoreSettings
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
class TestTagBrowser:
    def test_browse_root_objects(self, opcua_server: OPCUATestServer):
        settings = _make_settings(opcua_server.endpoint)
        adapter = OPCUAAdapter(settings=settings)
        adapter.start()
        try:
            adapter.wait_connected(timeout_s=5.0)
            # Browse Objects folder (i=85)
            children = adapter.browse_children("i=85")
            names = [c["display_name"] for c in children]
            assert "Controller1" in names
        finally:
            adapter.stop()

    def test_browse_controller_folder(self, opcua_server: OPCUATestServer):
        settings = _make_settings(opcua_server.endpoint)
        adapter = OPCUAAdapter(settings=settings)
        adapter.start()
        try:
            adapter.wait_connected(timeout_s=5.0)
            children = adapter.browse_children("i=85")
            ctrl_folder = next(c for c in children if c["display_name"] == "Controller1")
            tags = adapter.browse_children(ctrl_folder["node_id"])
            tag_names = {t["display_name"] for t in tags}
            assert {"PV", "SP", "CO", "Mode"} <= tag_names
        finally:
            adapter.stop()

    def test_search_by_name(self, opcua_server: OPCUATestServer):
        settings = _make_settings(opcua_server.endpoint)
        adapter = OPCUAAdapter(settings=settings)
        adapter.start()
        try:
            adapter.wait_connected(timeout_s=5.0)
            results = adapter.search("PV")
            assert len(results) >= 1
            assert any(r["display_name"] == "PV" for r in results)
        finally:
            adapter.stop()

    def test_search_no_results(self, opcua_server: OPCUATestServer):
        settings = _make_settings(opcua_server.endpoint)
        adapter = OPCUAAdapter(settings=settings)
        adapter.start()
        try:
            adapter.wait_connected(timeout_s=5.0)
            results = adapter.search("NONEXISTENT_TAG_XYZ")
            assert results == []
        finally:
            adapter.stop()
