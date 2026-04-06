# Executive Dashboard — Controller Cards Redesign

**Date:** 2026-04-06
**Branch:** `feat/executive-dashboard-cards`
**Status:** Design approved

## Summary

Replace the `QTableWidget` performance grid in the Executive Dashboard with individual
controller cards using a "Dashboard Tiles" visual style. Each card displays process values,
AI optimization info, and all performance indices in a compact, tile-based layout.

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Card content scope | All info (AI + performance + process) | User wants full visibility per controller |
| KPI summary cards | Keep at top | Aggregated view has independent value |
| Card layout style | Dashboard tiles (option C) | Modern SCADA-like look, mini-tiles per metric |
| Grid responsiveness | Flow layout (3/2/1 cols) | Adapts to window width automatically |
| AI NONE display | Show disabled (greyed out) | Uniform card height across the grid |

## Page Structure

```
+------------------------------------------------------------------+
|  Executive Dashboard (title)                                      |
+------------------------------------------------------------------+
| [Total Loops: 3] [In AUTO: 3] [Active Alarms: 0] [AI Active: 1] |  <- existing _KPICard row
+------------------------------------------------------------------+
| QScrollArea with _FlowLayout                                      |
|                                                                    |
|  +------------------+  +------------------+  +------------------+ |
|  |   FIC-101 card   |  |   LIC-201 card   |  |   TIC-301 card   | |
|  +------------------+  +------------------+  +------------------+ |
|                                                                    |
+------------------------------------------------------------------+
```

## Controller Card Anatomy

Each card is a `_ControllerCard(QFrame)` with the following vertical sections:

### Header
- **Left:** Status LED + controller name (bold)
  - LED green: mode is AUTO, CAS, RCAS, or ROUT
  - LED yellow: mode is MAN or IMAN
  - LED grey: mode is OOS or LO
- **Right:** Three badges:
  - Mode badge (AUTO/MAN/CAS/etc) — green bg for AUTO, neutral for others
  - Engine badge (NONE/FUZZY/RL) — amber bg for active, neutral for NONE
  - Execution badge (DDC/SUPERVISORY) — blue bg

### Process Values (3 mini-tiles, horizontal)
- **PV** — value in `theme.chart_pv` color
- **SP** — value in `theme.chart_sp` color
- **Error%** — value in `theme.fg_primary` color, computed as `|PV-SP| / span * 100`

Each tile: small label on top, large bold value below, centered.

### Optimization Section (3 mini-tiles, horizontal)
- **Objective** — SP Tracking / Disturbance Rejection / Surge Level
- **Optimizer State** — RUN (green) / PAUSE (amber) / STOP (red)
- **Last gamma** — numeric value or "—" if unavailable

When `ai_config.engine == NONE`:
- All three tiles show greyed-out text
- Objective shows "—", State shows "Disabled", gamma shows "—"
- Uses `theme.fg_muted` color

### Performance Grid (4x2 mini-tiles)

| IAE | ITAE | ISE | MSE |
|-----|------|-----|-----|
| Std Dev | TV | Var/SP | Var/Range |

Each tile: small label on top, bold value below, centered.
Values show "—" when stats data is unavailable (Phase 5 not yet implemented).

## Widget Architecture

All new widgets live in `executive_dashboard.py`:

### `_ControllerCard(QFrame)`

```python
class _ControllerCard(QFrame):
    def __init__(self, theme: ThemeBase | None = None, parent: QWidget | None = None): ...
    def update_data(self, data: dict) -> None: ...
    def apply_theme(self, theme: ThemeBase) -> None: ...
```

**`data` dict expected keys:**
- Required: `name`, `mode`, `execution_mode`
- Optional (show "—" if absent):
  - `pv`, `sp`, `sp_hi_lim`, `sp_lo_lim` (process values)
  - `ai_engine`, `ai_objective`, `ai_state`, `ai_gamma` (optimization)
  - `iae`, `itae`, `ise`, `mse`, `std_dev`, `total_variation`, `variability_sp`, `variability_range` (performance)

