"""Tests for mock service implementations."""
import time

from smart_pid_hmi.services.mock_service import MockAPIClient, MockTelemetrySource


def test_mock_telemetry_generates_frames():
    source = MockTelemetrySource(interval_ms=50)
    source.start()
    time.sleep(0.3)
    source.stop()

    assert not source.queue.empty()
    topic, data = source.queue.get_nowait()
    assert topic.startswith("STATUS.")
    assert "pv" in data
    assert "sp" in data
    assert "co" in data
    assert "controller_id" in data


def test_mock_telemetry_three_controllers():
    source = MockTelemetrySource(interval_ms=50)
    source.start()
    time.sleep(0.5)
    source.stop()

    seen_ids: set[int] = set()
    while not source.queue.empty():
        _, data = source.queue.get_nowait()
        seen_ids.add(data["controller_id"])
    assert len(seen_ids) == 3


def test_mock_api_login():
    client = MockAPIClient()
    resp = client.login("admin", "pass")
    assert resp.access_token
    assert resp.token_type == "bearer"


def test_mock_api_list_controllers():
    client = MockAPIClient()
    controllers = client.list_controllers()
    assert len(controllers) == 3
    names = {c.name for c in controllers}
    assert "FIC-101" in names
    assert "LIC-201" in names
    assert "TIC-301" in names


def test_mock_api_set_setpoint():
    client = MockAPIClient()
    resp = client.set_setpoint(1, 55.0)
    assert resp.ok is True


def test_mock_api_set_mode():
    client = MockAPIClient()
    resp = client.set_mode(1, "MAN")
    assert resp.ok is True


def test_mock_api_set_output():
    client = MockAPIClient()
    resp = client.set_output(1, 30.0)
    assert resp.ok is True


def test_mock_api_get_history():
    from datetime import datetime, timezone

    client = MockAPIClient()
    resp = client.get_history(
        1,
        datetime(2026, 4, 3, 9, 0, tzinfo=timezone.utc),
        datetime(2026, 4, 3, 11, 0, tzinfo=timezone.utc),
    )
    assert resp.controller_id == 1
    assert resp.count >= 0
