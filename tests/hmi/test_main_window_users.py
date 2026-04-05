"""Tests for Users button visibility in MainWindow based on role."""
from __future__ import annotations

import base64
import json
import time

from PySide6.QtWidgets import QApplication

from smart_pid_hmi.config import HMISettings
from smart_pid_hmi.main import MainWindow
from smart_pid_hmi.services.mock_service import MockAPIClient, MockTelemetrySource
from smart_pid_hmi.services.session import Session

app = QApplication.instance() or QApplication([])


def _make_token(role: str) -> str:
    header = base64.urlsafe_b64encode(b'{"alg":"HS256"}').rstrip(b"=").decode()
    payload = base64.urlsafe_b64encode(json.dumps({
        "sub": "1", "username": "testuser", "role": role,
        "exp": int(time.time()) + 86400,
    }).encode()).rstrip(b"=").decode()
    return f"{header}.{payload}.mocksig"


def _make_window() -> tuple[MainWindow, Session]:
    from smart_pid_hmi.bus_bridge import BusBridge
    settings = HMISettings(mock_mode=True)
    session = Session()
    api_client = MockAPIClient()
    telemetry_source = MockTelemetrySource()
    bus_bridge = BusBridge(queue=telemetry_source.queue, refresh_ms=100)
    window = MainWindow(
        settings=settings, session=session,
        api_client=api_client, telemetry_source=telemetry_source,
        bus_bridge=bus_bridge,
    )
    return window, session


def test_users_button_hidden_by_default():
    window, _ = _make_window()
    # Use isHidden() since window is not shown (isVisible checks ancestors)
    assert window._users_btn.isHidden()


def test_users_button_visible_for_admin():
    window, session = _make_window()
    session.store_token(_make_token("ADMIN"))
    window._show_admin_controls()
    assert not window._users_btn.isHidden()


def test_users_button_hidden_for_operator():
    window, session = _make_window()
    session.store_token(_make_token("OPERATOR"))
    window._show_admin_controls()
    assert window._users_btn.isHidden()


def test_users_button_hidden_for_supervisor():
    window, session = _make_window()
    session.store_token(_make_token("SUPERVISOR"))
    window._show_admin_controls()
    assert window._users_btn.isHidden()
