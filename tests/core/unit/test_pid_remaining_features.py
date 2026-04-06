"""Unit tests for the 7 remaining PID engine features.

1. CAS_IN / RCAS_IN handling
2. SIMULATE mode
3. STATUS_OPTS signal quality interpretation
4. TRACK_OPT — TRK_IN_D resolution with bad quality
5. ProcessType enum
6. Alarm detection in PID worker
7. BYPASS mode (N/A check + implementation)
"""
from __future__ import annotations

from smart_pid_core.application.workers.pid_worker import _evaluate_pv_quality
from smart_pid_core.domain.services.alarm_engine import AlarmEngine
from smart_pid_core.domain.services.pid_engine import PIDEngine, PIDState
from smart_pid_domain.enums import (
    AlarmPriority,
    AlarmType,
    ControllerMode,
    LimitBits,
    ProcessType,
    SignalSeverity,
    TrackOpt,
)
from smart_pid_domain.models.alarm_config import AlarmConfig
from smart_pid_domain.models.controller import (
    Controller,
    ControlOpts,
    IOOpts,
    PIDParams,
    StatusOpts,
)
from smart_pid_domain.models.signal import FFSignal, FFSignalStatus


# ===================================================================
# Feature 1: CAS_IN / RCAS_IN — unit-level checks on SP override
# ===================================================================
class TestCASINUnit:
    """Verify CAS/RCAS SP override at the model/enum level."""

    def test_cas_mode_exists(self) -> None:
        assert ControllerMode.CAS == "CAS"

    def test_rcas_mode_exists(self) -> None:
        assert ControllerMode.RCAS == "RCAS"

    def test_controller_defaults_allow_auto(self) -> None:
        ctrl = Controller()
        assert ControllerMode.AUTO in ctrl.permitted_modes


# ===================================================================
# Feature 2: SIMULATE mode — unit-level checks
# ===================================================================
class TestSimulateUnit:
    """Test simulate PV at PID engine level."""

    def test_pid_engine_uses_provided_pv(self) -> None:
        """If simulate replaces PV, the engine should see the new value."""
        engine = PIDEngine()
        params = PIDParams(gain=1.0, reset=10.0, rate=0.0)
        state = PIDState(cv=50.0, pv_prev=50.0, pv_prev2=50.0)
        # Simulate PV=80, SP=50 -> error = 50-80 = -30
        result = engine.compute(
            params=params,
            state=state,
            pv=FFSignal.good(80.0),  # simulated value
            sp=FFSignal.good(50.0),
            bkcal_in=FFSignal.good(0.0),
            dt=1.0,
            out_limits=(0.0, 100.0),
        )
        assert result.error < 0  # error = SP - PV = 50 - 80 = -30

    def test_engine_bumpless_transfer_preserves_co(self) -> None:
        """Bumpless transfer sets CV to current CO for seamless switch."""
        engine = PIDEngine()
        state = PIDState(cv=30.0, pv_prev=50.0, pv_prev2=50.0)
        new_state = engine.bumpless_transfer(
            state=state,
            current_pv=60.0,
            current_co=45.0,
            params=PIDParams(),
        )
        assert new_state.cv == 45.0
        assert new_state.pv_prev == 60.0


