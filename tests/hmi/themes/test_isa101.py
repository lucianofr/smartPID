"""Tests for ISA-101 theme."""
import pytest

from smart_pid_hmi.themes.base import ThemeBase
from smart_pid_hmi.themes.isa101 import ISA101Theme


def test_isa101_implements_protocol():
    theme = ISA101Theme()
    # Structural check: all required attributes exist
    assert theme.name == "isa101"
    assert isinstance(theme.bg_primary, str)
    assert isinstance(theme.fg_primary, str)
    assert isinstance(theme.alarm_critical, str)
    assert isinstance(theme.alarm_warning, str)
    assert isinstance(theme.bar_pv, str)
    assert isinstance(theme.chart_pv, str)
    assert isinstance(theme.font_family, str)
    assert isinstance(theme.font_size_normal, int)


def test_isa101_color_values():
    theme = ISA101Theme()
    assert theme.bg_primary == "#808080"
    assert theme.alarm_critical == "#FF0000"
    assert theme.alarm_warning == "#FFCC00"


def test_isa101_stylesheet_not_empty():
    theme = ISA101Theme()
    qss = theme.stylesheet()
    assert len(qss) > 0
    assert "background" in qss.lower() or "background-color" in qss.lower()


def test_apply_no_crash(qtbot):
    """Verify apply() does not raise on a real QApplication."""
    from PySide6.QtWidgets import QApplication

    theme = ISA101Theme()
    app = QApplication.instance()
    assert app is not None
    theme.apply(app)
    # No crash = pass
