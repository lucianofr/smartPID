"""ThemeBase Protocol — contract for all themes."""
from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from PySide6.QtWidgets import QApplication


class ThemeBase(Protocol):
    """Protocol that all themes must satisfy."""

    name: str

    # Core palette
    bg_primary: str
    bg_secondary: str
    bg_widget: str
    fg_primary: str
    fg_secondary: str
    border: str

    # Semantic (alarms)
    alarm_critical: str
    alarm_warning: str
    alarm_text: str

    # Bars
    bar_pv: str
    bar_sp: str
    bar_co: str

    # Chart
    chart_pv: str
    chart_sp: str
    chart_co: str
    chart_grid: str
    chart_bg: str

    # Typography
    font_family: str
    font_size_normal: int
    font_size_label: int
    font_size_value: int
    font_size_title: int

    def stylesheet(self) -> str: ...
    def apply(self, app: QApplication) -> None: ...
