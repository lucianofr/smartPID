from __future__ import annotations

from smart_pid_domain.enums import (
    AIEngine, ConnectionState, ControllerMode, ControlObjective,
    ExecutionMode, IntegralType, OptimizerState, PIDStructure,
    ProcessSpeed, SignalStatus, UserRole,
)


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
        assert len(ConnectionState) == 3

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