### `_FlowLayout(QLayout)`

Custom QLayout that arranges child widgets in rows, wrapping to the next row when
the container width is exceeded. Common Qt pattern (not built-in).

- Card min width: 380px
- Card max width: 450px
- Spacing: 12px horizontal, 12px vertical

### Modified `ExecutiveDashboardPage`

```python
class ExecutiveDashboardPage(QWidget):
    # KEPT:
    _card_total, _card_auto, _card_alarms, _card_ai  # KPI cards
    update_kpis(...)  # unchanged

    # REMOVED:
    _table: QTableWidget
    update_performance_table(...)
    _PERF_COLUMNS

    # ADDED:
    _scroll_area: QScrollArea
    _cards_container: QWidget  # with _FlowLayout
    _controller_cards: dict[str, _ControllerCard]  # keyed by controller name
    update_controller_cards(controllers: list[dict]) -> None
```

**`update_controller_cards` behavior:**
- Clears existing cards
- Creates one `_ControllerCard` per controller in the list
- Calls `update_data(controller_dict)` on each card
- Stores references in `_controller_cards` dict

## Changes to `main.py`

### `_on_controllers_received` (line ~394)

Before:
```python
perf_rows = []
for c in controllers:
    # ... build perf_rows dict ...
self._executive_page.update_performance_table(perf_rows)
```

After:
```python
self._executive_page.update_controller_cards(controllers)
```

The card itself handles extracting fields from the controller dict. No more
intermediate `perf_rows` transformation.

The KPI computation block (`update_kpis`) remains unchanged.

## Theme Integration

All colors come from `ThemeBase` protocol attributes:
- Card background: `theme.bg_card`
- Card border: `theme.border`, `theme.border_radius`
- Labels: `theme.fg_secondary`
- Values: `theme.fg_primary`
- Muted/disabled: `theme.fg_muted`
- PV/SP colors: `theme.chart_pv`, `theme.chart_sp`
- Accent: `theme.accent`
- Badge backgrounds: derived from semantic colors (alarm_warning_bg for FUZZY/RL, bg_hover for NONE)
- Mini-tile backgrounds: `theme.bg_input` or similar dark sub-surface

`apply_theme` cascades from `ExecutiveDashboardPage` -> each `_ControllerCard` -> all sub-widgets.

## Removed Artifacts

- `_PERF_COLUMNS` constant
- `QTableWidget` instance and all table-related code
- `update_performance_table` method
- Imports: `QTableWidgetItem`, `QHeaderView`

## Test Plan

### File: `tests/hmi/pages/test_executive_dashboard.py`

**Kept unchanged:**
- `test_creation`
- `test_has_title`
- `test_has_kpi_labels`
- `test_update_kpis`

**Removed:**
- `test_has_performance_table`
- `test_update_performance_table`

**New tests:**
- `test_has_scroll_area` — QScrollArea exists in the page
- `test_update_controller_cards_creates_cards` — 3 controllers -> 3 cards
- `test_controller_card_shows_name_and_mode` — name label and mode badge text
- `test_controller_card_shows_ai_info` — engine/objective badges when FUZZY
- `test_controller_card_ai_none_shows_disabled` — "Disabled" text when NONE
- `test_controller_card_shows_performance_metrics` — IAE, ITAE etc labels present
- `test_controller_card_placeholder_when_no_stats` — shows "—" when metrics absent
- `test_cards_update_on_second_call` — calling update twice recreates cards correctly
- `test_flow_layout_exists` — scroll area uses flow layout

### File: `tests/hmi/test_main_window_audit_gaps.py`

**Modified:**
- `test_controllers_loaded_populates_performance_table` — renamed to
  `test_controllers_loaded_populates_controller_cards`, verifies card count
  and card name labels instead of table rows

## Spec Update Requirements

Per project conventions, UI changes must update relevant spec docs:
- `docs/smartPIDv2.md` — Executive Dashboard section (table -> cards description)
- `docs/superpowers/specs/2026-04-02-smart-pid-v2-architecture-design.md` — if Executive Dashboard is described there
