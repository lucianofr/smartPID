# Phase 7 — Executive Dashboard + Multi-Trend + Export + Themes

**Date:** 2026-04-03
**Status:** Approved
**Dependencies:** Phase 5 (Statistics/AI), Phase 6 (Alarms/RBAC)

---

## Overview

Phase 7 adds executive-level visibility, multi-trend analysis, data export, a 3-theme system,
and a basic SVG overlay for the simulator. This is the final phase of the V2 spec, delivering
the operational polish and reporting capabilities needed for production use.

## Theme System

### ThemeBase Protocol

```python
@dataclass(frozen=True)
class ThemeColors:
    background: str
    surface: str
    card: str
    text_primary: str
    text_secondary: str
    accent: str
    alarm_critical: str   # HIHI/LOLO
    alarm_warning: str    # HI/LO
    alarm_advisory: str   # advisory
    bar_pv: str
    bar_sp: str
    bar_co: str
    chart_bg: str
    chart_pv: str
    chart_sp: str
    chart_co: str
    chart_error: str
    success: str
    border: str

@dataclass(frozen=True)
class ThemeFonts:
    family: str
    mono_family: str
    size_label: int      # 10
    size_normal: int     # 12
    size_value: int      # 14
    size_title: int      # 16
    size_heading: int    # 20

class ThemeBase(Protocol):
    name: str
    colors: ThemeColors
    fonts: ThemeFonts
    chart_palette: list[str]   # 8+ colors for multi-series

    def stylesheet(self) -> str: ...
    def apply(self, app: QApplication) -> None: ...
```

### Theme Implementations

| Property | DarkRoom | MD3 Dark | ISA-101 |
|----------|----------|----------|---------|
| **Target** | Mission-critical control rooms | Modern desktop | ANSI/ISA-101.01 HPC |
| `background` | `#000000` | `#141218` | `#808080` |
| `surface` | `#08080A` | `#1D1B20` | `#999999` |
| `card` | `#0D0D11` | `#211F26` | `#B0B0B0` |
| `text_primary` | `#B0B0B8` | `#E6E0E9` | `#1A1A1A` |
| `text_secondary` | `#666670` | `#938F99` | `#4D4D4D` |
| `accent` | `#4A90D9` | `#D0BCFF` | `#333333` |
| `alarm_critical` | `#D92525` | `#F2B8B5` | `#FF0000` |
| `alarm_warning` | `#D9A000` | `#FFD8A8` | `#FFCC00` |
| `font_family` | Fira Code | Roboto | Segoe UI |
| `mono_family` | JetBrains Mono | Roboto Mono | Consolas |

### ThemeManager

```python
class ThemeManager(QObject):
    theme_changed = Signal(str)  # emits theme name

    def __init__(self):
        self._themes: dict[str, ThemeBase] = {}
        self._current: str = "isa101"

    def register(self, theme: ThemeBase) -> None
    def set_theme(self, name: str) -> None  # applies + emits signal
    def current(self) -> ThemeBase
```

- Registered in MainWindow at startup (3 themes)
- Hot-switch without restart: `set_theme()` reapplies stylesheet globally
- All widgets connect to `theme_changed` signal to refresh dynamic elements (charts, icons)
- Refactor existing ISA101Theme to implement ThemeBase protocol

## New HMI Pages

### Page Structure

```
MainWindow (QStackedWidget)
  ├─ ConnectionPage          # existing
  ├─ DashboardPage           # existing (operational view)
  ├─ ExecutiveDashboardPage  # NEW — KPI overview
  ├─ MultiTrendPage          # NEW — 2x2 trend grid
  ├─ SimulatorPage           # existing
  ├─ AlarmPanel              # existing
  └─ SettingsPage            # NEW — theme picker, preferences
```

Toolbar buttons: **Dashboard | Executive | Trends | Simulator | Alarms | Settings**

### ExecutiveDashboardPage

High-level system overview with KPI summary cards and per-controller dashboard-tile cards.

**Layout:**
```
┌──────────────────────────────────────────────────┐
│  KPI Cards Row (QHBoxLayout)                     │
│  ┌──────────┐ ┌──────────┐ ┌─────────┐ ┌──────┐│
│  │Total     │ │In Auto   │ │Active   │ │AI    ││
│  │Loops: 8  │ │6 (75%)   │ │Alarms:3 │ │Tuning││
│  └──────────┘ └──────────┘ └─────────┘ └──────┘│
│                                                  │
│  QScrollArea + FlowLayout (responsive 3/2/1 col) │
│  ┌──────────────┐ ┌──────────────┐ ┌───────────┐│
│  │ FIC-101      │ │ LIC-201      │ │ TIC-301   ││
│  │ AUTO FUZZY   │ │ AUTO NONE    │ │ MAN RL    ││
│  │ DDC          │ │ SUPERVISORY  │ │ DDC       ││
│  │ PV:50 SP:50  │ │ PV:65 SP:65  │ │ PV:180    ││
│  │ Err: 0.0%    │ │ Err: 0.0%    │ │ Err: 0.5% ││
│  │ AI: SP Track │ │ AI: Disabled │ │ AI: Dist  ││
│  │ IAE ITAE ISE │ │ IAE ITAE ISE │ │ IAE ITAE  ││
│  │ MSE σ TV     │ │ MSE σ TV     │ │ MSE σ TV  ││
│  │ Var/SP Var/R │ │ Var/SP Var/R │ │ Var/SP    ││
│  └──────────────┘ └──────────────┘ └───────────┘│
└──────────────────────────────────────────────────┘
```

