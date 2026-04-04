# tests/hmi/themes/test_theme_dataclasses.py
"""Tests for ThemeColors and ThemeFonts frozen dataclasses."""
from smart_pid_hmi.themes.base import ThemeColors, ThemeFonts


def test_theme_colors_creation():
    colors = ThemeColors(
        bg_primary="#808080",
        bg_secondary="#999999",
        bg_widget="#B0B0B0",
        fg_primary="#1A1A1A",
        fg_secondary="#4D4D4D",
        border="#666666",
        alarm_critical="#FF0000",
        alarm_warning="#FFCC00",
        alarm_text="#FFFFFF",
        bar_pv="#404040",
        bar_sp="#606060",
        bar_co="#505050",
        chart_pv="#333333",
        chart_sp="#666666",
        chart_co="#505050",
        chart_grid="#999999",
        chart_bg="#B0B0B0",
    )
    assert colors.bg_primary == "#808080"
    assert colors.alarm_critical == "#FF0000"
    assert colors.chart_pv == "#333333"


def test_theme_colors_is_frozen():
    colors = ThemeColors(
        bg_primary="#808080",
        bg_secondary="#999999",
        bg_widget="#B0B0B0",
        fg_primary="#1A1A1A",
        fg_secondary="#4D4D4D",
        border="#666666",
        alarm_critical="#FF0000",
        alarm_warning="#FFCC00",
        alarm_text="#FFFFFF",
        bar_pv="#404040",
        bar_sp="#606060",
        bar_co="#505050",
        chart_pv="#333333",
        chart_sp="#666666",
        chart_co="#505050",
        chart_grid="#999999",
        chart_bg="#B0B0B0",
    )
    try:
        colors.bg_primary = "#000000"  # type: ignore[misc]
        raise AssertionError("Should be frozen")
    except AttributeError:
        pass


def test_theme_fonts_creation():
    fonts = ThemeFonts(
        family="Segoe UI",
        size_normal=12,
        size_label=10,
        size_value=14,
        size_title=16,
    )
    assert fonts.family == "Segoe UI"
    assert fonts.size_normal == 12
    assert fonts.size_title == 16


def test_theme_fonts_is_frozen():
    fonts = ThemeFonts(
        family="Segoe UI",
        size_normal=12,
        size_label=10,
        size_value=14,
        size_title=16,
    )
    try:
        fonts.family = "Arial"  # type: ignore[misc]
        raise AssertionError("Should be frozen")
    except AttributeError:
        pass
