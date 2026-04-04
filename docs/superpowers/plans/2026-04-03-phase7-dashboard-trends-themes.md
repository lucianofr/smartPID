# Phase 7 — Executive Dashboard + Multi-Trend + Export + Themes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add executive dashboard, multi-trend analysis, data export (CSV/XLSX), 3-theme system with hot-switch, and SVG overlay for the simulator page.

**Architecture:** ThemeBase protocol with 3 implementations (DarkRoom, MD3 Dark, ISA-101) managed by ThemeManager with hot-switch via signal. New pages (Executive, MultiTrend, Settings) added to QStackedWidget. Export via backend worker thread + REST endpoints. SVG overlay composites QSvgWidget + QLabels.

**Tech Stack:** PySide6, pyqtgraph, openpyxl, httpx, FastAPI, QSvgWidget

**Existing ThemeBase Protocol:** `packages/smart_pid_hmi/src/smart_pid_hmi/themes/base.py` already defines the Protocol with 22 attributes (bg_primary, fg_primary, alarm_critical, bar_pv, chart_pv, font_family, etc.) and methods `stylesheet()`, `apply()`.

**Existing ISA101Theme:** `packages/smart_pid_hmi/src/smart_pid_hmi/themes/isa101.py` already satisfies the Protocol with flat class attributes.

**Dependencies:** All new HMI code depends on the existing ThemeBase protocol. Export backend depends on openpyxl (new dependency).

---

## File Structure

```
packages/smart_pid_hmi/src/smart_pid_hmi/
├── themes/
│   ├── __init__.py                          # Updated: export all themes + ThemeManager
│   ├── base.py                              # Existing (ThemeBase Protocol) — add ThemeColors, ThemeFonts
│   ├── isa101.py                            # Existing — refactor to use dataclasses
│   ├── dark_room.py                         # NEW: DarkRoom theme
│   ├── md3_dark.py                          # NEW: MD3 Dark theme
│   └── manager.py                           # NEW: ThemeManager QObject with hot-switch
│
├── pages/
│   ├── executive_dashboard.py               # NEW: KPI cards + performance table
│   ├── multi_trend_page.py                  # NEW: 2x2 pyqtgraph grid
│   └── settings_page.py                     # NEW: theme picker + preferences
│
├── widgets/
│   └── svg_overlay.py                       # NEW: QSvgWidget + positioned QLabels
│
├── services/
│   └── api_client.py                        # Modified: add stats + export methods
│
└── main.py                                  # Modified: add new pages + ThemeManager

packages/smart_pid_core/src/smart_pid_core/
├── adapters/inbound/api/
│   ├── routers/
│   │   └── export.py                        # NEW: POST/GET export endpoints
│   └── app.py                               # Modified: register export router
│
└── application/
    └── export_worker.py                     # NEW: CSV/XLSX generation worker

packages/smart_pid_domain/src/smart_pid_domain/
└── dtos/
    ├── export.py                            # NEW: ExportRequest, ExportStatusResponse
    └── __init__.py                          # Modified: add export DTOs

tests/hmi/
├── themes/
│   ├── test_isa101.py                       # Modified: add dataclass tests
│   ├── test_dark_room.py                    # NEW
│   ├── test_md3_dark.py                     # NEW
│   └── test_theme_manager.py               # NEW
├── pages/
│   ├── test_executive_dashboard.py          # NEW
│   ├── test_multi_trend_page.py             # NEW
│   └── test_settings_page.py               # NEW
├── widgets/
│   └── test_svg_overlay.py                  # NEW
└── services/
    └── test_api_client.py                   # Modified: add export tests

tests/core/
├── unit/
│   └── test_export_worker.py               # NEW
└── integration/
    └── test_api_export.py                   # NEW
```

---

## Task 1: ThemeColors + ThemeFonts dataclasses in base.py

**Files:**
- Modify: `packages/smart_pid_hmi/src/smart_pid_hmi/themes/base.py`
- Create: `tests/hmi/themes/test_theme_dataclasses.py`

- [ ] **Step 1.1: Write the failing test**

```python
# tests/hmi/themes/test_theme_dataclasses.py
"""Tests for ThemeColors and ThemeFonts frozen dataclasses."""
from smart_pid_hmi.themes.base import ThemeColors, ThemeFonts


def test_theme_colors_creation():
    colors = ThemeColors(
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
    assert colors.bg_primary == "#808080"
    assert colors.alarm_critical == "#FF0000"
    assert colors.chart_pv == "#333333"


def test_theme_colors_is_frozen():
    colors = ThemeColors(
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
    try:
        colors.bg_primary = "#000000"  # type: ignore[misc]
        raise AssertionError("Should be frozen")
    except AttributeError:
        pass


def test_theme_fonts_creation():
    fonts = ThemeFonts(
        family="Segoe UI",
        size_normal=12,
        size_label=10,
        size_value=14,
        size_title=16,
    )
    assert fonts.family == "Segoe UI"
    assert fonts.size_normal == 12
    assert fonts.size_title == 16


def test_theme_fonts_is_frozen():
    fonts = ThemeFonts(
        family="Segoe UI",
        size_normal=12,
        size_label=10,
        size_value=14,
        size_title=16,
    )
    try:
        fonts.family = "Arial"  # type: ignore[misc]
        raise AssertionError("Should be frozen")
    except AttributeError:
        pass
```

- [ ] **Step 1.2: Run test to verify it fails**

```bash
uv run pytest tests/hmi/themes/test_theme_dataclasses.py -v
```
Expected: FAIL — `ImportError: cannot import name 'ThemeColors' from 'smart_pid_hmi.themes.base'`

- [ ] **Step 1.3: Write minimal implementation**

```python
# packages/smart_pid_hmi/src/smart_pid_hmi/themes/base.py
"""ThemeBase Protocol — contract for all themes."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from PySide6.QtWidgets import QApplication


@dataclass(frozen=True)
class ThemeColors:
    """Immutable color palette for a theme."""

    bg_primary: str
    bg_secondary: str
    bg_widget: str
    fg_primary: str
    fg_secondary: str
    border: str

    alarm_critical: str
    alarm_warning: str
    alarm_text: str

    bar_pv: str
    bar_sp: str
    bar_co: str

    chart_pv: str
    chart_sp: str
    chart_co: str
    chart_grid: str
    chart_bg: str


@dataclass(frozen=True)
class ThemeFonts:
    """Immutable font settings for a theme."""

    family: str
    size_normal: int
    size_label: int
    size_value: int
    size_title: int


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
```

- [ ] **Step 1.4: Run test to verify it passes**

```bash
uv run pytest tests/hmi/themes/test_theme_dataclasses.py -v
```
Expected: 4 PASSED

- [ ] **Step 1.5: Commit**

```bash
git add packages/smart_pid_hmi/src/smart_pid_hmi/themes/base.py \
       tests/hmi/themes/test_theme_dataclasses.py
git commit -m "feat(hmi): add ThemeColors + ThemeFonts frozen dataclasses"
```

---

## Task 2: ISA-101 Refactor — use ThemeColors/ThemeFonts internally

**Files:**
- Modify: `packages/smart_pid_hmi/src/smart_pid_hmi/themes/isa101.py`
- Modify: `tests/hmi/themes/test_isa101.py`

- [ ] **Step 2.1: Write the failing test**

```python
# tests/hmi/themes/test_isa101.py (add to existing)
"""Tests for ISA-101 theme."""
from smart_pid_hmi.themes.base import ThemeColors, ThemeFonts
from smart_pid_hmi.themes.isa101 import ISA101Theme


def test_isa101_implements_protocol():
    theme = ISA101Theme()
    assert theme.name == "isa101"
    assert isinstance(theme.bg_primary, str)
    assert isinstance(theme.fg_primary, str)
    assert isinstance(theme.alarm_critical, str)
    assert isinstance(theme.alarm_warning, str)
    assert isinstance(theme.bar_pv, str)
    assert isinstance(theme.chart_pv, str)
    assert isinstance(theme.font_family, str)
    assert isinstance(theme.font_size_normal, int)


def test_isa101_color_values():
    theme = ISA101Theme()
    assert theme.bg_primary == "#808080"
    assert theme.alarm_critical == "#FF0000"
    assert theme.alarm_warning == "#FFCC00"


def test_isa101_stylesheet_not_empty():
    theme = ISA101Theme()
    qss = theme.stylesheet()
    assert len(qss) > 0
    assert "background" in qss.lower() or "background-color" in qss.lower()


def test_apply_no_crash(qtbot):
    """Verify apply() does not raise on a real QApplication."""
    from PySide6.QtWidgets import QApplication

    theme = ISA101Theme()
    app = QApplication.instance()
    assert app is not None
    theme.apply(app)


def test_isa101_has_colors_dataclass():
    """ISA-101 exposes ThemeColors via .colors property."""
    theme = ISA101Theme()
    assert hasattr(theme, "colors")
    colors = theme.colors
    assert isinstance(colors, ThemeColors)
    assert colors.bg_primary == "#808080"
    assert colors.alarm_critical == "#FF0000"


def test_isa101_has_fonts_dataclass():
    """ISA-101 exposes ThemeFonts via .fonts property."""
    theme = ISA101Theme()
    assert hasattr(theme, "fonts")
    fonts = theme.fonts
    assert isinstance(fonts, ThemeFonts)
    assert fonts.family == "Segoe UI"
    assert fonts.size_normal == 12


def test_isa101_has_chart_palette():
    """ISA-101 exposes a chart_palette list for multi-trend."""
    theme = ISA101Theme()
    assert hasattr(theme, "chart_palette")
    palette = theme.chart_palette
    assert isinstance(palette, list)
    assert len(palette) >= 4
    for color in palette:
        assert isinstance(color, str)
        assert color.startswith("#")
```

- [ ] **Step 2.2: Run test to verify it fails**

```bash
uv run pytest tests/hmi/themes/test_isa101.py -v
```
Expected: FAIL — `test_isa101_has_colors_dataclass` and `test_isa101_has_fonts_dataclass` fail (no `.colors` attribute)

- [ ] **Step 2.3: Write minimal implementation**

```python
# packages/smart_pid_hmi/src/smart_pid_hmi/themes/isa101.py
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
```

- [ ] **Step 2.4: Run test to verify it passes**

```bash
uv run pytest tests/hmi/themes/test_isa101.py -v
```
Expected: 7 PASSED (4 existing + 3 new)

- [ ] **Step 2.5: Run existing dashboard and widget tests to verify backward compatibility**

```bash
uv run pytest tests/hmi/ -v
```
Expected: All existing tests PASS (theme attributes are backward-compatible)

- [ ] **Step 2.6: Commit**

```bash
git add packages/smart_pid_hmi/src/smart_pid_hmi/themes/isa101.py \
       tests/hmi/themes/test_isa101.py
git commit -m "refactor(hmi): ISA-101 theme uses ThemeColors/ThemeFonts dataclasses + chart palette"
```

---

## Task 3: DarkRoom Theme

**Files:**
- Create: `packages/smart_pid_hmi/src/smart_pid_hmi/themes/dark_room.py`
- Create: `tests/hmi/themes/test_dark_room.py`

- [ ] **Step 3.1: Write the failing test**

```python
# tests/hmi/themes/test_dark_room.py
"""Tests for DarkRoom theme."""
from smart_pid_hmi.themes.base import ThemeColors, ThemeFonts
from smart_pid_hmi.themes.dark_room import DarkRoomTheme


def test_dark_room_name():
    theme = DarkRoomTheme()
    assert theme.name == "dark_room"


def test_dark_room_implements_protocol():
    theme = DarkRoomTheme()
    assert isinstance(theme.bg_primary, str)
    assert isinstance(theme.fg_primary, str)
    assert isinstance(theme.alarm_critical, str)
    assert isinstance(theme.alarm_warning, str)
    assert isinstance(theme.bar_pv, str)
    assert isinstance(theme.chart_pv, str)
    assert isinstance(theme.font_family, str)
    assert isinstance(theme.font_size_normal, int)


def test_dark_room_colors():
    theme = DarkRoomTheme()
    assert theme.bg_primary == "#000000"
    assert theme.bg_secondary == "#0D0D11"
    assert theme.fg_primary == "#B0B0B8"
    assert theme.alarm_critical == "#D92525"
    assert theme.alarm_warning == "#D9A000"


def test_dark_room_colors_dataclass():
    theme = DarkRoomTheme()
    colors = theme.colors
    assert isinstance(colors, ThemeColors)
    assert colors.bg_primary == "#000000"


def test_dark_room_fonts_dataclass():
    theme = DarkRoomTheme()
    fonts = theme.fonts
    assert isinstance(fonts, ThemeFonts)
    assert "Fira Code" in fonts.family or "JetBrains Mono" in fonts.family


def test_dark_room_chart_palette():
    theme = DarkRoomTheme()
    palette = theme.chart_palette
    assert isinstance(palette, list)
    assert len(palette) >= 4


def test_dark_room_stylesheet_not_empty():
    theme = DarkRoomTheme()
    qss = theme.stylesheet()
    assert len(qss) > 0
    assert "#000000" in qss


def test_dark_room_apply_no_crash(qtbot):
    from PySide6.QtWidgets import QApplication

    theme = DarkRoomTheme()
    app = QApplication.instance()
    assert app is not None
    theme.apply(app)
```