- KPI cards: QFrame styled per theme, large numeric values (unchanged)
- Controller cards (`_ControllerCard`): dashboard-tile style with:
  - Header: LED status indicator, controller name, badges (Mode, AI Engine, DDC/Supervisory)
  - Process values row: PV, SP, Error% as mini-tiles
  - Optimization row: Objective, State, gamma (greyed out when AI engine = NONE)
  - Performance grid (4x2): IAE, ITAE, ISE, MSE, Std Dev, TV, Var/SP, Var/Range
- Responsive flow layout: 3 cards per row on wide screens, 2 on medium, 1 on narrow
- Card data from `GET /controllers` + `GET /controllers/{id}/stats` (stats show "—" until Phase 5)
- Auto-refresh: 5s polling (configurable in SettingsPage)

### MultiTrendPage

Time-synchronized 2x2 trend grid for cross-loop analysis.

**Layout:**
```
┌─ Loop Selector (QComboBox multi-select, up to 4) ─────────┐
│                                                              │
│  ┌──────────────────────┬──────────────────────┐           │
│  │  PV + SP (Loop 1)    │  PV + SP (Loop 2)    │           │
│  │  pyqtgraph PlotWidget│  pyqtgraph PlotWidget│           │
│  ├──────────────────────┼──────────────────────┤           │
│  │  CO (Loop 1)         │  CO (Loop 2)         │           │
│  │  pyqtgraph PlotWidget│  pyqtgraph PlotWidget│           │
│  └──────────────────────┴──────────────────────┘           │
│                                                              │
│  ┌─ Time Range ──────────────────────────────────┐         │
│  │ [1m] [5m] [15m] [1h] [Custom...] [▶ Live]   │         │
│  └───────────────────────────────────────────────┘         │
└──────────────────────────────────────────────────────────────┘
```

- **pyqtgraph** for high-performance plotting (handles 10K+ points smoothly)
- Time sync: all 4 plots share X-axis range via `sigXRangeChanged` signal
- Loop selector: choose which controllers to display (up to 4 in 2x2)
- Time range buttons: preset ranges + custom date picker
- Live mode: auto-scroll with latest data (polls `GET /history/{id}?last=300`)
- Historical mode: fixed range, data from `GET /history/{id}?start=...&end=...`
- Chart colors from `ThemeBase.chart_palette`

### SettingsPage

User preferences panel.

**Sections:**
1. **Theme** — radio buttons for DarkRoom / MD3 Dark / ISA-101, live preview
2. **Dashboard** — refresh rate slider (1s–30s), default page after login
3. **Export** — default format (CSV/XLSX/PDF), default time range
4. **About** — version, build info

Settings stored locally in `~/.smartpid/settings.json` (QSettings or plain JSON).

## Export System

### Backend

