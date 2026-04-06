# Loop Configuration Dialog + Hide P&ID Tab

**Date:** 2026-04-05
**Scope:** HMI gear button on cards, full-field edit dialog, expanded DTOs/API, hide P&ID tab

---

## 1. Problem Statement

Two UX issues in the current HMI:

1. **P&ID tab is misplaced** — The "P&ID" nav tab shows an SVG process viewer with instrument list. This functionality belongs inside the Simulator tab (Phase 4), not as a standalone tab. It should be hidden until Phase 4 integrates it.

2. **No way to edit loop configuration** — Controller cards on the Dashboard show PV/SP/CO and mode, but there's no button to open the full configuration of a registered loop. The `AddControllerDialog` already has all 30+ fields in 7 tabs, but it's only used for creation. Users need a gear button on each card to open the same dialog pre-filled for editing.

Additionally, a **major gap** exists: the DTOs (`ControllerCreate`, `ControllerUpdate`, `ControllerResponse`) and the backend API only handle ~10 basic fields, while the domain `Controller` model has 30+ fields and the `AddControllerDialog` already collects all of them. The API needs to be expanded to carry all fields end-to-end.

---

## 2. Changes

### 2.1 Hide P&ID Tab

- Remove `self._process_nav` from the toolbar navigation in `main.py`
- Remove `ProcessViewPage` from `_nav_page_map`
- Keep the `ProcessViewPage` class and widget in the stack (dormant) for future use in Phase 4/Simulator
- Remove the backward-compat `self._process_btn` reference

**Files:** `main.py`

### 2.2 Gear Button on ControllerCardWidget

Add a settings button to each controller card header:

- `QPushButton("⚙")` placed in the header layout, after the mode label
- Fixed size 28x28, transparent background, themed border on hover
- New signal: `settings_requested = Signal(int)` — emits `controller_id`
- Button click calls `event.stopPropagation()` equivalent (accept the event) so it does NOT trigger `controller_selected` / card selection
- The gear button is always visible (not hidden behind hover)

**Files:** `widgets/controller_card.py`

### 2.3 Reuse AddControllerDialog for Edit Mode

Rename `AddControllerDialog` → `ControllerDialog` to serve both create and edit:

