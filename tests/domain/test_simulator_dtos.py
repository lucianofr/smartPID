"""Tests for simulator request/response DTOs."""
from __future__ import annotations

from smart_pid_domain.dtos.simulator import (
    ControllerSimStatus,
    SimulatorDisturbanceRequest,
    SimulatorParametersRequest,
    SimulatorPIDModeRequest,
    SimulatorPIDParamsRequest,
    SimulatorPIDStatusResponse,
    SimulatorPresetRequest,
    SimulatorStatusResponse,
)
from smart_pid_domain.enums import ProcessPresetName


class TestSimulatorPresetRequest:
    def test_valid(self) -> None:
        req = SimulatorPresetRequest(controller_id=1, preset=ProcessPresetName.FLOW)
        assert req.controller_id == 1
        assert req.preset == ProcessPresetName.FLOW

    def test_from_json(self) -> None:
        req = SimulatorPresetRequest.model_validate(
            {"controller_id": 1, "preset": "FLOW"}
        )
        assert req.preset == ProcessPresetName.FLOW


class TestSimulatorParametersRequest:
    def test_foptd_no_tau2(self) -> None:
        req = SimulatorParametersRequest(
            controller_id=1, gain=1.0, tau1=5.0, dead_time=1.0,
        )
        assert req.tau2 is None

    def test_soptd_with_tau2(self) -> None:
        req = SimulatorParametersRequest(
            controller_id=1, gain=1.0, tau1=5.0, tau2=3.0, dead_time=1.0,
        )
        assert req.tau2 == 3.0


class TestSimulatorDisturbanceRequest:
    def test_step_type(self) -> None:
        req = SimulatorDisturbanceRequest(
            controller_id=1, type="step", amplitude=5.0,
        )
        assert req.type == "step"

    def test_noise_type(self) -> None:
        req = SimulatorDisturbanceRequest(
            controller_id=1, type="noise", amplitude=0.5,
        )
        assert req.type == "noise"


class TestControllerSimStatus:
    def test_no_disturbances(self) -> None:
        s = ControllerSimStatus(
            preset="FLOW", gain=1.2, tau1=3.0, tau2=None, dead_time=1.0,
            step_active=False, step_amplitude=0.0,
            noise_active=False, noise_amplitude=0.0,
        )
        assert not s.step_active
        assert not s.noise_active


class TestSimulatorStatusResponse:
    def test_enabled(self) -> None:
        s = SimulatorStatusResponse(enabled=True, controllers={})
        assert s.enabled
        assert s.controllers == {}

    def test_with_controllers(self) -> None:
        ctrl = ControllerSimStatus(
            preset="FLOW", gain=1.2, tau1=3.0, tau2=None, dead_time=1.0,
            step_active=True, step_amplitude=5.0,
            noise_active=False, noise_amplitude=0.0,
        )
        s = SimulatorStatusResponse(enabled=True, controllers={1: ctrl})
        assert s.controllers[1].step_active


class TestControllerSimStatusPIDFields:
    def test_defaults(self) -> None:
        status = ControllerSimStatus(
            preset="FLOW", gain=1.2, tau1=3.0, tau2=None, dead_time=1.0,
            step_active=False, step_amplitude=0.0,
            noise_active=False, noise_amplitude=0.0,
        )
        assert status.pid_kp == 1.0
        assert status.pid_ti == 10.0
        assert status.pid_td == 0.0
        assert status.pid_mode == 0
        assert status.pid_cv == 0.0

    def test_with_pid_values(self) -> None:
        status = ControllerSimStatus(
            preset="FLOW", gain=1.2, tau1=3.0, tau2=None, dead_time=1.0,
            step_active=False, step_amplitude=0.0,
            noise_active=False, noise_amplitude=0.0,
            pid_kp=2.0, pid_ti=5.0, pid_td=1.0,
            pid_mode=1, pid_cv=42.0,
        )
        assert status.pid_kp == 2.0
        assert status.pid_cv == 42.0


class TestSimulatorPIDRequestDTOs:
    def test_params_request(self) -> None:
        req = SimulatorPIDParamsRequest(controller_id=1, kp=2.0, ti=5.0, td=1.0)
        assert req.kp == 2.0
        assert req.ti == 5.0

    def test_mode_request(self) -> None:
        req = SimulatorPIDModeRequest(controller_id=1, mode="AUTO")
        assert req.mode == "AUTO"

    def test_status_response(self) -> None:
        resp = SimulatorPIDStatusResponse(
            enabled=True, kp=1.0, ti=10.0, td=0.0, mode=1, cv=50.0,
        )
        assert resp.enabled is True
        assert resp.cv == 50.0


class TestOPCUAServerStatus:
    def test_opcua_server_status_dto(self) -> None:
        from smart_pid_domain.dtos.simulator import OPCUAServerStatus

        status = OPCUAServerStatus(running=True, port=4849, endpoint="opc.tcp://0.0.0.0:4849")
        assert status.running is True
        assert status.port == 4849
        assert status.endpoint == "opc.tcp://0.0.0.0:4849"
