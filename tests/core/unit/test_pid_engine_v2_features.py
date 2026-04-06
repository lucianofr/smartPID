"""Unit tests for PID engine v2 features: use_pv_for_bkcal_out, no_out_limits,
check_tracking, handle_fault, clamp_sp_if_cas, normalize_ff, toggle_watchdog.

NOTE: Some of these features (use_pv_for_bkcal_out, no_out_limits, etc.)
are not yet implemented in PIDEngine as keyword args. Tests here verify the
existing engine behavior and the model-level additions (StatusOpts, TrackOpt,
ProcessType, BYPASS enum, Controller fields).
"""
from __future__ import annotations

import pytest

from smart_pid_core.domain.services.pid_engine import (
    PIDEngine,
    PIDState,
)
from smart_pid_domain.enums import (
    ControllerMode,
    ProcessType,
    TrackOpt,
)
from smart_pid_domain.models.controller import (
    Controller,
    ControlOpts,
    PIDParams,
    StatusOpts,
)
from smart_pid_domain.models.signal import FFSignal


# ---------------------------------------------------------------------------
# Feature: use_pv_for_bkcal_out — the flag exists on ControlOpts
# ---------------------------------------------------------------------------
class TestUsePVForBkcalOut:
    def test_control_opts_has_use_pv_for_bkcal_out(self) -> None:
        opts = ControlOpts(use_pv_for_bkcal_out=True)
        assert opts.use_pv_for_bkcal_out is True

    def test_default_is_false(self) -> None:
        opts = ControlOpts()
        assert opts.use_pv_for_bkcal_out is False


# ---------------------------------------------------------------------------
# Feature: no_out_limits — tested at engine level (clamp behavior)
# ---------------------------------------------------------------------------
class TestNoOutLimits:
    def setup_method(self) -> None:
        self.engine = PIDEngine()
        self.params = PIDParams(gain=2.0, reset=1e9, rate=0.0)

    def test_output_clamped_to_limits_by_default(self) -> None:
        state = PIDState(
            cv=98.0, error_prev=0.0, pv_prev=50.0, pv_prev2=50.0,
        )
        result = self.engine.compute(
            params=self.params, state=state,
            pv=FFSignal.good(50.0), sp=FFSignal.good(60.0),
            bkcal_in=FFSignal.good(0.0), dt=1.0,
            out_limits=(0.0, 100.0),
        )
        # 98 + 20 = 118, clamped to 100
        assert result.cv == pytest.approx(100.0)
        assert result.new_state.is_saturated is True

    def test_no_out_limits_in_manual_flag(self) -> None:
        opts = ControlOpts(no_out_limits_in_manual=True)
        assert opts.no_out_limits_in_manual is True


# ---------------------------------------------------------------------------
# Feature 4: StatusOpts model
# ---------------------------------------------------------------------------
class TestStatusOptsModel:
    def test_defaults(self) -> None:
        opts = StatusOpts()
        assert opts.bad_if_limited is False
        assert opts.use_uncertain_as_good is True

    def test_custom(self) -> None:
        opts = StatusOpts(
            bad_if_limited=True,
            use_uncertain_as_good=True,
        )
        assert opts.bad_if_limited is True
        assert opts.use_uncertain_as_good is True


# ---------------------------------------------------------------------------
# Feature 5: TrackOpt enum
# ---------------------------------------------------------------------------
class TestTrackOptEnum:
    def test_all_values(self) -> None:
        assert TrackOpt.ALWAYS_USE_VALUE == "ALWAYS_USE_VALUE"
        assert TrackOpt.USE_LAST_GOOD == "USE_LAST_GOOD"
        assert TrackOpt.TRACK_IF_BAD == "TRACK_IF_BAD"


# ---------------------------------------------------------------------------
# Feature 6: ProcessType
# ---------------------------------------------------------------------------
class TestProcessType:
    def test_all_values(self) -> None:
        assert ProcessType.SELF_REGULATING == "SELF_REGULATING"
        assert ProcessType.INTEGRATING == "INTEGRATING"

    def test_controller_default(self) -> None:
        ctrl = Controller()
        assert ctrl.process_type == ProcessType.SELF_REGULATING

    def test_controller_integrating(self) -> None:
        ctrl = Controller(process_type=ProcessType.INTEGRATING)
        assert ctrl.process_type == ProcessType.INTEGRATING


# ---------------------------------------------------------------------------
# Feature 2: BYPASS enum
# ---------------------------------------------------------------------------
class TestBypassMode:
    def test_bypass_in_enum(self) -> None:
        assert ControllerMode.BYPASS == "BYPASS"

    def test_controller_bypass_enable(self) -> None:
        ctrl = Controller(
            control_opts=ControlOpts(bypass_enable=True),
        )
        assert ctrl.control_opts.bypass_enable is True


# ---------------------------------------------------------------------------
# Controller model new fields
# ---------------------------------------------------------------------------
class TestControllerNewFields:
    def test_trk_in_d_default(self) -> None:
        ctrl = Controller()
        assert ctrl.trk_in_d is False

    def test_trk_in_d_set(self) -> None:
        ctrl = Controller(trk_in_d=True)
        assert ctrl.trk_in_d is True

    def test_track_opt_default(self) -> None:
        ctrl = Controller()
        assert ctrl.track_opt == TrackOpt.ALWAYS_USE_VALUE

    def test_alarm_config_default_none(self) -> None:
        ctrl = Controller()
        assert ctrl.alarm_config is None

    def test_status_opts_default(self) -> None:
        ctrl = Controller()
        assert ctrl.status_opts.bad_if_limited is False
        assert ctrl.status_opts.use_uncertain_as_good is True
