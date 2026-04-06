# OPC-UA Mode Target/Actual + Integer Mapping — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the single `node_id_mode` OPC-UA field with target/actual mode NodeIDs plus a configurable integer-to-ControllerMode mapping, enabling integration with real DCS/PLCs that use vendor-specific integer codes for operating modes.

**Architecture:** Extend `TagBindings` (domain) and `TagBindingsDTO` (Pydantic) with three new fields replacing `node_id_mode`. Add `permitted_modes` to CRUD DTOs (currently missing from API). Update SQLite DDL/repo, API router conversions, OPC-UA adapter read/write, and HMI dialog (OPC-UA tab + General tab permitted_modes selector).

**Tech Stack:** Python 3.13, dataclasses, Pydantic v2, aiosqlite, PySide6, pytest

**Spec:** `docs/superpowers/specs/2026-04-06-opc-mode-target-actual-mapping-design.md`

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `packages/smart_pid_domain/src/smart_pid_domain/models/controller.py` | Modify | TagBindings: 3 new fields, remove `node_id_mode` |
| `packages/smart_pid_domain/src/smart_pid_domain/dtos/controllers.py` | Modify | TagBindingsDTO: 3 new fields + validator; `permitted_modes` in Create/Update/Response |
| `packages/smart_pid_core/src/smart_pid_core/adapters/outbound/sqlite_repo.py` | Modify | DDL: 3 new columns; save/load mode fields |
| `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/controllers.py` | Modify | `_to_response`, `_body_to_controller`, `_NESTED_BUILDERS`, PATCH `_ENUM_FIELDS` |
| `packages/smart_pid_core/src/smart_pid_core/adapters/outbound/opcua_adapter.py` | Modify | `register_controller`, `read_actual_mode`, `write_target_mode` |
| `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/commands.py` | Modify | Update `read_external_mode` caller |
| `packages/smart_pid_core/src/smart_pid_core/main.py` | Modify | Pass new fields to `register_controller` |
| `packages/smart_pid_hmi/src/smart_pid_hmi/widgets/controller_dialog.py` | Modify | General tab: permitted_modes; OPC-UA tab: target/actual + int map |
| `tests/domain/test_models.py` | Modify | Update `TestTagBindingsExpanded` |
| `tests/domain/test_controller_dtos.py` | Modify | Update `TestTagBindingsDTO`, add `permitted_modes` + `mode_int_map` tests |
| `tests/core/integration/test_sqlite_repo.py` | Modify | Add mode field round-trip test |
| `tests/core/integration/test_api_controllers.py` | Modify | Update for new fields |
| `tests/core/unit/test_opcua_adapter.py` | Modify | Tests for `register_controller`, `read_actual_mode`, `write_target_mode` |
| `tests/hmi/widgets/test_controller_dialog.py` | Modify | Update EDIT_DATA, add mode map + permitted_modes tests |

---

### Task 1: Domain Model — Replace `node_id_mode` in TagBindings

**Files:**
- Modify: `packages/smart_pid_domain/src/smart_pid_domain/models/controller.py:64-78`
- Test: `tests/domain/test_models.py`

- [ ] **Step 1: Write failing tests for new TagBindings fields**

In `tests/domain/test_models.py`, replace `TestTagBindingsExpanded`:

```python
class TestTagBindingsExpanded:
    def test_new_fields_default_empty(self) -> None:
        tb = TagBindings()
        assert tb.node_id_kp == ""
        assert tb.node_id_ti == ""
        assert tb.node_id_td == ""
        assert tb.node_id_mode_target == ""
        assert tb.node_id_mode_actual == ""
        assert tb.mode_int_map == {}

    def test_mode_int_map_stores_values(self) -> None:
        tb = TagBindings(mode_int_map={"MAN": 1, "AUTO": 2, "CAS": 4})
        assert tb.mode_int_map["MAN"] == 1
        assert tb.mode_int_map["AUTO"] == 2
        assert len(tb.mode_int_map) == 3

    def test_no_node_id_mode_field(self) -> None:
        """Old node_id_mode field must not exist."""
        tb = TagBindings()
        assert not hasattr(tb, "node_id_mode")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/domain/test_models.py::TestTagBindingsExpanded -v`
Expected: FAIL — `node_id_mode_target` not found, `node_id_mode` still exists

- [ ] **Step 3: Update TagBindings dataclass**

In `packages/smart_pid_domain/src/smart_pid_domain/models/controller.py`, replace the `TagBindings` class:

```python
@dataclass
class TagBindings:
    """OPC-UA NodeID mappings for a controller."""

    node_id_pv: str = ""
    node_id_sp: str = ""
    node_id_co: str = ""
    node_id_integral: str = ""
    node_id_bkcal_in: str = ""
    node_id_bkcal_out: str = ""
    node_id_kp: str = ""
    node_id_ti: str = ""
    node_id_td: str = ""
    node_id_mode_target: str = ""
    node_id_mode_actual: str = ""
    mode_int_map: dict[str, int] = field(default_factory=dict)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/domain/test_models.py::TestTagBindingsExpanded -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_domain/src/smart_pid_domain/models/controller.py tests/domain/test_models.py
git commit -m "feat(domain): replace node_id_mode with target/actual + mode_int_map in TagBindings"
```

---

### Task 2: DTOs — TagBindingsDTO + mode_int_map Validator

**Files:**
- Modify: `packages/smart_pid_domain/src/smart_pid_domain/dtos/controllers.py:37-49`
- Test: `tests/domain/test_controller_dtos.py`

- [ ] **Step 1: Write failing tests for new TagBindingsDTO**

