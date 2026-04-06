# Loop Config Dialog Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a gear button to controller cards that opens a full-field edit dialog, expand DTOs/API to carry all 30+ controller fields, and hide the P&ID tab.

**Architecture:** Reuse the existing `AddControllerDialog` (rename to `ControllerDialog`) for both create and edit modes. Expand `ControllerCreate`/`ControllerUpdate`/`ControllerResponse` DTOs with pydantic sub-models matching all domain Controller fields. Expand the backend router to map all fields. Add `update_controller` to HMI API client.

**Tech Stack:** PySide6, FastAPI, pydantic v2, httpx, pytest + pytest-asyncio

**Spec:** `docs/superpowers/specs/2026-04-05-loop-config-dialog-design.md`

---

## Task 1: Expand DTOs with Full Controller Fields

**Files:**
- Modify: `packages/smart_pid_domain/src/smart_pid_domain/dtos/controllers.py`
- Test: `tests/domain/test_controller_dtos.py`

- [ ] **Step 1: Write failing tests for new DTO sub-models**

Create `tests/domain/test_controller_dtos.py`:

```python
"""Tests for expanded controller DTOs — full 30+ field coverage."""
from __future__ import annotations

import pytest

from smart_pid_domain.dtos.controllers import (
    AIConfigDTO,
    ControllerCreate,
    ControllerResponse,
    ControllerUpdate,
    ControlOptsDTO,
    IOOptsDTO,
    PIDParamsDTO,
    ScaleConfigDTO,
    TagBindingsDTO,
)


class TestSubModels:
    def test_pid_params_defaults(self):
        p = PIDParamsDTO()
        assert p.gain == 1.0
        assert p.reset == 10.0
        assert p.rate == 0.0
        assert p.alpha == 0.125
        assert p.deadband == 0.0

    def test_scale_config_defaults(self):
        s = ScaleConfigDTO()
        assert s.eu_min == 0.0
        assert s.eu_max == 100.0
        assert s.unit == ""

    def test_ai_config_defaults(self):
        a = AIConfigDTO()
        assert a.engine == "NONE"
        assert a.objective == "DISTURBANCE_REJECTION"
        assert a.process_speed == "MEDIUM"
        assert a.dead_time_l == 1.0

    def test_tag_bindings_defaults(self):
        t = TagBindingsDTO()
        assert t.node_id_pv == ""
        assert t.node_id_mode == ""

    def test_control_opts_defaults(self):
        c = ControlOptsDTO()
        assert c.direct_acting is False
        assert c.track_enable is False

    def test_io_opts_defaults(self):
        io = IOOptsDTO()
        assert io.low_cutoff is False
        assert io.increase_to_close is False


class TestControllerCreateExpanded:
    def test_minimal_create(self):
        c = ControllerCreate(name="TIC-101")
        assert c.name == "TIC-101"
        assert c.execution_mode == "DDC"
        assert c.pid_params.gain == 1.0
        assert c.ai_config.engine == "NONE"

    def test_full_create(self):
        c = ControllerCreate(
            name="TIC-101",
            execution_mode="SUPERVISORY",
            pid_params=PIDParamsDTO(gain=2.0, reset=5.0),
            ai_config=AIConfigDTO(engine="FUZZY"),
            tag_bindings=TagBindingsDTO(node_id_pv="ns=2;s=PV"),
        )
        assert c.execution_mode == "SUPERVISORY"
        assert c.pid_params.gain == 2.0
        assert c.ai_config.engine == "FUZZY"
        assert c.tag_bindings.node_id_pv == "ns=2;s=PV"


class TestControllerUpdateExpanded:
    def test_all_optional(self):
        u = ControllerUpdate()
        assert u.name is None
        assert u.pid_params is None
        assert u.ai_config is None

    def test_partial_update(self):
        u = ControllerUpdate(
            description="Updated",
            pid_params=PIDParamsDTO(gain=3.0),
        )
        assert u.description == "Updated"
        assert u.pid_params.gain == 3.0


class TestControllerResponseExpanded:
    def test_has_all_fields(self):
        r = ControllerResponse(
            id=1, name="TIC-101", description="", mode="AUTO",
            pv=50.0, sp=50.0, co=45.0,
        )
        assert r.execution_mode == "DDC"
        assert r.pid_params.gain == 1.0
        assert r.ai_config.engine == "NONE"
        assert r.tag_bindings.node_id_pv == ""
        assert r.control_opts.direct_acting is False
        assert r.io_opts.low_cutoff is False
        assert r.pv_scale.eu_min == 0.0
        assert r.out_scale.eu_max == 100.0
        assert r.shed_opt == "MAN"
        assert r.tuning_write_mode == "APPROVAL_REQUIRED"

    def test_round_trip_json(self):
        r = ControllerResponse(
            id=1, name="TIC-101", description="Temp", mode="AUTO",
            pv=50.0, sp=50.0, co=45.0,
            pid_params=PIDParamsDTO(gain=2.5),
            ai_config=AIConfigDTO(engine="FUZZY"),
        )
        data = r.model_dump()
        r2 = ControllerResponse.model_validate(data)
        assert r2.pid_params.gain == 2.5
        assert r2.ai_config.engine == "FUZZY"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/domain/test_controller_dtos.py -v`
Expected: ImportError — `PIDParamsDTO` etc. not found

- [ ] **Step 3: Implement expanded DTOs**

Replace `packages/smart_pid_domain/src/smart_pid_domain/dtos/controllers.py` with:

