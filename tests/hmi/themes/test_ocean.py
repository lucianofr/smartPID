"""Tests for Ocean theme."""
from smart_pid_hmi.themes.base import ThemeColors, ThemeFonts
from smart_pid_hmi.themes.ocean import OceanTheme


def test_ocean_implements_protocol():
    theme = OceanTheme()
    assert theme.name == "ocean"
    assert isinstance(theme.bg_primary, str)
    assert isinstance(theme.fg_primary, str)
    assert isinstance(theme.alarm_critical, str)
    assert isinstance(theme.alarm_warning, str)
    assert isinstance(theme.bar_pv, str)
    assert isinstance(theme.chart_pv, str)
    assert isinstance(theme.font_family, str)
    assert isinstance(theme.font_size_normal, int)


def test_ocean_color_values():
    theme = OceanTheme()
    assert theme.bg_primary == "#CED7E0"  # cool blue-gray per Ocean spec
    assert theme.bar_pv == "#2B6BAE"  # vibrant medium blue for dynamic values
    assert theme.alarm_critical == "#D32F2F"  # vibrant red
    assert theme.alarm_warning == "#F9A825"  # vibrant yellow
    assert theme.alarm_text == "#000000"  # black text on alarm backgrounds


def test_ocean_stylesheet_not_empty():
    theme = OceanTheme()
    qss = theme.stylesheet()
    assert len(qss) > 0
    assert "background-color" in qss.lower()


def test_apply_no_crash(qtbot):
    """Verify apply() does not raise on a real QApplication."""
    from PySide6.QtWidgets import QApplication

    theme = OceanTheme()
    app = QApplication.instance()
    assert app is not None
    theme.apply(app)


def test_ocean_has_colors_dataclass():
    """Ocean exposes ThemeColors via .colors property."""
    theme = OceanTheme()
    assert hasattr(theme, "colors")
    colors = theme.colors
    assert isinstance(colors, ThemeColors)
    assert colors.bg_primary == "#CED7E0"
    assert colors.accent == "#2B6BAE"


def test_ocean_has_fonts_dataclass():
    """Ocean exposes ThemeFonts via .fonts property."""
    theme = OceanTheme()
    assert hasattr(theme, "fonts")
    fonts = theme.fonts
    assert isinstance(fonts, ThemeFonts)
    assert fonts.family == "Arial"
    assert fonts.size_title == 20  # ~20pt per spec


def test_ocean_has_chart_palette():
    """Ocean exposes a chart_palette list for multi-trend."""
    theme = OceanTheme()
    assert hasattr(theme, "chart_palette")
    palette = theme.chart_palette
    assert isinstance(palette, list)
    assert len(palette) >= 4
    for color in palette:
        assert isinstance(color, str)
        assert color.startswith("#")


def test_ocean_extended_palette():
    """Ocean has all extended palette fields."""
    theme = OceanTheme()
    assert theme.bg_card != ""
    assert theme.bg_input != ""
    assert theme.bg_toolbar != ""
    assert theme.bg_hover != ""
    assert theme.fg_muted != ""
    assert theme.border_focus == "#2B6BAE"
    assert theme.border_radius == "0px"  # flat 2D, no rounded corners


def test_ocean_registered_in_manager(qtbot):
    """Ocean can be registered and selected in ThemeManager."""
    from smart_pid_hmi.themes.manager import ThemeManager

    mgr = ThemeManager()
    mgr.register(OceanTheme())
    mgr.set_theme("ocean")
    assert mgr.current.name == "ocean"
