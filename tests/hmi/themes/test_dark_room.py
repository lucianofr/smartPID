"""Tests for DarkRoom theme."""
from smart_pid_hmi.themes.base import ThemeColors, ThemeFonts
from smart_pid_hmi.themes.dark_room import DarkRoomTheme


def test_dark_room_name():
    theme = DarkRoomTheme()
    assert theme.name == "dark_room"


def test_dark_room_implements_protocol():
    theme = DarkRoomTheme()
    assert isinstance(theme.bg_primary, str)
    assert isinstance(theme.fg_primary, str)
    assert isinstance(theme.alarm_critical, str)
    assert isinstance(theme.alarm_warning, str)
    assert isinstance(theme.bar_pv, str)
    assert isinstance(theme.chart_pv, str)
    assert isinstance(theme.font_family, str)
    assert isinstance(theme.font_size_normal, int)


def test_dark_room_colors():
    theme = DarkRoomTheme()
    assert theme.bg_primary == "#000000"
    assert theme.bg_secondary == "#0D0D11"
    assert theme.fg_primary == "#B0B0B8"
    assert theme.alarm_critical == "#D92525"
    assert theme.alarm_warning == "#D9A000"


def test_dark_room_colors_dataclass():
    theme = DarkRoomTheme()
    colors = theme.colors
    assert isinstance(colors, ThemeColors)
    assert colors.bg_primary == "#000000"


def test_dark_room_fonts_dataclass():
    theme = DarkRoomTheme()
    fonts = theme.fonts
    assert isinstance(fonts, ThemeFonts)
    assert "Fira Code" in fonts.family or "JetBrains Mono" in fonts.family


def test_dark_room_chart_palette():
    theme = DarkRoomTheme()
    palette = theme.chart_palette
    assert isinstance(palette, list)
    assert len(palette) >= 4


def test_dark_room_stylesheet_not_empty():
    theme = DarkRoomTheme()
    qss = theme.stylesheet()
    assert len(qss) > 0
    assert "#000000" in qss


def test_dark_room_apply_no_crash(qtbot):
    from PySide6.QtWidgets import QApplication

    theme = DarkRoomTheme()
    app = QApplication.instance()
    assert app is not None
    theme.apply(app)