- [ ] **Step 3.2: Run test to verify it fails**

```bash
uv run pytest tests/hmi/themes/test_dark_room.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'smart_pid_hmi.themes.dark_room'`

- [ ] **Step 3.3: Write minimal implementation**

```python
# packages/smart_pid_hmi/src/smart_pid_hmi/themes/dark_room.py
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
            background: {self.bg_secondary};
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
```

- [ ] **Step 3.4: Run test to verify it passes**

```bash
uv run pytest tests/hmi/themes/test_dark_room.py -v
```
Expected: 8 PASSED

- [ ] **Step 3.5: Commit**

```bash
git add packages/smart_pid_hmi/src/smart_pid_hmi/themes/dark_room.py \
       tests/hmi/themes/test_dark_room.py
git commit -m "feat(hmi): add DarkRoom theme for control room environments"
```

---

## Task 4: MD3 Dark Theme

**Files:**
- Create: `packages/smart_pid_hmi/src/smart_pid_hmi/themes/md3_dark.py`
- Create: `tests/hmi/themes/test_md3_dark.py`

- [ ] **Step 4.1: Write the failing test**

```python
# tests/hmi/themes/test_md3_dark.py
"""Tests for MD3 Dark theme."""
from smart_pid_hmi.themes.base import ThemeColors, ThemeFonts
from smart_pid_hmi.themes.md3_dark import MD3DarkTheme


def test_md3_dark_name():
    theme = MD3DarkTheme()
    assert theme.name == "md3_dark"


def test_md3_dark_implements_protocol():
    theme = MD3DarkTheme()
    assert isinstance(theme.bg_primary, str)
    assert isinstance(theme.fg_primary, str)
    assert isinstance(theme.alarm_critical, str)
    assert isinstance(theme.alarm_warning, str)
    assert isinstance(theme.bar_pv, str)
    assert isinstance(theme.chart_pv, str)
    assert isinstance(theme.font_family, str)
    assert isinstance(theme.font_size_normal, int)


def test_md3_dark_colors():
    theme = MD3DarkTheme()
    assert theme.bg_primary == "#141218"
    assert theme.bg_secondary == "#211F26"
    assert theme.fg_primary == "#E6E0E9"
    assert theme.alarm_critical == "#8C1D18"
    assert theme.alarm_warning == "#4D3300"


def test_md3_dark_colors_dataclass():
    theme = MD3DarkTheme()
    colors = theme.colors
    assert isinstance(colors, ThemeColors)
    assert colors.bg_primary == "#141218"


def test_md3_dark_fonts_dataclass():
    theme = MD3DarkTheme()
    fonts = theme.fonts
    assert isinstance(fonts, ThemeFonts)
    assert "Roboto" in fonts.family


def test_md3_dark_chart_palette():
    theme = MD3DarkTheme()
    palette = theme.chart_palette
    assert isinstance(palette, list)
    assert len(palette) >= 4


def test_md3_dark_stylesheet_not_empty():
    theme = MD3DarkTheme()
    qss = theme.stylesheet()
    assert len(qss) > 0
    assert "#141218" in qss


def test_md3_dark_apply_no_crash(qtbot):
    from PySide6.QtWidgets import QApplication

    theme = MD3DarkTheme()
    app = QApplication.instance()
    assert app is not None
    theme.apply(app)
```

- [ ] **Step 4.2: Run test to verify it fails**

```bash
uv run pytest tests/hmi/themes/test_md3_dark.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'smart_pid_hmi.themes.md3_dark'`

- [ ] **Step 4.3: Write minimal implementation**

```python
# packages/smart_pid_hmi/src/smart_pid_hmi/themes/md3_dark.py
"""Material Design 3 Dark theme — neutral tones, rounded corners."""
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
```

- [ ] **Step 4.4: Run test to verify it passes**

```bash
uv run pytest tests/hmi/themes/test_md3_dark.py -v
```
Expected: 8 PASSED

- [ ] **Step 4.5: Commit**

```bash
git add packages/smart_pid_hmi/src/smart_pid_hmi/themes/md3_dark.py \
       tests/hmi/themes/test_md3_dark.py
git commit -m "feat(hmi): add MD3 Dark theme with Material Design 3 tokens"
```

---

## Task 5: ThemeManager

**Files:**
- Create: `packages/smart_pid_hmi/src/smart_pid_hmi/themes/manager.py`
- Create: `tests/hmi/themes/test_theme_manager.py`

- [ ] **Step 5.1: Write the failing test**

```python
# tests/hmi/themes/test_theme_manager.py
"""Tests for ThemeManager."""
import pytest

from smart_pid_hmi.themes.dark_room import DarkRoomTheme
from smart_pid_hmi.themes.isa101 import ISA101Theme
from smart_pid_hmi.themes.manager import ThemeManager
from smart_pid_hmi.themes.md3_dark import MD3DarkTheme


def test_manager_register_and_current(qtbot):
    mgr = ThemeManager()
    theme = ISA101Theme()
    mgr.register(theme)
    mgr.set_theme("isa101")
    assert mgr.current.name == "isa101"


def test_manager_register_multiple(qtbot):
    mgr = ThemeManager()
    mgr.register(ISA101Theme())
    mgr.register(DarkRoomTheme())
    mgr.register(MD3DarkTheme())
    assert mgr.available_themes() == ["dark_room", "isa101", "md3_dark"]


def test_manager_switch_theme(qtbot):
    mgr = ThemeManager()
    mgr.register(ISA101Theme())
    mgr.register(DarkRoomTheme())
    mgr.set_theme("isa101")
    assert mgr.current.name == "isa101"

    mgr.set_theme("dark_room")
    assert mgr.current.name == "dark_room"


def test_manager_emits_signal(qtbot):
    mgr = ThemeManager()
    mgr.register(ISA101Theme())
    mgr.register(DarkRoomTheme())
    mgr.set_theme("isa101")

    with qtbot.waitSignal(mgr.theme_changed, timeout=1000) as blocker:
        mgr.set_theme("dark_room")
    assert blocker.args == ["dark_room"]


def test_manager_unknown_theme_raises(qtbot):
    mgr = ThemeManager()
    mgr.register(ISA101Theme())
    with pytest.raises(KeyError, match="no_such_theme"):
        mgr.set_theme("no_such_theme")


def test_manager_no_signal_if_same_theme(qtbot):
    mgr = ThemeManager()
    mgr.register(ISA101Theme())
    mgr.set_theme("isa101")

    signals = []
    mgr.theme_changed.connect(lambda name: signals.append(name))
    mgr.set_theme("isa101")  # same theme, no signal
    assert signals == []


def test_manager_current_raises_if_none(qtbot):
    mgr = ThemeManager()
    with pytest.raises(RuntimeError, match="No theme set"):
        _ = mgr.current
```

- [ ] **Step 5.2: Run test to verify it fails**

```bash
uv run pytest tests/hmi/themes/test_theme_manager.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'smart_pid_hmi.themes.manager'`

- [ ] **Step 5.3: Write minimal implementation**

```python
# packages/smart_pid_hmi/src/smart_pid_hmi/themes/manager.py
"""ThemeManager — register, switch, and notify on theme changes."""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Signal

if TYPE_CHECKING:
    from smart_pid_hmi.themes.base import ThemeBase


class ThemeManager(QObject):
    """Manages registered themes and emits signals on theme switch.

    Usage:
        mgr = ThemeManager()
        mgr.register(ISA101Theme())
        mgr.register(DarkRoomTheme())
        mgr.set_theme("isa101")
        mgr.theme_changed.connect(on_theme_change)
    """

    theme_changed = Signal(str)  # emits theme name

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._themes: dict[str, ThemeBase] = {}
        self._current: ThemeBase | None = None

    def register(self, theme: ThemeBase) -> None:
        """Register a theme instance. Uses theme.name as key."""
        self._themes[theme.name] = theme

    def set_theme(self, name: str) -> None:
        """Switch to a registered theme by name.

        Raises KeyError if the theme is not registered.
        Does not emit theme_changed if already on that theme.
        """
        if name not in self._themes:
            raise KeyError(name)
        if self._current is not None and self._current.name == name:
            return
        self._current = self._themes[name]
        self.theme_changed.emit(name)

    @property
    def current(self) -> ThemeBase:
        """Return the current active theme.

        Raises RuntimeError if no theme has been set.
        """
        if self._current is None:
            raise RuntimeError("No theme set")
        return self._current

    def available_themes(self) -> list[str]:
        """Return sorted list of registered theme names."""
        return sorted(self._themes.keys())

    def get(self, name: str) -> ThemeBase:
        """Get a specific theme by name. Raises KeyError if not found."""
        return self._themes[name]
```

- [ ] **Step 5.4: Run test to verify it passes**

```bash
uv run pytest tests/hmi/themes/test_theme_manager.py -v
```
Expected: 7 PASSED

- [ ] **Step 5.5: Commit**

```bash
git add packages/smart_pid_hmi/src/smart_pid_hmi/themes/manager.py \
       tests/hmi/themes/test_theme_manager.py
git commit -m "feat(hmi): add ThemeManager with register/switch/signal"
```

---

## Task 6: themes/__init__.py — export all themes

**Files:**
- Modify: `packages/smart_pid_hmi/src/smart_pid_hmi/themes/__init__.py`

- [ ] **Step 6.1: Write the failing test**

```python
# Add to tests/hmi/themes/test_theme_manager.py (append)

def test_themes_init_exports():
    from smart_pid_hmi.themes import (
        DarkRoomTheme,
        ISA101Theme,
        MD3DarkTheme,
        ThemeManager,
    )
    assert ISA101Theme is not None
    assert DarkRoomTheme is not None
    assert MD3DarkTheme is not None
    assert ThemeManager is not None
```

- [ ] **Step 6.2: Run test to verify it fails**

```bash
uv run pytest tests/hmi/themes/test_theme_manager.py::test_themes_init_exports -v
```
Expected: FAIL — `ImportError: cannot import name 'DarkRoomTheme' from 'smart_pid_hmi.themes'`

- [ ] **Step 6.3: Write minimal implementation**

```python
# packages/smart_pid_hmi/src/smart_pid_hmi/themes/__init__.py
"""Theme system — ISA-101, DarkRoom, MD3 Dark, and ThemeManager."""
from smart_pid_hmi.themes.dark_room import DarkRoomTheme
from smart_pid_hmi.themes.isa101 import ISA101Theme
from smart_pid_hmi.themes.manager import ThemeManager
from smart_pid_hmi.themes.md3_dark import MD3DarkTheme

__all__ = [
    "DarkRoomTheme",
    "ISA101Theme",
    "MD3DarkTheme",
    "ThemeManager",
]
```

- [ ] **Step 6.4: Run test to verify it passes**

```bash
uv run pytest tests/hmi/themes/test_theme_manager.py -v
```
Expected: 8 PASSED (7 + 1 new)

- [ ] **Step 6.5: Commit**

```bash
git add packages/smart_pid_hmi/src/smart_pid_hmi/themes/__init__.py \
       tests/hmi/themes/test_theme_manager.py
git commit -m "chore(hmi): export all themes + ThemeManager from themes package"
```

---

## Task 7: ExecutiveDashboardPage

**Files:**
- Create: `packages/smart_pid_hmi/src/smart_pid_hmi/pages/executive_dashboard.py`
- Create: `tests/hmi/pages/test_executive_dashboard.py`

- [ ] **Step 7.1: Write the failing test**

