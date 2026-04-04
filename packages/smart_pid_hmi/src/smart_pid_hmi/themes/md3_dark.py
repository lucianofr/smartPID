"""MD3 Dark theme — Material Design 3 with neutral tones and rounded corners."""
from __future__ import annotations

from typing import TYPE_CHECKING

from smart_pid_hmi.themes.base import ThemeColors, ThemeFonts

if TYPE_CHECKING:
    from PySide6.QtWidgets import QApplication

_COLORS = ThemeColors(
    bg_primary="#141218",       # Surface
    bg_secondary="#211F26",     # Surface Container
    bg_widget="#1D1B20",        # Surface Container Low
    fg_primary="#E6E0E9",       # On-Surface
    fg_secondary="#938F99",     # Outline
    border="#49454F",           # Outline Variant
    alarm_critical="#8C1D18",   # Error Container
    alarm_warning="#4D3300",    # Warning Container
    alarm_text="#F9DEDC",       # On-Error Container
    bar_pv="#938F99",           # Outline (normal fill)
    bar_sp="#CAC4D0",           # On-Surface Variant
    bar_co="#79747E",           # Outline Variant
    chart_pv="#E6E0E9",         # On-Surface
    chart_sp="#CAC4D0",         # On-Surface Variant
    chart_co="#938F99",         # Outline
    chart_grid="#2B2930",       # Surface Container High
    chart_bg="#141218",         # Surface
)

_FONTS = ThemeFonts(
    family="Roboto",
    size_normal=14,
    size_label=12,
    size_value=16,
    size_title=18,
)

_CHART_PALETTE = [
    "#E6E0E9",  # on-surface
    "#CAC4D0",  # on-surface-variant
    "#938F99",  # outline
    "#79747E",  # outline-variant
    "#F9DEDC",  # error light
    "#FFDC99",  # warning light
    "#D0BCFF",  # primary light (muted purple)
    "#B0B0B8",  # neutral
]


class MD3DarkTheme:
    """Material Design 3 Dark theme with neutral tones and rounded corners.

    Design spec: docs/identidade_visual_MD3.md
    - Surface tonal elevation instead of shadows
    - Color ONLY for alarms
    - Rounded corners (12px cards)
    """

    name = "md3_dark"

    bg_primary = _COLORS.bg_primary
    bg_secondary = _COLORS.bg_secondary
    bg_widget = _COLORS.bg_widget
    fg_primary = _COLORS.fg_primary
    fg_secondary = _COLORS.fg_secondary
    border = _COLORS.border

    alarm_critical = _COLORS.alarm_critical
    alarm_warning = _COLORS.alarm_warning
    alarm_text = _COLORS.alarm_text

    bar_pv = _COLORS.bar_pv
    bar_sp = _COLORS.bar_sp
    bar_co = _COLORS.bar_co

    chart_pv = _COLORS.chart_pv
    chart_sp = _COLORS.chart_sp
    chart_co = _COLORS.chart_co
    chart_grid = _COLORS.chart_grid
    chart_bg = _COLORS.chart_bg

    font_family = _FONTS.family
    font_size_normal = _FONTS.size_normal
    font_size_label = _FONTS.size_label
    font_size_value = _FONTS.size_value
    font_size_title = _FONTS.size_title

    @property
    def colors(self) -> ThemeColors:
        return _COLORS

    @property
    def fonts(self) -> ThemeFonts:
        return _FONTS

    @property
    def chart_palette(self) -> list[str]:
        return list(_CHART_PALETTE)

    def stylesheet(self) -> str:
        return f"""
        QMainWindow, QWidget {{
            background-color: {self.bg_primary};
            color: {self.fg_primary};
            font-family: "{self.font_family}", "Google Sans", "Segoe UI", sans-serif;
            font-size: {self.font_size_normal}px;
        }}
        QLabel {{
            color: {self.fg_primary};
            background: transparent;
        }}
        QPushButton {{
            background-color: {self.bg_secondary};
            color: {self.fg_primary};
            border: 1px solid {self.border};
            border-radius: 12px;
            padding: 8px 20px;
            font-size: {self.font_size_normal}px;
        }}
        QPushButton:hover {{
            background-color: #2B2930;
        }}
        QPushButton:pressed {{
            background-color: #36343B;
        }}
        QLineEdit {{
            background-color: {self.bg_widget};
            color: {self.fg_primary};
            border: 1px solid {self.border};
            border-radius: 8px;
            padding: 8px 12px;
            font-size: {self.font_size_normal}px;
        }}
        QComboBox {{
            background-color: {self.bg_widget};
            color: {self.fg_primary};
            border: 1px solid {self.border};
            border-radius: 8px;
            padding: 6px 12px;
        }}
        QComboBox QAbstractItemView {{
            background-color: {self.bg_secondary};
            color: {self.fg_primary};
            selection-background-color: #2B2930;
            border-radius: 8px;
        }}
        QScrollArea {{
            border: none;
            background: transparent;
        }}
        QTableWidget {{
            background-color: {self.bg_secondary};
            color: {self.fg_primary};
            gridline-color: {self.border};
            border: 1px solid {self.border};
            border-radius: 12px;
            font-size: {self.font_size_normal}px;
        }}
        QHeaderView::section {{
            background-color: #2B2930;
            color: {self.fg_primary};
            border: 1px solid {self.border};
            padding: 6px;
            font-weight: bold;
        }}
        QGroupBox {{
            border: 1px solid {self.border};
            border-radius: 12px;
            margin-top: 8px;
            padding-top: 16px;
            color: {self.fg_primary};
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 16px;
            color: {self.fg_secondary};
        }}
        QSlider::groove:horizontal {{
            background: {self.bg_secondary};
            height: 6px;
            border-radius: 3px;
        }}
        QSlider::handle:horizontal {{
            background: {self.fg_secondary};
            width: 16px;
            margin: -5px 0;
            border-radius: 8px;
        }}
        QRadioButton {{
            color: {self.fg_primary};
            spacing: 10px;
        }}
        QToolBar {{
            background-color: {self.bg_widget};
            border-bottom: 1px solid {self.border};
        }}
        """

    def apply(self, app: QApplication) -> None:
        app.setStyleSheet(self.stylesheet())
