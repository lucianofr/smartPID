from __future__ import annotations

from datetime import UTC, datetime

from smart_pid_domain.enums import (
    AIEngine,
    ConnectionState,
    ControllerMode,
    ControlObjective,
    ExecutionMode,
    IntegralType,
    OptimizerState,
    PIDStructure,
    ProcessSpeed,
    SignalStatus,
    UserRole,
)
from smart_pid_domain.exceptions import ControllerNotFoundError, DomainError
from smart_pid_domain.models.controller import (
    Controller,
    PIDParams,
    ScaleConfig,
    TagBindings,
)
from smart_pid_domain.models.signal import FFSignal
from smart_pid_domain.models.telemetry import ControlAction, TelemetryFrame


class TestEnums:
    def test_controller_mode_has_eight_values(self) -> None:
        assert len(ControllerMode) == 8
        assert ControllerMode.OOS == "OOS"
        assert ControllerMode.AUTO == "AUTO"

    def test_execution_mode_values(self) -> None:
        assert ExecutionMode.SUPERVISORY == "SUPERVISORY"
        assert ExecutionMode.DDC == "DDC"

    def test_ai_engine_values(self) -> None:
        assert AIEngine.NONE == "NONE"
        assert AIEngine.FUZZY == "FUZZY"
        assert AIEngine.RL == "RL"

    def test_control_objective_values(self) -> None:
        assert len(ControlObjective) == 3

    def test_process_speed_values(self) -> None:
        assert len(ProcessSpeed) == 3

    def test_connection_state_values(self) -> None:
        assert len(ConnectionState) == 4

    def test_signal_status_values(self) -> None:
        assert len(SignalStatus) == 3

    def test_pid_structure_values(self) -> None:
        assert len(PIDStructure) == 3

    def test_integral_type_values(self) -> None:
        assert len(IntegralType) == 2

    def test_optimizer_state_values(self) -> None:
        assert OptimizerState.RUN == "RUN"
        assert OptimizerState.PAUSE == "PAUSE"
        assert OptimizerState.STOP == "STOP"

    def test_user_role_values(self) -> None:
        assert UserRole.ADMIN == "ADMIN"
        assert UserRole.SUPERVISOR == "SUPERVISOR"
        assert UserRole.OPERATOR == "OPERATOR"


class TestPIDParams:
    def test_defaults(self) -> None:
        p = PIDParams()
        assert p.gain == 1.0
        assert p.reset == 10.0
        assert p.rate == 0.0
        assert p.alpha == 0.125
        assert p.deadband == 0.0


class TestScaleConfig:
    def test_span(self) -> None:
        s = ScaleConfig(eu_min=0.0, eu_max=100.0, unit="degC")
        assert s.span == 100.0

    def test_negative_range(self) -> None:
        s = ScaleConfig(eu_min=-50.0, eu_max=50.0, unit="%")
        assert s.span == 100.0


class TestTelemetryFrame:
    def test_is_frozen(self) -> None:
        now = datetime.now(tz=UTC)
        frame = TelemetryFrame(
            controller_id=1, pv=FFSignal.good(50.0), sp=FFSignal.good(50.0),
            co=FFSignal.good(25.0), bkcal_in=FFSignal.good(0.0),
            integral_val=1.0, timestamp=now,
        )
        assert frame.pv.value == 50.0
        import pytest
        with pytest.raises(AttributeError):
            frame.pv = FFSignal.good(99.0)  # type: ignore[misc]


class TestControlAction:
    def test_construction(self) -> None:
        now = datetime.now(tz=UTC)
        action = ControlAction(
            controller_id=1, co=FFSignal.good(45.0),
            bkcal_out=FFSignal.good(45.0), integral_val=1.5, timestamp=now,
        )
        assert action.co.value == 45.0



class TestControllerNotFoundError:
    def test_is_domain_error(self) -> None:
        err = ControllerNotFoundError(42)
        assert isinstance(err, DomainError)

    def test_stores_controller_id(self) -> None:
        err = ControllerNotFoundError(42)
        assert err.controller_id == 42

    def test_message(self) -> None:
        err = ControllerNotFoundError(42)
        assert "42" in str(err)


