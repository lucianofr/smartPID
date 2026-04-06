"""MD3 Light theme — Material Design 3 light with neutral tones and rounded corners."""
from __future__ import annotations

from typing import TYPE_CHECKING

from smart_pid_hmi.themes.base import ThemeColors, ThemeFonts

if TYPE_CHECKING:
    from PySide6.QtWidgets import QApplication

# Material Design 3 Light baseline palette — navy blue accent
# Reference: https://m3.material.io/styles/color/system/overview
_COLORS = ThemeColors(
    bg_primary="#FAFCFF",       # Surface (cool white)
    bg_secondary="#EDF1F9",     # Surface Container
    bg_widget="#E3E8F0",        # Surface Container Low
    fg_primary="#191C20",       # On-Surface
    fg_secondary="#43474E",     # On-Surface Variant
    border="#C3C7CF",           # Outline Variant
    alarm_critical="#BA1A1A",   # Error
    alarm_warning="#7D5700",    # Warning
    alarm_text="#FFFFFF",       # On-Error
    bar_pv="#1B5FA0",           # Primary (navy blue)
    bar_sp="#5A5F71",           # Secondary (slate)
    bar_co="#715A60",           # Tertiary (muted rose)
    chart_pv="#1B5FA0",         # Primary
    chart_sp="#5A5F71",         # Secondary
    chart_co="#715A60",         # Tertiary
    chart_grid="#DEE3EB",       # Surface Variant
    chart_bg="#FAFCFF",         # Surface
    bg_card="#F0F4FC",          # Surface Container High (cool tint)
    bg_input="#FAFCFF",         # Surface
    bg_toolbar="#EDF1F9",       # Surface Container
    bg_hover="#D3E4FF",         # Primary Container (light navy)
    fg_muted="#73777F",         # Outline
    border_focus="#1B5FA0",     # Primary
    border_radius="12px",
    accent="#1B5FA0",           # Primary (navy blue)
    alarm_critical_bg="#FFDAD6",  # Error Container
    alarm_warning_bg="#FFDDB3",   # Warning Container
)

_FONTS = ThemeFonts(
    family="Roboto",
    size_normal=14,
    size_label=12,
    size_value=16,
    size_title=18,
)

_CHART_PALETTE = [
    "#1B5FA0",  # primary (navy blue)
    "#5A5F71",  # secondary (slate)
    "#715A60",  # tertiary (muted rose)
    "#191C20",  # on-surface
    "#BA1A1A",  # error
    "#7D5700",  # warning
    "#43474E",  # on-surface-variant
    "#73777F",  # outline
]


