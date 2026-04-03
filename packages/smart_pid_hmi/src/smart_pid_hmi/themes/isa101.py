"""ISA-101 concrete theme — gray-scale, color = alarm only."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PySide6.QtWidgets import QApplication


class ISA101Theme:
    """ISA-101 HMI theme: 100% flat, gray-scale, color only for alarms."""

    name = "isa101"

    # Core palette
    bg_primary = "#808080"
    bg_secondary = "#999999"
    bg_widget = "#B0B0B0"
    fg_primary = "#1A1A1A"
    fg_secondary = "#4D4D4D"
    border = "#666666"

    # Semantic (alarms)
    alarm_critical = "#FF0000"
    alarm_warning = "#FFCC00"
    alarm_text = "#FFFFFF"

    # Bars
    bar_pv = "#404040"
    bar_sp = "#606060"
    bar_co = "#505050"

    # Chart
    chart_pv = "#333333"
    chart_sp = "#666666"
    chart_co = "#505050"
    chart_grid = "#999999"
    chart_bg = "#B0B0B0"

    # Typography
    font_family = "Segoe UI"
    font_size_normal = 12
    font_size_label = 10
    font_size_value = 14
    font_size_title = 16

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
        """

    def apply(self, app: QApplication) -> None:
        app.setStyleSheet(self.stylesheet())
