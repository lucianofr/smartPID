"""Unit tests for RLEngine -- pure domain service (lazy sb3 import)."""
from __future__ import annotations

import pytest

from smart_pid_domain.enums import ControlObjective, ProcessSpeed


class TestRLEngineInit:
    def test_creates_without_sb3_installed(self):
        from smart_pid_core.domain.services.rl_engine import RLEngine

        engine = RLEngine(algorithm="SAC")
        assert engine.algorithm == "SAC"
        assert not engine.is_trained

    def test_default_algorithm_is_sac(self):
        from smart_pid_core.domain.services.rl_engine import RLEngine

        engine = RLEngine()
        assert engine.algorithm == "SAC"

    def test_ppo_algorithm(self):
        from smart_pid_core.domain.services.rl_engine import RLEngine

        engine = RLEngine(algorithm="PPO")
        assert engine.algorithm == "PPO"

    def test_initial_counters_are_zero(self):
        from smart_pid_core.domain.services.rl_engine import RLEngine

        engine = RLEngine()
        assert engine.reward_steps == 0
        assert engine.step_count == 0
        assert engine.avg_reward == 0.0


class TestFallbackPolicy:
    """Test the proportional fallback policy when sb3 is not available."""

    def test_zero_error_returns_zero_gamma(self):
        from smart_pid_core.domain.services.rl_engine import _FallbackPolicy

        policy = _FallbackPolicy()
        gamma = policy.predict([0.0, 0.0, 0.0, 0.0])
        assert gamma == pytest.approx(0.0)

    def test_positive_error_returns_positive_gamma(self):
        from smart_pid_core.domain.services.rl_engine import _FallbackPolicy

        policy = _FallbackPolicy()
        gamma = policy.predict([0.5, 0.0, 0.0, 0.0])
        assert gamma > 0.0

    def test_negative_error_returns_negative_gamma(self):
        from smart_pid_core.domain.services.rl_engine import _FallbackPolicy

        policy = _FallbackPolicy()
        gamma = policy.predict([-0.5, 0.0, 0.0, 0.0])
        assert gamma < 0.0

    def test_gamma_clamped_to_bounds(self):
        from smart_pid_core.domain.services.rl_engine import _FallbackPolicy

        policy = _FallbackPolicy(kp=10.0, kd=10.0)
        gamma = policy.predict([1.0, 1.0, 0.0, 0.0])
        assert gamma == pytest.approx(1.0)
        gamma = policy.predict([-1.0, -1.0, 0.0, 0.0])
        assert gamma == pytest.approx(-1.0)

    def test_delta_error_contributes_to_gamma(self):
        from smart_pid_core.domain.services.rl_engine import _FallbackPolicy

        policy = _FallbackPolicy()
        gamma_no_de = policy.predict([0.2, 0.0, 0.0, 0.0])
        gamma_with_de = policy.predict([0.2, 0.3, 0.0, 0.0])
        assert gamma_with_de > gamma_no_de


