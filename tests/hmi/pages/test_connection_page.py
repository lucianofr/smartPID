"""Tests for ConnectionPage — login screen."""
import pytest
from PySide6.QtCore import Qt

from smart_pid_hmi.pages.connection_page import ConnectionPage
from smart_pid_hmi.themes.isa101 import ISA101Theme


@pytest.fixture
def theme():
    return ISA101Theme()


def test_creation(qtbot, theme):
    page = ConnectionPage(theme=theme, default_url="http://localhost:8000")
    qtbot.addWidget(page)
    assert page._url_input.text() == "http://localhost:8000"


def test_connect_emits_signal(qtbot, theme):
    page = ConnectionPage(theme=theme, default_url="http://test:8000")
    qtbot.addWidget(page)

    received = []
    page.login_requested.connect(lambda url, u, p: received.append((url, u, p)))

    page._url_input.setText("http://10.0.0.1:8000")
    page._user_input.setText("admin")
    page._pass_input.setText("secret")
    qtbot.mouseClick(page._connect_btn, Qt.MouseButton.LeftButton)

    assert len(received) == 1
    assert received[0] == ("http://10.0.0.1:8000", "admin", "secret")


def test_show_error(qtbot, theme):
    page = ConnectionPage(theme=theme, default_url="http://test:8000")
    qtbot.addWidget(page)
    page.show_error("Connection refused")
    assert page._status_label.text() == "Connection refused"
    assert not page._status_label.isHidden()


def test_show_error_clears(qtbot, theme):
    page = ConnectionPage(theme=theme, default_url="http://test:8000")
    qtbot.addWidget(page)
    page.show_error("Error")
    page.clear_error()
    assert page._status_label.text() == ""