class TestTelemetryFrameFFSignal:
    """TelemetryFrame fields are now FFSignal."""

    def test_create_with_ff_signals(self) -> None:
        from datetime import UTC, datetime

        from smart_pid_domain.models.signal import FFSignal

        ts = datetime.now(tz=UTC)
        frame = TelemetryFrame(
            controller_id=1,
            pv=FFSignal.good(50.0, ts),
            sp=FFSignal.good(50.0, ts),
            co=FFSignal.good(62.0, ts),
            bkcal_in=FFSignal.good(62.0, ts),
            integral_val=45.0,
            timestamp=ts,
        )
        assert frame.pv.value == 50.0
        assert frame.pv.status.is_good is True
        assert frame.bkcal_in.value == 62.0

    def test_bkcal_in_with_limit_bits(self) -> None:
        from datetime import UTC, datetime

        from smart_pid_domain.enums import LimitBits
        from smart_pid_domain.models.signal import FFSignal

        ts = datetime.now(tz=UTC)
        frame = TelemetryFrame(
            controller_id=1,
            pv=FFSignal.good(50.0),
            sp=FFSignal.good(50.0),
            co=FFSignal.with_limits(100.0, LimitBits.HIGH_LIMITED),
            bkcal_in=FFSignal.with_limits(100.0, LimitBits.HIGH_LIMITED),
            integral_val=45.0,
            timestamp=ts,
        )
        assert frame.bkcal_in.status.is_high_limited is True


class TestControlActionFFSignal:
    """ControlAction fields now use FFSignal."""

    def test_create_with_bkcal_out(self) -> None:
        from datetime import UTC, datetime

        from smart_pid_domain.models.signal import FFSignal

        ts = datetime.now(tz=UTC)
        action = ControlAction(
            controller_id=1,
            co=FFSignal.good(62.0, ts),
            bkcal_out=FFSignal.good(62.0, ts),
            integral_val=45.0,
            timestamp=ts,
        )
        assert action.co.value == 62.0
        assert action.bkcal_out.value == 62.0


class TestTagBindingsFFSignal:
    """TagBindings has BKCAL node ID fields."""

    def test_bkcal_node_ids(self) -> None:
        from smart_pid_domain.models.controller import TagBindings

        tb = TagBindings(
            node_id_pv="ns=2;s=PV",
            node_id_bkcal_in="ns=2;s=BKCAL_IN",
            node_id_bkcal_out="ns=2;s=BKCAL_OUT",
        )
        assert tb.node_id_bkcal_in == "ns=2;s=BKCAL_IN"
        assert tb.node_id_bkcal_out == "ns=2;s=BKCAL_OUT"

    def test_bkcal_defaults_empty(self) -> None:
        from smart_pid_domain.models.controller import TagBindings

        tb = TagBindings()
        assert tb.node_id_bkcal_in == ""
        assert tb.node_id_bkcal_out == ""


class TestTagBindingsExpanded:
    def test_new_fields_default_empty(self) -> None:
        tb = TagBindings()
        assert tb.node_id_kp == ""
        assert tb.node_id_ti == ""
        assert tb.node_id_td == ""
        assert tb.node_id_mode == ""

    def test_new_fields_set(self) -> None:
        tb = TagBindings(
            node_id_kp="ns=2;s=PID1.KP",
            node_id_ti="ns=2;s=PID1.TI",
            node_id_td="ns=2;s=PID1.TD",
            node_id_mode="ns=2;s=PID1.MODE",
        )
        assert tb.node_id_kp == "ns=2;s=PID1.KP"
        assert tb.node_id_mode == "ns=2;s=PID1.MODE"


class TestControllerTuningFields:
    def test_default_tuning_write_mode(self) -> None:
        from smart_pid_domain.enums import TuningWriteMode
        c = Controller(id=1, name="test")
        assert c.tuning_write_mode == TuningWriteMode.APPROVAL_REQUIRED

    def test_default_max_tuning_change_pct(self) -> None:
        c = Controller(id=1, name="test")
        assert c.max_tuning_change_pct == 10.0

    def test_custom_tuning_config(self) -> None:
        from smart_pid_domain.enums import TuningWriteMode
        c = Controller(
            id=1,
            name="test",
            tuning_write_mode=TuningWriteMode.AUTO_APPLY,
            max_tuning_change_pct=5.0,
        )
        assert c.tuning_write_mode == TuningWriteMode.AUTO_APPLY
        assert c.max_tuning_change_pct == 5.0
