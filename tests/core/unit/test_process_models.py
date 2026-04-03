"""Tests for ProcessModel — FOPTD/SOPTD step response simulation."""
from __future__ import annotations

from smart_pid_core.domain.services.process_models import ProcessModel
from smart_pid_domain.enums import ProcessPresetName
from smart_pid_domain.models.process_preset import PRESETS


class TestProcessModel:
    def test_initial_pv_is_zero(self) -> None:
        model = ProcessModel(gain=1.0, tau1=5.0, tau2=None, dead_time=0.0)
        assert model.pv == 0.0

    def test_step_response_foptd_converges_to_gain(self) -> None:
        """FOPTD with K=2, tau=5, L=0: after many steps at CO=1.0, PV -> K*CO = 2.0."""
        model = ProcessModel(gain=2.0, tau1=5.0, tau2=None, dead_time=0.0)
        dt = 0.1
        for _ in range(500):
            model.step(co=1.0, dt=dt)
        assert abs(model.pv - 2.0) < 0.05

    def test_step_response_soptd_converges_to_gain(self) -> None:
        """SOPTD with K=1.5, tau1=10, tau2=5, L=0: PV -> 1.5."""
        model = ProcessModel(gain=1.5, tau1=10.0, tau2=5.0, dead_time=0.0)
        dt = 0.1
        for _ in range(1000):
            model.step(co=1.0, dt=dt)
        assert abs(model.pv - 1.5) < 0.05

    def test_dead_time_delays_response(self) -> None:
        """With L=2s, after 1s of simulation PV should still be near zero."""
        model = ProcessModel(gain=1.0, tau1=5.0, tau2=None, dead_time=2.0)
        dt = 0.1
        for _ in range(10):  # 1.0 seconds
            model.step(co=1.0, dt=dt)
        assert abs(model.pv) < 0.15  # still delayed

    def test_reset_returns_to_zero(self) -> None:
        model = ProcessModel(gain=1.0, tau1=5.0, tau2=None, dead_time=0.0)
        for _ in range(100):
            model.step(co=1.0, dt=0.1)
        assert model.pv > 0.5
        model.reset()
        assert model.pv == 0.0

    def test_zero_co_stays_at_zero(self) -> None:
        model = ProcessModel(gain=1.0, tau1=5.0, tau2=None, dead_time=0.0)
        for _ in range(50):
            model.step(co=0.0, dt=0.1)
        assert abs(model.pv) < 1e-10

    def test_from_preset_creates_model(self) -> None:
        preset = PRESETS[ProcessPresetName.TEMPERATURE]
        model = ProcessModel.from_preset(preset)
        assert model.pv == 0.0
        # Should use Temperature params
        for _ in range(2000):
            model.step(co=1.0, dt=0.1)
        assert abs(model.pv - preset.gain) < 0.1
