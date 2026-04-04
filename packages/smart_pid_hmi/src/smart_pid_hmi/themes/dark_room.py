"""DarkRoom theme — ultra-dark for control room environments."""
from __future__ import annotations

from typing import TYPE_CHECKING

from smart_pid_hmi.themes.base import ThemeColors, ThemeFonts

if TYPE_CHECKING:
    from PySide6.QtWidgets import QApplication

_COLORS = ThemeColors(
    bg_primary="#000000",
    bg_secondary="#0D0D11",
    bg_widget="#050508",
    fg_primary="#B0B0B8",
    fg_secondary="#666670",
    border="#222228",
    alarm_critical="#D92525",
    alarm_warning="#D9A000",
    alarm_text="#FFFFFF",
    bar_pv="#4A4A52",
    bar_sp="#888890",
    bar_co="#3A3A42",
    chart_pv="#B0B0B8",
    chart_sp="#888890",
    chart_co="#666670",
    chart_grid="#1A1A20",
    chart_bg="#000000",
)

_FONTS = ThemeFonts(
    family="Fira Code",
    size_normal=13,
    size_label=11,
    size_value=15,
    size_title=17,
)

_CHART_PALETTE = [
    "#B0B0B8",  # primary gray
    "#888890",  # medium gray
    "#666670",  # dim gray
    "#4A4A52",  # dark gray
    "#D92525",  # alarm red
    "#D9A000",  # alarm amber
    "#555560",  # muted
    "#9999A0",  # light
]


class DarkRoomTheme:
    """Ultra-dark theme for control room (Dark Room) environments.

    Design spec: docs/identidade_visual_Dark.md
    - Background: pure black (#000000)
    - Color ONLY for alarms
    - Monospaced font for readability in low light
    """

    name = "dark_room"

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
            font-family: "{self.font_family}", "JetBrains Mono", "Consolas", monospace;
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
            padding: 6px 16px;
            font-size: {self.font_size_normal}px;
        }}
        QPushButton:hover {{
            background-color: #15151A;
        }}
        QPushButton:pressed {{
            background-color: {self.border};
        }}
        QLineEdit {{
            background-color: {self.bg_widget};
            color: {self.fg_primary};
            border: 1px solid {self.border};
            padding: 4px 8px;
            font-size: {self.font_size_normal}px;
        }}
        QComboBox {{
            background-color: {self.bg_widget};
            color: {self.fg_primary};
            border: 1px solid {self.border};
            padding: 4px 8px;
        }}
        QComboBox QAbstractItemView {{
            background-color: {self.bg_secondary};
            color: {self.fg_primary};
            selection-background-color: {self.border};
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
            font-size: {self.font_size_normal}px;
        }}
        QHeaderView::section {{
            background-color: #15151A;
            color: {self.fg_primary};
            border: 1px solid {self.border};
            padding: 4px;
            font-weight: bold;
        }}
        QGroupBox {{
            border: 1px solid {self.border};
            margin-top: 8px;
            padding-top: 12px;
            color: {self.fg_primary};
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 10px;
            color: {self.fg_secondary};
        }}
        QSlider::groove:horizontal {{
            background: {self.bg_widget};
            height: 6px;
            border: 1px solid {self.border};
        }}
        QSlider::handle:horizontal {{
            background: {self.fg_secondary};
            width: 14px;
            margin: -4px 0;
        }}
        QRadioButton {{
            color: {self.fg_primary};
            spacing: 8px;
        }}
        QToolBar {{
            background-color: {self.bg_secondary};
            border-bottom: 1px solid {self.border};
        }}
        """

    def apply(self, app: QApplication) -> None:
        app.setStyleSheet(self.stylesheet())