```python
"""Controller CRUD DTOs — full field coverage matching domain Controller."""
from __future__ import annotations

from pydantic import BaseModel


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
    no_out_limits_in_manual: bool = False
    obey_sp_limits_if_cas: bool = False
    track_in_manual: bool = False
    track_enable: bool = False
    direct_acting: bool = False
    sp_track_retained_target: bool = False
    sp_pv_track_in_lo_or_iman: bool = False
    sp_pv_track_in_rout: bool = False
    sp_pv_track_in_man: bool = False
    use_pv_for_bkcal_out: bool = False


class IOOptsDTO(BaseModel):
    low_cutoff: bool = False
    target_to_man_if_fault: bool = False
    fault_state_to_value: bool = False
    increase_to_close: bool = False
    sp_pv_track_in_lo_or_iman: bool = False
    sp_pv_track_in_man: bool = False


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


class ControllerUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    execution_mode: str | None = None
    scan_rate_ms: int | None = None
    pid_structure: str | None = None
    integral_type: str | None = None
    mode_normal: str | None = None
    pid_params: PIDParamsDTO | None = None
    pv_scale: ScaleConfigDTO | None = None
    out_scale: ScaleConfigDTO | None = None
    tag_bindings: TagBindingsDTO | None = None
    control_opts: ControlOptsDTO | None = None
    io_opts: IOOptsDTO | None = None
    ai_config: AIConfigDTO | None = None
    sp_hi_lim: float | None = None
    sp_lo_lim: float | None = None
    sp_rate_up: float | None = None
    sp_rate_dn: float | None = None
    out_hi_lim: float | None = None
    out_lo_lim: float | None = None
    arw_hi_lim: float | None = None
    arw_lo_lim: float | None = None
    pv_ftime: float | None = None
    sp_ftime: float | None = None
    low_cut: float | None = None
    ff_enable: bool | None = None
    ff_gain: float | None = None
    shed_opt: str | None = None
    shed_time_s: float | None = None
    tuning_write_mode: str | None = None
    max_tuning_change_pct: float | None = None


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

- [ ] **Step 4: Update `dtos/__init__.py` exports**

Add to the imports in `packages/smart_pid_domain/src/smart_pid_domain/dtos/__init__.py`:

```python
from smart_pid_domain.dtos.controllers import (
    AIConfigDTO,
    ControllerCreate,
    ControllerResponse,
    ControllerUpdate,
    ControlOptsDTO,
    IOOptsDTO,
    PIDParamsDTO,
    ScaleConfigDTO,
    TagBindingsDTO,
)
```

Add to `__all__`: `"AIConfigDTO"`, `"ControlOptsDTO"`, `"IOOptsDTO"`, `"PIDParamsDTO"`, `"ScaleConfigDTO"`, `"TagBindingsDTO"`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/domain/test_controller_dtos.py -v`
Expected: All tests PASS

- [ ] **Step 6: Run existing DTO tests to check backward compat**

Run: `uv run pytest tests/domain/test_dtos.py -v`
Expected: All PASS (existing tests create ControllerResponse with basic fields only — these still work because new fields have defaults)

- [ ] **Step 7: Commit**

```bash
git add packages/smart_pid_domain/src/smart_pid_domain/dtos/controllers.py \
       packages/smart_pid_domain/src/smart_pid_domain/dtos/__init__.py \
       tests/domain/test_controller_dtos.py
git commit -m "feat(domain): expand controller DTOs with full 30+ fields"
```

---

## Task 2: Expand Backend API Router

**Files:**
- Modify: `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/controllers.py`
- Test: `tests/core/integration/test_api_controllers.py`

- [ ] **Step 1: Write failing tests for full-field create/update/get**

Add to `tests/core/integration/test_api_controllers.py`:

```python
class TestFullFieldCreateAndGet:
    @pytest.mark.asyncio
    async def test_create_with_all_fields(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        resp = await client.post(
            "/controllers",
            json={
                "name": "TIC-201",
                "description": "Temperature loop",
                "execution_mode": "SUPERVISORY",
                "scan_rate_ms": 500,
                "pid_structure": "PARALLEL",
                "integral_type": "GAIN_KI",
                "pid_params": {"gain": 2.5, "reset": 5.0, "rate": 1.0, "alpha": 0.1, "deadband": 0.5},
                "pv_scale": {"eu_min": -50.0, "eu_max": 200.0, "unit": "degC"},
                "out_scale": {"eu_min": 0.0, "eu_max": 100.0, "unit": "%"},
                "ai_config": {"engine": "FUZZY", "objective": "SP_TRACKING", "process_speed": "SLOW"},
                "tag_bindings": {"node_id_pv": "ns=2;s=TIC201.PV", "node_id_sp": "ns=2;s=TIC201.SP"},
                "sp_hi_lim": 200.0,
                "sp_lo_lim": -50.0,
                "arw_hi_lim": 110.0,
                "shed_opt": "AUTO",
            },
            headers=admin_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["execution_mode"] == "SUPERVISORY"
        assert data["pid_params"]["gain"] == 2.5
        assert data["pv_scale"]["unit"] == "degC"
        assert data["ai_config"]["engine"] == "FUZZY"
        assert data["tag_bindings"]["node_id_pv"] == "ns=2;s=TIC201.PV"
        assert data["sp_hi_lim"] == 200.0
        assert data["arw_hi_lim"] == 110.0
        assert data["shed_opt"] == "AUTO"

    @pytest.mark.asyncio
    async def test_get_returns_all_fields(
        self, client: AsyncClient, admin_headers: dict[str, str], user_headers: dict[str, str]
    ) -> None:
        create_resp = await client.post(
            "/controllers",
            json={
                "name": "FIC-301",
                "pid_params": {"gain": 3.0},
                "ai_config": {"engine": "RL"},
            },
            headers=admin_headers,
        )
        cid = create_resp.json()["id"]
        resp = await client.get(f"/controllers/{cid}", headers=user_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["pid_params"]["gain"] == 3.0
        assert data["ai_config"]["engine"] == "RL"
        assert "tag_bindings" in data
        assert "control_opts" in data
        assert "io_opts" in data


class TestFullFieldUpdate:
    @pytest.mark.asyncio
    async def test_update_nested_fields(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        create_resp = await client.post(
            "/controllers",
            json={"name": "PIC-401"},
            headers=admin_headers,
        )
        cid = create_resp.json()["id"]
        resp = await client.put(
            f"/controllers/{cid}",
            json={
                "pid_params": {"gain": 5.0, "reset": 20.0},
                "ai_config": {"engine": "FUZZY", "objective": "SURGE_LEVEL"},
                "tag_bindings": {"node_id_pv": "ns=4;s=PIC401.PV"},
                "execution_mode": "SUPERVISORY",
                "arw_hi_lim": 95.0,
            },
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["pid_params"]["gain"] == 5.0
        assert data["pid_params"]["reset"] == 20.0
        assert data["ai_config"]["engine"] == "FUZZY"
        assert data["ai_config"]["objective"] == "SURGE_LEVEL"
        assert data["tag_bindings"]["node_id_pv"] == "ns=4;s=PIC401.PV"
        assert data["execution_mode"] == "SUPERVISORY"
        assert data["arw_hi_lim"] == 95.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/core/integration/test_api_controllers.py::TestFullFieldCreateAndGet -v`
Expected: FAIL — response missing `execution_mode`, `pid_params`, etc.

- [ ] **Step 3: Update `_to_response()` to include all fields**

In `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/controllers.py`, replace the `_to_response` function:

```python
from smart_pid_domain.dtos.controllers import (
    AIConfigDTO,
    ControllerCreate,
    ControllerResponse,
    ControllerUpdate,
    ControlOptsDTO,
    IOOptsDTO,
    PIDParamsDTO,
    ScaleConfigDTO,
    TagBindingsDTO,
)


def _to_response(c: Controller) -> ControllerResponse:
    """Convert domain Controller to API response DTO."""
    return ControllerResponse(
        id=c.id,
        name=c.name,
        description=c.description,
        mode=str(c.mode_normal),
        pv=0.0,
        sp=0.0,
        co=0.0,
        execution_mode=str(c.execution_mode),
        scan_rate_ms=c.scan_rate_ms,
        pid_structure=str(c.pid_structure),
        integral_type=str(c.integral_type),
        mode_normal=str(c.mode_normal),
        pid_params=PIDParamsDTO(
            gain=c.pid_params.gain,
            reset=c.pid_params.reset,
            rate=c.pid_params.rate,
            alpha=c.pid_params.alpha,
            deadband=c.pid_params.deadband,
        ),
        pv_scale=ScaleConfigDTO(
            eu_min=c.pv_scale.eu_min,
            eu_max=c.pv_scale.eu_max,
            unit=c.pv_scale.unit,
        ),
        out_scale=ScaleConfigDTO(
            eu_min=c.out_scale.eu_min,
            eu_max=c.out_scale.eu_max,
            unit=c.out_scale.unit,
        ),
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
            node_id_mode=c.tag_bindings.node_id_mode,
        ),
        control_opts=ControlOptsDTO(
            no_out_limits_in_manual=c.control_opts.no_out_limits_in_manual,
            obey_sp_limits_if_cas=c.control_opts.obey_sp_limits_if_cas,
            track_in_manual=c.control_opts.track_in_manual,
            track_enable=c.control_opts.track_enable,
            direct_acting=c.control_opts.direct_acting,
            sp_track_retained_target=c.control_opts.sp_track_retained_target,
            sp_pv_track_in_lo_or_iman=c.control_opts.sp_pv_track_in_lo_or_iman,
            sp_pv_track_in_rout=c.control_opts.sp_pv_track_in_rout,
            sp_pv_track_in_man=c.control_opts.sp_pv_track_in_man,
            use_pv_for_bkcal_out=c.control_opts.use_pv_for_bkcal_out,
        ),
        io_opts=IOOptsDTO(
            low_cutoff=c.io_opts.low_cutoff,
            target_to_man_if_fault=c.io_opts.target_to_man_if_fault,
            fault_state_to_value=c.io_opts.fault_state_to_value,
            increase_to_close=c.io_opts.increase_to_close,
            sp_pv_track_in_lo_or_iman=c.io_opts.sp_pv_track_in_lo_or_iman,
            sp_pv_track_in_man=c.io_opts.sp_pv_track_in_man,
        ),
        ai_config=AIConfigDTO(
            engine=str(c.ai_config.engine),
            objective=str(c.ai_config.objective),
            process_speed=str(c.ai_config.process_speed),
            dead_time_l=c.ai_config.dead_time_l,
            limit_min=c.ai_config.limit_min,
            limit_max=c.ai_config.limit_max,
        ),
        sp_hi_lim=c.sp_hi_lim,
        sp_lo_lim=c.sp_lo_lim,
        sp_rate_up=c.sp_rate_up,
        sp_rate_dn=c.sp_rate_dn,
        out_hi_lim=c.out_hi_lim,
        out_lo_lim=c.out_lo_lim,
        arw_hi_lim=c.arw_hi_lim,
        arw_lo_lim=c.arw_lo_lim,
        pv_ftime=c.pv_ftime,
        sp_ftime=c.sp_ftime,
        low_cut=c.low_cut,
        ff_enable=c.ff_enable,
        ff_gain=c.ff_gain,
        shed_opt=str(c.shed_opt),
        shed_time_s=c.shed_time_s,
        tuning_write_mode=str(c.tuning_write_mode),
        max_tuning_change_pct=c.max_tuning_change_pct,
    )
```

- [ ] **Step 4: Add `_body_to_controller()` helper and update `create_controller`**

Add a helper function that builds a full Controller from ControllerCreate, and update `create_controller` to use it:

```python
def _body_to_controller(body: ControllerCreate) -> Controller:
    """Build a full Controller from a ControllerCreate DTO."""
    return Controller(
        id=0,
        name=body.name,
        description=body.description,
        execution_mode=ExecutionMode(body.execution_mode),
        scan_rate_ms=body.scan_rate_ms,
        pid_structure=PIDStructure(body.pid_structure),
        integral_type=IntegralType(body.integral_type),
        mode_normal=ControllerMode(body.mode_normal),
        pid_params=PIDParams(
            gain=body.pid_params.gain,
            reset=body.pid_params.reset,
            rate=body.pid_params.rate,
            alpha=body.pid_params.alpha,
            deadband=body.pid_params.deadband,
        ),
        pv_scale=ScaleConfig(body.pv_scale.eu_min, body.pv_scale.eu_max, body.pv_scale.unit),
        out_scale=ScaleConfig(body.out_scale.eu_min, body.out_scale.eu_max, body.out_scale.unit),
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
            node_id_mode=body.tag_bindings.node_id_mode,
        ),
        control_opts=ControlOpts(
            no_out_limits_in_manual=body.control_opts.no_out_limits_in_manual,
            obey_sp_limits_if_cas=body.control_opts.obey_sp_limits_if_cas,
            track_in_manual=body.control_opts.track_in_manual,
            track_enable=body.control_opts.track_enable,
            direct_acting=body.control_opts.direct_acting,
            sp_track_retained_target=body.control_opts.sp_track_retained_target,
            sp_pv_track_in_lo_or_iman=body.control_opts.sp_pv_track_in_lo_or_iman,
            sp_pv_track_in_rout=body.control_opts.sp_pv_track_in_rout,
            sp_pv_track_in_man=body.control_opts.sp_pv_track_in_man,
            use_pv_for_bkcal_out=body.control_opts.use_pv_for_bkcal_out,
        ),
        io_opts=IOOpts(
            low_cutoff=body.io_opts.low_cutoff,
            target_to_man_if_fault=body.io_opts.target_to_man_if_fault,
            fault_state_to_value=body.io_opts.fault_state_to_value,
            increase_to_close=body.io_opts.increase_to_close,
            sp_pv_track_in_lo_or_iman=body.io_opts.sp_pv_track_in_lo_or_iman,
            sp_pv_track_in_man=body.io_opts.sp_pv_track_in_man,
        ),
        ai_config=AIConfig(
            engine=AIEngine(body.ai_config.engine),
            objective=ControlObjective(body.ai_config.objective),
            process_speed=ProcessSpeed(body.ai_config.process_speed),
            dead_time_l=body.ai_config.dead_time_l,
            limit_min=body.ai_config.limit_min,
            limit_max=body.ai_config.limit_max,
        ),
        sp_hi_lim=body.sp_hi_lim,
        sp_lo_lim=body.sp_lo_lim,
        sp_rate_up=body.sp_rate_up,
        sp_rate_dn=body.sp_rate_dn,
        out_hi_lim=body.out_hi_lim,
        out_lo_lim=body.out_lo_lim,
        arw_hi_lim=body.arw_hi_lim,
        arw_lo_lim=body.arw_lo_lim,
        pv_ftime=body.pv_ftime,
        sp_ftime=body.sp_ftime,
        low_cut=body.low_cut,
        ff_enable=body.ff_enable,
        ff_gain=body.ff_gain,
        shed_opt=ControllerMode(body.shed_opt),
        shed_time_s=body.shed_time_s,
        tuning_write_mode=TuningWriteMode(body.tuning_write_mode),
        max_tuning_change_pct=body.max_tuning_change_pct,
    )
```