```python
# tests/hmi/pages/test_executive_dashboard.py
"""Tests for ExecutiveDashboardPage."""
import pytest

from smart_pid_hmi.pages.executive_dashboard import ExecutiveDashboardPage
from smart_pid_hmi.themes.isa101 import ISA101Theme


@pytest.fixture
def theme():
    return ISA101Theme()


def test_creation(qtbot, theme):
    page = ExecutiveDashboardPage(theme=theme)
    qtbot.addWidget(page)
    assert page._kpi_total is not None
    assert page._kpi_auto is not None
    assert page._kpi_alarms is not None
    assert page._kpi_ai is not None
    assert page._perf_table is not None


def test_update_kpis(qtbot, theme):
    page = ExecutiveDashboardPage(theme=theme)
    qtbot.addWidget(page)
    page.update_kpis(total=10, in_auto=8, active_alarms=2, ai_active=3)
    assert page._kpi_total.text() == "10"
    assert page._kpi_auto.text() == "8"
    assert page._kpi_alarms.text() == "2"
    assert page._kpi_ai.text() == "3"


def test_update_performance_table(qtbot, theme):
    page = ExecutiveDashboardPage(theme=theme)
    qtbot.addWidget(page)
    stats = [
        {
            "tag": "FIC-101", "mode": "AUTO",
            "iae": 5.0, "itae": 10.0, "tv": 3.0,
            "variability_range": 0.04,
        },
        {
            "tag": "LIC-201", "mode": "MAN",
            "iae": 12.0, "itae": 25.0, "tv": 8.0,
            "variability_range": 0.09,
        },
    ]
    page.update_performance_table(stats)
    assert page._perf_table.rowCount() == 2
    assert page._perf_table.item(0, 0).text() == "FIC-101"
    assert page._perf_table.item(1, 0).text() == "LIC-201"


def test_performance_table_columns(qtbot, theme):
    page = ExecutiveDashboardPage(theme=theme)
    qtbot.addWidget(page)
    headers = []
    for col in range(page._perf_table.columnCount()):
        headers.append(page._perf_table.horizontalHeaderItem(col).text())
    assert "Tag" in headers
    assert "Mode" in headers
    assert "IAE" in headers
    assert "ITAE" in headers
    assert "TV" in headers


def test_clear_data(qtbot, theme):
    page = ExecutiveDashboardPage(theme=theme)
    qtbot.addWidget(page)
    page.update_kpis(total=5, in_auto=3, active_alarms=1, ai_active=2)
    page.clear_data()
    assert page._kpi_total.text() == "0"
    assert page._perf_table.rowCount() == 0
```

- [ ] **Step 7.2: Run test to verify it fails**

```bash
uv run pytest tests/hmi/pages/test_executive_dashboard.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'smart_pid_hmi.pages.executive_dashboard'`

- [ ] **Step 7.3: Write minimal implementation**

```python
# packages/smart_pid_hmi/src/smart_pid_hmi/pages/executive_dashboard.py
"""ExecutiveDashboardPage — KPI cards + performance table for plant overview."""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from smart_pid_hmi.themes.base import ThemeBase

_PERF_COLUMNS = ["Tag", "Mode", "IAE", "ITAE", "TV", "\u03c3/Range"]


class _KPICard(QFrame):
    """A single KPI display card with title and large value."""

    def __init__(
        self,
        title: str,
        theme: ThemeBase,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setStyleSheet(
            f"_KPICard {{ background-color: {theme.bg_secondary}; "
            f"border: 1px solid {theme.border}; padding: 8px; }}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)

        title_label = QLabel(title)
        title_label.setStyleSheet(
            f"color: {theme.fg_secondary}; font-size: {theme.font_size_label}px; "
            f"background: transparent;"
        )
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)

        self._value_label = QLabel("0")
        self._value_label.setStyleSheet(
            f"color: {theme.fg_primary}; font-size: {theme.font_size_title + 8}px; "
            f"font-weight: bold; background: transparent;"
        )
        self._value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._value_label)

    @property
    def value_label(self) -> QLabel:
        return self._value_label


class ExecutiveDashboardPage(QWidget):
    """Plant-wide executive dashboard with KPI cards and performance table."""

    def __init__(
        self,
        theme: ThemeBase,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._theme = theme

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Title
        title = QLabel("Executive Dashboard")
        title.setStyleSheet(
            f"font-size: {theme.font_size_title}px; font-weight: bold; "
            f"color: {theme.fg_primary};"
        )
        layout.addWidget(title)

        # KPI cards row
        kpi_row = QHBoxLayout()
        kpi_row.setSpacing(12)

        card_total = _KPICard("Total Loops", theme)
        self._kpi_total = card_total.value_label
        kpi_row.addWidget(card_total)

        card_auto = _KPICard("In AUTO", theme)
        self._kpi_auto = card_auto.value_label
        kpi_row.addWidget(card_auto)

        card_alarms = _KPICard("Active Alarms", theme)
        self._kpi_alarms = card_alarms.value_label
        kpi_row.addWidget(card_alarms)

        card_ai = _KPICard("AI Tuning Active", theme)
        self._kpi_ai = card_ai.value_label
        kpi_row.addWidget(card_ai)

        layout.addLayout(kpi_row)

        # Performance table
        table_label = QLabel("Performance Summary")
        table_label.setStyleSheet(
            f"font-size: {theme.font_size_value}px; font-weight: bold; "
            f"color: {theme.fg_primary}; margin-top: 8px;"
        )
        layout.addWidget(table_label)

        self._perf_table = QTableWidget(0, len(_PERF_COLUMNS))
        self._perf_table.setHorizontalHeaderLabels(_PERF_COLUMNS)
        self._perf_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self._perf_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._perf_table.setSortingEnabled(True)
        self._perf_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self._perf_table, stretch=1)

    def update_kpis(
        self,
        total: int,
        in_auto: int,
        active_alarms: int,
        ai_active: int,
    ) -> None:
        """Update the KPI card values."""
        self._kpi_total.setText(str(total))
        self._kpi_auto.setText(str(in_auto))
        self._kpi_alarms.setText(str(active_alarms))
        self._kpi_ai.setText(str(ai_active))

    def update_performance_table(self, stats: list[dict]) -> None:
        """Populate the performance table from a list of stat dicts.

        Each dict should have keys: tag, mode, iae, itae, tv, variability_range.
        """
        self._perf_table.setSortingEnabled(False)
        self._perf_table.setRowCount(0)

        for entry in stats:
            row = self._perf_table.rowCount()
            self._perf_table.insertRow(row)
            values = [
                entry.get("tag", ""),
                entry.get("mode", ""),
                f"{entry.get('iae', 0.0):.2f}",
                f"{entry.get('itae', 0.0):.2f}",
                f"{entry.get('tv', 0.0):.2f}",
                f"{entry.get('variability_range', 0.0):.4f}",
            ]
            for col, text in enumerate(values):
                item = QTableWidgetItem(text)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                # For numeric columns, set sort data as float
                if col >= 2:
                    item.setData(Qt.ItemDataRole.UserRole, float(text))
                self._perf_table.setItem(row, col, item)

        self._perf_table.setSortingEnabled(True)

    def clear_data(self) -> None:
        """Reset all KPIs and clear the performance table."""
        self._kpi_total.setText("0")
        self._kpi_auto.setText("0")
        self._kpi_alarms.setText("0")
        self._kpi_ai.setText("0")
        self._perf_table.setRowCount(0)
```

- [ ] **Step 7.4: Run test to verify it passes**

```bash
uv run pytest tests/hmi/pages/test_executive_dashboard.py -v
```
Expected: 5 PASSED

- [ ] **Step 7.5: Commit**

```bash
git add packages/smart_pid_hmi/src/smart_pid_hmi/pages/executive_dashboard.py \
       tests/hmi/pages/test_executive_dashboard.py
git commit -m "feat(hmi): add ExecutiveDashboardPage with KPI cards + performance table"
```

---

## Task 8: APIClient stats methods

**Files:**
- Modify: `packages/smart_pid_hmi/src/smart_pid_hmi/services/api_client.py`
- Modify: `tests/hmi/services/test_api_client.py`

- [ ] **Step 8.1: Write the failing test**

```python
# tests/hmi/services/test_api_client.py (append these tests)

def test_get_controller_stats():
    data = {
        "controller_id": 1, "iae": 5.0, "itae": 10.0, "ise": 25.0,
        "mse": 12.5, "std_dev": 2.0, "total_variation": 3.0,
        "variability_sp": 0.08, "variability_range": 0.04, "sample_count": 100,
    }
    transport = _mock_transport(200, data)
    session = Session()
    client = APIClient(base_url="http://test:8000", session=session, transport=transport)
    result = client.get_controller_stats(1)
    assert result.iae == 5.0
    assert result.total_variation == 3.0
    assert result.sample_count == 100


def test_get_all_stats():
    """get_all_stats returns a dict of controller_id -> StatsResponse."""
    from smart_pid_domain.dtos.controllers import ControllerResponse

    responses = {
        "/controllers": [
            {"id": 1, "name": "FIC-101", "description": "Flow",
             "mode": "AUTO", "pv": 45.0, "sp": 50.0, "co": 62.0},
            {"id": 2, "name": "LIC-201", "description": "Level",
             "mode": "MAN", "pv": 30.0, "sp": 35.0, "co": 40.0},
        ],
        "/controllers/1/stats": {
            "controller_id": 1, "iae": 5.0, "itae": 10.0, "ise": 25.0,
            "mse": 12.5, "std_dev": 2.0, "total_variation": 3.0,
            "variability_sp": 0.08, "variability_range": 0.04, "sample_count": 100,
        },
        "/controllers/2/stats": {
            "controller_id": 2, "iae": 12.0, "itae": 25.0, "ise": 50.0,
            "mse": 20.0, "std_dev": 4.0, "total_variation": 8.0,
            "variability_sp": 0.12, "variability_range": 0.09, "sample_count": 200,
        },
    }

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path in responses:
            return httpx.Response(200, json=responses[path])
        return httpx.Response(404, json={"detail": "not found"})

    transport = httpx.MockTransport(handler)
    session = Session()
    client = APIClient(base_url="http://test:8000", session=session, transport=transport)
    result = client.get_all_stats()
    assert len(result) == 2
    assert result[1].iae == 5.0
    assert result[2].total_variation == 8.0
```

- [ ] **Step 8.2: Run test to verify it fails**

```bash
uv run pytest tests/hmi/services/test_api_client.py::test_get_controller_stats -v
uv run pytest tests/hmi/services/test_api_client.py::test_get_all_stats -v
```
Expected: FAIL — `AttributeError: 'APIClient' object has no attribute 'get_controller_stats'`

- [ ] **Step 8.3: Write minimal implementation**

Add these methods to `packages/smart_pid_hmi/src/smart_pid_hmi/services/api_client.py`:

```python
    # --- In class APIClient, after close() method ---

    def get_controller_stats(self, controller_id: int) -> StatsResponse:
        resp = self._http.get(
            f"/controllers/{controller_id}/stats",
            headers=self._headers(),
        )
        resp.raise_for_status()
        return StatsResponse.model_validate(resp.json())

    def get_all_stats(self) -> dict[int, StatsResponse]:
        """Fetch stats for all controllers. Returns {controller_id: StatsResponse}."""
        controllers = self.list_controllers()
        result: dict[int, StatsResponse] = {}
        for ctrl in controllers:
            try:
                stats = self.get_controller_stats(ctrl.id)
                result[ctrl.id] = stats
            except Exception:
                pass  # Skip controllers without stats worker
        return result
```

Also add the import at the top of `api_client.py`:

```python
from smart_pid_domain.dtos.ai import StatsResponse
```

- [ ] **Step 8.4: Run test to verify it passes**

```bash
uv run pytest tests/hmi/services/test_api_client.py -v
```
Expected: All PASSED (existing + 2 new)

- [ ] **Step 8.5: Commit**

```bash
git add packages/smart_pid_hmi/src/smart_pid_hmi/services/api_client.py \
       tests/hmi/services/test_api_client.py
git commit -m "feat(hmi): add get_controller_stats + get_all_stats to APIClient"
```

---

## Task 9: MultiTrendPage

**Files:**
- Create: `packages/smart_pid_hmi/src/smart_pid_hmi/pages/multi_trend_page.py`
- Create: `tests/hmi/pages/test_multi_trend_page.py`

- [ ] **Step 9.1: Write the failing test**

