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
    bg_card="#0D0D11",
    bg_input="#050508",
    bg_toolbar="#08080C",
    bg_hover="#15151A",
    fg_muted="#444448",
    border_focus="#555560",
    border_radius="0px",
    accent="#555560",
    alarm_critical_bg="#1A0808",
    alarm_warning_bg="#1A1500",
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
    - Monospaced font (Fira Code) for readability in low light
    - Zero color outside alarms, flat design
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
        /* ===== DarkRoom Ultra-Dark Theme ===== */
        /* Pure black, zero color outside alarms, Fira Code monospace */

        /* --- Base --- */
        QMainWindow, QDialog, QWidget {{
            background-color: {self.bg_primary};
            color: {self.fg_primary};
            font-family: "{self.font_family}", "JetBrains Mono", "Consolas", monospace;
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
            min-height: 24px;
        }}
        QPushButton:hover {{
            background-color: {self.bg_hover};
            border-color: #2A2A30;
        }}
        QPushButton:pressed {{
            background-color: {self.border};
        }}
        QPushButton:checked {{
            background-color: {self.accent};
            color: #E0E0E8;
            border-color: {self.accent};
        }}
        QPushButton:disabled {{
            background-color: #08080C;
            color: {self.fg_muted};
            border-color: #18181E;
        }}

        /* --- Line Edits --- */
        QLineEdit {{
            background-color: {self.bg_input};
            color: {self.fg_primary};
            border: 1px solid {self.border};
            padding: 5px 8px;
            font-size: {self.font_size_normal}px;
            selection-background-color: {self.accent};
            selection-color: #E0E0E8;
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
            font-size: {self.font_size_normal}px;
        }}
        QSpinBox:focus, QDoubleSpinBox:focus {{
            border-color: {self.border_focus};
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
            border-color: #2A2A30;
        }}
        QComboBox:focus {{
            border-color: {self.border_focus};
        }}
        QComboBox QAbstractItemView {{
            background-color: {self.bg_secondary};
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
            border-color: #2A2A30;
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

        /* --- Scroll Bars (nearly invisible, ultra-thin) --- */
        QScrollBar:vertical {{
            background: transparent;
            width: 4px;
            margin: 0px;
            border: none;
        }}
        QScrollBar::handle:vertical {{
            background: #1A1A20;
            min-height: 30px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: {self.border};
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
        }}
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
            background: none;
        }}
        QScrollBar:horizontal {{
            background: transparent;
            height: 4px;
            margin: 0px;
            border: none;
        }}
        QScrollBar::handle:horizontal {{
            background: #1A1A20;
            min-width: 30px;
        }}
        QScrollBar::handle:horizontal:hover {{
            background: {self.border};
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
            alternate-background-color: #08080C;
        }}
        QTableWidget::item, QTableView::item {{
            padding: 4px 8px;
        }}
        QTableWidget::item:selected, QTableView::item:selected {{
            background-color: {self.bg_hover};
        }}
        QHeaderView::section {{
            background-color: {self.bg_hover};
            color: {self.fg_primary};
            border: none;
            border-right: 1px solid {self.border};
            border-bottom: 1px solid {self.border};
            padding: 6px 8px;
            font-weight: bold;
            font-size: {self.font_size_label}px;
        }}
        QHeaderView::section:hover {{
            background-color: #1E1E24;
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
            background: {self.bg_secondary};
            height: 4px;
            border: none;
        }}
        QSlider::handle:horizontal {{
            background: {self.fg_secondary};
            width: 12px;
            height: 12px;
            margin: -4px 0;
        }}
        QSlider::handle:horizontal:hover {{
            background: {self.fg_primary};
        }}
        QSlider::sub-page:horizontal {{
            background: {self.accent};
        }}
        QSlider::groove:vertical {{
            background: {self.bg_secondary};
            width: 4px;
            border: none;
        }}
        QSlider::handle:vertical {{
            background: {self.fg_secondary};
            width: 12px;
            height: 12px;
            margin: 0 -4px;
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
            background-color: {self.bg_secondary};
            border-color: {self.accent};
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
            background-color: {self.bg_secondary};
            color: {self.fg_primary};
            border: 1px solid {self.border};
            padding: 4px 8px;
            font-size: {self.font_size_label}px;
        }}

        /* --- Progress Bar --- */
        QProgressBar {{
            background-color: {self.bg_secondary};
            border: 1px solid {self.border};
            text-align: center;
            color: {self.fg_primary};
            font-size: {self.font_size_label}px;
            height: 14px;
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
            background-color: {self.bg_secondary};
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
