"""ISA-101 concrete theme — dark industrial, color = alarm only."""
from __future__ import annotations

from typing import TYPE_CHECKING

from smart_pid_hmi.themes.base import ThemeColors, ThemeFonts

if TYPE_CHECKING:
    from PySide6.QtWidgets import QApplication

_COLORS = ThemeColors(
    bg_primary="#1E1E1E",
    bg_secondary="#252526",
    bg_widget="#2D2D30",
    fg_primary="#CCCCCC",
    fg_secondary="#808080",
    border="#454548",
    alarm_critical="#FF3333",
    alarm_warning="#FFCC00",
    alarm_text="#FFFFFF",
    bar_pv="#4D8BCC",
    bar_sp="#808080",
    bar_co="#5A5A60",
    chart_pv="#CCCCCC",
    chart_sp="#808080",
    chart_co="#5A5A60",
    chart_grid="#333337",
    chart_bg="#1E1E1E",
    bg_card="#2D2D30",
    bg_input="#252526",
    bg_toolbar="#1E1E1E",
    bg_hover="#3E3E42",
    fg_muted="#555555",
    border_focus="#4D8BCC",
    border_radius="0px",
    accent="#4D8BCC",
    alarm_critical_bg="#3D1111",
    alarm_warning_bg="#3D3011",
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
    "#CCCCCC",  # primary text
    "#808080",  # secondary
    "#5A5A60",  # muted
    "#999999",  # light gray
    "#FF3333",  # alarm red
    "#FFCC00",  # alarm yellow
    "#4D8BCC",  # accent blue
    "#AA55FF",  # diagnostic purple
]