```python
# tests/hmi/pages/test_multi_trend_page.py
"""Tests for MultiTrendPage."""
import pytest

from smart_pid_hmi.pages.multi_trend_page import MultiTrendPage
from smart_pid_hmi.themes.isa101 import ISA101Theme


@pytest.fixture
def theme():
    return ISA101Theme()


def test_creation(qtbot, theme):
    page = MultiTrendPage(theme=theme)
    qtbot.addWidget(page)
    assert len(page._plots) == 4  # 2x2 grid
    assert page._time_range_combo is not None
    assert page._loop_selectors is not None


def test_four_plot_widgets(qtbot, theme):
    page = MultiTrendPage(theme=theme)
    qtbot.addWidget(page)
    # Each plot slot should have a PlotWidget
    for plot in page._plots:
        assert plot is not None


def test_time_range_buttons(qtbot, theme):
    page = MultiTrendPage(theme=theme)
    qtbot.addWidget(page)
    expected = ["1m", "5m", "15m", "1h"]
    actual_items = [
        page._time_range_combo.itemText(i)
        for i in range(page._time_range_combo.count())
    ]
    for tr in expected:
        assert tr in actual_items


def test_populate_loop_selectors(qtbot, theme):
    page = MultiTrendPage(theme=theme)
    qtbot.addWidget(page)
    controllers = [
        {"id": 1, "name": "FIC-101"},
        {"id": 2, "name": "LIC-201"},
        {"id": 3, "name": "TIC-301"},
    ]
    page.populate_controllers(controllers)
    for combo in page._loop_selectors:
        assert combo.count() >= 4  # "(none)" + 3 controllers


def test_update_trend_data(qtbot, theme):
    page = MultiTrendPage(theme=theme)
    qtbot.addWidget(page)
    # Update plot 0 with some data points
    times = [0.0, 1.0, 2.0]
    pvs = [45.0, 46.0, 47.0]
    sps = [50.0, 50.0, 50.0]
    cos = [62.0, 63.0, 64.0]
    page.update_plot_data(0, times, pvs, sps, cos)
    # No crash = pass; data is internal to pyqtgraph


def test_live_mode_toggle(qtbot, theme):
    page = MultiTrendPage(theme=theme)
    qtbot.addWidget(page)
    assert page._live_mode is True  # default
    page.set_live_mode(False)
    assert page._live_mode is False
```

- [ ] **Step 9.2: Run test to verify it fails**

```bash
uv run pytest tests/hmi/pages/test_multi_trend_page.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'smart_pid_hmi.pages.multi_trend_page'`

- [ ] **Step 9.3: Write minimal implementation**

```python
# packages/smart_pid_hmi/src/smart_pid_hmi/pages/multi_trend_page.py
"""MultiTrendPage — 2x2 pyqtgraph grid with time-synchronized trends."""
from __future__ import annotations

from typing import TYPE_CHECKING

import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from smart_pid_hmi.themes.base import ThemeBase

_TIME_RANGES = {
    "1m": 60,
    "5m": 300,
    "15m": 900,
    "1h": 3600,
}

_GRID_ROWS = 2
_GRID_COLS = 2
_NUM_PLOTS = _GRID_ROWS * _GRID_COLS


class MultiTrendPage(QWidget):
    """2x2 grid of time-synchronized pyqtgraph trend charts."""

    def __init__(
        self,
        theme: ThemeBase,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._theme = theme
        self._live_mode: bool = True

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Title row
        title = QLabel("Multi-Trend Analysis")
        title.setStyleSheet(
            f"font-size: {theme.font_size_title}px; font-weight: bold; "
            f"color: {theme.fg_primary};"
        )
        layout.addWidget(title)

        # Controls row: time range + live toggle
        ctrl_row = QHBoxLayout()
        ctrl_row.setSpacing(8)

        ctrl_row.addWidget(QLabel("Time Range:"))
        self._time_range_combo = QComboBox()
        self._time_range_combo.addItems(list(_TIME_RANGES.keys()))
        self._time_range_combo.setCurrentText("5m")
        ctrl_row.addWidget(self._time_range_combo)

        self._live_btn = QPushButton("Live: ON")
        self._live_btn.setCheckable(True)
        self._live_btn.setChecked(True)
        self._live_btn.clicked.connect(self._toggle_live)
        ctrl_row.addWidget(self._live_btn)

        ctrl_row.addStretch()
        layout.addLayout(ctrl_row)

        # Loop selectors row (one per plot)
        selector_row = QHBoxLayout()
        selector_row.setSpacing(8)
        self._loop_selectors: list[QComboBox] = []
        for i in range(_NUM_PLOTS):
            combo = QComboBox()
            combo.addItem("(none)", None)
            self._loop_selectors.append(combo)
            group = QHBoxLayout()
            group.addWidget(QLabel(f"Plot {i + 1}:"))
            group.addWidget(combo, stretch=1)
            selector_row.addLayout(group)
        layout.addLayout(selector_row)

        # 2x2 Plot grid
        plot_grid = QGridLayout()
        plot_grid.setSpacing(4)
        self._plots: list[pg.PlotWidget] = []
        self._pv_curves: list[pg.PlotDataItem] = []
        self._sp_curves: list[pg.PlotDataItem] = []
        self._co_views: list[pg.ViewBox] = []
        self._co_curves: list[pg.PlotCurveItem] = []

        palette = getattr(theme, "chart_palette", None) or [
            theme.chart_pv, theme.chart_sp, theme.chart_co, theme.fg_secondary,
        ]

        for idx in range(_NUM_PLOTS):
            row = idx // _GRID_COLS
            col = idx % _GRID_COLS

            pw = pg.PlotWidget()
            pw.setBackground(theme.chart_bg)
            pw.getAxis("bottom").setPen(theme.fg_primary)
            pw.getAxis("left").setPen(theme.fg_primary)
            pw.showGrid(x=True, y=True, alpha=0.3)
            pw.setLabel("bottom", "Time (s)")

            pv_curve = pw.plot(
                pen=pg.mkPen(color=palette[0 % len(palette)], width=2),
                name="PV",
            )
            sp_curve = pw.plot(
                pen=pg.mkPen(
                    color=palette[1 % len(palette)], width=1,
                    style=Qt.PenStyle.DashLine,
                ),
                name="SP",
            )

            # Y2 axis for CO
            y2 = pg.ViewBox()
            pw.scene().addItem(y2)
            pw.getAxis("right").linkToView(y2)
            y2.setXLink(pw)
            pw.showAxis("right")

            co_curve = pg.PlotCurveItem(
                pen=pg.mkPen(color=palette[2 % len(palette)], width=1),
            )
            y2.addItem(co_curve)

            self._plots.append(pw)
            self._pv_curves.append(pv_curve)
            self._sp_curves.append(sp_curve)
            self._co_views.append(y2)
            self._co_curves.append(co_curve)

            plot_grid.addWidget(pw, row, col)

        layout.addLayout(plot_grid, stretch=1)

        # Time-synchronize all plots via X-range linking
        self._link_x_ranges()

    def _link_x_ranges(self) -> None:
        """Link X-axis ranges of all plots to the first plot."""
        if len(self._plots) < 2:
            return
        master = self._plots[0]
        for pw in self._plots[1:]:
            pw.setXLink(master)

    def _toggle_live(self) -> None:
        self._live_mode = self._live_btn.isChecked()
        self._live_btn.setText(f"Live: {'ON' if self._live_mode else 'OFF'}")

    def set_live_mode(self, enabled: bool) -> None:
        self._live_mode = enabled
        self._live_btn.setChecked(enabled)
        self._live_btn.setText(f"Live: {'ON' if enabled else 'OFF'}")

    def populate_controllers(self, controllers: list[dict]) -> None:
        """Populate all loop selector combos with controller list."""
        for combo in self._loop_selectors:
            combo.clear()
            combo.addItem("(none)", None)
            for ctrl in controllers:
                combo.addItem(ctrl["name"], ctrl["id"])

    def update_plot_data(
        self,
        plot_index: int,
        times: list[float],
        pvs: list[float],
        sps: list[float],
        cos: list[float],
    ) -> None:
        """Update a specific plot (0-3) with new data arrays."""
        if plot_index < 0 or plot_index >= _NUM_PLOTS:
            return
        self._pv_curves[plot_index].setData(times, pvs)
        self._sp_curves[plot_index].setData(times, sps)
        self._co_curves[plot_index].setData(times, cos)

    def get_selected_controller(self, plot_index: int) -> int | None:
        """Return the selected controller ID for a plot, or None."""
        if plot_index < 0 or plot_index >= _NUM_PLOTS:
            return None
        data = self._loop_selectors[plot_index].currentData()
        return data if isinstance(data, int) else None

    def get_time_range_seconds(self) -> int:
        """Return the selected time range in seconds."""
        text = self._time_range_combo.currentText()
        return _TIME_RANGES.get(text, 300)
```

- [ ] **Step 9.4: Run test to verify it passes**

```bash
uv run pytest tests/hmi/pages/test_multi_trend_page.py -v
```
Expected: 6 PASSED

- [ ] **Step 9.5: Commit**

```bash
git add packages/smart_pid_hmi/src/smart_pid_hmi/pages/multi_trend_page.py \
       tests/hmi/pages/test_multi_trend_page.py
git commit -m "feat(hmi): add MultiTrendPage with 2x2 pyqtgraph grid + time sync"
```

---

## Task 10: SettingsPage

**Files:**
- Create: `packages/smart_pid_hmi/src/smart_pid_hmi/pages/settings_page.py`
- Create: `tests/hmi/pages/test_settings_page.py`

- [ ] **Step 10.1: Write the failing test**

```python
# tests/hmi/pages/test_settings_page.py
"""Tests for SettingsPage."""
import json

import pytest

from smart_pid_hmi.pages.settings_page import SettingsPage
from smart_pid_hmi.themes.isa101 import ISA101Theme


@pytest.fixture
def theme():
    return ISA101Theme()


def test_creation(qtbot, theme):
    page = SettingsPage(theme=theme, available_themes=["isa101", "dark_room", "md3_dark"])
    qtbot.addWidget(page)
    assert page._theme_radios is not None
    assert len(page._theme_radios) == 3


def test_current_theme_selection(qtbot, theme):
    page = SettingsPage(
        theme=theme,
        available_themes=["isa101", "dark_room", "md3_dark"],
        current_theme="dark_room",
    )
    qtbot.addWidget(page)
    assert page._theme_radios["dark_room"].isChecked()


def test_theme_changed_signal(qtbot, theme):
    page = SettingsPage(
        theme=theme,
        available_themes=["isa101", "dark_room", "md3_dark"],
        current_theme="isa101",
    )
    qtbot.addWidget(page)

    with qtbot.waitSignal(page.theme_selected, timeout=1000) as blocker:
        page._theme_radios["dark_room"].setChecked(True)
    assert blocker.args == ["dark_room"]


def test_refresh_rate_slider(qtbot, theme):
    page = SettingsPage(theme=theme, available_themes=["isa101"])
    qtbot.addWidget(page)
    assert page._refresh_slider is not None
    page._refresh_slider.setValue(5)
    assert page._refresh_slider.value() == 5


def test_export_format_selector(qtbot, theme):
    page = SettingsPage(theme=theme, available_themes=["isa101"])
    qtbot.addWidget(page)
    assert page._format_combo is not None
    formats = [
        page._format_combo.itemText(i)
        for i in range(page._format_combo.count())
    ]
    assert "CSV" in formats
    assert "XLSX" in formats


def test_save_settings(qtbot, theme, tmp_path):
    settings_file = tmp_path / "settings.json"
    page = SettingsPage(
        theme=theme,
        available_themes=["isa101", "dark_room"],
        current_theme="isa101",
        settings_path=str(settings_file),
    )
    qtbot.addWidget(page)
    page._refresh_slider.setValue(10)
    page._format_combo.setCurrentText("XLSX")
    page.save_settings()

    data = json.loads(settings_file.read_text())
    assert data["theme"] == "isa101"
    assert data["refresh_rate_s"] == 10
    assert data["export_format"] == "XLSX"


def test_load_settings(qtbot, theme, tmp_path):
    settings_file = tmp_path / "settings.json"
    settings_file.write_text(json.dumps({
        "theme": "dark_room",
        "refresh_rate_s": 15,
        "export_format": "CSV",
    }))
    page = SettingsPage(
        theme=theme,
        available_themes=["isa101", "dark_room"],
        settings_path=str(settings_file),
    )
    qtbot.addWidget(page)
    page.load_settings()
    assert page._theme_radios["dark_room"].isChecked()
    assert page._refresh_slider.value() == 15
    assert page._format_combo.currentText() == "CSV"
```

- [ ] **Step 10.2: Run test to verify it fails**

```bash
uv run pytest tests/hmi/pages/test_settings_page.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'smart_pid_hmi.pages.settings_page'`

- [ ] **Step 10.3: Write minimal implementation**