class TestComputeGammaFallback:
    """Test compute_gamma when no sb3 model is loaded (fallback mode)."""

    def test_returns_meaningful_gamma_for_positive_error(self):
        from smart_pid_core.domain.services.rl_engine import RLEngine

        engine = RLEngine()
        decision = engine.compute_gamma(
            error=10.0,
            delta_error=0.0,
            ki_current=1.0,
            span=100.0,
            co=50.0,
            integral_val=0.0,
            objective=ControlObjective.SP_TRACKING,
            speed=ProcessSpeed.MEDIUM,
            limit_min=0.1,
            limit_max=100.0,
        )
        # Positive error -> fallback should increase Ki (positive gamma)
        assert decision.gamma > 0.0
        assert decision.new_ki > 1.0
        assert "fallback" in decision.reasoning
        assert decision.membership_values is None

    def test_returns_meaningful_gamma_for_negative_error(self):
        from smart_pid_core.domain.services.rl_engine import RLEngine

        engine = RLEngine()
        decision = engine.compute_gamma(
            error=-10.0,
            delta_error=0.0,
            ki_current=1.0,
            span=100.0,
            co=50.0,
            integral_val=0.0,
            objective=ControlObjective.SP_TRACKING,
            speed=ProcessSpeed.MEDIUM,
            limit_min=0.1,
            limit_max=100.0,
        )
        # Negative error -> fallback should decrease Ki (negative gamma)
        assert decision.gamma < 0.0
        assert decision.new_ki < 1.0

    def test_zero_error_returns_near_zero_gamma(self):
        from smart_pid_core.domain.services.rl_engine import RLEngine

        engine = RLEngine()
        decision = engine.compute_gamma(
            error=0.0,
            delta_error=0.0,
            ki_current=1.0,
            span=100.0,
            co=50.0,
            integral_val=0.0,
            objective=ControlObjective.SP_TRACKING,
            speed=ProcessSpeed.MEDIUM,
            limit_min=0.1,
            limit_max=100.0,
        )
        assert decision.gamma == pytest.approx(0.0, abs=0.01)
        assert decision.new_ki == pytest.approx(1.0, abs=0.01)

    def test_ki_clamped_to_limits(self):
        from smart_pid_core.domain.services.rl_engine import RLEngine

        engine = RLEngine()
        # Large positive error should try to increase Ki a lot
        decision = engine.compute_gamma(
            error=100.0,
            delta_error=50.0,
            ki_current=99.0,
            span=100.0,
            co=50.0,
            integral_val=0.0,
            objective=ControlObjective.SP_TRACKING,
            speed=ProcessSpeed.SLOW,
            limit_min=0.1,
            limit_max=100.0,
        )
        assert decision.new_ki <= 100.0

    def test_zero_span_returns_zero_gamma(self):
        from smart_pid_core.domain.services.rl_engine import RLEngine

        engine = RLEngine()
        decision = engine.compute_gamma(
            error=10.0,
            delta_error=5.0,
            ki_current=1.0,
            span=0.0,
            co=50.0,
            integral_val=0.0,
            objective=ControlObjective.SP_TRACKING,
            speed=ProcessSpeed.MEDIUM,
            limit_min=0.1,
            limit_max=100.0,
        )
        # Zero span -> normalized error is 0 -> gamma near 0
        assert decision.gamma == pytest.approx(0.0, abs=0.01)

    def test_step_count_increments(self):
        from smart_pid_core.domain.services.rl_engine import RLEngine

        engine = RLEngine()
        assert engine.step_count == 0

        engine.compute_gamma(
            error=5.0, delta_error=1.0, ki_current=1.0, span=100.0,
            co=50.0, integral_val=0.0,
            objective=ControlObjective.SP_TRACKING,
            speed=ProcessSpeed.MEDIUM,
            limit_min=0.1, limit_max=100.0,
        )
        assert engine.step_count == 1

        engine.compute_gamma(
            error=3.0, delta_error=-2.0, ki_current=1.0, span=100.0,
            co=52.0, integral_val=5.0,
            objective=ControlObjective.SP_TRACKING,
            speed=ProcessSpeed.MEDIUM,
            limit_min=0.1, limit_max=100.0,
        )
        assert engine.step_count == 2


class TestComputeGammaSpeedFactors:
    """Test that speed factors affect Ki update magnitude."""

    def _get_new_ki(self, speed: ProcessSpeed) -> float:
        from smart_pid_core.domain.services.rl_engine import RLEngine

        engine = RLEngine()
        decision = engine.compute_gamma(
            error=20.0,
            delta_error=5.0,
            ki_current=10.0,
            span=100.0,
            co=50.0,
            integral_val=0.0,
            objective=ControlObjective.SP_TRACKING,
            speed=speed,
            limit_min=0.1,
            limit_max=100.0,
        )
        return decision.new_ki

    def test_slow_speed_changes_ki_most(self):
        ki_slow = self._get_new_ki(ProcessSpeed.SLOW)
        ki_fast = self._get_new_ki(ProcessSpeed.FAST)
        # Slow has larger Sv so same gamma produces larger Ki change
        assert abs(ki_slow - 10.0) > abs(ki_fast - 10.0)

    def test_fast_speed_changes_ki_least(self):
        ki_medium = self._get_new_ki(ProcessSpeed.MEDIUM)
        ki_fast = self._get_new_ki(ProcessSpeed.FAST)
        assert abs(ki_medium - 10.0) > abs(ki_fast - 10.0)