class ISA101Theme:
    """ISA-101 HMI theme: dark industrial, 100% flat, color only for alarms.

    Design spec: docs/identidade_visual_ISA101.md
    - Dark background (#1E1E1E), NOT gray
    - Flat design, zero shadows/gradients/3D effects
    - Monospaced values (Consolas, Roboto Mono)
    """

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

    # Extended palette
    bg_card = _COLORS.bg_card
    bg_input = _COLORS.bg_input
    bg_toolbar = _COLORS.bg_toolbar
    bg_hover = _COLORS.bg_hover
    fg_muted = _COLORS.fg_muted
    border_focus = _COLORS.border_focus
    border_radius = _COLORS.border_radius
    accent = _COLORS.accent
    alarm_critical_bg = _COLORS.alarm_critical_bg
    alarm_warning_bg = _COLORS.alarm_warning_bg

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
        /* ===== ISA-101 Dark Industrial Theme ===== */
        /* 100% flat, zero shadows/gradients/3D */

        /* --- Base --- */
        QMainWindow, QWidget {{
            background-color: {self.bg_primary};
            color: {self.fg_primary};
            font-family: "{self.font_family}", "Arial", sans-serif;
            font-size: {self.font_size_normal}px;
        }}

        /* --- Labels --- */
        QLabel {{
            color: {self.fg_primary};
            background: transparent;
            padding: 0px;
        }}

        /* --- Push Buttons --- */
        QPushButton {{
            background-color: {self.bg_widget};
            color: {self.fg_primary};
            border: 1px solid {self.border};
            padding: 6px 16px;
            font-size: {self.font_size_normal}px;
            min-height: 24px;
        }}
        QPushButton:hover {{
            background-color: {self.bg_hover};
            border-color: {self.fg_secondary};
        }}
        QPushButton:pressed {{
            background-color: {self.border};
        }}
        QPushButton:checked {{
            background-color: {self.accent};
            color: #FFFFFF;
            border-color: {self.accent};
        }}
        QPushButton:disabled {{
            background-color: {self.bg_secondary};
            color: {self.fg_muted};
            border-color: {self.bg_widget};
        }}

        /* --- Line Edits --- */
        QLineEdit {{
            background-color: {self.bg_input};
            color: {self.fg_primary};
            border: 1px solid {self.border};
            padding: 5px 8px;
            font-size: {self.font_size_normal}px;
            font-family: "Consolas", "Roboto Mono", monospace;
            selection-background-color: {self.accent};
            selection-color: #FFFFFF;
        }}
        QLineEdit:focus {{
            border-color: {self.border_focus};
        }}
        QLineEdit:disabled {{
            background-color: {self.bg_primary};
            color: {self.fg_muted};
        }}

        /* --- Spin Boxes --- */
        QSpinBox, QDoubleSpinBox {{
            background-color: {self.bg_input};
            color: {self.fg_primary};
            border: 1px solid {self.border};
            padding: 4px 8px;
            font-family: "Consolas", "Roboto Mono", monospace;
            font-size: {self.font_size_normal}px;
        }}
        QSpinBox:focus, QDoubleSpinBox:focus {{
            border-color: {self.border_focus};
        }}
        QSpinBox::up-button, QDoubleSpinBox::up-button,
        QSpinBox::down-button, QDoubleSpinBox::down-button {{
            background-color: {self.bg_widget};
            border: 1px solid {self.border};
            width: 16px;
        }}
        QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
        QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{
            background-color: {self.bg_hover};
        }}
        QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{
            image: none;
            border-left: 4px solid transparent;
            border-right: 4px solid transparent;
            border-bottom: 5px solid {self.fg_secondary};
            width: 0px; height: 0px;
        }}
        QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{
            image: none;
            border-left: 4px solid transparent;
            border-right: 4px solid transparent;
            border-top: 5px solid {self.fg_secondary};
            width: 0px; height: 0px;
        }}

        /* --- Combo Boxes --- */
        QComboBox {{
            background-color: {self.bg_input};
            color: {self.fg_primary};
            border: 1px solid {self.border};
            padding: 5px 8px;
            font-size: {self.font_size_normal}px;
        }}
        QComboBox:hover {{
            border-color: {self.fg_secondary};
        }}
        QComboBox:focus {{
            border-color: {self.border_focus};
        }}
        QComboBox::drop-down {{
            border: none;
            width: 24px;
        }}
        QComboBox::down-arrow {{
            image: none;
            border-left: 4px solid transparent;
            border-right: 4px solid transparent;
            border-top: 5px solid {self.fg_secondary};
            width: 0px; height: 0px;
        }}
        QComboBox QAbstractItemView {{
            background-color: {self.bg_widget};
            color: {self.fg_primary};
            border: 1px solid {self.border};
            selection-background-color: {self.bg_hover};
            selection-color: {self.fg_primary};
            outline: none;
        }}

        /* --- Check Boxes --- */
        QCheckBox {{
            color: {self.fg_primary};
            spacing: 8px;
        }}
        QCheckBox::indicator {{
            width: 16px;
            height: 16px;
            border: 1px solid {self.border};
            background-color: {self.bg_input};
        }}
        QCheckBox::indicator:checked {{
            background-color: {self.accent};
            border-color: {self.accent};
        }}
        QCheckBox::indicator:hover {{
            border-color: {self.fg_secondary};
        }}

        /* --- Radio Buttons --- */
        QRadioButton {{
            color: {self.fg_primary};
            spacing: 8px;
        }}
        QRadioButton::indicator {{
            width: 16px;
            height: 16px;
            border: 1px solid {self.border};
            background-color: {self.bg_input};
        }}
        QRadioButton::indicator:checked {{
            background-color: {self.accent};
            border-color: {self.accent};
        }}

        /* --- Scroll Area --- */
        QScrollArea {{
            border: none;
            background: transparent;
        }}

        /* --- Scroll Bars (thin, unobtrusive) --- */
        QScrollBar:vertical {{
            background: {self.bg_primary};
            width: 6px;
            margin: 0px;
            border: none;
        }}
        QScrollBar::handle:vertical {{
            background: {self.border};
            min-height: 30px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: {self.fg_secondary};
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
        }}
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
            background: none;
        }}
        QScrollBar:horizontal {{
            background: {self.bg_primary};
            height: 6px;
            margin: 0px;
            border: none;
        }}
        QScrollBar::handle:horizontal {{
            background: {self.border};
            min-width: 30px;
        }}
        QScrollBar::handle:horizontal:hover {{
            background: {self.fg_secondary};
        }}
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
            width: 0px;
        }}
        QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
            background: none;
        }}

        /* --- Tables --- */
        QTableWidget, QTableView {{
            background-color: {self.bg_secondary};
            color: {self.fg_primary};
            gridline-color: {self.border};
            border: 1px solid {self.border};
            font-size: {self.font_size_normal}px;
            selection-background-color: {self.bg_hover};
            selection-color: {self.fg_primary};
            alternate-background-color: {self.bg_widget};
        }}
        QTableWidget::item, QTableView::item {{
            padding: 4px 8px;
        }}
        QTableWidget::item:selected, QTableView::item:selected {{
            background-color: {self.bg_hover};
        }}
        QHeaderView::section {{
            background-color: {self.bg_widget};
            color: {self.fg_primary};
            border: none;
            border-right: 1px solid {self.border};
            border-bottom: 1px solid {self.border};
            padding: 6px 8px;
            font-weight: bold;
            font-size: {self.font_size_label}px;
        }}
        QHeaderView::section:hover {{
            background-color: {self.bg_hover};
        }}

        /* --- Group Boxes --- */
        QGroupBox {{
            border: 1px solid {self.border};
            margin-top: 10px;
            padding: 16px 8px 8px 8px;
            color: {self.fg_primary};
            font-weight: bold;
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 4px;
            color: {self.fg_secondary};
        }}

        /* --- Sliders --- */
        QSlider::groove:horizontal {{
            background: {self.bg_widget};
            height: 4px;
            border: none;
        }}
        QSlider::handle:horizontal {{
            background: {self.fg_secondary};
            width: 14px;
            height: 14px;
            margin: -5px 0;
        }}
        QSlider::handle:horizontal:hover {{
            background: {self.fg_primary};
        }}
        QSlider::sub-page:horizontal {{
            background: {self.accent};
        }}
        QSlider::groove:vertical {{
            background: {self.bg_widget};
            width: 4px;
            border: none;
        }}
        QSlider::handle:vertical {{
            background: {self.fg_secondary};
            width: 14px;
            height: 14px;
            margin: 0 -5px;
        }}
        QSlider::sub-page:vertical {{
            background: {self.accent};
        }}

        /* --- Toolbar --- */
        QToolBar {{
            background-color: {self.bg_toolbar};
            border-bottom: 1px solid {self.border};
            padding: 2px 4px;
            spacing: 4px;
        }}
        QToolBar QToolButton {{
            background-color: transparent;
            color: {self.fg_primary};
            border: 1px solid transparent;
            padding: 6px 12px;
            font-size: {self.font_size_normal}px;
        }}
        QToolBar QToolButton:hover {{
            background-color: {self.bg_hover};
            border-color: {self.border};
        }}
        QToolBar QToolButton:pressed {{
            background-color: {self.border};
        }}
        QToolBar QToolButton:checked {{
            background-color: {self.bg_widget};
            border-color: {self.accent};
            color: {self.fg_primary};
        }}

        /* --- Frames --- */
        QFrame {{
            border: none;
        }}
        QFrame[frameShape="4"] /* HLine */ {{
            background-color: {self.border};
            max-height: 1px;
        }}
        QFrame[frameShape="5"] /* VLine */ {{
            background-color: {self.border};
            max-width: 1px;
        }}

        /* --- Splitter --- */
        QSplitter::handle {{
            background-color: {self.border};
        }}
        QSplitter::handle:horizontal {{
            width: 1px;
        }}
        QSplitter::handle:vertical {{
            height: 1px;
        }}

        /* --- Tab Widget --- */
        QTabWidget::pane {{
            border: 1px solid {self.border};
            background-color: {self.bg_primary};
        }}
        QTabBar::tab {{
            background-color: {self.bg_secondary};
            color: {self.fg_secondary};
            border: 1px solid {self.border};
            border-bottom: none;
            padding: 8px 16px;
            font-size: {self.font_size_normal}px;
        }}
        QTabBar::tab:hover {{
            background-color: {self.bg_hover};
            color: {self.fg_primary};
        }}
        QTabBar::tab:selected {{
            background-color: {self.bg_primary};
            color: {self.fg_primary};
            border-bottom: 2px solid {self.accent};
        }}

        /* --- Tooltips --- */
        QToolTip {{
            background-color: {self.bg_widget};
            color: {self.fg_primary};
            border: 1px solid {self.border};
            padding: 4px 8px;
            font-size: {self.font_size_label}px;
        }}

        /* --- Progress Bar --- */
        QProgressBar {{
            background-color: {self.bg_widget};
            border: 1px solid {self.border};
            text-align: center;
            color: {self.fg_primary};
            font-size: {self.font_size_label}px;
            height: 16px;
        }}
        QProgressBar::chunk {{
            background-color: {self.accent};
        }}

        /* --- Menu --- */
        QMenuBar {{
            background-color: {self.bg_toolbar};
            color: {self.fg_primary};
            border-bottom: 1px solid {self.border};
        }}
        QMenuBar::item:selected {{
            background-color: {self.bg_hover};
        }}
        QMenu {{
            background-color: {self.bg_widget};
            color: {self.fg_primary};
            border: 1px solid {self.border};
        }}
        QMenu::item {{
            padding: 6px 24px;
        }}
        QMenu::item:selected {{
            background-color: {self.bg_hover};
        }}
        QMenu::separator {{
            height: 1px;
            background-color: {self.border};
            margin: 4px 8px;
        }}

        /* --- Status Bar --- */
        QStatusBar {{
            background-color: {self.bg_toolbar};
            color: {self.fg_secondary};
            border-top: 1px solid {self.border};
            font-size: {self.font_size_label}px;
        }}
        """

    def apply(self, app: QApplication) -> None:
        app.setStyleSheet(self.stylesheet())
