"""Tests for expanded Controller DTOs with full 30+ fields."""
from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

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

# ── Sub-model defaults ──────────────────────────────────────────────────────


class TestPIDParamsDTO:
    def test_defaults(self) -> None:
        p = PIDParamsDTO()
        assert p.gain == 1.0
        assert p.reset == 10.0
        assert p.rate == 0.0
        assert p.alpha == 0.125
        assert p.deadband == 0.0

    def test_custom_values(self) -> None:
        p = PIDParamsDTO(gain=2.5, reset=5.0, rate=1.0, alpha=0.25, deadband=0.5)
        assert p.gain == 2.5
        assert p.rate == 1.0


class TestScaleConfigDTO:
    def test_defaults(self) -> None:
        s = ScaleConfigDTO()
        assert s.eu_min == 0.0
        assert s.eu_max == 100.0
        assert s.unit == ""

    def test_custom(self) -> None:
        s = ScaleConfigDTO(eu_min=-50.0, eu_max=200.0, unit="degC")
        assert s.eu_max == 200.0
        assert s.unit == "degC"


class TestAIConfigDTO:
    def test_defaults(self) -> None:
        a = AIConfigDTO()
        assert a.engine == "NONE"
        assert a.objective == "DISTURBANCE_REJECTION"
        assert a.process_speed == "MEDIUM"
        assert a.dead_time_l == 1.0
        assert a.limit_min == 0.1
        assert a.limit_max == 100.0


class TestTagBindingsDTO:
    def test_defaults_all_empty(self) -> None:
        t = TagBindingsDTO()
        for field_name in [
            "node_id_pv", "node_id_sp", "node_id_co", "node_id_integral",
            "node_id_bkcal_in", "node_id_bkcal_out",
            "node_id_kp", "node_id_ti", "node_id_td", "node_id_mode",
        ]:
            assert getattr(t, field_name) == ""

    def test_custom(self) -> None:
        t = TagBindingsDTO(node_id_pv="ns=2;s=TIC100.PV")
        assert t.node_id_pv == "ns=2;s=TIC100.PV"


class TestControlOptsDTO:
    def test_all_default_false(self) -> None:
        c = ControlOptsDTO()
        assert c.no_out_limits_in_manual is False
        assert c.direct_acting is False
        assert c.use_pv_for_bkcal_out is False

    def test_set_true(self) -> None:
        c = ControlOptsDTO(direct_acting=True, track_enable=True)
        assert c.direct_acting is True
        assert c.track_enable is True


class TestIOOptsDTO:
    def test_all_default_false(self) -> None:
        io = IOOptsDTO()
        assert io.low_cutoff is False
        assert io.increase_to_close is False

    def test_set_true(self) -> None:
        io = IOOptsDTO(increase_to_close=True)
        assert io.increase_to_close is True


# ── ControllerCreate ────────────────────────────────────────────────────────


class TestControllerCreate:
    def test_minimal(self) -> None:
        c = ControllerCreate(name="TIC-100")
        assert c.name == "TIC-100"
        assert c.description == ""
        assert c.scan_rate_ms == 1000
        assert c.pid_params == PIDParamsDTO()
        assert c.sp_hi_lim == 100.0
        assert c.sp_lo_lim == 0.0
        assert c.out_hi_lim == 100.0
        assert c.out_lo_lim == 0.0
        assert c.ff_enable is False

    def test_full_creation(self) -> None:
        c = ControllerCreate(
            name="FIC-200",
            description="Flow controller",
            execution_mode="DDC",
            scan_rate_ms=500,
            pid_params=PIDParamsDTO(gain=2.0, reset=5.0),
            pid_structure="ISA",
            pv_scale=ScaleConfigDTO(eu_min=0, eu_max=500, unit="m3/h"),
            ai_config=AIConfigDTO(engine="FUZZY"),
            tag_bindings=TagBindingsDTO(node_id_pv="ns=2;s=FIC200.PV"),
            control_opts=ControlOptsDTO(direct_acting=True),
            io_opts=IOOptsDTO(increase_to_close=True),
            sp_rate_up=5.0,
            sp_rate_dn=5.0,
            arw_hi_lim=95.0,
            arw_lo_lim=5.0,
        )
        assert c.pid_params.gain == 2.0
        assert c.pv_scale.eu_max == 500
        assert c.ai_config.engine == "FUZZY"
        assert c.tag_bindings.node_id_pv == "ns=2;s=FIC200.PV"
        assert c.control_opts.direct_acting is True
        assert c.io_opts.increase_to_close is True
        assert c.sp_rate_up == 5.0

    def test_name_required(self) -> None:
        with pytest.raises(ValidationError):
            ControllerCreate()  # type: ignore[call-arg]


