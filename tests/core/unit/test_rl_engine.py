"""Unit tests for RLEngine — pure domain service (lazy sb3 import)."""
from __future__ import annotations

import pytest

from smart_pid_domain.enums import ControlObjective, ProcessSpeed


class TestRLEngineInit:
    def test_creates_without_sb3_installed(self):
        from smart_pid_core.domain.services.rl_engine import RLEngine

        engine = RLEngine(algorithm="SAC")
        assert engine.algorithm == "SAC"
        assert not engine.is_trained

    def test_compute_gamma_without_model_returns_zero(self):
        from smart_pid_core.domain.services.rl_engine import RLEngine

        engine = RLEngine(algorithm="SAC")
        decision = engine.compute_gamma(
            error=10.0, delta_error=5.0, ki_current=1.0, span=100.0,
            co=50.0, integral_val=25.0,
            objective=ControlObjective.SP_TRACKING,
            speed=ProcessSpeed.MEDIUM,
            limit_min=0.1, limit_max=100.0,
        )
        # Without trained model, should return gamma=0 (no change)
        assert decision.gamma == pytest.approx(0.0)
        assert decision.new_ki == pytest.approx(1.0)
        assert decision.membership_values is None

    def test_update_without_model_is_noop(self):
        from smart_pid_core.domain.services.rl_engine import RLEngine

        engine = RLEngine(algorithm="SAC")
        # Should not raise
        engine.update(reward=1.0, observation=[0.0, 0.0, 0.5, 0.25])
