# OPC-UA Mode Target/Actual + Integer Mapping

**Date:** 2026-04-06
**Status:** Approved
**Scope:** Domain model, DTOs, SQLite, API router, OPC-UA adapter, HMI dialog

---

## Problem

In real DCS/PLC systems, the PID operating mode is represented by two OPC-UA variables:

- **Target mode** — the mode the operator or system is requesting (written by SmartPID)
- **Actual mode** — the mode the DCS is currently executing (read by SmartPID)

Both variables expose integer values, and the integer-to-mode mapping varies per DCS vendor/configuration. For example, one DCS might use `1=MAN, 2=AUTO, 4=CAS` while another uses `0=MAN, 1=AUTO, 2=CAS, 3=RCAS`.

The current implementation has a single `node_id_mode` field with no integer conversion.

## Decision

**Approach A — Extend `TagBindings` directly.** All three new fields (two NodeIDs + mapping dict) live in `TagBindings`, keeping all OPC binding config in one place.

## Design

### 1. Data Model

**`TagBindings` (domain dataclass)** — replace `node_id_mode: str` with:

```python
node_id_mode_target: str = ""          # NodeID to write target mode to DCS
node_id_mode_actual: str = ""          # NodeID to read actual mode from DCS
mode_int_map: dict[str, int] = field(default_factory=dict)
# Keys are ControllerMode string values, e.g. {"MAN": 1, "AUTO": 2, "CAS": 4}
```

**`TagBindingsDTO` (Pydantic)** — mirrors the domain model:

```python
node_id_mode_target: str = ""
node_id_mode_actual: str = ""
mode_int_map: dict[str, int] = {}
```

The mapping is bidirectional at runtime:
- **Reading actual mode:** invert the map (`int → ControllerMode`)
- **Writing target mode:** use the map directly (`ControllerMode → int`)

Both directions share the same map; a single configuration per controller.

### 2. SQLite Persistence

Migration adds 3 columns to `Controlador`:

```sql
ALTER TABLE Controlador ADD COLUMN node_id_mode_target TEXT DEFAULT '';
ALTER TABLE Controlador ADD COLUMN node_id_mode_actual TEXT DEFAULT '';
ALTER TABLE Controlador ADD COLUMN mode_int_map TEXT DEFAULT '{}';

-- Migrate legacy data
UPDATE Controlador SET node_id_mode_target = node_id_mode WHERE node_id_mode != '';
```

The legacy `node_id_mode` column is retained but ignored in code (no DROP COLUMN).

`mode_int_map` is stored as a JSON string in the TEXT column. Serialized via `json.dumps`/`json.loads` in the repository.

### 3. OPC-UA Adapter

**`register_controller`** accepts the new fields instead of `node_id_mode`:

```python
def register_controller(
    self, controller_id: int, *,
    node_id_pv: str = "", ...,
    node_id_mode_target: str = "",
    node_id_mode_actual: str = "",
    mode_int_map: dict[str, int] | None = None,
) -> None:
```

Internal storage includes an inverted map for read lookups:

```python
{
    "mode_target": node_id_mode_target,
    "mode_actual": node_id_mode_actual,
    "mode_int_map": mode_int_map,            # {"MAN": 1, "AUTO": 2}
    "mode_int_map_inv": {1: "MAN", 2: "AUTO"},  # built at registration
}
```

**`read_actual_mode(controller_id) -> ControllerMode | None`** replaces the old `read_external_mode`:
- Reads integer value from `mode_actual` OPC-UA node
- Looks up in `mode_int_map_inv`
- Returns `None` if: node not mapped, read fails, or **integer not in map** (caller treats as `SignalSeverity.BAD`)

**`write_target_mode(controller_id, mode: ControllerMode) -> bool`** (new):
- Looks up `mode_int_map[mode.value]` to get the integer
- Writes the integer to `mode_target` OPC-UA node
- Returns `False` if mode not in map or write fails

The old `read_external_mode` method is removed.

### 4. API Router

Mechanical updates to the 3 conversion points in `controllers.py`:

- **`_to_response`** (Controller → DTO): maps the 3 new fields
- **`_NESTED_BUILDERS`** (DTO → Controller): same 3 fields
- **PATCH partial update**: works as-is since `TagBindingsDTO` is already `Optional` in `ControllerUpdate`

JSON shape:

```json
{
  "tag_bindings": {
    "node_id_pv": "ns=2;s=PV",
    "node_id_mode_target": "ns=2;s=MODE_TGT",
    "node_id_mode_actual": "ns=2;s=MODE_ACT",
    "mode_int_map": {"MAN": 1, "AUTO": 2, "CAS": 4}
  }
}
```

No new endpoints. No new routes.

### 5. HMI — OPC-UA Tags Tab

**Mode tag rows** replace the single "Mode" line:
- "Mode (Target):" — QLineEdit + Browse button
- "Mode (Actual):" — QLineEdit + Browse button

**Mode Integer Mapping group** below the tag rows:
- `QGroupBox("Mode Integer Mapping")` with a form layout
- One row per `ControllerMode` member: `QLabel("MAN:")` + `QSpinBox(0..255)`
- Value `0` = not mapped (sentinel — no DCS uses 0 for mode)
- All 9 modes are created at init, stored in `self._mode_map_widgets: dict[str, tuple[QLabel, QSpinBox]]`

**Dynamic visibility** linked to `permitted_modes`:
- Method `_refresh_mode_map_visibility()` iterates widgets and calls `setVisible(mode in current_permitted_modes)`
- Connected to the `permitted_modes` widget's change signal from the General tab
- On dialog open (edit mode), initial visibility set from loaded `permitted_modes`

**Data flow:**
- `populate()`: fills spinboxes from `mode_int_map` dict
- `get_controller_data()`: collects only visible modes with value > 0 into `mode_int_map`

## Error Handling

| Scenario | Behavior |
|---|---|
| OPC-UA actual mode returns unmapped integer | Treat as `SignalSeverity.BAD`, log warning |
| `write_target_mode` called with mode not in map | Return `False`, log warning, no OPC write |
| `mode_int_map` is empty (no mapping configured) | Mode reading/writing disabled (same as today with empty `node_id_mode`) |
| Duplicate integers in map (e.g. two modes → same int) | Validated at DTO level: Pydantic validator rejects duplicate values |

## Migration Path

- Existing controllers with `node_id_mode` set: value migrated to `node_id_mode_target`, `node_id_mode_actual` left empty, `mode_int_map` left empty
- Users must manually configure the integer mapping after upgrade (no way to guess DCS vendor values)
- Until mapping is configured, behavior is equivalent to current: mode tag exists but integer conversion is a no-op
