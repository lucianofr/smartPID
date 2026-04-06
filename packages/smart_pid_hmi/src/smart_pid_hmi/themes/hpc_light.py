"""HPC Light theme — High Performance Control, Rockwell/Elipse style.

Based on docs/tema_rockwell_elipse.md:
- Light gray backgrounds (#E0E0E0), flat 2D, no shadows/gradients
- Color reserved EXCLUSIVELY for alarms
- Dynamic values in cold blue (#475CA7)
- Four alarm priorities: Critical(red), High(orange), Medium(yellow), Low(magenta)
- Arial font family, mixed-case text
- Touch-friendly: min 40x40 buttons
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from smart_pid_hmi.themes.base import ThemeColors, ThemeFonts

if TYPE_CHECKING:
    from PySide6.QtWidgets import QApplication

_COLORS = ThemeColors(
    bg_primary="#E0E0E0",       # Main background (gray)
    bg_secondary="#E8E8E8",     # Group box / panel background
    bg_widget="#C0C0C0",        # Tab background / widget area
    fg_primary="#3F3F3F",       # Main text (dark gray, not pure black)
    fg_secondary="#919191",     # Units, secondary labels
    border="#A0A0A4",           # Borders and process lines
    alarm_critical="#E22028",   # Urgent/Critical — red
    alarm_warning="#EC8629",    # High priority — orange
    alarm_text="#FFFFFF",       # White text on alarm backgrounds
    bar_pv="#475CA7",           # Dynamic value blue (cold)
    bar_sp="#808080",           # SP marker — neutral gray
    bar_co="#6A6A70",           # CO bar — darker gray
    chart_pv="#475CA7",         # PV line — dynamic blue
    chart_sp="#808080",         # SP line — gray
    chart_co="#3F3F3F",         # CO line — dark gray
    chart_grid="#C8C8C8",       # Grid lines — subtle
    chart_bg="#E0E0E0",         # Chart background matches app
    bg_card="#E8E8E8",          # Card background (groupbox gray)
    bg_input="#FFFFFF",         # Editable input fields — white
    bg_toolbar="#D0D0D0",       # Toolbar slightly darker
    bg_hover="#D4D4D4",         # Hover state
    fg_muted="#A0A0A4",         # Muted text (borders gray)
    border_focus="#475CA7",     # Focus border — dynamic blue
    border_radius="0px",       # Flat 2D — no rounded corners
    accent="#475CA7",           # Primary accent — cold blue
    alarm_critical_bg="#FCCECE",  # Light red background
    alarm_warning_bg="#FDE8CC",   # Light orange background
)

_FONTS = ThemeFonts(
    family="Arial",
    size_normal=11,
    size_label=10,
    size_value=12,
    size_title=14,
)

# Chart palette — neutral + alarm colors
_CHART_PALETTE = [
    "#475CA7",  # dynamic blue (PV)
    "#3F3F3F",  # dark gray (CO)
    "#808080",  # medium gray (SP)
    "#5A5A5A",  # darker gray
    "#E22028",  # critical red
    "#EC8629",  # high orange
    "#F5E11B",  # medium yellow
    "#916AAD",  # low magenta
]


class HPCLightTheme:
    """High Performance Control Light theme — Rockwell/Elipse style.

    Design spec: docs/tema_rockwell_elipse.md
    - Flat 2D, no shadows, no gradients, no 3D
    - Light gray backgrounds, color only for alarms
    - Dynamic values in cold blue (#475CA7)
    - Arial font, mixed-case, touch-friendly sizing
    """

    name = "hpc_light"

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
        /* ===== High Performance Control Light Theme ===== */
        /* Flat 2D, no shadows/gradients, color = alarm only */

        /* --- Base --- */
        QMainWindow, QDialog, QWidget {{
            background-color: {self.bg_primary};
            color: {self.fg_primary};
            font-family: "{self.font_family}", sans-serif;
            font-size: {self.font_size_normal}px;
        }}

        /* --- Labels --- */
        QLabel {{
            color: {self.fg_primary};
            background: transparent;
            padding: 0px;
        }}

        /* --- Push Buttons (min 40x40 for touch) --- */
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
            border-color: #C0C0C0;
        }}

        /* --- Line Edits (white background when editable) --- */
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
            font-weight: bold;
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

        /* --- Plain Text Edit (AI Log) --- */
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