In `tests/domain/test_controller_dtos.py`, replace `TestTagBindingsDTO`:

```python
class TestTagBindingsDTO:
    def test_defaults_all_empty(self) -> None:
        t = TagBindingsDTO()
        for field_name in [
            "node_id_pv", "node_id_sp", "node_id_co", "node_id_integral",
            "node_id_bkcal_in", "node_id_bkcal_out",
            "node_id_kp", "node_id_ti", "node_id_td",
            "node_id_mode_target", "node_id_mode_actual",
        ]:
            assert getattr(t, field_name) == ""
        assert t.mode_int_map == {}

    def test_custom(self) -> None:
        t = TagBindingsDTO(node_id_pv="ns=2;s=TIC100.PV")
        assert t.node_id_pv == "ns=2;s=TIC100.PV"

    def test_mode_int_map_accepted(self) -> None:
        t = TagBindingsDTO(mode_int_map={"MAN": 1, "AUTO": 2})
        assert t.mode_int_map == {"MAN": 1, "AUTO": 2}

    def test_mode_int_map_rejects_duplicate_values(self) -> None:
        with pytest.raises(ValidationError, match="[Dd]uplicate"):
            TagBindingsDTO(mode_int_map={"MAN": 1, "AUTO": 1})

    def test_no_old_node_id_mode(self) -> None:
        assert "node_id_mode" not in TagBindingsDTO.model_fields
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/domain/test_controller_dtos.py::TestTagBindingsDTO -v`
Expected: FAIL

- [ ] **Step 3: Update TagBindingsDTO**

In `packages/smart_pid_domain/src/smart_pid_domain/dtos/controllers.py`, replace the `TagBindingsDTO` class. Add `model_validator` import:

```python
from pydantic import BaseModel, model_validator
```

Replace the class:

```python
class TagBindingsDTO(BaseModel):
    """OPC-UA NodeID mappings (mirrors domain TagBindings)."""

    node_id_pv: str = ""
    node_id_sp: str = ""
    node_id_co: str = ""
    node_id_integral: str = ""
    node_id_bkcal_in: str = ""
    node_id_bkcal_out: str = ""
    node_id_kp: str = ""
    node_id_ti: str = ""
    node_id_td: str = ""
    node_id_mode_target: str = ""
    node_id_mode_actual: str = ""
    mode_int_map: dict[str, int] = {}

    @model_validator(mode="after")
    def _no_duplicate_int_values(self) -> TagBindingsDTO:
        vals = list(self.mode_int_map.values())
        if len(vals) != len(set(vals)):
            msg = "Duplicate integer values in mode_int_map"
            raise ValueError(msg)
        return self
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/domain/test_controller_dtos.py::TestTagBindingsDTO -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_domain/src/smart_pid_domain/dtos/controllers.py tests/domain/test_controller_dtos.py
git commit -m "feat(domain): update TagBindingsDTO with mode target/actual + int map validator"
```

---

### Task 3: DTOs — Add permitted_modes to CRUD DTOs

**Files:**
- Modify: `packages/smart_pid_domain/src/smart_pid_domain/dtos/controllers.py`
- Test: `tests/domain/test_controller_dtos.py`

**Context:** `permitted_modes` is stored in the DB and used by `loop_manager`, but it is NOT in the CRUD DTOs or the HMI dialog. We need it exposed through the API so the HMI can read/write it, and so the OPC-UA mode map tab can dynamically show only permitted modes.

- [ ] **Step 1: Write failing tests for permitted_modes in DTOs**

Add to `tests/domain/test_controller_dtos.py`:

```python
class TestPermittedModesDTOs:
    def test_create_default_permitted_modes(self) -> None:
        c = ControllerCreate(name="TIC-100")
        assert c.permitted_modes == ["MAN", "AUTO"]

    def test_create_custom_permitted_modes(self) -> None:
        c = ControllerCreate(name="TIC-100", permitted_modes=["MAN", "AUTO", "CAS"])
        assert "CAS" in c.permitted_modes

    def test_update_permitted_modes_optional(self) -> None:
        u = ControllerUpdate()
        assert u.permitted_modes is None

    def test_response_has_permitted_modes(self) -> None:
        r = ControllerResponse(
            id=1, name="TIC-100", description="", mode="AUTO",
            pv=0.0, sp=0.0, co=0.0,
            permitted_modes=["MAN", "AUTO", "CAS"],
        )
        assert r.permitted_modes == ["MAN", "AUTO", "CAS"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/domain/test_controller_dtos.py::TestPermittedModesDTOs -v`
Expected: FAIL — `permitted_modes` not a field

- [ ] **Step 3: Add permitted_modes to ControllerCreate, ControllerUpdate, ControllerResponse**

In `packages/smart_pid_domain/src/smart_pid_domain/dtos/controllers.py`:

In `ControllerCreate`, after `mode_normal: str = "AUTO"` (line ~106), add:

```python
    permitted_modes: list[str] = ["MAN", "AUTO"]
```

In `ControllerUpdate`, after `mode_normal: str | None = None` (line ~160), add:

```python
    permitted_modes: list[str] | None = None
```

In `ControllerResponse`, after `mode_normal: str = "AUTO"` (line ~213), add:

```python
    permitted_modes: list[str] = ["MAN", "AUTO"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/domain/test_controller_dtos.py::TestPermittedModesDTOs -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_domain/src/smart_pid_domain/dtos/controllers.py tests/domain/test_controller_dtos.py
git commit -m "feat(domain): add permitted_modes to ControllerCreate/Update/Response DTOs"
```

---