class MD3LightTheme:
    """Material Design 3 Light theme with navy blue accent and rounded corners.

    Design spec: docs/identidade_visual_MD3.md (light variant)
    - Surface tonal elevation with cool white/blue-tint backgrounds
    - Navy blue (#1B5FA0) accent for primary actions and bars
    - Color ONLY for alarms
    - Rounded corners (12px cards, 8px inputs)
    - Roboto / Google Sans font family
    """

    name = "md3_light"

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
        /* ===== Material Design 3 Light Theme ===== */

        /* --- Base --- */
        QMainWindow, QDialog, QWidget {{
            background-color: {self.bg_primary};
            color: {self.fg_primary};
            font-family: "{self.font_family}", "Google Sans", "Segoe UI", sans-serif;
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
            border-radius: 12px;
            padding: 8px 20px;
            font-size: {self.font_size_normal}px;
            min-height: 28px;
        }}
        QPushButton:hover {{
            background-color: {self.bg_hover};
            border-color: {self.fg_secondary};
        }}
        QPushButton:pressed {{
            background-color: #BDD3EE;
        }}
        QPushButton:checked {{
            background-color: {self.accent};
            color: #FFFFFF;
            border-color: {self.accent};
        }}
        QPushButton:disabled {{
            background-color: {self.bg_widget};
            color: {self.fg_muted};
            border-color: #D8D2DC;
        }}

        /* --- Line Edits --- */
        QLineEdit {{
            background-color: {self.bg_input};
            color: {self.fg_primary};
            border: 1px solid {self.border};
            border-radius: 8px;
            padding: 8px 12px;
            font-size: {self.font_size_normal}px;
            selection-background-color: {self.bg_hover};
            selection-color: {self.fg_primary};
        }}
        QLineEdit:focus {{
            border-color: {self.border_focus};
            border-width: 2px;
            padding: 7px 11px;
        }}
        QLineEdit:disabled {{
            background-color: {self.bg_secondary};
            color: {self.fg_muted};
        }}

        /* --- Spin Boxes --- */
        QSpinBox, QDoubleSpinBox {{
            background-color: {self.bg_input};
            color: {self.fg_primary};
            border: 1px solid {self.border};
            border-radius: 8px;
            padding: 6px 10px;
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
            border-radius: 8px;
            padding: 8px 12px;
            font-size: {self.font_size_normal}px;
        }}
        QComboBox:hover {{
            border-color: {self.fg_secondary};
        }}
        QComboBox:focus {{
            border-color: {self.border_focus};
            border-width: 2px;
        }}
        QComboBox QAbstractItemView {{
            background-color: {self.bg_card};
            color: {self.fg_primary};
            border: 1px solid {self.border};
            border-radius: 8px;
            selection-background-color: {self.bg_hover};
            selection-color: {self.fg_primary};
            outline: none;
            padding: 4px;
        }}

        /* --- Check Boxes --- */
        QCheckBox {{
            color: {self.fg_primary};
            spacing: 10px;
        }}
        QCheckBox::indicator {{
            width: 18px;
            height: 18px;
            border: 2px solid {self.border};
            border-radius: 4px;
            background-color: transparent;
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
            spacing: 10px;
        }}
        QRadioButton::indicator {{
            width: 18px;
            height: 18px;
            border: 2px solid {self.border};
            border-radius: 9px;
            background-color: transparent;
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
            background: transparent;
            width: 8px;
            margin: 4px 2px;
            border: none;
        }}
        QScrollBar::handle:vertical {{
            background: {self.border};
            min-height: 30px;
            border-radius: 3px;
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
            background: transparent;
            height: 8px;
            margin: 2px 4px;
            border: none;
        }}
        QScrollBar::handle:horizontal {{
            background: {self.border};
            min-width: 30px;
            border-radius: 3px;
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
            background-color: {self.bg_card};
            color: {self.fg_primary};
            gridline-color: #E7E0EC;
            border: 1px solid {self.border};
            border-radius: 12px;
            font-size: {self.font_size_normal}px;
            selection-background-color: {self.bg_hover};
            selection-color: {self.fg_primary};
            alternate-background-color: {self.bg_secondary};
        }}
        QTableWidget::item, QTableView::item {{
            padding: 6px 10px;
        }}
        QTableWidget::item:selected, QTableView::item:selected {{
            background-color: {self.bg_hover};
        }}
        QHeaderView::section {{
            background-color: {self.bg_secondary};
            color: {self.fg_primary};
            border: none;
            border-right: 1px solid #E7E0EC;
            border-bottom: 1px solid #E7E0EC;
            padding: 8px 10px;
            font-weight: bold;
            font-size: {self.font_size_label}px;
        }}

        /* --- Group Boxes --- */
        QGroupBox {{
            border: 1px solid {self.border};
            border-radius: 12px;
            margin-top: 12px;
            padding: 20px 12px 12px 12px;
            color: {self.fg_primary};
            font-weight: bold;
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 16px;
            padding: 0 6px;
            color: {self.fg_secondary};
        }}

        /* --- Sliders --- */
        QSlider::groove:horizontal {{
            background: {self.bg_widget};
            height: 6px;
            border-radius: 3px;
        }}
        QSlider::handle:horizontal {{
            background: {self.accent};
            width: 18px;
            height: 18px;
            margin: -6px 0;
            border-radius: 9px;
        }}
        QSlider::handle:horizontal:hover {{
            background: #2E7BC4;
        }}
        QSlider::sub-page:horizontal {{
            background: {self.accent};
            border-radius: 3px;
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
            border-radius: 8px;
            padding: 8px 14px;
            font-size: {self.font_size_normal}px;
        }}
        QToolBar QToolButton:hover {{
            background-color: {self.bg_hover};
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
            border-radius: 1px;
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
            border-radius: 12px;
            background-color: {self.bg_primary};
        }}
        QTabBar::tab {{
            background-color: transparent;
            color: {self.fg_secondary};
            border: none;
            border-bottom: 2px solid transparent;
            padding: 10px 20px;
            font-size: {self.font_size_normal}px;
        }}
        QTabBar::tab:hover {{
            background-color: {self.bg_hover};
            color: {self.fg_primary};
            border-radius: 8px 8px 0px 0px;
        }}
        QTabBar::tab:selected {{
            color: {self.accent};
            border-bottom: 2px solid {self.accent};
        }}

        /* --- Tooltips --- */
        QToolTip {{
            background-color: {self.bg_card};
            color: {self.fg_primary};
            border: 1px solid {self.border};
            border-radius: 8px;
            padding: 6px 10px;
            font-size: {self.font_size_label}px;
        }}

        /* --- Progress Bar --- */
        QProgressBar {{
            background-color: {self.bg_widget};
            border: none;
            border-radius: 4px;
            text-align: center;
            color: {self.fg_primary};
            font-size: {self.font_size_label}px;
            height: 8px;
        }}
        QProgressBar::chunk {{
            background-color: {self.accent};
            border-radius: 4px;
        }}

        /* --- Menu --- */
        QMenuBar {{
            background-color: {self.bg_toolbar};
            color: {self.fg_primary};
            border-bottom: 1px solid {self.border};
            padding: 2px;
        }}
        QMenuBar::item {{
            padding: 6px 12px;
            border-radius: 6px;
        }}
        QMenuBar::item:selected {{
            background-color: {self.bg_hover};
        }}
        QMenu {{
            background-color: {self.bg_card};
            color: {self.fg_primary};
            border: 1px solid {self.border};
            border-radius: 8px;
            padding: 4px;
        }}
        QMenu::item {{
            padding: 8px 24px;
            border-radius: 6px;
        }}
        QMenu::item:selected {{
            background-color: {self.bg_hover};
        }}
        QMenu::separator {{
            height: 1px;
            background-color: {self.border};
            margin: 4px 12px;
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
            background-color: {self.bg_card};
            color: {self.fg_primary};
            border: 1px solid {self.border};
            border-radius: 8px;
            font-size: {self.font_size_normal}px;
            padding: 6px;
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