class TestRewardFunctions:
    """Test reward computation for different objectives."""

    def test_sp_tracking_zero_error_high_reward(self):
        from smart_pid_core.domain.services.rl_engine import compute_reward_sp_tracking

        reward = compute_reward_sp_tracking(
            error=0.0, delta_error=0.0, co=50.0, prev_co=50.0, step=0
        )
        # Zero error, no CO change -> highest reward (settle bonus)
        assert reward > 0.0

    def test_sp_tracking_large_error_low_reward(self):
        from smart_pid_core.domain.services.rl_engine import compute_reward_sp_tracking

        reward = compute_reward_sp_tracking(
            error=0.8, delta_error=0.0, co=50.0, prev_co=50.0, step=0
        )
        assert reward < 0.0

    def test_sp_tracking_penalizes_valve_chattering(self):
        from smart_pid_core.domain.services.rl_engine import compute_reward_sp_tracking

        reward_stable = compute_reward_sp_tracking(
            error=0.1, delta_error=0.0, co=50.0, prev_co=50.0, step=0
        )
        reward_chattering = compute_reward_sp_tracking(
            error=0.1, delta_error=0.0, co=70.0, prev_co=50.0, step=0
        )
        # Same error but chattering should have lower reward
        assert reward_chattering < reward_stable

    def test_dr_itae_increases_with_time(self):
        from smart_pid_core.domain.services.rl_engine import (
            compute_reward_disturbance_rejection,
        )

        reward_early = compute_reward_disturbance_rejection(
            error=0.5, delta_error=0.0, co=50.0, prev_co=50.0, step=0
        )
        reward_late = compute_reward_disturbance_rejection(
            error=0.5, delta_error=0.0, co=50.0, prev_co=50.0, step=100
        )
        # Same error later in time should be penalized more (ITAE in DR)
        assert reward_late < reward_early

    def test_sp_tracking_no_prev_co(self):
        from smart_pid_core.domain.services.rl_engine import compute_reward_sp_tracking

        reward = compute_reward_sp_tracking(
            error=0.1, delta_error=0.0, co=50.0, prev_co=None, step=0
        )
        # No TV penalty when no previous CO
        assert reward < 0.0  # Still has IAE penalty

    def test_surge_level_rewards_valve_stability(self):
        from smart_pid_core.domain.services.rl_engine import compute_reward_surge_level

        reward_stable = compute_reward_surge_level(
            error=0.0, delta_error=0.0, co=50.0, prev_co=50.0, step=0
        )
        reward_unstable = compute_reward_surge_level(
            error=0.0, delta_error=0.0, co=80.0, prev_co=50.0, step=0
        )
        assert reward_stable > reward_unstable

    def test_surge_level_ignores_error_inside_deadband(self):
        from smart_pid_core.domain.services.rl_engine import compute_reward_surge_level

        reward_zero = compute_reward_surge_level(
            error=0.0, delta_error=0.0, co=50.0, prev_co=50.0, step=0
        )
        reward_small = compute_reward_surge_level(
            error=0.01, delta_error=0.0, co=50.0, prev_co=50.0, step=0
        )
        # Small error within deadband should have same reward
        assert reward_zero == pytest.approx(reward_small)

    def test_surge_level_penalizes_error_outside_deadband(self):
        from smart_pid_core.domain.services.rl_engine import compute_reward_surge_level

        reward_in = compute_reward_surge_level(
            error=0.01, delta_error=0.0, co=50.0, prev_co=50.0, step=0
        )
        reward_out = compute_reward_surge_level(
            error=0.5, delta_error=0.0, co=50.0, prev_co=50.0, step=0
        )
        assert reward_out < reward_in

    def test_surge_level_no_prev_co(self):
        from smart_pid_core.domain.services.rl_engine import compute_reward_surge_level

        reward = compute_reward_surge_level(
            error=0.5, delta_error=0.0, co=50.0, prev_co=None, step=0
        )
        # No stability reward, only IAE penalty outside deadband
        assert reward < 0.0