New router: `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/export.py`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/export` | operator+ | Request export generation |
| `GET` | `/export/{id}/status` | operator+ | Check export status |
| `GET` | `/export/{id}/download` | operator+ | Download generated file |

**Request body (POST /export):**
```json
{
    "controller_ids": [1, 2],
    "start": "2026-04-03T00:00:00Z",
    "end": "2026-04-03T12:00:00Z",
    "format": "csv",
    "include_alarms": true,
    "include_ai_log": false
}
```

**Response (POST /export):**
```json
{
    "export_id": "uuid",
    "status": "processing"
}
```

**Export generation:**
- Worker thread (not async — file I/O is CPU-bound for large exports)
- CSV: `csv` stdlib — one row per telemetry sample, columns: timestamp, tag, pv, sp, co, mode
- XLSX: `openpyxl` — separate sheets per controller + summary sheet with stats
- PDF: `reportlab` — header + stats table + trend chart image (matplotlib for static render)
- Generated files stored in `/tmp/spid_exports/`, auto-cleaned after 1h (TTL)
- Audit log entry on export request (action: EXPORT_DATA)

### HMI

- Export button on MultiTrendPage toolbar and ExecutiveDashboardPage
- Export dialog (QDialog): format selector, time range, controller checkboxes
- Progress: polls `/export/{id}/status`, shows QProgressBar
- On ready: auto-download via `GET /export/{id}/download` → save file dialog

## SVG Overlay (Simulator Page Enhancement)

Basic P&ID visualization on the SimulatorPage.

**Design:**
- Generic SVG template: tank + control valve + transmitter + piping
- QSvgWidget renders the static P&ID
- QLabel overlays positioned at fixed coordinates show live values (PV, SP, CO, mode)
- Valve opening animation: rotate/scale valve symbol proportional to CO%
- Color changes: transmitter icon color follows alarm state (green/yellow/red)
- One generic template — not customized per process preset

**Implementation:**
- SVG file: `packages/smart_pid_hmi/src/smart_pid_hmi/assets/pid_generic.svg`
- Overlay widget: `SvgOverlayWidget` composites QSvgWidget + positioned QLabels
- Updates on telemetry_received signal (same as existing dashboard)

## REST Endpoints (New/Modified)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/controllers/{id}/stats` | operator+ | Performance stats (IAE, ITAE, ISE, TV, σ) |
| `POST` | `/export` | operator+ | Request data export |
| `GET` | `/export/{id}/status` | operator+ | Export generation status |
| `GET` | `/export/{id}/download` | operator+ | Download export file |

Note: `/controllers/{id}/stats` may already exist from Phase 5 stats work. Verify and extend if needed.

## Dependencies

### New Python Packages
- `pyqtgraph` — high-performance plotting for MultiTrendPage
- `openpyxl` — XLSX export generation
- `reportlab` — PDF export generation

### Existing (no changes)
- `PySide6` — GUI framework
- `matplotlib` — static chart rendering for PDF export (if not already present)

## Testing Strategy

### Theme Tests
- Each theme generates valid QSS (no syntax errors)
- ThemeColors: all fields are valid hex colors
- ThemeManager: register, switch, signal emission
- Hot-switch: apply new theme, verify stylesheet changes

### Page Tests (with MockService)
- ExecutiveDashboardPage: renders KPI cards, populates table, handles empty state
- MultiTrendPage: renders 2x2 grid, time sync works, loop selector changes plots
- SettingsPage: theme switch triggers ThemeManager, settings persist

### Export Tests
- CSV: correct columns, correct data, proper timestamp formatting
- XLSX: separate sheets per controller, summary sheet present
- PDF: file is valid PDF, contains expected content
- Export lifecycle: POST → status polling → download

### SVG Overlay Tests
- SvgOverlayWidget: renders SVG, positions labels correctly
- Value updates: labels reflect new telemetry data
- Alarm colors: transmitter icon changes color on alarm state

## Files to Create/Modify

### New Files
- `packages/smart_pid_hmi/src/smart_pid_hmi/themes/base.py` — ThemeBase, ThemeColors, ThemeFonts
- `packages/smart_pid_hmi/src/smart_pid_hmi/themes/dark_room.py` — DarkRoom theme
- `packages/smart_pid_hmi/src/smart_pid_hmi/themes/md3_dark.py` — MD3 Dark theme
- `packages/smart_pid_hmi/src/smart_pid_hmi/themes/manager.py` — ThemeManager
- `packages/smart_pid_hmi/src/smart_pid_hmi/pages/executive_dashboard.py`
- `packages/smart_pid_hmi/src/smart_pid_hmi/pages/multi_trend_page.py`
- `packages/smart_pid_hmi/src/smart_pid_hmi/pages/settings_page.py`
- `packages/smart_pid_hmi/src/smart_pid_hmi/widgets/svg_overlay.py`
- `packages/smart_pid_hmi/src/smart_pid_hmi/assets/pid_generic.svg`
- `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/export.py`
- `packages/smart_pid_core/src/smart_pid_core/application/export_worker.py`
- `tests/test_themes.py`
- `tests/test_executive_dashboard.py`
- `tests/test_multi_trend.py`
- `tests/test_export.py`
- `tests/test_svg_overlay.py`

### Modified Files
- `packages/smart_pid_hmi/src/smart_pid_hmi/themes/isa101.py` — refactor to implement ThemeBase
- `packages/smart_pid_hmi/src/smart_pid_hmi/themes/__init__.py` — export all themes
- `packages/smart_pid_hmi/src/smart_pid_hmi/main.py` — add new pages, toolbar buttons, ThemeManager
- `packages/smart_pid_hmi/src/smart_pid_hmi/pages/simulator_page.py` — add SVG overlay
- `packages/smart_pid_hmi/src/smart_pid_hmi/api_client.py` — export methods, stats method
- `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/app.py` — register export router
- `packages/smart_pid_core/pyproject.toml` — add openpyxl, reportlab deps
- `packages/smart_pid_hmi/pyproject.toml` — add pyqtgraph dep
