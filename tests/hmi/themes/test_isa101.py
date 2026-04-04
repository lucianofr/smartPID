"""Tests for ISA-101 theme."""
from smart_pid_hmi.themes.base import ThemeColors, ThemeFonts
from smart_pid_hmi.themes.isa101 import ISA101Theme


def test_isa101_implements_protocol():
    theme = ISA101Theme()
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


def test_isa101_has_colors_dataclass():
    """ISA-101 exposes ThemeColors via .colors property."""
    theme = ISA101Theme()
    assert hasattr(theme, "colors")
    colors = theme.colors
    assert isinstance(colors, ThemeColors)
    assert colors.bg_primary == "#808080"
    assert colors.alarm_critical == "#FF0000"


def test_isa101_has_fonts_dataclass():
    """ISA-101 exposes ThemeFonts via .fonts property."""
    theme = ISA101Theme()
    assert hasattr(theme, "fonts")
    fonts = theme.fonts
    assert isinstance(fonts, ThemeFonts)
    assert fonts.family == "Segoe UI"
    assert fonts.size_normal == 12


def test_isa101_has_chart_palette():
    """ISA-101 exposes a chart_palette list for multi-trend."""
    theme = ISA101Theme()
    assert hasattr(theme, "chart_palette")
    palette = theme.chart_palette
    assert isinstance(palette, list)
    assert len(palette) >= 4
    for color in palette:
        assert isinstance(color, str)
        assert color.startswith("#")
