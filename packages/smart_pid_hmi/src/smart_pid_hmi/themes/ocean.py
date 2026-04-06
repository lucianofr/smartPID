"""Ocean theme — High Performance HMI with cool-toned palette.

Based on docs/tema_ocean.txt:
- Cool blue-gray backgrounds (#CED7E0) to reduce visual fatigue
- Flat 2D, no shadows, gradients, or 3D elements
- Dynamic values in vibrant medium blue (#2B6BAE)
- Color reserved EXCLUSIVELY for alarms (yellow=attention, red=critical)
- Dual coding for alarms: color + shape + number (accessibility)
- Arial/Segoe UI font family
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from smart_pid_hmi.themes.base import ThemeColors, ThemeFonts

if TYPE_CHECKING:
    from PySide6.QtWidgets import QApplication

_COLORS = ThemeColors(
    bg_primary="#CED7E0",       # Cool blue-gray main background
    bg_secondary="#D6DEE6",     # Slightly lighter for grouping panels
    bg_widget="#B8C4CF",        # Tab/widget area — cooler gray
    fg_primary="#3F3F3F",       # Dark gray text (not pure black)
    fg_secondary="#7A8B99",     # Units, secondary labels — blue-gray muted
    border="#9BAAB8",           # Borders / process lines — blue-gray medium
    alarm_critical="#D32F2F",   # Priority 1 — vibrant red
    alarm_warning="#F9A825",    # Priority 2 — vibrant yellow
    alarm_text="#000000",       # Black text on alarm backgrounds
    bar_pv="#2B6BAE",           # Dynamic value — vibrant medium blue
    bar_sp="#6E7B87",           # SP marker — neutral cool gray
    bar_co="#5A6670",           # CO bar — darker cool gray
    chart_pv="#2B6BAE",         # PV line — dynamic blue
    chart_sp="#6E7B87",         # SP line — cool gray
    chart_co="#3F3F3F",         # CO line — dark gray
    chart_grid="#B8C4CF",       # Grid lines — subtle, dotted style
    chart_bg="#CED7E0",         # Chart background matches app
    bg_card="#D6DEE6",          # Card background (panel blue-gray)
    bg_input="#F0F4F7",         # Editable input fields — very light blue-white
    bg_toolbar="#C2CCD6",       # Toolbar — slightly darker blue-gray
    bg_hover="#BEC9D3",         # Hover state
    fg_muted="#9BAAB8",         # Muted text (same as border)
    border_focus="#2B6BAE",     # Focus border — dynamic blue
    border_radius="0px",       # Flat 2D — no rounded corners
    accent="#2B6BAE",           # Primary accent — vibrant medium blue
    alarm_critical_bg="#FDCECE",  # Light red background
    alarm_warning_bg="#FFF3C4",   # Light yellow background
)

_FONTS = ThemeFonts(
    family="Arial",
    size_normal=11,
    size_label=10,
    size_value=12,
    size_title=20,
)

# Chart palette — ocean tones + alarm colors
_CHART_PALETTE = [
    "#2B6BAE",  # dynamic blue (PV)
    "#3F3F3F",  # dark gray (CO)
    "#6E7B87",  # cool gray (SP)
    "#1A4D7E",  # deep ocean blue
    "#D32F2F",  # critical red
    "#F9A825",  # warning yellow
    "#4A90C4",  # lighter ocean blue
    "#5A6670",  # slate gray
]


class OceanTheme:
    """Ocean theme — cool-toned High Performance HMI.

    Design spec: docs/tema_ocean.txt
    - Flat 2D, no shadows/gradients, no 3D elements
    - Cool blue-gray backgrounds (#CED7E0) for reduced visual fatigue
    - Dynamic values in vibrant medium blue (#2B6BAE)
    - Alarms: red (critical, square+1) and yellow (attention, triangle+2)
    - Arial font, situational awareness priority
    """

    name = "ocean"

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
        /* ===== Ocean Theme — Cool-Toned High Performance HMI ===== */
        /* Flat 2D, no shadows/gradients, situational awareness first */

        /* --- Base --- */
        QMainWindow, QWidget {{
            background-color: {self.bg_primary};
            color: {self.fg_primary};
            font-family: "{self.font_family}", "Segoe UI", sans-serif;
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
            background-color: {self.bg_secondary};
            color: {self.fg_primary};
            border: 1px solid {self.border};
            padding: 6px 16px;
            font-size: {self.font_size_normal}px;
            min-height: 30px;
        }}
        QPushButton:hover {{
            background-color: {self.bg_hover};
            border-color: {self.fg_primary};
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
            background-color: {self.bg_widget};
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
        }}
        QLineEdit:focus {{
            border-color: {self.border_focus};
            border-width: 2px;
            padding: 4px 7px;
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
            padding: 5px 8px;
            font-size: {self.font_size_normal}px;
        }}
        QSpinBox:focus, QDoubleSpinBox:focus {{
            border-color: {self.border_focus};
            border-width: 2px;
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
            border-color: {self.fg_primary};
        }}
        QComboBox:focus {{
            border-color: {self.border_focus};
            border-width: 2px;
        }}
        QComboBox QAbstractItemView {{
            background-color: {self.bg_input};
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
            border-color: {self.fg_primary};
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
            border-radius: 8px;
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

        /* --- Scroll Bars --- */
        QScrollBar:vertical {{
            background: {self.bg_secondary};
            width: 14px;
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
            background: {self.bg_secondary};
            height: 14px;
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
            background-color: {self.bg_input};
            color: {self.fg_primary};
            gridline-color: {self.border};
            border: 1px solid {self.border};
            font-size: {self.font_size_normal}px;
            selection-background-color: {self.bg_hover};
            selection-color: {self.fg_primary};
            alternate-background-color: {self.bg_secondary};
        }}
        QTableWidget::item, QTableView::item {{
            padding: 4px 8px;
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

        /* --- Group Boxes --- */
        QGroupBox {{
            border: 1px solid {self.border};
            margin-top: 10px;
            padding: 16px 8px 8px 8px;
            color: {self.fg_primary};
            font-weight: normal;
            font-size: {self.font_size_label}px;
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 4px;
            color: {self.fg_primary};
        }}

        /* --- Sliders --- */
        QSlider::groove:horizontal {{
            background: {self.bg_widget};
            height: 6px;
        }}
        QSlider::handle:horizontal {{
            background: {self.accent};
            width: 16px;
            height: 16px;
            margin: -5px 0;
        }}
        QSlider::sub-page:horizontal {{
            background: {self.accent};
        }}

        /* --- Toolbar --- */
        QToolBar {{
            background-color: {self.bg_toolbar};
            border-bottom: 1px solid {self.border};
            padding: 4px 8px;
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
        QToolBar QToolButton:checked {{
            background-color: {self.bg_hover};
            border-color: {self.accent};
            color: {self.accent};
        }}

        /* --- Frames --- */
        QFrame {{
            border: none;
        }}
        QFrame[frameShape="4"] {{
            background-color: {self.border};
            max-height: 1px;
        }}
        QFrame[frameShape="5"] {{
            background-color: {self.border};
            max-width: 1px;
        }}

        /* --- Splitter --- */
        QSplitter::handle {{
            background-color: {self.border};
        }}
        QSplitter::handle:horizontal {{
            width: 2px;
        }}
        QSplitter::handle:vertical {{
            height: 2px;
        }}

        /* --- Tab Widget --- */
        QTabWidget::pane {{
            border: 1px solid {self.border};
            background-color: {self.bg_primary};
        }}
        QTabBar::tab {{
            background-color: {self.bg_widget};
            color: {self.fg_primary};
            border: 1px solid {self.border};
            border-bottom: none;
            padding: 8px 16px;
            font-size: {self.font_size_normal}px;
        }}
        QTabBar::tab:hover {{
            background-color: {self.bg_hover};
        }}
        QTabBar::tab:selected {{
            background-color: {self.bg_primary};
            border-bottom: 2px solid {self.accent};
            font-weight: bold;
        }}

        /* --- Tooltips --- */
        QToolTip {{
            background-color: {self.bg_secondary};
            color: {self.fg_primary};
            border: 1px solid {self.border};
            padding: 4px 8px;
            font-size: {self.font_size_label}px;
        }}

        /* --- Progress Bar (analog bar fill) --- */
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
        QMenuBar::item {{
            padding: 6px 10px;
        }}
        QMenuBar::item:selected {{
            background-color: {self.bg_hover};
        }}
        QMenu {{
            background-color: {self.bg_input};
            color: {self.fg_primary};
            border: 1px solid {self.border};
        }}
        QMenu::item {{
            padding: 6px 20px;
        }}
        QMenu::item:selected {{
            background-color: {self.bg_hover};
        }}
        QMenu::separator {{
            height: 1px;
            background-color: {self.border};
            margin: 2px 8px;
        }}

        /* --- Status Bar --- */
        QStatusBar {{
            background-color: {self.bg_toolbar};
            color: {self.fg_secondary};
            border-top: 1px solid {self.border};
            font-size: {self.font_size_label}px;
        }}

        /* --- Plain Text Edit --- */
        QPlainTextEdit {{
            background-color: {self.bg_input};
            color: {self.fg_primary};
            border: 1px solid {self.border};
            font-size: {self.font_size_normal}px;
            padding: 4px;
        }}

        /* --- Welcome / Project Dialog --- */
        QLabel#welcome_title {{
            font-size: {self.font_size_title + 4}px;
            font-weight: bold;
            color: {self.fg_primary};
            padding: 8px 0;
        }}
        QLabel#welcome_subtitle {{
            font-size: {self.font_size_normal}px;
            color: {self.fg_secondary};
        }}
        QLabel#welcome_recent_label {{
            font-size: {self.font_size_label}px;
            color: {self.fg_secondary};
            letter-spacing: 1px;
        }}
        QListWidget#recent_list {{
            background-color: {self.bg_secondary};
            color: {self.fg_primary};
            border: 1px solid {self.border};
        }}
        QListWidget#recent_list::item {{
            padding: 6px 8px;
            border-bottom: 1px solid {self.border};
        }}
        QListWidget#recent_list::item:hover {{
            background-color: {self.bg_hover};
        }}
        QListWidget#recent_list::item:selected {{
            background-color: {self.bg_hover};
            color: {self.fg_primary};
        }}
        """

    def apply(self, app: QApplication) -> None:
        app.setStyleSheet(self.stylesheet())
