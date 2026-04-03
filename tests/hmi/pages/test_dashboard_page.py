"""Tests for DashboardPage layout and signal wiring."""
from queue import SimpleQueue

import pytest

from smart_pid_hmi.bus_bridge import BusBridge
from smart_pid_hmi.pages.dashboard_page import DashboardPage
from smart_pid_hmi.themes.isa101 import ISA101Theme


@pytest.fixture
def theme():
    return ISA101Theme()


@pytest.fixture
def bridge(qtbot):
    q = SimpleQueue()
    b = BusBridge(queue=q, refresh_ms=10)
    yield b
    b.stop()


def test_creation(qtbot, theme, bridge):
    page = DashboardPage(theme=theme, bus_bridge=bridge)
    qtbot.addWidget(page)
    assert page._faceplate is not None
    assert page._trend is not None
    assert page._alarm_bar is not None


def test_populate_controllers(qtbot, theme, bridge):
    page = DashboardPage(theme=theme, bus_bridge=bridge)
    qtbot.addWidget(page)
    controllers = [
        {"id": 1, "name": "FIC-101", "sp_hi_lim": 100.0, "sp_lo_lim": 0.0},
        {"id": 2, "name": "LIC-201", "sp_hi_lim": 100.0, "sp_lo_lim": 0.0},
    ]
    page.populate_controllers(controllers)
    assert len(page._cards) == 2


def test_first_controller_auto_selected(qtbot, theme, bridge):
    page = DashboardPage(theme=theme, bus_bridge=bridge)
    qtbot.addWidget(page)
    controllers = [
        {"id": 1, "name": "FIC-101", "sp_hi_lim": 100.0, "sp_lo_lim": 0.0},
    ]
    page.populate_controllers(controllers)
    assert page._faceplate._controller_id == 1
    assert page._trend._controller_id == 1
