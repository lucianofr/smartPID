"""Tests for new simulator auto-excitation DTOs."""
import pytest
from pydantic import ValidationError
from smart_pid_domain.dtos.simulator import (
    AutoDisturbanceRequest,
    AutoSPRequest,
    ControllerSimStatus,
)


class TestAutoSPRequest:
    def test_defaults(self):
        r = AutoSPRequest(enabled=True)
        assert r.sp_min_pct == 30.0
        assert r.sp_max_pct == 70.0

    def test_custom_values(self):
        r = AutoSPRequest(enabled=False, sp_min_pct=20.0, sp_max_pct=80.0)
        assert r.sp_min_pct == 20.0
        assert r.sp_max_pct == 80.0

    def test_pct_out_of_range_raises(self):
        with pytest.raises(ValidationError):
            AutoSPRequest(enabled=True, sp_min_pct=-1.0)
        with pytest.raises(ValidationError):
            AutoSPRequest(enabled=True, sp_max_pct=101.0)


class TestAutoDisturbanceRequest:
    def test_defaults(self):
        r = AutoDisturbanceRequest(enabled=True)
        assert r.max_amplitude_pct == 10.0

    def test_custom_value(self):
        r = AutoDisturbanceRequest(enabled=True, max_amplitude_pct=25.0)
        assert r.max_amplitude_pct == 25.0

    def test_pct_out_of_range_raises(self):
        with pytest.raises(ValidationError):
            AutoDisturbanceRequest(enabled=True, max_amplitude_pct=101.0)


class TestControllerSimStatusExtended:
    def test_auto_fields_default_to_none(self):
        s = ControllerSimStatus(
            preset="FLOW", gain=1.2, tau1=3.0, tau2=None,
            dead_time=1.0, step_active=False, step_amplitude=0.0,
            noise_active=False, noise_amplitude=0.0,
        )
        assert s.auto_sp is None
        assert s.auto_disturbance is None

    def test_auto_fields_accepted(self):
        s = ControllerSimStatus(
            preset="FLOW", gain=1.2, tau1=3.0, tau2=None,
            dead_time=1.0, step_active=False, step_amplitude=0.0,
            noise_active=False, noise_amplitude=0.0,
            auto_sp=AutoSPRequest(enabled=True),
            auto_disturbance=AutoDisturbanceRequest(enabled=False),
        )
        assert s.auto_sp.enabled is True
        assert s.auto_disturbance.enabled is False
