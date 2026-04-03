"""Tests for simulator request/response DTOs."""
from __future__ import annotations

from smart_pid_domain.dtos.simulator import (
    ControllerSimStatus,
    SimulatorDisturbanceRequest,
    SimulatorParametersRequest,
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