# ===================================================================
# Feature 3: STATUS_OPTS — signal quality interpretation
# ===================================================================
class TestStatusOptsUnit:
    """STATUS_OPTS rules for _evaluate_pv_quality."""

    def test_default_status_opts(self) -> None:
        opts = StatusOpts()
        assert opts.bad_if_limited is False
        assert opts.use_uncertain_as_good is True

    def test_bad_if_limited_high(self) -> None:
        opts = StatusOpts(bad_if_limited=True)
        sig = FFSignal(
            value=50.0,
            status=FFSignalStatus(
                severity=SignalSeverity.GOOD,
                limit_bits=LimitBits.HIGH_LIMITED,
            ),
        )
        result = _evaluate_pv_quality(sig, opts)
        assert result.status.severity == SignalSeverity.BAD

    def test_bad_if_limited_low(self) -> None:
        opts = StatusOpts(bad_if_limited=True)
        sig = FFSignal(
            value=50.0,
            status=FFSignalStatus(
                severity=SignalSeverity.GOOD,
                limit_bits=LimitBits.LOW_LIMITED,
            ),
        )
        result = _evaluate_pv_quality(sig, opts)
        assert result.status.severity == SignalSeverity.BAD

    def test_bad_if_limited_constant(self) -> None:
        opts = StatusOpts(bad_if_limited=True)
        sig = FFSignal(
            value=50.0,
            status=FFSignalStatus(
                severity=SignalSeverity.GOOD,
                limit_bits=LimitBits.CONSTANT,
            ),
        )
        result = _evaluate_pv_quality(sig, opts)
        assert result.status.severity == SignalSeverity.BAD

    def test_bad_if_limited_none_stays_good(self) -> None:
        opts = StatusOpts(bad_if_limited=True)
        sig = FFSignal.good(50.0)
        result = _evaluate_pv_quality(sig, opts)
        assert result.status.severity == SignalSeverity.GOOD

    def test_uncertain_as_good_true(self) -> None:
        opts = StatusOpts(use_uncertain_as_good=True)
        sig = FFSignal(
            value=50.0,
            status=FFSignalStatus(severity=SignalSeverity.UNCERTAIN),
        )
        result = _evaluate_pv_quality(sig, opts)
        assert result.status.severity == SignalSeverity.GOOD

    def test_uncertain_stays_when_opt_false(self) -> None:
        opts = StatusOpts(use_uncertain_as_good=False)
        sig = FFSignal(
            value=50.0,
            status=FFSignalStatus(severity=SignalSeverity.UNCERTAIN),
        )
        result = _evaluate_pv_quality(sig, opts)
        assert result.status.severity == SignalSeverity.UNCERTAIN

    def test_good_signal_returns_same_object(self) -> None:
        opts = StatusOpts(bad_if_limited=True, use_uncertain_as_good=True)
        sig = FFSignal.good(50.0)
        result = _evaluate_pv_quality(sig, opts)
        assert result is sig

    def test_bad_if_limited_overrides_uncertain_as_good(self) -> None:
        """bad_if_limited turns to BAD; uncertain_as_good does NOT
        convert BAD back to GOOD (only converts UNCERTAIN)."""
        opts = StatusOpts(
            bad_if_limited=True, use_uncertain_as_good=True,
        )
        sig = FFSignal(
            value=50.0,
            status=FFSignalStatus(
                severity=SignalSeverity.GOOD,
                limit_bits=LimitBits.HIGH_LIMITED,
            ),
        )
        result = _evaluate_pv_quality(sig, opts)
        assert result.status.severity == SignalSeverity.BAD


# ===================================================================
# Feature 4: TRACK_OPT — TRK_IN_D behavior with BAD quality
# ===================================================================
class TestTrackOptUnit:
    """TrackOpt enum values and controller defaults."""

    def test_track_opt_values(self) -> None:
        assert TrackOpt.ALWAYS_USE_VALUE == "ALWAYS_USE_VALUE"
        assert TrackOpt.USE_LAST_GOOD == "USE_LAST_GOOD"
        assert TrackOpt.TRACK_IF_BAD == "TRACK_IF_BAD"

    def test_controller_default_track_opt(self) -> None:
        ctrl = Controller()
        assert ctrl.track_opt == TrackOpt.ALWAYS_USE_VALUE

    def test_controller_trk_in_d_default(self) -> None:
        ctrl = Controller()
        assert ctrl.trk_in_d is False


# ===================================================================
# Feature 5: ProcessType enum
# ===================================================================
class TestProcessTypeUnit:
    """ProcessType enum and controller integration."""

    def test_process_type_values(self) -> None:
        assert ProcessType.SELF_REGULATING == "SELF_REGULATING"
        assert ProcessType.INTEGRATING == "INTEGRATING"

    def test_controller_default(self) -> None:
        ctrl = Controller()
        assert ctrl.process_type == ProcessType.SELF_REGULATING

    def test_controller_integrating(self) -> None:
        ctrl = Controller(process_type=ProcessType.INTEGRATING)
        assert ctrl.process_type == ProcessType.INTEGRATING


