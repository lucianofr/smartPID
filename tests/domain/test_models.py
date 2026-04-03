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
    PIDParams,
    ScaleConfig,
)
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
            controller_id=1, pv=50.0, sp=50.0, co=25.0,
            integral_val=1.0, timestamp=now, status=SignalStatus.GOOD,
        )
        assert frame.pv == 50.0
        import pytest
        with pytest.raises(AttributeError):
            frame.pv = 99.0  # type: ignore[misc]


class TestControlAction:
    def test_construction(self) -> None:
        now = datetime.now(tz=UTC)
        action = ControlAction(controller_id=1, co=45.0, integral_val=1.5, timestamp=now)
        assert action.co == 45.0



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