# ── ControllerUpdate ────────────────────────────────────────────────────────


class TestControllerUpdate:
    def test_all_none_by_default(self) -> None:
        u = ControllerUpdate()
        assert u.name is None
        assert u.pid_params is None
        assert u.pv_scale is None
        assert u.ai_config is None
        assert u.tag_bindings is None
        assert u.control_opts is None
        assert u.io_opts is None
        assert u.sp_hi_lim is None
        assert u.scan_rate_ms is None

    def test_partial_update(self) -> None:
        u = ControllerUpdate(
            name="TIC-101",
            pid_params=PIDParamsDTO(gain=3.0),
        )
        assert u.name == "TIC-101"
        assert u.pid_params is not None
        assert u.pid_params.gain == 3.0
        assert u.description is None  # untouched


# ── ControllerResponse ──────────────────────────────────────────────────────


class TestControllerResponse:
    def test_basic_fields_still_work(self) -> None:
        """Backward compat: basic fields with defaults for new nested fields."""
        r = ControllerResponse(
            id=1, name="TIC-100", description="", mode="AUTO",
            pv=50.0, sp=55.0, co=42.0,
        )
        assert r.id == 1
        assert r.pid_params == PIDParamsDTO()
        assert r.pv_scale == ScaleConfigDTO()

    def test_full_response(self) -> None:
        r = ControllerResponse(
            id=42,
            name="FIC-200",
            description="Flow",
            mode="AUTO",
            pv=100.0,
            sp=100.0,
            co=65.0,
            execution_mode="SUPERVISORY",
            scan_rate_ms=500,
            pid_params=PIDParamsDTO(gain=2.0),
            pid_structure="PARALLEL",
            integral_type="GAIN_KI",
            pv_scale=ScaleConfigDTO(eu_min=0, eu_max=500, unit="m3/h"),
            out_scale=ScaleConfigDTO(eu_min=0, eu_max=100),
            ai_config=AIConfigDTO(engine="RL"),
            tag_bindings=TagBindingsDTO(node_id_pv="ns=2;s=FIC200.PV"),
            control_opts=ControlOptsDTO(direct_acting=True),
            io_opts=IOOptsDTO(increase_to_close=True),
            sp_hi_lim=500.0,
            sp_lo_lim=0.0,
            sp_rate_up=10.0,
            arw_hi_lim=95.0,
            ff_enable=True,
            ff_gain=0.5,
            tuning_write_mode="auto_apply",
            max_tuning_change_pct=20.0,
            mode_normal="AUTO",
            shed_opt="MAN",
            shed_time_s=15.0,
        )
        assert r.execution_mode == "SUPERVISORY"
        assert r.pid_params.gain == 2.0
        assert r.ai_config.engine == "RL"
        assert r.ff_enable is True
        assert r.tuning_write_mode == "auto_apply"

    def test_json_round_trip(self) -> None:
        r = ControllerResponse(
            id=1, name="TIC-100", description="test", mode="MAN",
            pv=25.0, sp=30.0, co=10.0,
            pid_params=PIDParamsDTO(gain=1.5, deadband=0.2),
            ai_config=AIConfigDTO(engine="FUZZY", objective="SP_TRACKING"),
        )
        data = r.model_dump()
        json_str = json.dumps(data)
        parsed = json.loads(json_str)
        r2 = ControllerResponse(**parsed)
        assert r2.pid_params.gain == 1.5
        assert r2.ai_config.engine == "FUZZY"
        assert r2.ai_config.objective == "SP_TRACKING"
        assert r2 == r
