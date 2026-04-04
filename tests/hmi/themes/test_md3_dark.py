"""Tests for MD3 Dark theme."""
from smart_pid_hmi.themes.base import ThemeColors, ThemeFonts
from smart_pid_hmi.themes.md3_dark import MD3DarkTheme


def test_md3_dark_name():
    theme = MD3DarkTheme()
    assert theme.name == "md3_dark"


def test_md3_dark_implements_protocol():
    theme = MD3DarkTheme()
    assert isinstance(theme.bg_primary, str)
    assert isinstance(theme.fg_primary, str)
    assert isinstance(theme.alarm_critical, str)
    assert isinstance(theme.alarm_warning, str)
    assert isinstance(theme.bar_pv, str)
    assert isinstance(theme.chart_pv, str)
    assert isinstance(theme.font_family, str)
    assert isinstance(theme.font_size_normal, int)


def test_md3_dark_colors():
    theme = MD3DarkTheme()
    assert theme.bg_primary == "#141218"
    assert theme.bg_secondary == "#211F26"
    assert theme.fg_primary == "#E6E0E9"
    assert theme.alarm_critical == "#8C1D18"
    assert theme.alarm_warning == "#4D3300"


def test_md3_dark_colors_dataclass():
    theme = MD3DarkTheme()
    colors = theme.colors
    assert isinstance(colors, ThemeColors)
    assert colors.bg_primary == "#141218"


def test_md3_dark_fonts_dataclass():
    theme = MD3DarkTheme()
    fonts = theme.fonts
    assert isinstance(fonts, ThemeFonts)
    assert fonts.family == "Roboto"
    assert fonts.size_normal == 14


def test_md3_dark_chart_palette():
    theme = MD3DarkTheme()
    palette = theme.chart_palette
    assert isinstance(palette, list)
    assert len(palette) >= 4


def test_md3_dark_stylesheet_not_empty():
    theme = MD3DarkTheme()
    qss = theme.stylesheet()
    assert len(qss) > 0
    assert "border-radius" in qss  # M3 rounded corners


def test_md3_dark_apply_no_crash(qtbot):
    from PySide6.QtWidgets import QApplication

    theme = MD3DarkTheme()
    app = QApplication.instance()
    assert app is not None
    theme.apply(app)