- Constructor accepts optional `edit_data: dict | None = None`
- When `edit_data` is provided:
  - Window title: `"Edit Controller — {name}"`
  - Name field becomes read-only (can't rename a controller)
  - All fields populated from the dict via new `_populate(data: dict)` method
- When `edit_data` is `None`: behaves exactly as current `AddControllerDialog` (create mode)
- `get_controller_data()` returns the same dict structure in both modes
- Update all existing imports/references from `AddControllerDialog` to `ControllerDialog`

**Files:** `widgets/add_controller_dialog.py` (renamed to `widgets/controller_dialog.py`), `main.py`, tests

### 2.4 Expand DTOs to Cover All Controller Fields

The DTOs need pydantic sub-models matching the domain dataclasses:

```python
# New sub-models in dtos/controllers.py

class PIDParamsDTO(BaseModel):
    gain: float = 1.0
    reset: float = 10.0
    rate: float = 0.0
    alpha: float = 0.125
    deadband: float = 0.0

class ScaleConfigDTO(BaseModel):
    eu_min: float = 0.0
    eu_max: float = 100.0
    unit: str = ""

class AIConfigDTO(BaseModel):
    engine: str = "NONE"
    objective: str = "DISTURBANCE_REJECTION"
    process_speed: str = "MEDIUM"
    dead_time_l: float = 1.0
    limit_min: float = 0.1
    limit_max: float = 100.0

class TagBindingsDTO(BaseModel):
    node_id_pv: str = ""
    node_id_sp: str = ""
    node_id_co: str = ""
    node_id_integral: str = ""
    node_id_bkcal_in: str = ""
    node_id_bkcal_out: str = ""
    node_id_kp: str = ""
    node_id_ti: str = ""
    node_id_td: str = ""
    node_id_mode: str = ""

class ControlOptsDTO(BaseModel):
    direct_acting: bool = False
    track_enable: bool = False
    track_in_manual: bool = False
    sp_pv_track_in_man: bool = False
    sp_pv_track_in_lo_or_iman: bool = False
    # ... all fields from ControlOpts

class IOOptsDTO(BaseModel):
    low_cutoff: bool = False
    increase_to_close: bool = False
    target_to_man_if_fault: bool = False
    fault_state_to_value: bool = False
    # ... all fields from IOOpts
```

**ControllerCreate** — expanded with all fields (defaults match domain model):

```python
class ControllerCreate(BaseModel):
    name: str
    description: str = ""
    execution_mode: str = "DDC"
    scan_rate_ms: int = 1000
    pid_structure: str = "ISA"
    integral_type: str = "TIME_TI"
    mode_normal: str = "AUTO"
    pid_params: PIDParamsDTO = PIDParamsDTO()
    pv_scale: ScaleConfigDTO = ScaleConfigDTO()
    out_scale: ScaleConfigDTO = ScaleConfigDTO()
    tag_bindings: TagBindingsDTO = TagBindingsDTO()
    control_opts: ControlOptsDTO = ControlOptsDTO()
    io_opts: IOOptsDTO = IOOptsDTO()
    ai_config: AIConfigDTO = AIConfigDTO()
    sp_hi_lim: float = 100.0
    sp_lo_lim: float = 0.0
    sp_rate_up: float = 0.0
    sp_rate_dn: float = 0.0
    out_hi_lim: float = 100.0
    out_lo_lim: float = 0.0
    arw_hi_lim: float = 100.0
    arw_lo_lim: float = 0.0
    pv_ftime: float = 0.0
    sp_ftime: float = 0.0
    low_cut: float = 0.0
    ff_enable: bool = False
    ff_gain: float = 1.0
    shed_opt: str = "MAN"
    shed_time_s: float = 10.0
    tuning_write_mode: str = "APPROVAL_REQUIRED"
    max_tuning_change_pct: float = 10.0
```

**ControllerUpdate** — same fields, all `Optional` (patch semantics):

```python
class ControllerUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    execution_mode: str | None = None
    # ... all fields as Optional
    pid_params: PIDParamsDTO | None = None
    # ... sub-models also Optional
```

**ControllerResponse** — all fields present (not Optional):

```python
class ControllerResponse(BaseModel):
    id: int
    name: str
    description: str
    mode: str
    pv: float
    sp: float
    co: float
    execution_mode: str = "DDC"
    scan_rate_ms: int = 1000
    pid_structure: str = "ISA"
    integral_type: str = "TIME_TI"
    mode_normal: str = "AUTO"
    pid_params: PIDParamsDTO = PIDParamsDTO()
    pv_scale: ScaleConfigDTO = ScaleConfigDTO()
    out_scale: ScaleConfigDTO = ScaleConfigDTO()
    tag_bindings: TagBindingsDTO = TagBindingsDTO()
    control_opts: ControlOptsDTO = ControlOptsDTO()
    io_opts: IOOptsDTO = IOOptsDTO()
    ai_config: AIConfigDTO = AIConfigDTO()
    sp_hi_lim: float = 100.0
    sp_lo_lim: float = 0.0
    sp_rate_up: float = 0.0
    sp_rate_dn: float = 0.0
    out_hi_lim: float = 100.0
    out_lo_lim: float = 0.0
    arw_hi_lim: float = 100.0
    arw_lo_lim: float = 0.0
    pv_ftime: float = 0.0
    sp_ftime: float = 0.0
    low_cut: float = 0.0
    ff_enable: bool = False
    ff_gain: float = 1.0
    shed_opt: str = "MAN"
    shed_time_s: float = 10.0
    tuning_write_mode: str = "APPROVAL_REQUIRED"
    max_tuning_change_pct: float = 10.0
```

**Files:** `smart_pid_domain/dtos/controllers.py`

### 2.5 Expand Backend API

**`_to_response()`** — map ALL Controller fields to the expanded ControllerResponse, including nested dataclasses → DTOs.

**`create_controller()`** — build the full Controller from ControllerCreate (map sub-models to domain dataclasses).

**`update_controller()`** — apply all provided fields from ControllerUpdate, including nested sub-models via `dataclasses.replace()`.

**Files:** `smart_pid_core/adapters/inbound/api/routers/controllers.py`

### 2.6 SQLite Repository — No Changes Needed

The `SQLiteRepository._controller_to_params()` and `_row_to_controller()` already serialize/deserialize **all** Controller fields (PID params, scales, tag bindings, control opts, IO opts, AI config, shed, etc.). No changes needed here.

### 2.7 Expand HMI API Client

**APIClientPort** — add method:
```python
def update_controller(self, controller_id: int, data: dict) -> ControllerResponse: ...
```

**APIClient** — implement via `PUT /controllers/{id}` with JSON body.

**MockService** — implement with in-memory update.

**Files:** `services/ports.py`, `services/api_client.py`, `services/mock_service.py`

### 2.8 Wiring in MainWindow

- `DashboardPage` exposes a new signal: `settings_requested = Signal(int)`
- When creating cards, connect `card.settings_requested` → `DashboardPage.settings_requested`
- `MainWindow` connects `DashboardPage.settings_requested` → `_on_edit_controller(id)`
- `_on_edit_controller(id)`:
  1. Fetch full controller data via `api_client.get_controller(id)` in background thread
  2. Open `ControllerDialog(edit_data=response.model_dump())` 
  3. On accept: call `api_client.update_controller(id, dialog.get_controller_data())` in background thread
  4. Refresh dashboard on success

**Files:** `main.py`, `pages/dashboard_page.py`

---

## 3. Testing Strategy

- **Unit tests** for `ControllerDialog` populate/get_data round-trip
- **Unit tests** for expanded DTOs (serialization, optional fields)
- **API tests** for full-field create/update/get round-trip
- **Widget test** for gear button signal emission on ControllerCardWidget
- **Integration test** for MainWindow edit flow (mock API)

---

## 4. Files Changed Summary

| Package | File | Change |
|---------|------|--------|
| domain | `dtos/controllers.py` | Add sub-model DTOs, expand Create/Update/Response |
| core | `routers/controllers.py` | Expand _to_response, create, update handlers |
| core | `sqlite_repo.py` | No changes needed (already full) |
| hmi | `widgets/controller_dialog.py` | Rename + add edit mode with populate() |
| hmi | `widgets/controller_card.py` | Add gear button + settings_requested signal |
| hmi | `pages/dashboard_page.py` | Forward settings_requested signal |
| hmi | `services/ports.py` | Add update_controller |
| hmi | `services/api_client.py` | Implement update_controller |
| hmi | `services/mock_service.py` | Implement update_controller |
| hmi | `main.py` | Hide P&ID tab, wire edit flow |
| tests | various | New tests for all above |