### Task 4: SQLite — DDL + Save/Load Mode Binding Columns

**Files:**
- Modify: `packages/smart_pid_core/src/smart_pid_core/adapters/outbound/sqlite_repo.py`
- Test: `tests/core/integration/test_sqlite_repo.py`

**Context:** The current DDL has `node_id_pv`, `node_id_sp`, `node_id_co`, `node_id_integral` columns only. The remaining tag fields (`node_id_bkcal_in`, etc.) are NOT in the DDL and NOT persisted. We add `node_id_mode_target`, `node_id_mode_actual`, `mode_int_map` as new columns. We use `CREATE TABLE IF NOT EXISTS` so no ALTER needed — just add to DDL.

- [ ] **Step 1: Write failing test for mode fields round-trip**

Add to `tests/core/integration/test_sqlite_repo.py`:

```python
class TestModeBindingRoundTrip:
    """TagBindings mode target/actual + int map are persisted and loaded."""

    @pytest.mark.asyncio
    async def test_save_and_load_mode_bindings(self, repo):
        from smart_pid_domain.models.controller import Controller, TagBindings

        ctrl = Controller(
            name="MODE-TEST",
            tag_bindings=TagBindings(
                node_id_pv="ns=2;s=PV",
                node_id_mode_target="ns=2;s=MODE_TGT",
                node_id_mode_actual="ns=2;s=MODE_ACT",
                mode_int_map={"MAN": 1, "AUTO": 2, "CAS": 4},
            ),
        )
        saved = await repo.save(ctrl)
        loaded = await repo.get(saved.id)

        assert loaded.tag_bindings.node_id_mode_target == "ns=2;s=MODE_TGT"
        assert loaded.tag_bindings.node_id_mode_actual == "ns=2;s=MODE_ACT"
        assert loaded.tag_bindings.mode_int_map == {"MAN": 1, "AUTO": 2, "CAS": 4}

    @pytest.mark.asyncio
    async def test_empty_mode_int_map_default(self, repo):
        from smart_pid_domain.models.controller import Controller

        ctrl = Controller(name="NO-MAP-TEST")
        saved = await repo.save(ctrl)
        loaded = await repo.get(saved.id)

        assert loaded.tag_bindings.node_id_mode_target == ""
        assert loaded.tag_bindings.node_id_mode_actual == ""
        assert loaded.tag_bindings.mode_int_map == {}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/core/integration/test_sqlite_repo.py::TestModeBindingRoundTrip -v`
Expected: FAIL — columns don't exist or not mapped

- [ ] **Step 3: Add columns to DDL**

In `packages/smart_pid_core/src/smart_pid_core/adapters/outbound/sqlite_repo.py`, inside the `_DDL` string, after the `node_id_integral` line (line ~57), add:

```sql
    node_id_mode_target TEXT NOT NULL DEFAULT '',
    node_id_mode_actual TEXT NOT NULL DEFAULT '',
    mode_int_map        TEXT NOT NULL DEFAULT '{}',
```

- [ ] **Step 4: Update `_controller_to_params` — add mode fields**

In `_controller_to_params`, after the `"node_id_integral"` entry (line ~323), add:

```python
            "node_id_mode_target": c.tag_bindings.node_id_mode_target,
            "node_id_mode_actual": c.tag_bindings.node_id_mode_actual,
            "mode_int_map": json.dumps(c.tag_bindings.mode_int_map),
```

Add `import json` at the top of the file if not already present.

- [ ] **Step 5: Update `_row_to_controller` — load mode fields**

In `_row_to_controller`, update the `tag_bindings=TagBindings(...)` block (line ~430) to include:

```python
            tag_bindings=TagBindings(
                node_id_pv=row["node_id_pv"],
                node_id_sp=row["node_id_sp"],
                node_id_co=row["node_id_co"],
                node_id_integral=row["node_id_integral"],
                node_id_mode_target=row["node_id_mode_target"],
                node_id_mode_actual=row["node_id_mode_actual"],
                mode_int_map=json.loads(row["mode_int_map"]),
            ),
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/core/integration/test_sqlite_repo.py::TestModeBindingRoundTrip -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/adapters/outbound/sqlite_repo.py tests/core/integration/test_sqlite_repo.py
git commit -m "feat(core): persist mode target/actual + int map in SQLite"
```

---

### Task 5: API Router — Conversion Functions

**Files:**
- Modify: `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/controllers.py`
- Test: `tests/core/integration/test_api_controllers.py`

- [ ] **Step 1: Write failing test for tag_bindings + permitted_modes in API**

Add to `tests/core/integration/test_api_controllers.py`:

```python
class TestModeBindingAPI:
    """API round-trip for mode target/actual + int map + permitted_modes."""

    @pytest.mark.asyncio
    async def test_create_with_mode_bindings(self, client):
        payload = {
            "name": "MODE-API-TEST",
            "tag_bindings": {
                "node_id_pv": "ns=2;s=PV",
                "node_id_mode_target": "ns=2;s=MODE_TGT",
                "node_id_mode_actual": "ns=2;s=MODE_ACT",
                "mode_int_map": {"MAN": 1, "AUTO": 2},
            },
            "permitted_modes": ["MAN", "AUTO", "CAS"],
        }
        resp = await client.post("/api/controllers", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["tag_bindings"]["node_id_mode_target"] == "ns=2;s=MODE_TGT"
        assert data["tag_bindings"]["node_id_mode_actual"] == "ns=2;s=MODE_ACT"
        assert data["tag_bindings"]["mode_int_map"] == {"MAN": 1, "AUTO": 2}
        assert set(data["permitted_modes"]) == {"MAN", "AUTO", "CAS"}

    @pytest.mark.asyncio
    async def test_no_old_node_id_mode_in_response(self, client):
        payload = {"name": "NO-OLD-MODE"}
        resp = await client.post("/api/controllers", json=payload)
        assert resp.status_code == 201
        assert "node_id_mode" not in resp.json()["tag_bindings"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/core/integration/test_api_controllers.py::TestModeBindingAPI -v`