class TestComputeRewardMethod:
    """Test the engine's compute_reward dispatching by objective."""

    def test_sp_tracking_objective(self):
        from smart_pid_core.domain.services.rl_engine import RLEngine

        engine = RLEngine()
        reward = engine.compute_reward(
            error=0.5, delta_error=0.0, co=50.0, span=100.0,
            objective=ControlObjective.SP_TRACKING,
        )
        assert reward < 0.0  # Error penalty

    def test_disturbance_rejection_objective(self):
        from smart_pid_core.domain.services.rl_engine import RLEngine

        engine = RLEngine()
        reward = engine.compute_reward(
            error=0.5, delta_error=0.0, co=50.0, span=100.0,
            objective=ControlObjective.DISTURBANCE_REJECTION,
        )
        assert reward < 0.0

    def test_surge_level_objective(self):
        from smart_pid_core.domain.services.rl_engine import RLEngine

        engine = RLEngine()
        reward = engine.compute_reward(
            error=0.0, delta_error=0.0, co=50.0, span=100.0,
            objective=ControlObjective.SURGE_LEVEL,
        )
        # Zero error, no prev_co -> no stability reward, no IAE penalty
        assert reward == pytest.approx(0.0)


class TestUpdate:
    """Test the update() method for manual reward injection."""

    def test_update_increments_counters(self):
        from smart_pid_core.domain.services.rl_engine import RLEngine

        engine = RLEngine()
        engine.update(reward=1.0, observation=[0.0, 0.0, 0.5, 0.25])
        assert engine.reward_steps == 1
        assert engine.avg_reward == pytest.approx(1.0)

    def test_multiple_updates_average_reward(self):
        from smart_pid_core.domain.services.rl_engine import RLEngine

        engine = RLEngine()
        engine.update(reward=1.0)
        engine.update(reward=3.0)
        assert engine.reward_steps == 2
        assert engine.avg_reward == pytest.approx(2.0)

    def test_update_stores_transition_in_buffer(self):
        from smart_pid_core.domain.services.rl_engine import RLEngine

        engine = RLEngine()
        # First set a last_observation
        engine.compute_gamma(
            error=5.0, delta_error=1.0, ki_current=1.0, span=100.0,
            co=50.0, integral_val=0.0,
            objective=ControlObjective.SP_TRACKING,
            speed=ProcessSpeed.MEDIUM,
            limit_min=0.1, limit_max=100.0,
        )
        # Now update with reward
        engine.update(reward=0.5, observation=[0.1, 0.0, 0.0, 0.0])
        assert len(engine._replay_buffer) > 0


class TestReset:
    """Test reset() clears episode state."""

    def test_reset_clears_state(self):
        from smart_pid_core.domain.services.rl_engine import RLEngine

        engine = RLEngine()
        engine.compute_gamma(
            error=5.0, delta_error=1.0, ki_current=1.0, span=100.0,
            co=50.0, integral_val=0.0,
            objective=ControlObjective.SP_TRACKING,
            speed=ProcessSpeed.MEDIUM,
            limit_min=0.1, limit_max=100.0,
        )
        assert engine.step_count == 1

        engine.reset()
        assert engine.step_count == 0
        assert engine._last_observation is None
        assert engine._last_action is None
        assert engine._prev_co is None


