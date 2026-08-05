"""Tests for the standalone simulator twin REST service."""
from __future__ import annotations

import socket
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from smart_pid_core.config import CoreSettings
from smart_pid_core.simulator_service import app


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def client() -> Iterator[TestClient]:
    """Real SimulatorAdapter + real OPC-UA server behind the FastAPI app.

    Each test gets its own free OPC-UA port and a fast tick interval so the
    default-loop watchdog and lifecycle behavior is exercised honestly
    (no mocking of the adapter), matching the pattern already used by
    test_opcua_server.py.
    """
    app.state.settings = CoreSettings(
        jwt_secret="test-secret-key-minimum-32-bytes!",
        simulator_interval_ms=20,
        simulator_port=_free_port(),
    )  # type: ignore[call-arg]
    with TestClient(app) as c:
        yield c


class TestHealth:
    def test_health_ok(self, client: TestClient) -> None:
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


class TestStatus:
    def test_status_shows_default_loop_running(self, client: TestClient) -> None:
        resp = client.get("/status")
        assert resp.status_code == 200
        body = resp.json()
        assert body["running"] is True
        assert "0" in body["controllers"]


class TestLoops:
    def test_create_loop_allocates_id(self, client: TestClient) -> None:
        resp = client.post("/loops", json={"controller_id": None})
        assert resp.status_code == 200
        cid = resp.json()["controller_id"]
        assert cid != 0
        status = client.get("/status").json()
        assert str(cid) in status["controllers"]

    def test_create_duplicate_loop_conflicts(self, client: TestClient) -> None:
        first = client.post("/loops", json={"controller_id": 5})
        assert first.status_code == 200
        dup = client.post("/loops", json={"controller_id": 5})
        assert dup.status_code == 409


class TestWatchdogReseed:
    def test_delete_last_loop_then_watchdog_reseeds(self, client: TestClient) -> None:
        assert client.delete("/controllers/0").json() == {"removed": True}
        assert client.get("/status").json()["controllers"] == {}

        # Drive the watchdog directly instead of sleeping for a tick.
        adapter = client.app.state.adapter
        adapter._reseed_if_empty()

        status = client.get("/status").json()
        assert "0" in status["controllers"]


class TestNodeIds:
    def test_node_ids_has_pv_sp_co(self, client: TestClient) -> None:
        resp = client.get("/node-ids/0")
        assert resp.status_code == 200
        body = resp.json()
        assert {"pv", "sp", "co"} <= set(body)

    def test_node_ids_unknown_controller_is_404(self, client: TestClient) -> None:
        resp = client.get("/node-ids/999")
        assert resp.status_code == 404


class TestUnknownControllerErrors:
    def test_pid_status_unknown_controller_is_404(self, client: TestClient) -> None:
        resp = client.get("/pid/status/999")
        assert resp.status_code == 404

    def test_preset_unknown_controller_is_404(self, client: TestClient) -> None:
        resp = client.post("/preset", json={"controller_id": 999, "preset": "FLOW"})
        assert resp.status_code == 404
