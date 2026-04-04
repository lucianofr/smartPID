"""Tests for Phase 7 MainWindow wiring — new pages + ThemeManager."""
from __future__ import annotations

from queue import SimpleQueue
from unittest.mock import MagicMock

import pytest

from smart_pid_hmi.bus_bridge import BusBridge
from smart_pid_hmi.config import HMISettings
from smart_pid_hmi.main import MainWindow
from smart_pid_hmi.pages.executive_dashboard import ExecutiveDashboardPage
from smart_pid_hmi.pages.multi_trend_page import MultiTrendPage
from smart_pid_hmi.pages.settings_page import SettingsPage
from smart_pid_hmi.services.session import Session


@pytest.fixture
def settings() -> HMISettings:
    return HMISettings(mock_mode=True)  # type: ignore[call-arg]


@pytest.fixture
def session() -> Session:
    return Session()


@pytest.fixture
def bus_bridge() -> BusBridge:
    return BusBridge(queue=SimpleQueue(), refresh_ms=100)


@pytest.fixture
def main_window(qtbot, settings, session, bus_bridge):
    api_client = MagicMock()
    telemetry_source = MagicMock()
    telemetry_source.queue = SimpleQueue()
    window = MainWindow(
        settings=settings,
        session=session,
        api_client=api_client,
        telemetry_source=telemetry_source,
        bus_bridge=bus_bridge,
    )
    qtbot.addWidget(window)
    return window


def test_has_executive_page(main_window):
    assert isinstance(main_window._executive_page, ExecutiveDashboardPage)


def test_has_multi_trend_page(main_window):
    assert isinstance(main_window._multi_trend_page, MultiTrendPage)


def test_has_settings_page(main_window):
    assert isinstance(main_window._settings_page, SettingsPage)


def test_has_theme_manager(main_window):
    assert main_window._theme_manager is not None


def test_executive_btn_exists(main_window):
    assert main_window._executive_btn is not None


def test_trends_btn_exists(main_window):
    assert main_window._trends_btn is not None


def test_settings_btn_exists(main_window):
    assert main_window._settings_btn is not None


def test_executive_btn_switches_page(main_window):
    main_window._executive_btn.trigger()
    assert main_window._stack.currentWidget() is main_window._executive_page


def test_trends_btn_switches_page(main_window):
    main_window._trends_btn.trigger()
    assert main_window._stack.currentWidget() is main_window._multi_trend_page


def test_settings_btn_switches_page(main_window):
    main_window._settings_btn.trigger()
    assert main_window._stack.currentWidget() is main_window._settings_page


def test_theme_manager_has_three_themes(main_window):
    themes = main_window._theme_manager.available_themes()
    assert "isa101" in themes
    assert "dark_room" in themes
    assert "md3_dark" in themes