Expected: FAIL

- [ ] **Step 3: Update `_to_response` — tag_bindings + permitted_modes**

In `_to_response`, replace the `tag_bindings=TagBindingsDTO(...)` block (lines ~95-106):

```python
        tag_bindings=TagBindingsDTO(
            node_id_pv=c.tag_bindings.node_id_pv,
            node_id_sp=c.tag_bindings.node_id_sp,
            node_id_co=c.tag_bindings.node_id_co,
            node_id_integral=c.tag_bindings.node_id_integral,
            node_id_bkcal_in=c.tag_bindings.node_id_bkcal_in,
            node_id_bkcal_out=c.tag_bindings.node_id_bkcal_out,
            node_id_kp=c.tag_bindings.node_id_kp,
            node_id_ti=c.tag_bindings.node_id_ti,
            node_id_td=c.tag_bindings.node_id_td,
            node_id_mode_target=c.tag_bindings.node_id_mode_target,
            node_id_mode_actual=c.tag_bindings.node_id_mode_actual,
            mode_int_map=c.tag_bindings.mode_int_map,
        ),
```

Add `permitted_modes` to the response, after `mode_normal`:

```python
        permitted_modes=sorted(str(m) for m in c.permitted_modes),
```

- [ ] **Step 4: Update `_body_to_controller` — tag_bindings + permitted_modes**

In `_body_to_controller`, replace the `tag_bindings=TagBindings(...)` block (lines ~186-194):

```python
        tag_bindings=TagBindings(
            node_id_pv=body.tag_bindings.node_id_pv,
            node_id_sp=body.tag_bindings.node_id_sp,
            node_id_co=body.tag_bindings.node_id_co,
            node_id_integral=body.tag_bindings.node_id_integral,
            node_id_bkcal_in=body.tag_bindings.node_id_bkcal_in,
            node_id_bkcal_out=body.tag_bindings.node_id_bkcal_out,
            node_id_kp=body.tag_bindings.node_id_kp,
            node_id_ti=body.tag_bindings.node_id_ti,
            node_id_td=body.tag_bindings.node_id_td,
            node_id_mode_target=body.tag_bindings.node_id_mode_target,
            node_id_mode_actual=body.tag_bindings.node_id_mode_actual,
            mode_int_map=body.tag_bindings.mode_int_map,
        ),
```

Add `permitted_modes` after `mode_normal`:

```python
        permitted_modes={ControllerMode(m) for m in body.permitted_modes},
```

- [ ] **Step 5: Update `_NESTED_BUILDERS` lambda — tag_bindings**

Replace the `"tag_bindings"` entry (lines ~254-259):

```python
    "tag_bindings": (TagBindingsDTO, lambda dto: TagBindings(
        node_id_pv=dto.node_id_pv, node_id_sp=dto.node_id_sp, node_id_co=dto.node_id_co,
        node_id_integral=dto.node_id_integral, node_id_bkcal_in=dto.node_id_bkcal_in,
        node_id_bkcal_out=dto.node_id_bkcal_out, node_id_kp=dto.node_id_kp,
        node_id_ti=dto.node_id_ti, node_id_td=dto.node_id_td,
        node_id_mode_target=dto.node_id_mode_target,
        node_id_mode_actual=dto.node_id_mode_actual,
        mode_int_map=dto.mode_int_map,
    )),
```

- [ ] **Step 6: Add PATCH handling for permitted_modes**

In the PATCH handler (wherever `_ENUM_FIELDS` or the update loop is), add handling for `permitted_modes`. If it appears in the update body, convert to `set[ControllerMode]` and assign to `controller.permitted_modes`:

```python
if body.permitted_modes is not None:
    controller.permitted_modes = {ControllerMode(m) for m in body.permitted_modes}
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `uv run pytest tests/core/integration/test_api_controllers.py::TestModeBindingAPI -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/controllers.py tests/core/integration/test_api_controllers.py
git commit -m "feat(core): update API router for mode target/actual + permitted_modes"
```

---

### Task 6: OPC-UA Adapter — Mode Read/Write with Integer Map

**Files:**
- Modify: `packages/smart_pid_core/src/smart_pid_core/adapters/outbound/opcua_adapter.py:199-471`
- Modify: `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/commands.py:148-154`
- Modify: `packages/smart_pid_core/src/smart_pid_core/main.py:156-162`
- Test: `tests/core/unit/test_opcua_adapter.py`

- [ ] **Step 1: Write failing tests for adapter mode methods**

Add to `tests/core/unit/test_opcua_adapter.py`:

```python
from smart_pid_domain.enums import ControllerMode


