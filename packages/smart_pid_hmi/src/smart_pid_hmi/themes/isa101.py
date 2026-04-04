"""ISA-101 concrete theme — gray-scale, color = alarm only."""
from __future__ import annotations

from typing import TYPE_CHECKING

from smart_pid_hmi.themes.base import ThemeColors, ThemeFonts

if TYPE_CHECKING:
    from PySide6.QtWidgets import QApplication

_COLORS = ThemeColors(
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

_FONTS = ThemeFonts(
    family="Segoe UI",
    size_normal=12,
    size_label=10,
    size_value=14,
    size_title=16,
)

# Multi-trend chart palette (ISA-101: muted grays + alarm colors)
_CHART_PALETTE = [
    "#333333",  # dark gray
    "#666666",  # medium gray
    "#505050",  # gray
    "#888888",  # light gray
    "#FF0000",  # alarm red
    "#FFCC00",  # alarm yellow
    "#404040",  # PV gray
    "#999999",  # grid gray
]


class ISA101Theme:
    """ISA-101 HMI theme: 100% flat, gray-scale, color only for alarms."""

    name = "isa101"

    # Backward-compatible flat attributes (all existing widgets use these)
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
            font-family: "{self.font_family}", "Arial", sans-serif;
            font-size: {self.font_size_normal}px;
        }}
        QLabel {{
            color: {self.fg_primary};
            background: transparent;
        }}
        QPushButton {{
            background-color: {self.bg_widget};
            color: {self.fg_primary};
            border: 1px solid {self.border};
            padding: 6px 16px;
            font-size: {self.font_size_normal}px;
        }}
        QPushButton:hover {{
            background-color: {self.bg_secondary};
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
        QScrollArea {{
            border: none;
            background: transparent;
        }}
        QTableWidget {{
            background-color: {self.bg_widget};
            color: {self.fg_primary};
            gridline-color: {self.border};
            border: 1px solid {self.border};
            font-size: {self.font_size_normal}px;
        }}
        QHeaderView::section {{
            background-color: {self.bg_secondary};
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
        """

    def apply(self, app: QApplication) -> None:
        app.setStyleSheet(self.stylesheet())