Update `create_controller` endpoint to use `_body_to_controller(body)` instead of manually constructing a partial Controller.

Add necessary imports: `ScaleConfig`, `TagBindings`, `ControlOpts`, `IOOpts`, `AIConfig`, `TuningWriteMode`, and the new DTO sub-models.

- [ ] **Step 5: Expand `update_controller` to handle all fields**

Replace the `update_controller` endpoint body with full-field update logic. For each scalar field on `ControllerUpdate`, if not None, add to `updates`. For nested sub-models (pid_params, ai_config, tag_bindings, etc.), if not None, build the domain dataclass from the DTO and add to `updates`. Use the same `replace(controller, **updates)` pattern.

Key updates dict construction:

```python
    updates: dict = {}
    # Scalar fields
    for field_name in (
        "name", "description", "scan_rate_ms",
        "sp_hi_lim", "sp_lo_lim", "sp_rate_up", "sp_rate_dn",
        "out_hi_lim", "out_lo_lim", "arw_hi_lim", "arw_lo_lim",
        "pv_ftime", "sp_ftime", "low_cut", "ff_enable", "ff_gain",
        "shed_time_s", "max_tuning_change_pct",
    ):
        val = getattr(body, field_name)
        if val is not None:
            updates[field_name] = val

    # Enum fields (need conversion)
    if body.execution_mode is not None:
        updates["execution_mode"] = ExecutionMode(body.execution_mode)
    if body.pid_structure is not None:
        updates["pid_structure"] = PIDStructure(body.pid_structure)
    if body.integral_type is not None:
        updates["integral_type"] = IntegralType(body.integral_type)
    if body.mode_normal is not None:
        updates["mode_normal"] = ControllerMode(body.mode_normal)
    if body.shed_opt is not None:
        updates["shed_opt"] = ControllerMode(body.shed_opt)
    if body.tuning_write_mode is not None:
        updates["tuning_write_mode"] = TuningWriteMode(body.tuning_write_mode)

    # Nested sub-models → domain dataclasses
    if body.pid_params is not None:
        updates["pid_params"] = PIDParams(
            gain=body.pid_params.gain, reset=body.pid_params.reset,
            rate=body.pid_params.rate, alpha=body.pid_params.alpha,
            deadband=body.pid_params.deadband,
        )
    if body.pv_scale is not None:
        updates["pv_scale"] = ScaleConfig(
            body.pv_scale.eu_min, body.pv_scale.eu_max, body.pv_scale.unit,
        )
    if body.out_scale is not None:
        updates["out_scale"] = ScaleConfig(
            body.out_scale.eu_min, body.out_scale.eu_max, body.out_scale.unit,
        )
    if body.tag_bindings is not None:
        updates["tag_bindings"] = TagBindings(**body.tag_bindings.model_dump())
    if body.control_opts is not None:
        updates["control_opts"] = ControlOpts(**body.control_opts.model_dump())
    if body.io_opts is not None:
        updates["io_opts"] = IOOpts(**body.io_opts.model_dump())
    if body.ai_config is not None:
        updates["ai_config"] = AIConfig(
            engine=AIEngine(body.ai_config.engine),
            objective=ControlObjective(body.ai_config.objective),
            process_speed=ProcessSpeed(body.ai_config.process_speed),
            dead_time_l=body.ai_config.dead_time_l,
            limit_min=body.ai_config.limit_min,
            limit_max=body.ai_config.limit_max,
        )
```

Keep the existing audit trail logic — expand it to cover nested objects.

- [ ] **Step 6: Run tests**

Run: `uv run pytest tests/core/integration/test_api_controllers.py -v`
Expected: All PASS (old + new tests)

- [ ] **Step 7: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/controllers.py \
       tests/core/integration/test_api_controllers.py
git commit -m "feat(core): expand controller API with full 30+ fields"
```

---

## Task 3: Rename AddControllerDialog → ControllerDialog with Edit Mode

**Files:**
- Create: `packages/smart_pid_hmi/src/smart_pid_hmi/widgets/controller_dialog.py` (moved from `add_controller_dialog.py`)
- Delete: `packages/smart_pid_hmi/src/smart_pid_hmi/widgets/add_controller_dialog.py`
- Modify: `tests/hmi/widgets/test_add_controller_dialog.py` → `tests/hmi/widgets/test_controller_dialog.py`
- Modify: `packages/smart_pid_hmi/src/smart_pid_hmi/main.py` (import update)

- [ ] **Step 1: Write failing tests for edit mode**

Create `tests/hmi/widgets/test_controller_dialog.py` — include ALL existing tests from `test_add_controller_dialog.py` (update import to `ControllerDialog`) plus new edit-mode tests:

```python
"""Tests for ControllerDialog — create + edit mode."""
import pytest

from smart_pid_hmi.widgets.controller_dialog import ControllerDialog


@pytest.fixture
def dialog(qtbot):
    dlg = ControllerDialog()
    qtbot.addWidget(dlg)
    return dlg