class TestOPCUAAdapterModeRegistration:
    def test_register_controller_stores_mode_fields(self):
        from smart_pid_core.adapters.outbound.opcua_adapter import OPCUAAdapter

        settings = _make_settings()
        adapter = OPCUAAdapter(settings=settings)
        adapter.register_controller(
            controller_id=1,
            node_id_pv="ns=2;s=PV",
            node_id_sp="ns=2;s=SP",
            node_id_co="ns=2;s=CO",
            node_id_mode_target="ns=2;s=MODE_TGT",
            node_id_mode_actual="ns=2;s=MODE_ACT",
            mode_int_map={"MAN": 1, "AUTO": 2, "CAS": 4},
        )
        tags = adapter._controllers[1]
        assert tags["mode_target"] == "ns=2;s=MODE_TGT"
        assert tags["mode_actual"] == "ns=2;s=MODE_ACT"
        assert tags["mode_int_map"] == {"MAN": 1, "AUTO": 2, "CAS": 4}
        assert tags["mode_int_map_inv"] == {1: "MAN", 2: "AUTO", 4: "CAS"}

    def test_register_controller_no_old_mode_key(self):
        from smart_pid_core.adapters.outbound.opcua_adapter import OPCUAAdapter

        settings = _make_settings()
        adapter = OPCUAAdapter(settings=settings)
        adapter.register_controller(
            controller_id=1,
            node_id_pv="ns=2;s=PV",
            node_id_sp="ns=2;s=SP",
            node_id_co="ns=2;s=CO",
        )
        assert "mode" not in adapter._controllers[1]

    def test_read_actual_mode_returns_none_when_offline(self):
        from smart_pid_core.adapters.outbound.opcua_adapter import OPCUAAdapter

        settings = _make_settings()
        adapter = OPCUAAdapter(settings=settings)
        adapter.register_controller(
            controller_id=1,
            node_id_pv="ns=2;s=PV",
            node_id_sp="ns=2;s=SP",
            node_id_co="ns=2;s=CO",
            node_id_mode_actual="ns=2;s=MODE_ACT",
            mode_int_map={"MAN": 1, "AUTO": 2},
        )
        result = adapter.read_actual_mode(1)
        assert result is None  # Not connected

    def test_read_actual_mode_returns_none_when_no_actual_node(self):
        from smart_pid_core.adapters.outbound.opcua_adapter import OPCUAAdapter

        settings = _make_settings()
        adapter = OPCUAAdapter(settings=settings)
        adapter.register_controller(
            controller_id=1,
            node_id_pv="ns=2;s=PV",
            node_id_sp="ns=2;s=SP",
            node_id_co="ns=2;s=CO",
        )
        result = adapter.read_actual_mode(1)
        assert result is None

    def test_write_target_mode_returns_false_when_offline(self):
        from smart_pid_core.adapters.outbound.opcua_adapter import OPCUAAdapter

        settings = _make_settings()
        adapter = OPCUAAdapter(settings=settings)
        adapter.register_controller(
            controller_id=1,
            node_id_pv="ns=2;s=PV",
            node_id_sp="ns=2;s=SP",
            node_id_co="ns=2;s=CO",
            node_id_mode_target="ns=2;s=MODE_TGT",
            mode_int_map={"MAN": 1, "AUTO": 2},
        )
        result = adapter.write_target_mode(1, ControllerMode.AUTO)
        assert result is False

    def test_write_target_mode_returns_false_when_mode_not_in_map(self):
        from smart_pid_core.adapters.outbound.opcua_adapter import OPCUAAdapter

        settings = _make_settings()
        adapter = OPCUAAdapter(settings=settings)
        adapter.register_controller(
            controller_id=1,
            node_id_pv="ns=2;s=PV",
            node_id_sp="ns=2;s=SP",
            node_id_co="ns=2;s=CO",
            node_id_mode_target="ns=2;s=MODE_TGT",
            mode_int_map={"MAN": 1},
        )
        # CAS is not in the map
        result = adapter.write_target_mode(1, ControllerMode.CAS)
        assert result is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/core/unit/test_opcua_adapter.py::TestOPCUAAdapterModeRegistration -v`
Expected: FAIL — parameter/method not found

- [ ] **Step 3: Update `register_controller` in OPC-UA adapter**

In `packages/smart_pid_core/src/smart_pid_core/adapters/outbound/opcua_adapter.py`, replace the `register_controller` method (lines ~199-226):

```python
    def register_controller(
        self,
        controller_id: int,
        node_id_pv: str,
        node_id_sp: str,
        node_id_co: str,
        node_id_integral: str = "",
        node_id_bkcal_in: str = "",
        node_id_bkcal_out: str = "",
        node_id_kp: str = "",
        node_id_ti: str = "",
        node_id_td: str = "",
        node_id_mode_target: str = "",
        node_id_mode_actual: str = "",
        mode_int_map: dict[str, int] | None = None,
    ) -> None:
        """Register a controller's OPC-UA node mappings."""
        int_map = mode_int_map or {}
        with self._lock:
            self._controllers[controller_id] = {
                "pv": node_id_pv,
                "sp": node_id_sp,
                "co": node_id_co,
                "integral": node_id_integral,
                "bkcal_in": node_id_bkcal_in,
                "bkcal_out": node_id_bkcal_out,
                "kp": node_id_kp,
                "ti": node_id_ti,
                "td": node_id_td,
                "mode_target": node_id_mode_target,
                "mode_actual": node_id_mode_actual,
                "mode_int_map": int_map,
                "mode_int_map_inv": {v: k for k, v in int_map.items()},
            }