# ===================================================================
# Feature 6: Alarm detection — engine-level unit test
# ===================================================================
class TestAlarmEngineUnit:
    """AlarmEngine.evaluate returns correct transitions."""

    def _make_config(self) -> AlarmConfig:
        return AlarmConfig(
            hihi_enabled=True,
            hihi_value=90.0,
            hihi_priority=AlarmPriority.CRITICAL,
            hi_enabled=True,
            hi_value=80.0,
            hi_priority=AlarmPriority.WARNING,
            lo_enabled=True,
            lo_value=20.0,
            lo_priority=AlarmPriority.WARNING,
            lolo_enabled=True,
            lolo_value=10.0,
            lolo_priority=AlarmPriority.CRITICAL,
            dv_hi_enabled=False,
            dv_hi_value=0.0,
            dv_hi_priority=AlarmPriority.ADVISORY,
            dv_lo_enabled=False,
            dv_lo_value=0.0,
            dv_lo_priority=AlarmPriority.ADVISORY,
            deadband_percent=2.0,
        )

    def test_hi_alarm_triggers(self) -> None:
        engine = AlarmEngine()
        cfg = self._make_config()
        transitions = engine.evaluate(
            controller_id=1, pv=85.0, sp=50.0,
            alarm_config=cfg, sp_ramping=False,
        )
        hi_trans = [
            t for t in transitions if t.alarm_type == AlarmType.HI
        ]
        assert len(hi_trans) == 1
        assert hi_trans[0].transition == "TRIGGERED"

    def test_hihi_alarm_triggers(self) -> None:
        engine = AlarmEngine()
        cfg = self._make_config()
        transitions = engine.evaluate(
            controller_id=1, pv=95.0, sp=50.0,
            alarm_config=cfg, sp_ramping=False,
        )
        hihi_trans = [
            t for t in transitions if t.alarm_type == AlarmType.HIHI
        ]
        assert len(hihi_trans) == 1
        assert hihi_trans[0].transition == "TRIGGERED"

    def test_lo_alarm_triggers(self) -> None:
        engine = AlarmEngine()
        cfg = self._make_config()
        transitions = engine.evaluate(
            controller_id=1, pv=15.0, sp=50.0,
            alarm_config=cfg, sp_ramping=False,
        )
        lo_trans = [
            t for t in transitions if t.alarm_type == AlarmType.LO
        ]
        assert len(lo_trans) == 1
        assert lo_trans[0].transition == "TRIGGERED"

    def test_lolo_alarm_triggers(self) -> None:
        engine = AlarmEngine()
        cfg = self._make_config()
        transitions = engine.evaluate(
            controller_id=1, pv=5.0, sp=50.0,
            alarm_config=cfg, sp_ramping=False,
        )
        lolo_trans = [
            t for t in transitions if t.alarm_type == AlarmType.LOLO
        ]
        assert len(lolo_trans) == 1
        assert lolo_trans[0].transition == "TRIGGERED"

    def test_alarm_cleared(self) -> None:
        engine = AlarmEngine()
        cfg = self._make_config()
        # Trigger
        engine.evaluate(
            controller_id=1, pv=85.0, sp=50.0,
            alarm_config=cfg, sp_ramping=False,
        )
        # Clear (below limit - deadband)
        transitions = engine.evaluate(
            controller_id=1, pv=50.0, sp=50.0,
            alarm_config=cfg, sp_ramping=False,
        )
        cleared = [
            t for t in transitions if t.transition == "CLEARED"
        ]
        assert len(cleared) > 0

    def test_no_transition_normal_range(self) -> None:
        engine = AlarmEngine()
        cfg = self._make_config()
        transitions = engine.evaluate(
            controller_id=1, pv=50.0, sp=50.0,
            alarm_config=cfg, sp_ramping=False,
        )
        assert len(transitions) == 0

    def test_controller_alarm_config_field(self) -> None:
        cfg = self._make_config()
        ctrl = Controller(alarm_config=cfg)
        assert ctrl.alarm_config is not None
        assert ctrl.alarm_config.hi_value == 80.0

    def test_controller_alarm_config_default_none(self) -> None:
        ctrl = Controller()
        assert ctrl.alarm_config is None


# ===================================================================
# Feature 7: BYPASS mode
# ===================================================================
class TestBypassModeUnit:
    """BYPASS mode exists and bypass_enable is a ControlOpts flag."""

    def test_bypass_mode_in_controller_mode(self) -> None:
        assert ControllerMode.BYPASS == "BYPASS"

    def test_bypass_enable_default_false(self) -> None:
        opts = ControlOpts()
        assert opts.bypass_enable is False

    def test_bypass_enable_true(self) -> None:
        opts = ControlOpts(bypass_enable=True)
        assert opts.bypass_enable is True

    def test_bypass_in_permitted_modes(self) -> None:
        ctrl = Controller(
            permitted_modes={
                ControllerMode.MAN, ControllerMode.BYPASS,
            },
        )
        assert ControllerMode.BYPASS in ctrl.permitted_modes


# ===================================================================
# Feature: StatusOpts on Controller
# ===================================================================
class TestStatusOptsOnController:
    def test_default_status_opts(self) -> None:
        ctrl = Controller()
        assert ctrl.status_opts.bad_if_limited is False
        assert ctrl.status_opts.use_uncertain_as_good is True

    def test_custom_status_opts(self) -> None:
        ctrl = Controller(
            status_opts=StatusOpts(
                bad_if_limited=True, use_uncertain_as_good=False,
            ),
        )
        assert ctrl.status_opts.bad_if_limited is True
        assert ctrl.status_opts.use_uncertain_as_good is False


# ===================================================================
# Feature: IOOpts increase_to_close
# ===================================================================
class TestIOOptsUnit:
    def test_increase_to_close_default(self) -> None:
        opts = IOOpts()
        assert opts.increase_to_close is False

    def test_increase_to_close_set(self) -> None:
        opts = IOOpts(increase_to_close=True)
        assert opts.increase_to_close is True