```python
# packages/smart_pid_hmi/src/smart_pid_hmi/pages/settings_page.py
"""SettingsPage — theme picker, refresh rate, default export format."""
from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from PySide6.QtCore import Qt

    from smart_pid_hmi.themes.base import ThemeBase

_DEFAULT_SETTINGS_PATH = str(Path.home() / ".smartpid" / "settings.json")
_EXPORT_FORMATS = ["CSV", "XLSX"]


class SettingsPage(QWidget):
    """Application settings: theme, refresh rate, export format."""

    theme_selected = Signal(str)  # emits theme name

    def __init__(
        self,
        theme: ThemeBase,
        available_themes: list[str],
        current_theme: str = "",
        settings_path: str = _DEFAULT_SETTINGS_PATH,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._theme = theme
        self._settings_path = settings_path

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Title
        title = QLabel("Settings")
        title.setStyleSheet(
            f"font-size: {theme.font_size_title}px; font-weight: bold; "
            f"color: {theme.fg_primary};"
        )
        layout.addWidget(title)

        # Theme selector
        theme_group = QGroupBox("Theme")
        theme_layout = QVBoxLayout(theme_group)
        self._theme_btn_group = QButtonGroup(self)
        self._theme_radios: dict[str, QRadioButton] = {}

        for name in available_themes:
            radio = QRadioButton(name)
            radio.setStyleSheet(f"color: {theme.fg_primary};")
            self._theme_btn_group.addButton(radio)
            self._theme_radios[name] = radio
            theme_layout.addWidget(radio)
            if name == current_theme:
                radio.setChecked(True)

        self._theme_btn_group.buttonClicked.connect(self._on_theme_radio_clicked)
        layout.addWidget(theme_group)

        # Refresh rate
        refresh_group = QGroupBox("Dashboard Refresh Rate")
        refresh_layout = QHBoxLayout(refresh_group)
        refresh_layout.addWidget(QLabel("Seconds:"))
        self._refresh_slider = QSlider()
        self._refresh_slider.setOrientation(
            __import__("PySide6.QtCore", fromlist=["Qt"]).Qt.Orientation.Horizontal
        )
        self._refresh_slider.setRange(1, 30)
        self._refresh_slider.setValue(5)
        self._refresh_slider.setTickInterval(5)
        refresh_layout.addWidget(self._refresh_slider, stretch=1)
        self._refresh_value_label = QLabel("5s")
        self._refresh_slider.valueChanged.connect(
            lambda v: self._refresh_value_label.setText(f"{v}s")
        )
        refresh_layout.addWidget(self._refresh_value_label)
        layout.addWidget(refresh_group)

        # Export format
        format_group = QGroupBox("Default Export Format")
        format_layout = QHBoxLayout(format_group)
        format_layout.addWidget(QLabel("Format:"))
        self._format_combo = QComboBox()
        self._format_combo.addItems(_EXPORT_FORMATS)
        format_layout.addWidget(self._format_combo, stretch=1)
        layout.addWidget(format_group)

        # Save button
        save_btn = QPushButton("Save Settings")
        save_btn.clicked.connect(self.save_settings)
        layout.addWidget(save_btn)

        layout.addStretch()

    def _on_theme_radio_clicked(self, button: QRadioButton) -> None:
        self.theme_selected.emit(button.text())

    def save_settings(self) -> None:
        """Persist settings to JSON file."""
        current = ""
        for name, radio in self._theme_radios.items():
            if radio.isChecked():
                current = name
                break

        data = {
            "theme": current,
            "refresh_rate_s": self._refresh_slider.value(),
            "export_format": self._format_combo.currentText(),
        }

        path = Path(self._settings_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2))

    def load_settings(self) -> None:
        """Load settings from JSON file if it exists."""
        path = Path(self._settings_path)
        if not path.exists():
            return

        try:
            data = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            return

        theme_name = data.get("theme", "")
        if theme_name in self._theme_radios:
            self._theme_radios[theme_name].setChecked(True)

        refresh = data.get("refresh_rate_s")
        if isinstance(refresh, int):
            self._refresh_slider.setValue(refresh)

        fmt = data.get("export_format", "")
        idx = self._format_combo.findText(fmt)
        if idx >= 0:
            self._format_combo.setCurrentIndex(idx)
```

- [ ] **Step 10.4: Run test to verify it passes**

```bash
uv run pytest tests/hmi/pages/test_settings_page.py -v
```
Expected: 7 PASSED

- [ ] **Step 10.5: Commit**

```bash
git add packages/smart_pid_hmi/src/smart_pid_hmi/pages/settings_page.py \
       tests/hmi/pages/test_settings_page.py
git commit -m "feat(hmi): add SettingsPage with theme picker, refresh rate, export format"
```

---

## Task 11: Export DTOs + Router + Worker (Backend)

**Files:**
- Create: `packages/smart_pid_domain/src/smart_pid_domain/dtos/export.py`
- Modify: `packages/smart_pid_domain/src/smart_pid_domain/dtos/__init__.py`
- Create: `packages/smart_pid_core/src/smart_pid_core/application/export_worker.py`
- Create: `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/export.py`
- Modify: `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/app.py`
- Modify: `packages/smart_pid_core/pyproject.toml`
- Create: `tests/core/unit/test_export_worker.py`
- Create: `tests/core/integration/test_api_export.py`

### Sub-step 11a: Export DTOs

- [ ] **Step 11a.1: Write the failing test**

```python
# tests/core/unit/test_export_worker.py (DTOs section)
"""Tests for export DTOs and worker."""
from smart_pid_domain.dtos.export import ExportFormat, ExportRequest, ExportStatusResponse


def test_export_request_defaults():
    req = ExportRequest(
        controller_id=1,
        start="2026-04-03T00:00:00Z",
        end="2026-04-03T12:00:00Z",
    )
    assert req.format == ExportFormat.CSV
    assert req.controller_id == 1


def test_export_request_xlsx():
    req = ExportRequest(
        controller_id=1,
        start="2026-04-03T00:00:00Z",
        end="2026-04-03T12:00:00Z",
        format=ExportFormat.XLSX,
    )
    assert req.format == ExportFormat.XLSX


def test_export_status_response():
    resp = ExportStatusResponse(
        export_id="abc123",
        status="completed",
        progress=100,
        filename="export_1.csv",
    )
    assert resp.export_id == "abc123"
    assert resp.status == "completed"
    assert resp.progress == 100
```

- [ ] **Step 11a.2: Run test to verify it fails**

```bash
uv run pytest tests/core/unit/test_export_worker.py::test_export_request_defaults -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'smart_pid_domain.dtos.export'`

- [ ] **Step 11a.3: Write minimal implementation**

```python
# packages/smart_pid_domain/src/smart_pid_domain/dtos/export.py
"""Export request/response DTOs."""
from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel


class ExportFormat(StrEnum):
    CSV = "CSV"
    XLSX = "XLSX"


class ExportRequest(BaseModel):
    controller_id: int
    start: str
    end: str
    format: ExportFormat = ExportFormat.CSV


class ExportStatusResponse(BaseModel):
    export_id: str
    status: str  # "pending", "running", "completed", "failed"
    progress: int = 0  # 0-100
    filename: str | None = None
    error: str | None = None
```

Update `packages/smart_pid_domain/src/smart_pid_domain/dtos/__init__.py` — add:

```python
from smart_pid_domain.dtos.export import ExportFormat, ExportRequest, ExportStatusResponse
```

And add to `__all__`:

```python
    "ExportFormat",
    "ExportRequest",
    "ExportStatusResponse",
```

- [ ] **Step 11a.4: Run test to verify it passes**

```bash
uv run pytest tests/core/unit/test_export_worker.py -v
```
Expected: 3 PASSED

- [ ] **Step 11a.5: Commit**

```bash
git add packages/smart_pid_domain/src/smart_pid_domain/dtos/export.py \
       packages/smart_pid_domain/src/smart_pid_domain/dtos/__init__.py \
       tests/core/unit/test_export_worker.py
git commit -m "feat(domain): add ExportFormat, ExportRequest, ExportStatusResponse DTOs"
```

### Sub-step 11b: Export Worker

- [ ] **Step 11b.1: Write the failing test**

```python
# tests/core/unit/test_export_worker.py (append)
import csv
import io
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from smart_pid_core.application.export_worker import ExportJob, ExportWorker


def test_export_job_creation():
    job = ExportJob(
        export_id="test-001",
        controller_id=1,
        start="2026-04-03T00:00:00Z",
        end="2026-04-03T12:00:00Z",
        format="CSV",
    )
    assert job.export_id == "test-001"
    assert job.status == "pending"
    assert job.progress == 0


@pytest.mark.asyncio
async def test_export_worker_csv(tmp_path):
    frames = [
        {"timestamp": "2026-04-03T10:00:00Z", "pv": 45.0, "sp": 50.0,
         "co": 62.0, "mode": "AUTO", "status": "GOOD"},
        {"timestamp": "2026-04-03T10:00:01Z", "pv": 46.0, "sp": 50.0,
         "co": 63.0, "mode": "AUTO", "status": "GOOD"},
    ]
    historian = AsyncMock()
    historian.query.return_value = [
        type("Frame", (), f)() for f in frames
    ]

    worker = ExportWorker(output_dir=tmp_path, historian=historian)
    job = ExportJob(
        export_id="test-csv",
        controller_id=1,
        start="2026-04-03T10:00:00Z",
        end="2026-04-03T10:00:02Z",
        format="CSV",
    )
    await worker.run_export(job)

    assert job.status == "completed"
    assert job.progress == 100
    assert job.filename is not None
    out_file = tmp_path / job.filename
    assert out_file.exists()

    content = out_file.read_text()
    reader = csv.reader(io.StringIO(content))
    rows = list(reader)
    assert rows[0] == ["timestamp", "pv", "sp", "co", "mode", "status"]
    assert len(rows) == 3  # header + 2 data rows


@pytest.mark.asyncio
async def test_export_worker_xlsx(tmp_path):
    frames = [
        {"timestamp": "2026-04-03T10:00:00Z", "pv": 45.0, "sp": 50.0,
         "co": 62.0, "mode": "AUTO", "status": "GOOD"},
    ]
    historian = AsyncMock()
    historian.query.return_value = [
        type("Frame", (), f)() for f in frames
    ]

    worker = ExportWorker(output_dir=tmp_path, historian=historian)
    job = ExportJob(
        export_id="test-xlsx",
        controller_id=1,
        start="2026-04-03T10:00:00Z",
        end="2026-04-03T10:00:01Z",
        format="XLSX",
    )
    await worker.run_export(job)

    assert job.status == "completed"
    assert job.filename is not None
    assert job.filename.endswith(".xlsx")
    out_file = tmp_path / job.filename
    assert out_file.exists()
    assert out_file.stat().st_size > 0
```

- [ ] **Step 11b.2: Run test to verify it fails**

```bash
uv run pytest tests/core/unit/test_export_worker.py::test_export_worker_csv -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'smart_pid_core.application.export_worker'`

- [ ] **Step 11b.3: Add openpyxl dependency**

Add `"openpyxl>=3.1"` to `packages/smart_pid_core/pyproject.toml` dependencies:

```toml
dependencies = [
    "smart-pid-domain",
    "pyzmq>=26.0",
    "msgpack>=1.0",
    "aiosqlite>=0.20",
    "pydantic-settings>=2.3",
    "structlog>=24.0",
    "numpy>=2.0",
    "scipy>=1.11",
    "asyncua>=1.1",
    "fastapi>=0.115",
    "uvicorn[standard]>=0.34",
    "pyjwt>=2.9",
    "bcrypt>=4.2",
    "openpyxl>=3.1",
]
```

Run: `uv sync --all-packages`

- [ ] **Step 11b.4: Write minimal implementation**