```

- [ ] **Step 4: Replace `read_external_mode` with `read_actual_mode`**

Remove the `read_external_mode` and `_async_read_mode` methods. Add:

```python
    def read_actual_mode(self, controller_id: int) -> ControllerMode | None:
        """Read actual PID mode from DCS with integer-to-mode conversion.

        Returns None if: node not mapped, not connected, or integer not in map.
        Caller should treat None as SignalSeverity.BAD.
        """
        with self._lock:
            tags = self._controllers.get(controller_id, {})
            mode_id = tags.get("mode_actual", "")
            inv_map = tags.get("mode_int_map_inv", {})
            client = self._client

        if not mode_id or not self.is_connected or client is None:
            return None

        future = asyncio.run_coroutine_threadsafe(
            self._async_read_actual_mode(client, mode_id, inv_map),
            self._loop,
        )
        return future.result(timeout=self._timeout_s)

    async def _async_read_actual_mode(
        self, client, mode_id: str, inv_map: dict[int, str],
    ) -> ControllerMode | None:
        """Async read of mode node, converting integer to ControllerMode."""
        node = client.get_node(mode_id)
        value = await node.read_value()
        int_val = int(value)
        mode_str = inv_map.get(int_val)
        if mode_str is None:
            logger.warning("unmapped_mode_integer value=%d node=%s", int_val, mode_id)
            return None
        return ControllerMode(mode_str)
```

Add the import for `ControllerMode` at the top of the file if not present:

```python
from smart_pid_domain.enums import ControllerMode
```

- [ ] **Step 5: Add `write_target_mode`**

```python
    def write_target_mode(self, controller_id: int, mode: ControllerMode) -> bool:
        """Write target mode to DCS as integer. Returns False on failure."""
        with self._lock:
            tags = self._controllers.get(controller_id, {})
            target_id = tags.get("mode_target", "")
            int_map = tags.get("mode_int_map", {})
            client = self._client

        if not target_id or not self.is_connected or client is None:
            return False

        int_val = int_map.get(mode.value)
        if int_val is None:
            logger.warning("mode_not_in_map mode=%s controller=%d", mode.value, controller_id)
            return False

        future = asyncio.run_coroutine_threadsafe(
            self._async_write_value(client, target_id, int_val),
            self._loop,
        )
        try:
            future.result(timeout=self._timeout_s)
            return True
        except Exception:
            logger.exception("write_target_mode_failed controller=%d", controller_id)
            return False
```

- [ ] **Step 6: Run unit tests to verify they pass**

Run: `uv run pytest tests/core/unit/test_opcua_adapter.py -v`
Expected: PASS

- [ ] **Step 7: Update `main.py` — pass new fields to register_controller**

In `packages/smart_pid_core/src/smart_pid_core/main.py`, update the `register_controller` call (lines ~156-162):

```python
                opcua_adapter.register_controller(
                    controller_id=ctrl.id,
                    node_id_pv=tb.node_id_pv,
                    node_id_sp=tb.node_id_sp,
                    node_id_co=tb.node_id_co,
                    node_id_integral=tb.node_id_integral,
                    node_id_mode_target=tb.node_id_mode_target,
                    node_id_mode_actual=tb.node_id_mode_actual,
                    mode_int_map=tb.mode_int_map,
                )
```

- [ ] **Step 8: Update `commands.py` — use `read_actual_mode`**

In `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/commands.py`, replace the `read_external_mode` call (lines ~148-154):

```python
    if opcua is not None:
        ext_mode = opcua.read_actual_mode(controller_id)
        if ext_mode is not None and ext_mode != ControllerMode.AUTO:
            raise HTTPException(
                status_code=409,
                detail=f"External PID is in {ext_mode.value} mode — tuning write-back requires Auto",
            )
```

Add import at top if needed:

```python
from smart_pid_domain.enums import ControllerMode
```

- [ ] **Step 9: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/adapters/outbound/opcua_adapter.py \
       packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/commands.py \
       packages/smart_pid_core/src/smart_pid_core/main.py \
       tests/core/unit/test_opcua_adapter.py
git commit -m "feat(core): OPC-UA adapter read_actual_mode + write_target_mode with int map"
```

---

### Task 7: HMI — Permitted Modes Selector in General Tab

**Files:**
- Modify: `packages/smart_pid_hmi/src/smart_pid_hmi/widgets/controller_dialog.py`
- Test: `tests/hmi/widgets/test_controller_dialog.py`

**Context:** The General tab currently has `mode_normal` combo but no way to configure `permitted_modes`. We add a checkbox group for all `ControllerMode` members. This widget emits a signal used by Task 8 to filter the mode int map.

- [ ] **Step 1: Write failing tests for permitted_modes in dialog**

Add to `tests/hmi/widgets/test_controller_dialog.py`. First update `EDIT_DATA` to include `permitted_modes`:

```python
# In EDIT_DATA dict, add after "mode_normal": "MAN":
    "permitted_modes": ["MAN", "AUTO", "CAS"],
```

Then add test class:

```python
class TestPermittedModes:
    """Verify permitted_modes checkbox group in General tab."""

    def test_default_permitted_modes(self, dialog):
        """Create mode defaults to MAN + AUTO checked."""
        data = dialog.get_controller_data()
        assert set(data["permitted_modes"]) == {"MAN", "AUTO"}

    def test_edit_mode_loads_permitted_modes(self, edit_dialog):
        data = edit_dialog.get_controller_data()
        assert set(data["permitted_modes"]) == {"MAN", "AUTO", "CAS"}

    def test_check_additional_mode(self, dialog, qtbot):
        dialog._permitted_mode_checks["CAS"].setChecked(True)
        data = dialog.get_controller_data()
        assert "CAS" in data["permitted_modes"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/hmi/widgets/test_controller_dialog.py::TestPermittedModes -v`
Expected: FAIL — `permitted_modes` not in output, `_permitted_mode_checks` not found

- [ ] **Step 3: Add permitted_modes checkbox group to General tab**

In `packages/smart_pid_hmi/src/smart_pid_hmi/widgets/controller_dialog.py`, in `_build_general_tab`, after the `mode_normal` combo (line ~202), add:

```python
        # Permitted Modes — checkbox group
        from PySide6.QtWidgets import QHBoxLayout
        perm_group = QGroupBox("Permitted Modes")
        perm_layout = QHBoxLayout()
        self._permitted_mode_checks: dict[str, QCheckBox] = {}
        for mode in ControllerMode:
            cb = QCheckBox(mode.value)
            cb.setChecked(mode.value in ("MAN", "AUTO"))  # defaults
            self._permitted_mode_checks[mode.value] = cb
            perm_layout.addWidget(cb)
        perm_group.setLayout(perm_layout)
        form.addRow(perm_group)
```

- [ ] **Step 4: Update `_populate` for permitted_modes**

In the `_populate` method, after `self._set_combo(self._mode_normal, ...)` (line ~475), add:

```python
        # Permitted Modes
        perm = set(data.get("permitted_modes", ["MAN", "AUTO"]))
        for mode_str, cb in self._permitted_mode_checks.items():
            cb.setChecked(mode_str in perm)
```

- [ ] **Step 5: Update `get_controller_data` for permitted_modes**

In `get_controller_data`, after the `"mode_normal"` entry, add:

```python
            "permitted_modes": [
                mode_str for mode_str, cb in self._permitted_mode_checks.items()
                if cb.isChecked()
            ],
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/hmi/widgets/test_controller_dialog.py::TestPermittedModes -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add packages/smart_pid_hmi/src/smart_pid_hmi/widgets/controller_dialog.py \
       tests/hmi/widgets/test_controller_dialog.py
git commit -m "feat(hmi): add permitted_modes checkbox group to controller dialog General tab"
```

---

### Task 8: HMI — OPC-UA Tab Mode Target/Actual + Integer Map

**Files:**
- Modify: `packages/smart_pid_hmi/src/smart_pid_hmi/widgets/controller_dialog.py`
- Test: `tests/hmi/widgets/test_controller_dialog.py`

**Context:** Replace the single "Mode" row in the OPC-UA tab with "Mode (Target)" + "Mode (Actual)" rows and a "Mode Integer Mapping" group with dynamic visibility tied to the permitted_modes checkboxes.

- [ ] **Step 1: Update EDIT_DATA and write failing tests**

In `tests/hmi/widgets/test_controller_dialog.py`, update `EDIT_DATA["tag_bindings"]` to replace `"node_id_mode": ""` with:

```python
        "node_id_mode_target": "ns=2;s=TIC101.MODE_TGT",
        "node_id_mode_actual": "ns=2;s=TIC101.MODE_ACT",
        "mode_int_map": {"MAN": 1, "AUTO": 2, "CAS": 4},
```

Add test class:

```python
class TestModeIntMapping:
    """Verify OPC-UA mode target/actual + integer mapping in dialog."""

    def test_tag_bindings_keys_updated(self, dialog):
        data = dialog.get_controller_data()
        tb = data["tag_bindings"]
        assert "node_id_mode_target" in tb
        assert "node_id_mode_actual" in tb
        assert "mode_int_map" in tb
        assert "node_id_mode" not in tb

    def test_edit_populates_mode_target(self, edit_dialog):
        assert edit_dialog._tag_mode_target.text() == "ns=2;s=TIC101.MODE_TGT"

    def test_edit_populates_mode_actual(self, edit_dialog):
        assert edit_dialog._tag_mode_actual.text() == "ns=2;s=TIC101.MODE_ACT"

    def test_edit_populates_mode_int_map(self, edit_dialog):
        data = edit_dialog.get_controller_data()
        assert data["tag_bindings"]["mode_int_map"]["MAN"] == 1
        assert data["tag_bindings"]["mode_int_map"]["AUTO"] == 2
        assert data["tag_bindings"]["mode_int_map"]["CAS"] == 4

    def test_mode_map_visibility_follows_permitted_modes(self, dialog, qtbot):
        """Only modes checked in permitted_modes are visible in the mode map."""
        # Default: MAN + AUTO checked
        lbl_man, spin_man = dialog._mode_map_widgets["MAN"]
        lbl_cas, spin_cas = dialog._mode_map_widgets["CAS"]
        assert lbl_man.isVisible()
        assert spin_man.isVisible()
        assert not lbl_cas.isVisible()
        assert not spin_cas.isVisible()

        # Check CAS in permitted_modes
        dialog._permitted_mode_checks["CAS"].setChecked(True)
        assert lbl_cas.isVisible()
        assert spin_cas.isVisible()

    def test_mode_map_only_collects_visible_nonzero(self, dialog, qtbot):
        """get_controller_data only includes visible modes with value > 0."""
        dialog._mode_map_widgets["MAN"][1].setValue(1)
        dialog._mode_map_widgets["AUTO"][1].setValue(2)
        # CAS is not permitted (not visible), even if we set its value
        dialog._mode_map_widgets["CAS"][1].setValue(4)

        data = dialog.get_controller_data()
        int_map = data["tag_bindings"]["mode_int_map"]
        assert int_map == {"MAN": 1, "AUTO": 2}
        assert "CAS" not in int_map

    def test_zero_value_excluded_from_map(self, dialog, qtbot):
        """Modes with value 0 are excluded from mode_int_map."""
        dialog._mode_map_widgets["MAN"][1].setValue(0)
        dialog._mode_map_widgets["AUTO"][1].setValue(2)
        data = dialog.get_controller_data()
        int_map = data["tag_bindings"]["mode_int_map"]
        assert "MAN" not in int_map
        assert int_map == {"AUTO": 2}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/hmi/widgets/test_controller_dialog.py::TestModeIntMapping -v`
