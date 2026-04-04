"""Tests for ThemeManager."""
import pytest

from smart_pid_hmi.themes.dark_room import DarkRoomTheme
from smart_pid_hmi.themes.isa101 import ISA101Theme
from smart_pid_hmi.themes.manager import ThemeManager
from smart_pid_hmi.themes.md3_dark import MD3DarkTheme


def test_manager_register_and_current(qtbot):
    mgr = ThemeManager()
    theme = ISA101Theme()
    mgr.register(theme)
    mgr.set_theme("isa101")
    assert mgr.current.name == "isa101"


def test_manager_register_multiple(qtbot):
    mgr = ThemeManager()
    mgr.register(ISA101Theme())
    mgr.register(DarkRoomTheme())
    mgr.register(MD3DarkTheme())
    assert mgr.available_themes() == ["dark_room", "isa101", "md3_dark"]


def test_manager_switch_theme(qtbot):
    mgr = ThemeManager()
    mgr.register(ISA101Theme())
    mgr.register(DarkRoomTheme())
    mgr.set_theme("isa101")
    assert mgr.current.name == "isa101"

    mgr.set_theme("dark_room")
    assert mgr.current.name == "dark_room"


def test_manager_emits_signal(qtbot):
    mgr = ThemeManager()
    mgr.register(ISA101Theme())
    mgr.register(DarkRoomTheme())
    mgr.set_theme("isa101")

    with qtbot.waitSignal(mgr.theme_changed, timeout=1000) as blocker:
        mgr.set_theme("dark_room")
    assert blocker.args == ["dark_room"]


def test_manager_unknown_theme_raises(qtbot):
    mgr = ThemeManager()
    mgr.register(ISA101Theme())
    with pytest.raises(KeyError, match="no_such_theme"):
        mgr.set_theme("no_such_theme")


def test_manager_no_signal_if_same_theme(qtbot):
    mgr = ThemeManager()
    mgr.register(ISA101Theme())
    mgr.set_theme("isa101")

    signals: list[str] = []
    mgr.theme_changed.connect(lambda name: signals.append(name))
    mgr.set_theme("isa101")  # same theme, no signal
    assert signals == []


def test_manager_current_raises_if_none(qtbot):
    mgr = ThemeManager()
    with pytest.raises(RuntimeError, match="No theme set"):
        _ = mgr.current


def test_themes_init_exports():
    from smart_pid_hmi.themes import (
        DarkRoomTheme,
        ISA101Theme,
        MD3DarkTheme,
        ThemeManager,
    )

    assert ISA101Theme is not None
    assert DarkRoomTheme is not None
    assert MD3DarkTheme is not None
    assert ThemeManager is not None