@pytest.fixture
def edit_data():
    return {
        "name": "TIC-101",
        "description": "Temperature loop",
        "execution_mode": "SUPERVISORY",
        "scan_rate_ms": 500,
        "pid_structure": "PARALLEL",
        "integral_type": "GAIN_KI",
        "mode_normal": "MAN",
        "pid_params": {"gain": 2.5, "reset": 5.0, "rate": 1.0, "alpha": 0.1, "deadband": 0.5},
        "pv_scale": {"eu_min": -50.0, "eu_max": 200.0, "unit": "degC"},
        "out_scale": {"eu_min": 0.0, "eu_max": 100.0, "unit": "%"},
        "ai_config": {
            "engine": "FUZZY", "objective": "SP_TRACKING",
            "process_speed": "SLOW", "dead_time_l": 5.0,
            "limit_min": 0.5, "limit_max": 50.0,
        },
        "tag_bindings": {
            "node_id_pv": "ns=2;s=TIC101.PV", "node_id_sp": "ns=2;s=TIC101.SP",
            "node_id_co": "", "node_id_integral": "",
            "node_id_bkcal_in": "", "node_id_bkcal_out": "",
            "node_id_kp": "", "node_id_ti": "", "node_id_td": "", "node_id_mode": "",
        },
        "control_opts": {
            "direct_acting": True, "track_enable": False,
            "track_in_manual": False, "sp_pv_track_in_man": False,
            "sp_pv_track_in_lo_or_iman": False,
        },
        "io_opts": {
            "low_cutoff": False, "increase_to_close": True,
            "target_to_man_if_fault": False, "fault_state_to_value": False,
        },
        "sp_hi_lim": 200.0,
        "sp_lo_lim": -50.0,
        "out_hi_lim": 100.0,
        "out_lo_lim": 0.0,
        "arw_hi_lim": 110.0,
        "arw_lo_lim": -10.0,
        "sp_rate_up": 1.0,
        "sp_rate_dn": 1.0,
        "pv_ftime": 2.0,
        "sp_ftime": 0.5,
        "low_cut": 0.1,
        "ff_enable": True,
        "ff_gain": 0.8,
        "shed_opt": "AUTO",
        "shed_time_s": 30.0,
        "tuning_write_mode": "DIRECT_WRITE",
        "max_tuning_change_pct": 15.0,
    }


@pytest.fixture
def edit_dialog(qtbot, edit_data):
    dlg = ControllerDialog(edit_data=edit_data)
    qtbot.addWidget(dlg)
    return dlg


# --- Existing tests (update import path) ---
# Copy ALL tests from TestDialogCreation, TestDefaults, TestGetControllerData,
# TestEditing, TestValidation from test_add_controller_dialog.py —
# just change the import from AddControllerDialog to ControllerDialog.


# --- NEW: Edit mode tests ---