```python
# packages/smart_pid_core/src/smart_pid_core/application/export_worker.py
"""Export worker — generates CSV/XLSX files from historian data."""
from __future__ import annotations

import csv
import uuid
from dataclasses import dataclass, field
from datetime import datetime, fromisoformat
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from smart_pid_core.adapters.outbound.historian import SQLiteHistorian

_COLUMNS = ["timestamp", "pv", "sp", "co", "mode", "status"]


@dataclass
class ExportJob:
    """Mutable state for an export job."""

    export_id: str
    controller_id: int
    start: str
    end: str
    format: str  # "CSV" or "XLSX"
    status: str = "pending"
    progress: int = 0
    filename: str | None = None
    error: str | None = None


class ExportWorker:
    """Generates CSV or XLSX export files from historian data."""

    def __init__(
        self,
        output_dir: Path,
        historian: SQLiteHistorian,
    ) -> None:
        self._output_dir = output_dir
        self._historian = historian
        self._jobs: dict[str, ExportJob] = {}

    def create_job(
        self,
        controller_id: int,
        start: str,
        end: str,
        fmt: str = "CSV",
    ) -> ExportJob:
        """Create and register a new export job."""
        export_id = uuid.uuid4().hex[:12]
        job = ExportJob(
            export_id=export_id,
            controller_id=controller_id,
            start=start,
            end=end,
            format=fmt,
        )
        self._jobs[export_id] = job
        return job

    def get_job(self, export_id: str) -> ExportJob | None:
        return self._jobs.get(export_id)

    async def run_export(self, job: ExportJob) -> None:
        """Execute the export job (query historian, write file)."""
        job.status = "running"
        job.progress = 10

        try:
            start_dt = fromisoformat(job.start)
            end_dt = fromisoformat(job.end)

            frames = await self._historian.query(
                job.controller_id, start_dt, end_dt,
            )
            job.progress = 50

            rows = []
            for f in frames:
                rows.append({
                    "timestamp": str(getattr(f, "timestamp", "")),
                    "pv": getattr(f, "pv", 0.0),
                    "sp": getattr(f, "sp", 0.0),
                    "co": getattr(f, "co", 0.0),
                    "mode": getattr(f, "mode", ""),
                    "status": str(getattr(f, "status", "")),
                })

            self._output_dir.mkdir(parents=True, exist_ok=True)

            if job.format == "XLSX":
                filename = f"export_{job.export_id}.xlsx"
                self._write_xlsx(self._output_dir / filename, rows)
            else:
                filename = f"export_{job.export_id}.csv"
                self._write_csv(self._output_dir / filename, rows)

            job.filename = filename
            job.progress = 100
            job.status = "completed"

        except Exception as e:
            job.status = "failed"
            job.error = str(e)

    def _write_csv(self, path: Path, rows: list[dict]) -> None:
        with open(path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=_COLUMNS)
            writer.writeheader()
            writer.writerows(rows)

    def _write_xlsx(self, path: Path, rows: list[dict]) -> None:
        from openpyxl import Workbook

        wb = Workbook()
        ws = wb.active
        ws.title = "Telemetry Export"

        # Header
        ws.append(_COLUMNS)

        # Data
        for row in rows:
            ws.append([row[col] for col in _COLUMNS])

        wb.save(str(path))

    def get_file_path(self, export_id: str) -> Path | None:
        job = self._jobs.get(export_id)
        if job is None or job.filename is None:
            return None
        return self._output_dir / job.filename
```

- [ ] **Step 11b.5: Run test to verify it passes**

```bash
uv run pytest tests/core/unit/test_export_worker.py -v
```
Expected: 6 PASSED (3 DTO + 3 worker)

- [ ] **Step 11b.6: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/application/export_worker.py \
       packages/smart_pid_core/pyproject.toml \
       tests/core/unit/test_export_worker.py
git commit -m "feat(core): add ExportWorker with CSV/XLSX generation + openpyxl dependency"
```

### Sub-step 11c: Export Router

- [ ] **Step 11c.1: Write the failing test**

```python
# tests/core/integration/test_api_export.py
"""Integration tests for Export REST API."""
from __future__ import annotations

import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from smart_pid_core.adapters.inbound.api.app import create_app
from smart_pid_core.adapters.inbound.api.auth import create_access_token, hash_password
from smart_pid_core.adapters.outbound.historian import SQLiteHistorian
from smart_pid_core.adapters.outbound.sqlite_repo import SQLiteRepository
from smart_pid_core.adapters.outbound.user_repo import UserRepository
from smart_pid_core.application.event_bus import EventBus
from smart_pid_core.application.export_worker import ExportJob, ExportWorker
from smart_pid_core.application.loop_manager import LoopManager
from smart_pid_core.config import CoreSettings


@pytest.fixture
async def export_client(tmp_path):
    db_path = tmp_path / "test.spid"
    repo = SQLiteRepository(db_path)
    await repo.initialize()
    historian = SQLiteHistorian(repo.db)
    user_repo = UserRepository(repo.db)
    bus = EventBus(url_prefix=f"inproc://test_{uuid.uuid4().hex[:8]}")
    bus.start()
    loop_manager = LoopManager(bus=bus)
    settings = CoreSettings(
        jwt_secret="test-secret-key-minimum-32-bytes!",  # type: ignore[call-arg]
    )
    admin_hash = hash_password("admin")
    await user_repo.create("admin", admin_hash, "admin")

    export_worker = ExportWorker(output_dir=tmp_path / "exports", historian=historian)

    app = create_app(
        repo=repo, historian=historian, user_repo=user_repo,
        loop_manager=loop_manager, settings=settings,
        export_worker=export_worker,
    )
    token = create_access_token(
        user_id=1, username="admin", role="admin", secret=settings.jwt_secret,
    )
    headers = {"Authorization": f"Bearer {token}"}
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c, headers, export_worker
    loop_manager.stop_all()
    bus.stop()