Expected: FAIL

- [ ] **Step 3: Replace "Mode" row with Target/Actual in OPC-UA tab**

In `_build_opcua_tab`, replace the `tag_fields` list to use the new mode rows:

```python
        tag_fields = [
            ("PV", "ns=2;s=PV"), ("SP", "ns=2;s=SP"), ("CO", "ns=2;s=CO"),
            ("Integral", ""), ("BkCal In", ""), ("BkCal Out", ""),
            ("Kp", ""), ("Ti", ""), ("Td", ""),
            ("Mode (Target)", ""), ("Mode (Actual)", ""),
        ]
        attr_map = {
            "PV": "_tag_pv", "SP": "_tag_sp", "CO": "_tag_co",
            "Integral": "_tag_integral", "BkCal In": "_tag_bkcal_in",
            "BkCal Out": "_tag_bkcal_out", "Kp": "_tag_kp",
            "Ti": "_tag_ti", "Td": "_tag_td",
            "Mode (Target)": "_tag_mode_target", "Mode (Actual)": "_tag_mode_actual",
        }
```

- [ ] **Step 4: Add Mode Integer Mapping group to OPC-UA tab**

After the tag fields loop in `_build_opcua_tab`, add the mapping group:

```python
        # Mode Integer Mapping group
        next_row = len(tag_fields)
        map_group = QGroupBox("Mode Integer Mapping")
        map_layout = QFormLayout()
        self._mode_map_widgets: dict[str, tuple[QLabel, QSpinBox]] = {}

        for mode in ControllerMode:
            lbl = QLabel(f"{mode.value}:")
            spin = QSpinBox()
            spin.setRange(0, 255)
            spin.setValue(0)
            spin.setToolTip("0 = not mapped")
            self._mode_map_widgets[mode.value] = (lbl, spin)
            map_layout.addRow(lbl, spin)

        map_group.setLayout(map_layout)
        grid.addWidget(map_group, next_row, 0, 1, 3)

        # Connect permitted_modes checkboxes to visibility refresh
        for cb in self._permitted_mode_checks.values():
            cb.toggled.connect(self._refresh_mode_map_visibility)
        self._refresh_mode_map_visibility()
```

- [ ] **Step 5: Add `_refresh_mode_map_visibility` method**

```python
    def _refresh_mode_map_visibility(self) -> None:
        """Show/hide mode map rows based on permitted_modes checkboxes."""
        for mode_str, (lbl, spin) in self._mode_map_widgets.items():
            cb = self._permitted_mode_checks.get(mode_str)
            visible = cb.isChecked() if cb else False
            lbl.setVisible(visible)
            spin.setVisible(visible)
```

- [ ] **Step 6: Update `_populate` for mode tag bindings + int map**

In `_populate`, replace the old `tag_bindings` section. Remove the `"node_id_mode": self._tag_mode` entry from `tag_map` and add the new fields:

```python
        tag_map = {
            "node_id_pv": self._tag_pv,
            "node_id_sp": self._tag_sp,
            "node_id_co": self._tag_co,
            "node_id_integral": self._tag_integral,
            "node_id_bkcal_in": self._tag_bkcal_in,
            "node_id_bkcal_out": self._tag_bkcal_out,
            "node_id_kp": self._tag_kp,
            "node_id_ti": self._tag_ti,
            "node_id_td": self._tag_td,
            "node_id_mode_target": self._tag_mode_target,
            "node_id_mode_actual": self._tag_mode_actual,
        }
        for key, widget in tag_map.items():
            widget.setText(tags.get(key, ""))

        # Mode integer mapping
        int_map = tags.get("mode_int_map", {})
        for mode_str, (lbl, spin) in self._mode_map_widgets.items():
            spin.setValue(int_map.get(mode_str, 0))
```

- [ ] **Step 7: Update `get_controller_data` for mode bindings + int map**

In `get_controller_data`, replace the `tag_bindings` dict:

```python
            "tag_bindings": {
                "node_id_pv": self._tag_pv.text().strip(),
                "node_id_sp": self._tag_sp.text().strip(),
                "node_id_co": self._tag_co.text().strip(),
                "node_id_integral": self._tag_integral.text().strip(),
                "node_id_bkcal_in": self._tag_bkcal_in.text().strip(),
                "node_id_bkcal_out": self._tag_bkcal_out.text().strip(),
                "node_id_kp": self._tag_kp.text().strip(),
                "node_id_ti": self._tag_ti.text().strip(),
                "node_id_td": self._tag_td.text().strip(),
                "node_id_mode_target": self._tag_mode_target.text().strip(),
                "node_id_mode_actual": self._tag_mode_actual.text().strip(),
                "mode_int_map": {
                    mode_str: spin.value()
                    for mode_str, (lbl, spin) in self._mode_map_widgets.items()
                    if lbl.isVisible() and spin.value() > 0
                },
            },
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `uv run pytest tests/hmi/widgets/test_controller_dialog.py -v`
Expected: ALL PASS (including the existing tests after EDIT_DATA update)

- [ ] **Step 9: Run full test suite**

Run: `uv run pytest tests/ -v`
Expected: ALL PASS (no regressions)

- [ ] **Step 10: Commit**

```bash
git add packages/smart_pid_hmi/src/smart_pid_hmi/widgets/controller_dialog.py \
       tests/hmi/widgets/test_controller_dialog.py
git commit -m "feat(hmi): OPC-UA tab mode target/actual + dynamic integer mapping"
```