class TestEditMode:
    def test_edit_title(self, edit_dialog):
        assert "Edit Controller" in edit_dialog.windowTitle()
        assert "TIC-101" in edit_dialog.windowTitle()

    def test_name_readonly(self, edit_dialog):
        assert edit_dialog._name.isReadOnly()

    def test_populated_name(self, edit_dialog):
        assert edit_dialog._name.text() == "TIC-101"

    def test_populated_description(self, edit_dialog):
        assert edit_dialog._description.text() == "Temperature loop"

    def test_populated_execution_mode(self, edit_dialog):
        assert edit_dialog._execution_mode.currentText() == "SUPERVISORY"

    def test_populated_scan_rate(self, edit_dialog):
        assert edit_dialog._scan_rate.value() == 500

    def test_populated_pid_params(self, edit_dialog):
        assert edit_dialog._gain.value() == pytest.approx(2.5)
        assert edit_dialog._reset.value() == pytest.approx(5.0)
        assert edit_dialog._rate.value() == pytest.approx(1.0)

    def test_populated_pv_scale(self, edit_dialog):
        assert edit_dialog._pv_eu_min.value() == pytest.approx(-50.0)
        assert edit_dialog._pv_eu_max.value() == pytest.approx(200.0)
        assert edit_dialog._pv_unit.text() == "degC"

    def test_populated_ai_config(self, edit_dialog):
        assert edit_dialog._ai_engine.currentText() == "FUZZY"
        assert edit_dialog._ai_objective.currentText() == "SP_TRACKING"
        assert edit_dialog._ai_speed.currentText() == "SLOW"

    def test_populated_tag_bindings(self, edit_dialog):
        assert edit_dialog._tag_pv.text() == "ns=2;s=TIC101.PV"

    def test_populated_control_opts(self, edit_dialog):
        assert edit_dialog._ctrl_direct_acting.isChecked() is True

    def test_populated_io_opts(self, edit_dialog):
        assert edit_dialog._io_increase_to_close.isChecked() is True

    def test_populated_limits(self, edit_dialog):
        assert edit_dialog._sp_hi.value() == pytest.approx(200.0)
        assert edit_dialog._arw_hi.value() == pytest.approx(110.0)

    def test_populated_filters(self, edit_dialog):
        assert edit_dialog._pv_ftime.value() == pytest.approx(2.0)
        assert edit_dialog._ff_enable.isChecked() is True
        assert edit_dialog._ff_gain.value() == pytest.approx(0.8)

    def test_populated_shed(self, edit_dialog):
        assert edit_dialog._shed_opt.currentText() == "AUTO"
        assert edit_dialog._shed_time.value() == pytest.approx(30.0)

    def test_round_trip(self, edit_dialog, edit_data):
        """get_controller_data() returns populated values back."""
        result = edit_dialog.get_controller_data()
        assert result["name"] == "TIC-101"
        assert result["execution_mode"] == "SUPERVISORY"
        assert result["pid_params"]["gain"] == pytest.approx(2.5)
        assert result["ai_config"]["engine"] == "FUZZY"
        assert result["tag_bindings"]["node_id_pv"] == "ns=2;s=TIC101.PV"

    def test_create_mode_title(self, dialog):
        assert dialog.windowTitle() == "Add Controller"

    def test_create_mode_name_editable(self, dialog):
        assert not dialog._name.isReadOnly()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/hmi/widgets/test_controller_dialog.py -v`
Expected: ImportError — `controller_dialog` module not found

- [ ] **Step 3: Create `controller_dialog.py` by extending `add_controller_dialog.py`**

Copy `add_controller_dialog.py` to `controller_dialog.py`. Rename `AddControllerDialog` → `ControllerDialog`. Add:

1. `edit_data` parameter to `__init__`:
```python
    def __init__(self, edit_data: dict | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._edit_mode = edit_data is not None
        self.setWindowTitle(
            f"Edit Controller — {edit_data['name']}" if self._edit_mode else "Add Controller"
        )
        # ... existing tab building ...
        if self._edit_mode:
            self._populate(edit_data)
```

2. `_populate()` method that sets all form fields from the dict:
```python
    def _populate(self, data: dict) -> None:
        """Pre-fill all form fields from existing controller data."""
        self._name.setText(data.get("name", ""))
        self._name.setReadOnly(True)
        self._description.setText(data.get("description", ""))

        # Combo boxes — find and select by text
        def _set_combo(combo: QComboBox, value: str) -> None:
            idx = combo.findText(value)
            if idx >= 0:
                combo.setCurrentIndex(idx)

        _set_combo(self._execution_mode, data.get("execution_mode", "DDC"))
        self._scan_rate.setValue(data.get("scan_rate_ms", 1000))
        _set_combo(self._pid_structure, data.get("pid_structure", "ISA"))
        _set_combo(self._integral_type, data.get("integral_type", "TIME_TI"))
        _set_combo(self._mode_normal, data.get("mode_normal", "AUTO"))

        # PID params
        pid = data.get("pid_params", {})
        self._gain.setValue(pid.get("gain", 1.0))
        self._reset.setValue(pid.get("reset", 10.0))
        self._rate.setValue(pid.get("rate", 0.0))
        self._alpha.setValue(pid.get("alpha", 0.125))
        self._deadband.setValue(pid.get("deadband", 0.0))

        # Scaling
        pv_scale = data.get("pv_scale", {})
        self._pv_eu_min.setValue(pv_scale.get("eu_min", 0.0))
        self._pv_eu_max.setValue(pv_scale.get("eu_max", 100.0))
        self._pv_unit.setText(pv_scale.get("unit", ""))

        out_scale = data.get("out_scale", {})
        self._out_eu_min.setValue(out_scale.get("eu_min", 0.0))
        self._out_eu_max.setValue(out_scale.get("eu_max", 100.0))
        self._out_unit.setText(out_scale.get("unit", ""))

        # Limits
        self._sp_hi.setValue(data.get("sp_hi_lim", 100.0))
        self._sp_lo.setValue(data.get("sp_lo_lim", 0.0))
        self._out_hi.setValue(data.get("out_hi_lim", 100.0))
        self._out_lo.setValue(data.get("out_lo_lim", 0.0))
        self._arw_hi.setValue(data.get("arw_hi_lim", 100.0))
        self._arw_lo.setValue(data.get("arw_lo_lim", 0.0))
        self._sp_rate_up.setValue(data.get("sp_rate_up", 0.0))
        self._sp_rate_dn.setValue(data.get("sp_rate_dn", 0.0))

        # Filters & IO
        self._pv_ftime.setValue(data.get("pv_ftime", 0.0))
        self._sp_ftime.setValue(data.get("sp_ftime", 0.0))
        self._low_cut.setValue(data.get("low_cut", 0.0))
        self._ff_enable.setChecked(data.get("ff_enable", False))
        self._ff_gain.setValue(data.get("ff_gain", 1.0))

        io_opts = data.get("io_opts", {})
        self._io_low_cutoff.setChecked(io_opts.get("low_cutoff", False))
        self._io_increase_to_close.setChecked(io_opts.get("increase_to_close", False))
        self._io_target_to_man.setChecked(io_opts.get("target_to_man_if_fault", False))
        self._io_fault_state_value.setChecked(io_opts.get("fault_state_to_value", False))

        ctrl_opts = data.get("control_opts", {})
        self._ctrl_direct_acting.setChecked(ctrl_opts.get("direct_acting", False))
        self._ctrl_track_enable.setChecked(ctrl_opts.get("track_enable", False))
        self._ctrl_track_in_manual.setChecked(ctrl_opts.get("track_in_manual", False))
        self._ctrl_sp_pv_track_man.setChecked(ctrl_opts.get("sp_pv_track_in_man", False))
        self._ctrl_sp_pv_track_lo_iman.setChecked(ctrl_opts.get("sp_pv_track_in_lo_or_iman", False))

        # AI
        ai = data.get("ai_config", {})
        _set_combo(self._ai_engine, ai.get("engine", "NONE"))
        _set_combo(self._ai_objective, ai.get("objective", "DISTURBANCE_REJECTION"))
        _set_combo(self._ai_speed, ai.get("process_speed", "MEDIUM"))
        self._ai_dead_time.setValue(ai.get("dead_time_l", 1.0))
        self._ai_limit_min.setValue(ai.get("limit_min", 0.1))
        self._ai_limit_max.setValue(ai.get("limit_max", 100.0))

        # OPC-UA Tags
        tags = data.get("tag_bindings", {})
        self._tag_pv.setText(tags.get("node_id_pv", ""))
        self._tag_sp.setText(tags.get("node_id_sp", ""))
        self._tag_co.setText(tags.get("node_id_co", ""))
        self._tag_integral.setText(tags.get("node_id_integral", ""))
        self._tag_bkcal_in.setText(tags.get("node_id_bkcal_in", ""))
        self._tag_bkcal_out.setText(tags.get("node_id_bkcal_out", ""))
        self._tag_kp.setText(tags.get("node_id_kp", ""))
        self._tag_ti.setText(tags.get("node_id_ti", ""))
        self._tag_td.setText(tags.get("node_id_td", ""))
        self._tag_mode.setText(tags.get("node_id_mode", ""))

        # Shed
        _set_combo(self._shed_opt, data.get("shed_opt", "MAN"))
        self._shed_time.setValue(data.get("shed_time_s", 10.0))
        _set_combo(self._tuning_write_mode, data.get("tuning_write_mode", "APPROVAL_REQUIRED"))
        self._max_tuning_pct.setValue(data.get("max_tuning_change_pct", 10.0))
```

3. Update `accept()` to skip name validation in edit mode:
```python
    def accept(self) -> None:
        if not self._edit_mode and not self._name.text().strip():
            self._name.setFocus()
            self._name.setStyleSheet("border: 1px solid red;")
            return
        super().accept()
```

4. Keep `AddControllerDialog` as a backward-compat alias at the bottom:
```python
# Backward compatibility alias
AddControllerDialog = ControllerDialog
```

5. Also update `add_controller_dialog.py` to re-export from new module:
```python
"""Backward compatibility — imports from controller_dialog."""
from smart_pid_hmi.widgets.controller_dialog import AddControllerDialog, ControllerDialog

__all__ = ["AddControllerDialog", "ControllerDialog"]
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/hmi/widgets/test_controller_dialog.py -v`
Expected: All PASS

- [ ] **Step 5: Run old tests to verify backward compat**

Run: `uv run pytest tests/hmi/widgets/test_add_controller_dialog.py -v`
Expected: All PASS (imports from the compat shim)

- [ ] **Step 6: Commit**

```bash
git add packages/smart_pid_hmi/src/smart_pid_hmi/widgets/controller_dialog.py \
       packages/smart_pid_hmi/src/smart_pid_hmi/widgets/add_controller_dialog.py \
       tests/hmi/widgets/test_controller_dialog.py
git commit -m "feat(hmi): ControllerDialog with edit mode + populate()"
```

---

## Task 4: Add Gear Button to ControllerCardWidget

**Files:**
- Modify: `packages/smart_pid_hmi/src/smart_pid_hmi/widgets/controller_card.py`
- Modify: `tests/hmi/widgets/test_controller_card.py`

- [ ] **Step 1: Write failing test for gear button**

Add to `tests/hmi/widgets/test_controller_card.py`:

```python
def test_gear_button_exists(qtbot, theme):
    card = ControllerCardWidget(
        controller_id=1, tag_name="FIC-101",
        min_val=0.0, max_val=100.0, theme=theme,
    )
    qtbot.addWidget(card)
    gear = card.findChild(QPushButton, "settings_btn")
    assert gear is not None


def test_gear_emits_settings_requested(qtbot, theme):
    card = ControllerCardWidget(
        controller_id=7, tag_name="FIC-101",
        min_val=0.0, max_val=100.0, theme=theme,
    )
    qtbot.addWidget(card)
    gear = card.findChild(QPushButton, "settings_btn")
    with qtbot.waitSignal(card.settings_requested, timeout=500) as blocker:
        qtbot.mouseClick(gear, Qt.MouseButton.LeftButton)
    assert blocker.args == [7]


def test_gear_click_does_not_emit_controller_selected(qtbot, theme):
    card = ControllerCardWidget(
        controller_id=1, tag_name="FIC-101",
        min_val=0.0, max_val=100.0, theme=theme,
    )
    qtbot.addWidget(card)
    gear = card.findChild(QPushButton, "settings_btn")
    selected_emitted = []
    card.controller_selected.connect(lambda cid: selected_emitted.append(cid))
    qtbot.mouseClick(gear, Qt.MouseButton.LeftButton)
    assert selected_emitted == []
```

Add `from PySide6.QtWidgets import QPushButton` to test imports.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/hmi/widgets/test_controller_card.py::test_gear_button_exists -v`
Expected: FAIL — no widget named "settings_btn"

- [ ] **Step 3: Add gear button to ControllerCardWidget**

In `packages/smart_pid_hmi/src/smart_pid_hmi/widgets/controller_card.py`:

1. Add `QPushButton` to imports.
2. Add new signal: `settings_requested = Signal(int)`
3. In `__init__`, after `header.addWidget(self._mode_label)`, before `layout.addLayout(header)`:

```python
        # Gear button for settings
        self._settings_btn = QPushButton("\u2699")
        self._settings_btn.setObjectName("settings_btn")
        self._settings_btn.setFixedSize(28, 28)
        self._settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._settings_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; border: 1px solid transparent;"
            f" font-size: 16px; color: {theme.fg_secondary};"
            f" border-radius: 4px; }}"
            f"QPushButton:hover {{ border: 1px solid {theme.border};"
            f" background: {_theme_attr(theme, 'bg_card', theme.bg_widget)}; }}"
        )
        self._settings_btn.clicked.connect(self._on_settings_clicked)
        header.addWidget(self._settings_btn)
```

4. Add the handler:
```python
    def _on_settings_clicked(self) -> None:
        self.settings_requested.emit(self._controller_id)
```

5. In `apply_theme`, add styling update for the gear button:
```python
        self._settings_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; border: 1px solid transparent;"
            f" font-size: 16px; color: {theme.fg_secondary};"
            f" border-radius: 4px; }}"
            f"QPushButton:hover {{ border: 1px solid {theme.border};"
            f" background: {_theme_attr(theme, 'bg_card', theme.bg_widget)}; }}"
        )
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/hmi/widgets/test_controller_card.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_hmi/src/smart_pid_hmi/widgets/controller_card.py \
       tests/hmi/widgets/test_controller_card.py
git commit -m "feat(hmi): gear button on controller cards emits settings_requested"
```

---

## Task 5: Add update_controller to HMI API Client

**Files:**
- Modify: `packages/smart_pid_hmi/src/smart_pid_hmi/services/ports.py`
- Modify: `packages/smart_pid_hmi/src/smart_pid_hmi/services/api_client.py`
- Modify: `packages/smart_pid_hmi/src/smart_pid_hmi/services/mock_service.py`
- Test: `tests/hmi/services/test_api_client.py`

- [ ] **Step 1: Write failing test for update_controller**

Add to `tests/hmi/services/test_api_client.py`:

```python
def test_update_controller(api_client, httpx_mock):
    httpx_mock.add_response(
        method="PUT",
        url="http://test/controllers/1",
        json={
            "id": 1, "name": "TIC-101", "description": "Updated",
            "mode": "AUTO", "pv": 0.0, "sp": 0.0, "co": 0.0,
        },
    )
    result = api_client.update_controller(1, {"description": "Updated"})
    assert result.description == "Updated"
```

If the test file doesn't use `httpx_mock`, check the existing pattern and adapt. The mock should match the existing fixture setup.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/hmi/services/test_api_client.py::test_update_controller -v`
Expected: AttributeError — `APIClient` has no `update_controller`

- [ ] **Step 3: Add `update_controller` to port and implementations**

In `packages/smart_pid_hmi/src/smart_pid_hmi/services/ports.py`, add to `APIClientPort`:
```python
    def create_controller(self, data: dict) -> ControllerResponse: ...
    def update_controller(self, controller_id: int, data: dict) -> ControllerResponse: ...
```

In `packages/smart_pid_hmi/src/smart_pid_hmi/services/api_client.py`, add after `create_controller`:
```python
    def update_controller(self, controller_id: int, data: dict) -> ControllerResponse:
        resp = self._http.put(
            f"/controllers/{controller_id}", json=data, headers=self._headers(),
        )
        resp.raise_for_status()
        return ControllerResponse.model_validate(resp.json())
```

In `packages/smart_pid_hmi/src/smart_pid_hmi/services/mock_service.py`, add to `MockAPIClient`:
```python
    def update_controller(self, controller_id: int, data: dict) -> ControllerResponse:
        for c in _MOCK_CONTROLLERS:
            if c["id"] == controller_id:
                c.update(data)
                return ControllerResponse(
                    id=c["id"], name=c.get("name", ""), description=c.get("description", ""),
                    mode="AUTO", pv=0.0, sp=0.0, co=0.0,
                )
        return ControllerResponse(
            id=controller_id, name="UNKNOWN", description="",
            mode="OOS", pv=0.0, sp=0.0, co=0.0,
        )
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/hmi/services/test_api_client.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_hmi/src/smart_pid_hmi/services/ports.py \
       packages/smart_pid_hmi/src/smart_pid_hmi/services/api_client.py \
       packages/smart_pid_hmi/src/smart_pid_hmi/services/mock_service.py \
       tests/hmi/services/test_api_client.py
git commit -m "feat(hmi): add update_controller to API client + mock"
```

---

## Task 6: Wire Edit Flow in MainWindow + Hide P&ID Tab

**Files:**
- Modify: `packages/smart_pid_hmi/src/smart_pid_hmi/pages/dashboard_page.py`
- Modify: `packages/smart_pid_hmi/src/smart_pid_hmi/main.py`
- Test: `tests/hmi/test_main_window_edit.py`

- [ ] **Step 1: Write failing test for edit wiring**

Create `tests/hmi/test_main_window_edit.py`:

```python
"""Tests for edit controller wiring in MainWindow."""
import pytest
from PySide6.QtWidgets import QPushButton

from smart_pid_hmi.themes.isa101 import ISA101Theme


class TestHidePIDTab:
    def test_pid_nav_not_visible(self, qtbot, main_window):
        """P&ID tab should not be in the navigation."""
        nav_texts = [
            btn.text() for btn in main_window._nav_buttons if btn.isVisible()
        ]
        assert "P&ID" not in nav_texts


class TestDashboardSettingsSignal:
    def test_dashboard_forwards_settings_requested(self, qtbot, main_window):
        """DashboardPage should expose settings_requested signal."""
        assert hasattr(main_window._dashboard_page, "settings_requested")
```

Note: Adapt fixtures to match the existing `conftest.py` for HMI tests. The `main_window` fixture should be the one already used in `test_main_window_users.py` etc.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/hmi/test_main_window_edit.py -v`
Expected: FAIL — P&ID still in nav, no settings_requested signal on DashboardPage

- [ ] **Step 3: Add `settings_requested` signal to DashboardPage**

In `packages/smart_pid_hmi/src/smart_pid_hmi/pages/dashboard_page.py`:

1. Add signal: `settings_requested = Signal(int)`
2. In the method that creates cards (look for where `ControllerCardWidget` is constructed and `controller_selected` is connected), add:
```python
        card.settings_requested.connect(self.settings_requested)
```

- [ ] **Step 4: Hide P&ID tab and wire edit flow in MainWindow**

In `packages/smart_pid_hmi/src/smart_pid_hmi/main.py`:

1. **Remove P&ID nav button creation** — comment out or remove `self._process_nav = _make_nav_btn("P&ID")` and its entry in `_nav_page_map`. Keep `ProcessViewPage` in the stack (dormant).

2. **Remove backward-compat reference**: Remove `self._process_btn = self._process_nav`.

3. **Update import**: Add `from smart_pid_hmi.widgets.controller_dialog import ControllerDialog`

4. **Connect settings signal** after dashboard is created:
```python
        self._dashboard_page.settings_requested.connect(self._on_edit_controller)
```

5. **Add `_on_edit_controller` method**:
```python
    def _on_edit_controller(self, controller_id: int) -> None:
        """Fetch controller data and open edit dialog."""
        def do_fetch():
            try:
                ctrl = self._api_client.get_controller(controller_id)
                data = ctrl.model_dump()
                # Open dialog on main thread
                QMetaObject.invokeMethod(
                    self, "_open_edit_dialog",
                    Qt.ConnectionType.QueuedConnection,
                    controller_id, data,
                )
            except Exception as e:
                logger.error("Failed to fetch controller %d: %s", controller_id, e)
                self._api_error_signal.emit(str(e))

        threading.Thread(target=do_fetch, daemon=True).start()

    @Slot(int, dict)
    def _open_edit_dialog(self, controller_id: int, data: dict) -> None:
        """Open the edit dialog with pre-filled data (runs on main thread)."""
        from smart_pid_hmi.widgets.controller_dialog import ControllerDialog

        dialog = ControllerDialog(edit_data=data, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        updated = dialog.get_controller_data()

        def do_update():
            try:
                self._api_client.update_controller(controller_id, updated)
                self._load_dashboard()
            except Exception as e:
                logger.error("Failed to update controller %d: %s", controller_id, e)
                self._api_error_signal.emit(str(e))

        threading.Thread(target=do_update, daemon=True).start()
```

Note: Since `QMetaObject.invokeMethod` with arbitrary Python types can be tricky, an alternative is to use a custom signal. Add:
```python
    _edit_dialog_signal = Signal(int, dict)
```
Connect in `__init__`: `self._edit_dialog_signal.connect(self._open_edit_dialog)`.
In `do_fetch`: `self._edit_dialog_signal.emit(controller_id, data)`.

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/hmi/test_main_window_edit.py -v`
Expected: All PASS

- [ ] **Step 6: Run full HMI test suite**

Run: `uv run pytest tests/hmi/ -v`
Expected: All PASS. Fix any tests that reference `self._process_btn` or `self._process_nav`.

- [ ] **Step 7: Commit**

```bash
git add packages/smart_pid_hmi/src/smart_pid_hmi/pages/dashboard_page.py \
       packages/smart_pid_hmi/src/smart_pid_hmi/main.py \
       tests/hmi/test_main_window_edit.py
git commit -m "feat(hmi): wire edit dialog from gear button, hide P&ID tab"
```

---

## Task 7: Final Integration Test + Cleanup

**Files:**
- Run all tests across packages

- [ ] **Step 1: Run full test suite**

Run: `uv run pytest tests/ -v`
Expected: All PASS

- [ ] **Step 2: Run linter**

Run: `uv run --with ruff ruff check .`
Fix any issues.

- [ ] **Step 3: Fix any broken references to old P&ID tab or AddControllerDialog**

Search for remaining references:
- `_process_nav` / `_process_btn` in test files
- `AddControllerDialog` direct imports (should go through compat shim or use new name)

- [ ] **Step 4: Commit any fixes**

```bash
git add -u
git commit -m "chore: fix lint and broken refs after loop config dialog"
```

- [ ] **Step 5: Update estado-atual.md**

Update `.claude/docs/estado-atual.md` with what was completed.