class TestExportAPI:
    @pytest.mark.asyncio
    async def test_create_export(self, export_client):
        client, headers, _ = export_client
        resp = await client.post(
            "/export",
            json={
                "controller_id": 1,
                "start": "2026-04-03T00:00:00Z",
                "end": "2026-04-03T12:00:00Z",
                "format": "CSV",
            },
            headers=headers,
        )
        assert resp.status_code == 202
        data = resp.json()
        assert "export_id" in data
        assert data["status"] == "pending"

    @pytest.mark.asyncio
    async def test_get_export_status(self, export_client):
        client, headers, worker = export_client
        # Create a job manually
        job = worker.create_job(1, "2026-04-03T00:00:00Z", "2026-04-03T12:00:00Z")
        resp = await client.get(f"/export/{job.export_id}/status", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["export_id"] == job.export_id

    @pytest.mark.asyncio
    async def test_get_export_status_not_found(self, export_client):
        client, headers, _ = export_client
        resp = await client.get("/export/nonexistent/status", headers=headers)
        assert resp.status_code == 404
```

- [ ] **Step 11c.2: Run test to verify it fails**

```bash
uv run pytest tests/core/integration/test_api_export.py -v
```
Expected: FAIL — router not registered, or import error

- [ ] **Step 11c.3: Write minimal implementation**

```python
# packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/export.py
"""Export router — create, status, download export files."""
from __future__ import annotations

import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse

from smart_pid_core.adapters.inbound.api.dependencies import (
    get_export_worker,
    require_operator,
)
from smart_pid_domain.dtos.auth import UserClaims  # noqa: TC001
from smart_pid_domain.dtos.export import ExportRequest, ExportStatusResponse

router = APIRouter()


@router.post("", status_code=status.HTTP_202_ACCEPTED, response_model=ExportStatusResponse)
async def create_export(
    request: ExportRequest,
    _user: Annotated[UserClaims, Depends(require_operator)],
    export_worker: Annotated[object, Depends(get_export_worker)],
) -> ExportStatusResponse:
    job = export_worker.create_job(
        controller_id=request.controller_id,
        start=request.start,
        end=request.end,
        fmt=request.format.value,
    )
    # Run export in background
    asyncio.create_task(_run_export(export_worker, job))
    return ExportStatusResponse(
        export_id=job.export_id,
        status=job.status,
        progress=job.progress,
    )


async def _run_export(worker, job) -> None:
    """Background task to run the export."""
    await worker.run_export(job)


@router.get("/{export_id}/status", response_model=ExportStatusResponse)
async def get_export_status(
    export_id: str,
    _user: Annotated[UserClaims, Depends(require_operator)],
    export_worker: Annotated[object, Depends(get_export_worker)],
) -> ExportStatusResponse:
    job = export_worker.get_job(export_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Export {export_id} not found",
        )
    return ExportStatusResponse(
        export_id=job.export_id,
        status=job.status,
        progress=job.progress,
        filename=job.filename,
        error=job.error,
    )


@router.get("/{export_id}/download")
async def download_export(
    export_id: str,
    _user: Annotated[UserClaims, Depends(require_operator)],
    export_worker: Annotated[object, Depends(get_export_worker)],
) -> FileResponse:
    job = export_worker.get_job(export_id)
    if job is None or job.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Export {export_id} not available for download",
        )
    file_path = export_worker.get_file_path(export_id)
    if file_path is None or not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Export file not found on disk",
        )
    media = "text/csv" if job.format == "CSV" else (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    return FileResponse(
        path=str(file_path),
        media_type=media,
        filename=job.filename,
    )
```

Add the dependency function. In `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/dependencies.py`, add:

```python
def get_export_worker(request: Request):
    return request.app.state.export_worker
```

Update `app.py` — add import and register router:

```python
from smart_pid_core.adapters.inbound.api.routers import (
    ...,
    export,
)
```

In `create_app()`, add parameter and state:

```python
def create_app(
    *,
    repo: SQLiteRepository,
    historian: SQLiteHistorian,
    user_repo: UserRepository,
    loop_manager: LoopManager,
    settings: CoreSettings,
    simulator_adapter=None,
    opcua_adapter=None,
    stats_workers=None,
    ai_workers=None,
    ai_repo=None,
    alarm_repo: AlarmRepository | None = None,
    audit_repo: AuditRepository | None = None,
    export_worker=None,
) -> FastAPI:
```

Add to app.state:

```python
    app.state.export_worker = export_worker
```

Register the router:

```python
    app.include_router(export.router, prefix="/export", tags=["export"])
```

- [ ] **Step 11c.4: Run test to verify it passes**

```bash
uv run pytest tests/core/integration/test_api_export.py -v
```
Expected: 3 PASSED

- [ ] **Step 11c.5: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/export.py \
       packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/app.py \
       packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/dependencies.py \
       tests/core/integration/test_api_export.py
git commit -m "feat(core): add export REST endpoints (POST/GET status/download)"
```

---

## Task 12: APIClient export methods

**Files:**
- Modify: `packages/smart_pid_hmi/src/smart_pid_hmi/services/api_client.py`
- Modify: `tests/hmi/services/test_api_client.py`

- [ ] **Step 12.1: Write the failing test**

```python
# tests/hmi/services/test_api_client.py (append)

def test_request_export():
    data = {"export_id": "abc123", "status": "pending", "progress": 0}
    transport = _mock_transport(202, data)
    session = Session()
    client = APIClient(base_url="http://test:8000", session=session, transport=transport)
    result = client.request_export(1, "2026-04-03T00:00:00Z", "2026-04-03T12:00:00Z", "CSV")
    assert result["export_id"] == "abc123"
    assert result["status"] == "pending"


def test_get_export_status():
    data = {
        "export_id": "abc123", "status": "completed",
        "progress": 100, "filename": "export_abc123.csv",
    }
    transport = _mock_transport(200, data)
    session = Session()
    client = APIClient(base_url="http://test:8000", session=session, transport=transport)
    result = client.get_export_status("abc123")
    assert result["status"] == "completed"
    assert result["filename"] == "export_abc123.csv"


def test_download_export():
    """download_export returns raw bytes."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"col1,col2\n1,2\n")

    transport = httpx.MockTransport(handler)
    session = Session()
    client = APIClient(base_url="http://test:8000", session=session, transport=transport)
    content = client.download_export("abc123")
    assert b"col1,col2" in content
```

- [ ] **Step 12.2: Run test to verify it fails**

```bash
uv run pytest tests/hmi/services/test_api_client.py::test_request_export -v
```
Expected: FAIL — `AttributeError: 'APIClient' object has no attribute 'request_export'`

- [ ] **Step 12.3: Write minimal implementation**

Add these methods to `packages/smart_pid_hmi/src/smart_pid_hmi/services/api_client.py`:

```python
    def request_export(
        self,
        controller_id: int,
        start: str,
        end: str,
        fmt: str = "CSV",
    ) -> dict:
        resp = self._http.post(
            "/export",
            json={
                "controller_id": controller_id,
                "start": start,
                "end": end,
                "format": fmt,
            },
            headers=self._headers(),
        )
        resp.raise_for_status()
        return resp.json()

    def get_export_status(self, export_id: str) -> dict:
        resp = self._http.get(
            f"/export/{export_id}/status",
            headers=self._headers(),
        )
        resp.raise_for_status()
        return resp.json()

    def download_export(self, export_id: str) -> bytes:
        resp = self._http.get(
            f"/export/{export_id}/download",
            headers=self._headers(),
        )
        resp.raise_for_status()
        return resp.content
```

- [ ] **Step 12.4: Run test to verify it passes**

```bash
uv run pytest tests/hmi/services/test_api_client.py -v
```
Expected: All PASSED (existing + 3 new)

- [ ] **Step 12.5: Commit**

```bash
git add packages/smart_pid_hmi/src/smart_pid_hmi/services/api_client.py \
       tests/hmi/services/test_api_client.py
git commit -m "feat(hmi): add request_export, get_export_status, download_export to APIClient"
```

---

## Task 13: SVG Overlay Widget

**Files:**
- Create: `packages/smart_pid_hmi/src/smart_pid_hmi/widgets/svg_overlay.py`
- Create: `tests/hmi/widgets/test_svg_overlay.py`

- [ ] **Step 13.1: Write the failing test**

```python
# tests/hmi/widgets/test_svg_overlay.py
"""Tests for SVGOverlayWidget."""
import pytest

from smart_pid_hmi.themes.isa101 import ISA101Theme
from smart_pid_hmi.widgets.svg_overlay import SVGOverlayWidget


@pytest.fixture
def theme():
    return ISA101Theme()


@pytest.fixture
def sample_svg(tmp_path):
    svg_content = """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="400" height="300" viewBox="0 0 400 300">
  <rect width="400" height="300" fill="#333"/>
  <circle cx="100" cy="150" r="20" fill="#666" id="valve1"/>
  <circle cx="300" cy="150" r="20" fill="#666" id="valve2"/>
</svg>"""
    path = tmp_path / "test.svg"
    path.write_text(svg_content)
    return str(path)


def test_creation(qtbot, theme, sample_svg):
    widget = SVGOverlayWidget(theme=theme)
    qtbot.addWidget(widget)
    assert widget is not None


def test_load_svg(qtbot, theme, sample_svg):
    widget = SVGOverlayWidget(theme=theme)
    qtbot.addWidget(widget)
    widget.load_svg(sample_svg)
    assert widget._svg_loaded is True


def test_add_overlay_label(qtbot, theme, sample_svg):
    widget = SVGOverlayWidget(theme=theme)
    qtbot.addWidget(widget)
    widget.load_svg(sample_svg)
    widget.add_overlay("tag1", x=100, y=150, text="FIC-101: 45.2")
    assert "tag1" in widget._overlays


def test_update_overlay(qtbot, theme, sample_svg):
    widget = SVGOverlayWidget(theme=theme)
    qtbot.addWidget(widget)
    widget.load_svg(sample_svg)
    widget.add_overlay("tag1", x=100, y=150, text="FIC-101: 45.2")
    widget.update_overlay("tag1", text="FIC-101: 46.0")
    assert widget._overlays["tag1"].text() == "FIC-101: 46.0"


def test_remove_overlay(qtbot, theme, sample_svg):
    widget = SVGOverlayWidget(theme=theme)
    qtbot.addWidget(widget)
    widget.load_svg(sample_svg)
    widget.add_overlay("tag1", x=100, y=150, text="FIC-101: 45.2")
    widget.remove_overlay("tag1")
    assert "tag1" not in widget._overlays


def test_clear_overlays(qtbot, theme, sample_svg):
    widget = SVGOverlayWidget(theme=theme)
    qtbot.addWidget(widget)
    widget.load_svg(sample_svg)
    widget.add_overlay("tag1", x=100, y=150, text="val1")
    widget.add_overlay("tag2", x=300, y=150, text="val2")
    widget.clear_overlays()
    assert len(widget._overlays) == 0
```

- [ ] **Step 13.2: Run test to verify it fails**

```bash
uv run pytest tests/hmi/widgets/test_svg_overlay.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'smart_pid_hmi.widgets.svg_overlay'`

- [ ] **Step 13.3: Write minimal implementation**

```python
# packages/smart_pid_hmi/src/smart_pid_hmi/widgets/svg_overlay.py
"""SVGOverlayWidget — composites QSvgWidget with positioned QLabel overlays."""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

if TYPE_CHECKING:
    from smart_pid_hmi.themes.base import ThemeBase


class SVGOverlayWidget(QWidget):
    """Widget that displays an SVG P&ID diagram with positioned data labels.

    Overlays are QLabels positioned absolutely over the SVG widget.
    Use add_overlay() to create labels at specific (x, y) positions,
    and update_overlay() to change their text (e.g., live PV values).
    """

    def __init__(
        self,
        theme: ThemeBase,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._theme = theme
        self._svg_loaded: bool = False
        self._overlays: dict[str, QLabel] = {}

        # Use a stacked layout where SVG is the base
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._svg_widget = QSvgWidget()
        layout.addWidget(self._svg_widget)

    def load_svg(self, path: str) -> None:
        """Load an SVG file from disk."""
        svg_path = Path(path)
        if not svg_path.exists():
            return
        self._svg_widget.load(str(svg_path))
        self._svg_loaded = True

    def load_svg_data(self, data: bytes) -> None:
        """Load SVG from raw bytes."""
        self._svg_widget.load(QByteArray(data))
        self._svg_loaded = True

    def add_overlay(
        self,
        tag: str,
        x: int,
        y: int,
        text: str = "",
        color: str | None = None,
    ) -> None:
        """Add a text overlay at position (x, y) relative to the widget."""
        if tag in self._overlays:
            self.remove_overlay(tag)

        label = QLabel(text, self)
        fg = color or self._theme.fg_primary
        label.setStyleSheet(
            f"color: {fg}; background: rgba(0, 0, 0, 180); "
            f"padding: 2px 6px; font-size: {self._theme.font_size_label}px; "
            f"font-family: '{self._theme.font_family}';"
        )
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.move(x, y)
        label.show()
        self._overlays[tag] = label

    def update_overlay(
        self,
        tag: str,
        text: str | None = None,
        color: str | None = None,
    ) -> None:
        """Update an existing overlay's text and/or color."""
        label = self._overlays.get(tag)
        if label is None:
            return
        if text is not None:
            label.setText(text)
        if color is not None:
            label.setStyleSheet(
                f"color: {color}; background: rgba(0, 0, 0, 180); "
                f"padding: 2px 6px; font-size: {self._theme.font_size_label}px; "
                f"font-family: '{self._theme.font_family}';"
            )

    def remove_overlay(self, tag: str) -> None:
        """Remove an overlay by tag name."""
        label = self._overlays.pop(tag, None)
        if label is not None:
            label.deleteLater()

    def clear_overlays(self) -> None:
        """Remove all overlays."""
        for label in self._overlays.values():
            label.deleteLater()
        self._overlays.clear()
```

- [ ] **Step 13.4: Run test to verify it passes**

```bash
uv run pytest tests/hmi/widgets/test_svg_overlay.py -v
```
Expected: 6 PASSED

- [ ] **Step 13.5: Commit**

```bash
git add packages/smart_pid_hmi/src/smart_pid_hmi/widgets/svg_overlay.py \
       tests/hmi/widgets/test_svg_overlay.py
git commit -m "feat(hmi): add SVGOverlayWidget with positioned QLabel overlays"
```

---

## Task 14: MainWindow Wiring — new pages, toolbar, ThemeManager

**Files:**
- Modify: `packages/smart_pid_hmi/src/smart_pid_hmi/main.py`
- Create: `tests/hmi/test_main_window_phase7.py`

- [ ] **Step 14.1: Write the failing test**

```python
# tests/hmi/test_main_window_phase7.py
"""Tests for Phase 7 MainWindow wiring — new pages + ThemeManager."""
from queue import SimpleQueue
from unittest.mock import MagicMock

import pytest

from smart_pid_hmi.bus_bridge import BusBridge
from smart_pid_hmi.config import HMISettings
from smart_pid_hmi.main import MainWindow
from smart_pid_hmi.services.session import Session


@pytest.fixture
def bridge(qtbot):
    q = SimpleQueue()
    b = BusBridge(queue=q, refresh_ms=10)
    yield b
    b.stop()


@pytest.fixture
def main_window(qtbot, bridge):
    settings = HMISettings(mock_mode=True)
    session = Session()
    api_client = MagicMock()
    telemetry_source = MagicMock()
    telemetry_source.queue = SimpleQueue()
    window = MainWindow(
        settings=settings,
        session=session,
        api_client=api_client,
        telemetry_source=telemetry_source,
        bus_bridge=bridge,
    )
    qtbot.addWidget(window)
    return window


def test_has_executive_page(main_window):
    assert main_window._executive_page is not None


def test_has_multi_trend_page(main_window):
    assert main_window._multi_trend_page is not None


def test_has_settings_page(main_window):
    assert main_window._settings_page is not None


def test_has_theme_manager(main_window):
    assert main_window._theme_manager is not None


def test_executive_btn_exists(main_window):
    assert main_window._executive_btn is not None


def test_trends_btn_exists(main_window):
    assert main_window._trends_btn is not None


def test_settings_btn_exists(main_window):
    assert main_window._settings_btn is not None


def test_executive_btn_switches_page(main_window):
    main_window._executive_btn.trigger()
    assert main_window._stack.currentWidget() is main_window._executive_page


def test_trends_btn_switches_page(main_window):
    main_window._trends_btn.trigger()
    assert main_window._stack.currentWidget() is main_window._multi_trend_page


def test_settings_btn_switches_page(main_window):
    main_window._settings_btn.trigger()
    assert main_window._stack.currentWidget() is main_window._settings_page


def test_theme_manager_has_three_themes(main_window):
    themes = main_window._theme_manager.available_themes()
    assert "isa101" in themes
    assert "dark_room" in themes
    assert "md3_dark" in themes
```

- [ ] **Step 14.2: Run test to verify it fails**

```bash
uv run pytest tests/hmi/test_main_window_phase7.py -v
```
Expected: FAIL — `AttributeError: 'MainWindow' object has no attribute '_executive_page'`

- [ ] **Step 14.3: Write minimal implementation**

Replace the content of `packages/smart_pid_hmi/src/smart_pid_hmi/main.py`:

```python
# packages/smart_pid_hmi/src/smart_pid_hmi/main.py
"""Application bootstrap — QApplication, MainWindow, service wiring."""
from __future__ import annotations

import sys
import threading

from PySide6.QtCore import QMetaObject, Qt, Slot
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QMainWindow,
    QStackedWidget,
    QToolBar,
    QWidget,
)

from smart_pid_hmi.bus_bridge import BusBridge
from smart_pid_hmi.config import HMISettings
from smart_pid_hmi.pages.alarm_panel import AlarmPanel
from smart_pid_hmi.pages.connection_page import ConnectionPage
from smart_pid_hmi.pages.dashboard_page import DashboardPage
from smart_pid_hmi.pages.executive_dashboard import ExecutiveDashboardPage
from smart_pid_hmi.pages.multi_trend_page import MultiTrendPage
from smart_pid_hmi.pages.settings_page import SettingsPage
from smart_pid_hmi.pages.simulator_page import SimulatorPage
from smart_pid_hmi.services.session import Session
from smart_pid_hmi.themes.dark_room import DarkRoomTheme
from smart_pid_hmi.themes.isa101 import ISA101Theme
from smart_pid_hmi.themes.manager import ThemeManager
from smart_pid_hmi.themes.md3_dark import MD3DarkTheme


class MainWindow(QMainWindow):
    """Top-level window with page stack and toolbar."""

    def __init__(
        self,
        settings: HMISettings,
        session: Session,
        api_client: object,
        telemetry_source: object,
        bus_bridge: BusBridge,
    ) -> None:
        super().__init__()
        self._settings = settings
        self._session = session
        self._api_client = api_client
        self._telemetry_source = telemetry_source
        self._bus_bridge = bus_bridge
        self._login_error: str = ""
        self._pending_controllers: list[dict] = []

        self.setWindowTitle("Smart PID HMI")
        self.setMinimumSize(1024, 700)

        # Theme Manager
        self._theme_manager = ThemeManager()
        self._theme_manager.register(ISA101Theme())
        self._theme_manager.register(DarkRoomTheme())
        self._theme_manager.register(MD3DarkTheme())
        self._theme_manager.set_theme(settings.theme)
        theme = self._theme_manager.current
        theme.apply(QApplication.instance())

        # Connect theme switch
        self._theme_manager.theme_changed.connect(self._on_theme_changed)

        # Toolbar
        toolbar = QToolBar("Main")
        toolbar.setMovable(False)
        app_label = QLabel("  Smart PID  ")
        app_label.setStyleSheet(
            f"font-weight: bold; font-size: {theme.font_size_title}px; "
            f"color: {theme.fg_primary}; background: transparent;"
        )
        toolbar.addWidget(app_label)
        toolbar.addSeparator()

        self._conn_indicator = QLabel(" \u25cf ")
        self._conn_indicator.setStyleSheet("color: red; background: transparent;")
        toolbar.addWidget(self._conn_indicator)

        self._user_label = QLabel("")
        self._user_label.setStyleSheet(
            f"color: {theme.fg_secondary}; background: transparent; padding-left: 8px;"
        )
        toolbar.addWidget(self._user_label)

        toolbar.addSeparator()
        self._dashboard_btn = toolbar.addAction("Dashboard")
        self._dashboard_btn.triggered.connect(
            lambda: self._stack.setCurrentWidget(self._dashboard_page)
        )
        self._executive_btn = toolbar.addAction("Executive")
        self._executive_btn.triggered.connect(
            lambda: self._stack.setCurrentWidget(self._executive_page)
        )
        self._trends_btn = toolbar.addAction("Trends")
        self._trends_btn.triggered.connect(
            lambda: self._stack.setCurrentWidget(self._multi_trend_page)
        )
        self._simulator_btn = toolbar.addAction("Simulator")
        self._simulator_btn.triggered.connect(
            lambda: self._stack.setCurrentWidget(self._simulator_page)
        )
        self._simulator_btn.setEnabled(False)
        self._alarms_btn = toolbar.addAction("Alarms")
        self._alarms_btn.triggered.connect(
            lambda: self._stack.setCurrentWidget(self._alarm_panel)
        )
        self._settings_btn = toolbar.addAction("Settings")
        self._settings_btn.triggered.connect(
            lambda: self._stack.setCurrentWidget(self._settings_page)
        )

        spacer = QWidget()
        toolbar.addWidget(spacer)
        self.addToolBar(toolbar)

        # Pages
        self._stack = QStackedWidget()
        self.setCentralWidget(self._stack)

        self._connection_page = ConnectionPage(theme=theme, default_url=settings.server_url)
        self._dashboard_page = DashboardPage(theme=theme, bus_bridge=bus_bridge)
        self._executive_page = ExecutiveDashboardPage(theme=theme)
        self._multi_trend_page = MultiTrendPage(theme=theme)
        self._simulator_page = SimulatorPage(theme=theme)
        self._alarm_panel = AlarmPanel(theme=theme)
        self._settings_page = SettingsPage(
            theme=theme,
            available_themes=self._theme_manager.available_themes(),
            current_theme=theme.name,
        )

        self._stack.addWidget(self._connection_page)
        self._stack.addWidget(self._dashboard_page)
        self._stack.addWidget(self._executive_page)
        self._stack.addWidget(self._multi_trend_page)
        self._stack.addWidget(self._simulator_page)
        self._stack.addWidget(self._alarm_panel)
        self._stack.addWidget(self._settings_page)

        # Wire signals
        self._connection_page.login_requested.connect(self._on_login)
        self._dashboard_page.setpoint_requested.connect(self._send_setpoint)
        self._dashboard_page.mode_requested.connect(self._send_mode)
        self._dashboard_page.output_requested.connect(self._send_output)
        bus_bridge.connection_lost.connect(
            lambda: self._conn_indicator.setStyleSheet("color: red; background: transparent;")
        )
        bus_bridge.connection_restored.connect(
            lambda: self._conn_indicator.setStyleSheet("color: green; background: transparent;")
        )
        bus_bridge.alarm_received.connect(self._alarm_panel.on_alarm)
        self._alarm_panel.ack_all_requested.connect(self._send_ack_all)
        self._simulator_page.preset_changed.connect(self._send_sim_preset)
        self._simulator_page.parameters_changed.connect(self._send_sim_parameters)
        self._simulator_page.step_requested.connect(self._send_sim_step)
        self._simulator_page.noise_requested.connect(self._send_sim_noise)
        self._simulator_page.clear_disturbance_requested.connect(self._send_sim_clear)
        self._settings_page.theme_selected.connect(self._on_settings_theme_selected)

    def _on_settings_theme_selected(self, name: str) -> None:
        """Handle theme selection from SettingsPage."""
        try:
            self._theme_manager.set_theme(name)
        except KeyError:
            pass

    def _on_theme_changed(self, name: str) -> None:
        """Apply new theme to entire application."""
        theme = self._theme_manager.current
        app = QApplication.instance()
        if app is not None:
            theme.apply(app)

    def _on_login(self, server_url: str, username: str, password: str) -> None:
        """Handle login in background thread."""
        def do_login():
            try:
                resp = self._api_client.login(username, password)
                self._session.store_token(resp.access_token)
                QMetaObject.invokeMethod(
                    self, "_login_success", Qt.ConnectionType.QueuedConnection,
                )
            except Exception as e:
                self._login_error = str(e)
                QMetaObject.invokeMethod(
                    self, "_login_failed", Qt.ConnectionType.QueuedConnection,
                )

        threading.Thread(target=do_login, daemon=True).start()

    @Slot()
    def _login_success(self) -> None:
        self._conn_indicator.setStyleSheet("color: green; background: transparent;")
        self._user_label.setText(self._session.username or "")
        self._telemetry_source.start()
        self._bus_bridge.start()
        self._load_dashboard()
        self._stack.setCurrentWidget(self._dashboard_page)
        self._check_simulator_available()

    @Slot()
    def _login_failed(self) -> None:
        self._connection_page.show_error(self._login_error or "Login failed")

    def _load_dashboard(self) -> None:
        """Load controllers from API and populate dashboard."""
        def do_load():
            try:
                controllers = self._api_client.list_controllers()
                self._pending_controllers = [c.model_dump() for c in controllers]
                QMetaObject.invokeMethod(
                    self, "_populate_dashboard", Qt.ConnectionType.QueuedConnection,
                )
            except Exception:
                pass

        threading.Thread(target=do_load, daemon=True).start()

    @Slot()
    def _populate_dashboard(self) -> None:
        self._dashboard_page.populate_controllers(self._pending_controllers)
        self._simulator_page.populate_controllers(self._pending_controllers)
        self._multi_trend_page.populate_controllers(self._pending_controllers)

    def _send_setpoint(self, controller_id: int, value: float) -> None:
        threading.Thread(
            target=lambda: self._api_client.set_setpoint(controller_id, value),
            daemon=True,
        ).start()

    def _send_mode(self, controller_id: int, mode: str) -> None:
        threading.Thread(
            target=lambda: self._api_client.set_mode(controller_id, mode),
            daemon=True,
        ).start()

    def _send_output(self, controller_id: int, value: float) -> None:
        threading.Thread(
            target=lambda: self._api_client.set_output(controller_id, value),
            daemon=True,
        ).start()

    def _send_ack_all(self) -> None:
        threading.Thread(
            target=lambda: self._api_client.ack_all_alarms(),
            daemon=True,
        ).start()

    def _check_simulator_available(self) -> None:
        """Check if backend has simulator and enable button if so."""
        def do_check():
            try:
                status = self._api_client.get_simulator_status()
                if status.enabled:
                    QMetaObject.invokeMethod(
                        self, "_enable_simulator", Qt.ConnectionType.QueuedConnection,
                    )
            except Exception:
                pass

        threading.Thread(target=do_check, daemon=True).start()

    @Slot()
    def _enable_simulator(self) -> None:
        self._simulator_btn.setEnabled(True)

    def _send_sim_preset(self, preset: str) -> None:
        cid = self._simulator_page.current_controller_id
        if cid is None:
            return
        threading.Thread(
            target=lambda: self._api_client.set_simulator_preset(cid, preset),
            daemon=True,
        ).start()

    def _send_sim_parameters(
        self, gain: float, tau1: float, tau2: float, dead_time: float,
    ) -> None:
        cid = self._simulator_page.current_controller_id
        if cid is None:
            return
        tau2_val = tau2 if tau2 > 0 else None
        threading.Thread(
            target=lambda: self._api_client.set_simulator_parameters(
                cid, gain, tau1, tau2_val, dead_time,
            ),
            daemon=True,
        ).start()

    def _send_sim_step(self, amplitude: float) -> None:
        cid = self._simulator_page.current_controller_id
        if cid is None:
            return
        threading.Thread(
            target=lambda: self._api_client.inject_simulator_disturbance(cid, "step", amplitude),
            daemon=True,
        ).start()

    def _send_sim_noise(self, amplitude: float) -> None:
        cid = self._simulator_page.current_controller_id
        if cid is None:
            return
        threading.Thread(
            target=lambda: self._api_client.inject_simulator_disturbance(cid, "noise", amplitude),
            daemon=True,
        ).start()

    def _send_sim_clear(self) -> None:
        cid = self._simulator_page.current_controller_id
        if cid is None:
            return
        threading.Thread(
            target=lambda: self._api_client.clear_simulator_disturbance(cid),
            daemon=True,
        ).start()

    def closeEvent(self, event) -> None:  # noqa: N802
        self._bus_bridge.stop()
        self._telemetry_source.stop()
        super().closeEvent(event)


def main() -> None:
    """Entry point for the HMI application."""
    settings = HMISettings()
    session = Session()

    if settings.mock_mode:
        from smart_pid_hmi.services.mock_service import MockAPIClient, MockTelemetrySource

        api_client = MockAPIClient()
        telemetry_source = MockTelemetrySource()
    else:
        from smart_pid_hmi.services.api_client import APIClient
        from smart_pid_hmi.services.telemetry_sub import TelemetrySub

        api_client = APIClient(base_url=settings.server_url, session=session)
        telemetry_source = TelemetrySub(zmq_url=settings.zmq_url)

    bus_bridge = BusBridge(queue=telemetry_source.queue, refresh_ms=settings.refresh_ms)

    app = QApplication(sys.argv)
    window = MainWindow(
        settings=settings,
        session=session,
        api_client=api_client,
        telemetry_source=telemetry_source,
        bus_bridge=bus_bridge,
    )
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
```

- [ ] **Step 14.4: Run test to verify it passes**

```bash
uv run pytest tests/hmi/test_main_window_phase7.py -v
```
Expected: 11 PASSED

- [ ] **Step 14.5: Run all existing HMI tests to verify no regressions**

```bash
uv run pytest tests/hmi/ -v
```
Expected: All tests PASS

- [ ] **Step 14.6: Commit**

```bash
git add packages/smart_pid_hmi/src/smart_pid_hmi/main.py \
       tests/hmi/test_main_window_phase7.py
git commit -m "feat(hmi): wire Phase 7 pages (Executive, Trends, Settings) + ThemeManager into MainWindow"
```

---

## Task 15: Final Integration — lint, full test suite, sync

**Files:**
- No new files. This is a verification and cleanup task.

- [ ] **Step 15.1: Run uv sync**

```bash
uv sync --all-packages
```

- [ ] **Step 15.2: Run full test suite**

```bash
uv run pytest tests/ -v
```
Expected: All tests PASS

- [ ] **Step 15.3: Run lint**

```bash
uv run --with ruff ruff check .
```
Expected: No errors (fix any import ordering issues)

- [ ] **Step 15.4: Run lint fix if needed**

```bash
uv run --with ruff ruff check --fix .
```

- [ ] **Step 15.5: Run mypy**

```bash
uv run mypy packages/
```
Expected: No blocking errors (note: PySide6 stubs may emit minor warnings)

- [ ] **Step 15.6: Commit any lint fixes**

```bash
git add -u
git commit -m "chore(phase7): fix lint + type check issues"
```

---

## Summary

| Task | Component | New Files | Test Count |
|------|-----------|-----------|------------|
| 1 | ThemeColors + ThemeFonts | 1 test | 4 |
| 2 | ISA-101 refactor | 0 (modify) | 7 |
| 3 | DarkRoom theme | 2 | 8 |
| 4 | MD3 Dark theme | 2 | 8 |
| 5 | ThemeManager | 2 | 7 |
| 6 | themes/__init__.py | 0 (modify) | 1 |
| 7 | ExecutiveDashboardPage | 2 | 5 |
| 8 | APIClient stats | 0 (modify) | 2 |
| 9 | MultiTrendPage | 2 | 6 |
| 10 | SettingsPage | 2 | 7 |
| 11a | Export DTOs | 2 | 3 |
| 11b | Export Worker | 1 | 3 |
| 11c | Export Router | 2 | 3 |
| 12 | APIClient export | 0 (modify) | 3 |
| 13 | SVG Overlay | 2 | 6 |
| 14 | MainWindow wiring | 1 (modify + test) | 11 |
| 15 | Integration verification | 0 | 0 |
| **Total** | | **20 new files** | **~84 tests** |

**Dependencies between tasks:**
- Tasks 1-6 are sequential (each builds on the previous)
- Tasks 7-10 depend on Tasks 1-6 (need ThemeBase + themes)
- Task 8 depends on Task 7 (executive dashboard needs stats)
- Tasks 11a-11c are sequential (DTOs -> Worker -> Router)
- Task 12 depends on 11c (client methods for export endpoints)
- Task 13 is independent (only needs ThemeBase from Task 1)
- Task 14 depends on all other tasks (wires everything into MainWindow)
- Task 15 is the final verification

**Parallelizable groups (after Tasks 1-6 complete):**
- Group A: Tasks 7+8 (Executive Dashboard + stats)
- Group B: Task 9 (MultiTrendPage)
- Group C: Task 10 (SettingsPage)
- Group D: Tasks 11a+11b+11c+12 (Export pipeline)
- Group E: Task 13 (SVG Overlay)