class TestObservationNormalization:
    """Test that observations are properly normalized to [-1, 1]."""

    def test_normalization_bounds(self):
        from smart_pid_core.domain.services.rl_engine import RLEngine

        engine = RLEngine()
        obs = engine._normalize_observation(
            error=200.0,  # Exceeds span
            delta_error=-200.0,
            span=100.0,
            co=150.0,  # Exceeds [0, 100]
            integral_val=500.0,
        )
        for v in obs:
            assert -1.0 <= v <= 1.0

    def test_normalization_zero_span(self):
        from smart_pid_core.domain.services.rl_engine import RLEngine

        engine = RLEngine()
        obs = engine._normalize_observation(
            error=10.0, delta_error=5.0, span=0.0, co=50.0, integral_val=0.0
        )
        assert obs[0] == 0.0
        assert obs[1] == 0.0

    def test_normalization_typical_values(self):
        from smart_pid_core.domain.services.rl_engine import RLEngine

        engine = RLEngine()
        obs = engine._normalize_observation(
            error=10.0, delta_error=-5.0, span=100.0, co=50.0, integral_val=50.0
        )
        assert obs[0] == pytest.approx(0.1)   # 10/100
        assert obs[1] == pytest.approx(-0.05)  # -5/100
        assert obs[2] == pytest.approx(0.0)   # (50-50)/50
        assert obs[3] == pytest.approx(0.5)   # 50/100


class TestReplayBuffer:
    """Test that the replay buffer accumulates transitions."""

    def test_buffer_grows_with_compute_gamma_calls(self):
        from smart_pid_core.domain.services.rl_engine import RLEngine

        engine = RLEngine()
        # First call: no previous observation, so no transition stored
        engine.compute_gamma(
            error=5.0, delta_error=1.0, ki_current=1.0, span=100.0,
            co=50.0, integral_val=0.0,
            objective=ControlObjective.SP_TRACKING,
            speed=ProcessSpeed.MEDIUM,
            limit_min=0.1, limit_max=100.0,
        )
        assert len(engine._replay_buffer) == 0

        # Second call: has previous observation, stores transition
        engine.compute_gamma(
            error=3.0, delta_error=-2.0, ki_current=1.05, span=100.0,
            co=52.0, integral_val=5.0,
            objective=ControlObjective.SP_TRACKING,
            speed=ProcessSpeed.MEDIUM,
            limit_min=0.1, limit_max=100.0,
        )
        assert len(engine._replay_buffer) == 1

    def test_buffer_respects_maxlen(self):
        from smart_pid_core.domain.services.rl_engine import RLEngine

        engine = RLEngine()
        engine._replay_buffer = type(engine._replay_buffer)(maxlen=5)

        # Generate 7 transitions
        for i in range(8):
            engine.compute_gamma(
                error=float(i), delta_error=0.0, ki_current=1.0, span=100.0,
                co=50.0, integral_val=0.0,
                objective=ControlObjective.SP_TRACKING,
                speed=ProcessSpeed.MEDIUM,
                limit_min=0.1, limit_max=100.0,
            )
        # Buffer should be capped at maxlen=5
        assert len(engine._replay_buffer) == 5


class TestAllObjectives:
    """Ensure compute_gamma works for all control objectives."""

    @pytest.mark.parametrize("objective", list(ControlObjective))
    def test_compute_gamma_all_objectives(self, objective):
        from smart_pid_core.domain.services.rl_engine import RLEngine

        engine = RLEngine()
        decision = engine.compute_gamma(
            error=10.0,
            delta_error=2.0,
            ki_current=5.0,
            span=100.0,
            co=50.0,
            integral_val=10.0,
            objective=objective,
            speed=ProcessSpeed.MEDIUM,
            limit_min=0.1,
            limit_max=100.0,
        )
        assert -1.0 <= decision.gamma <= 1.0
        assert 0.1 <= decision.new_ki <= 100.0
        assert len(decision.reasoning) > 0
