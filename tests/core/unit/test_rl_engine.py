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

    def test_unsupported_algorithm_coerces_to_sac(self, caplog):
        from smart_pid_core.domain.services.rl_engine import RLEngine

        with caplog.at_level("WARNING"):
            engine = RLEngine(algorithm="PPO")
        assert engine.algorithm == "SAC"
        assert "rl_unsupported_algorithm" in caplog.text

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
            integral_type='GAIN_KI',
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
            integral_type='GAIN_KI',
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
            integral_type='GAIN_KI',
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
            integral_type='GAIN_KI',
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
            integral_type='GAIN_KI',
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
            integral_type='GAIN_KI',
        )
        assert engine.step_count == 1

        engine.compute_gamma(
            error=3.0, delta_error=-2.0, ki_current=1.0, span=100.0,
            co=52.0, integral_val=5.0,
            objective=ControlObjective.SP_TRACKING,
            speed=ProcessSpeed.MEDIUM,
            limit_min=0.1, limit_max=100.0,
            integral_type='GAIN_KI',
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
            integral_type='GAIN_KI',
        )
        return decision.new_ki

    def test_ultra_fast_changes_ki_most(self):
        ki_ultra = self._get_new_ki(ProcessSpeed.ULTRA_FAST)
        ki_slow = self._get_new_ki(ProcessSpeed.SLOW)
        # ULTRA_FAST has the largest Sv → largest Ki change per gamma
        assert abs(ki_ultra - 10.0) > abs(ki_slow - 10.0)

    def test_fast_changes_more_than_medium(self):
        ki_fast = self._get_new_ki(ProcessSpeed.FAST)
        ki_medium = self._get_new_ki(ProcessSpeed.MEDIUM)
        # FAST has larger Sv than MEDIUM
        assert abs(ki_fast - 10.0) > abs(ki_medium - 10.0)


class TestEventRelativeTimeEscalation:
    """steps_in_error should track consecutive out-of-band cycles, not wall-clock step_count."""

    def test_steps_in_error_resets_on_near_zero_error(self):
        from smart_pid_core.domain.services.rl_engine import RLEngine

        engine = RLEngine()
        # 5 cycles with a large error -> steps_in_error should climb to 5.
        for _ in range(5):
            engine.compute_gamma(
                error=20.0, delta_error=0.0, ki_current=1.0, span=100.0,
                co=50.0, integral_val=0.0,
                objective=ControlObjective.SP_TRACKING,
                speed=ProcessSpeed.MEDIUM,
                limit_min=0.1, limit_max=100.0,
                integral_type='GAIN_KI',
            )
        assert engine._steps_in_error == 5

        # 1 cycle with near-zero error -> counter resets to 0.
        engine.compute_gamma(
            error=0.001, delta_error=0.0, ki_current=1.0, span=100.0,
            co=50.0, integral_val=0.0,
            objective=ControlObjective.SP_TRACKING,
            speed=ProcessSpeed.MEDIUM,
            limit_min=0.1, limit_max=100.0,
            integral_type='GAIN_KI',
        )
        assert engine._steps_in_error == 0

        # Large error again -> counter climbs from 0, not from 6 (step_count).
        engine.compute_gamma(
            error=20.0, delta_error=0.0, ki_current=1.0, span=100.0,
            co=50.0, integral_val=0.0,
            objective=ControlObjective.SP_TRACKING,
            speed=ProcessSpeed.MEDIUM,
            limit_min=0.1, limit_max=100.0,
            integral_type='GAIN_KI',
        )
        assert engine._steps_in_error == 1
        assert engine.step_count == 7


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

    def test_surge_level_reversal_penalizes_with_explicit_prev_delta(self):
        from smart_pid_core.domain.services.rl_engine import compute_reward_surge_level

        # Same |co - prev_co| in both cases; only the reversal differs.
        reward_no_reversal = compute_reward_surge_level(
            error=0.0, delta_error=0.0, co=52.0, prev_co=50.0, step=0, prev_delta_co=2.0,
        )
        reward_reversal = compute_reward_surge_level(
            error=0.0, delta_error=0.0, co=48.0, prev_co=50.0, step=0, prev_delta_co=2.0,
        )
        assert reward_reversal < reward_no_reversal

    def test_surge_level_no_cross_engine_contamination(self):
        """Two RLEngine instances must track prev_delta_co independently."""
        from smart_pid_core.domain.services.rl_engine import RLEngine

        engine1 = RLEngine()
        engine2 = RLEngine()
        engine1._prev_co = 50.0
        engine1._prev_delta_co = 5.0  # engine1 "remembers" co was rising
        engine2._prev_co = 50.0
        engine2._prev_delta_co = None  # engine2 has no history

        # Same current step for both: co drops from 50 to 45.
        r1 = engine1.compute_reward(0.0, 0.0, 45.0, 100.0, ControlObjective.SURGE_LEVEL)
        r2 = engine2.compute_reward(0.0, 0.0, 45.0, 100.0, ControlObjective.SURGE_LEVEL)

        # engine1 sees a reversal (prev_delta_co=+5 vs curr_delta=-5) -> penalized.
        # engine2 has no prior delta -> no reversal penalty.
        assert r1 < r2
        # Each instance updated its OWN state, proving no shared module state.
        assert engine1._prev_delta_co == pytest.approx(-5.0)
        assert engine2._prev_delta_co == pytest.approx(-5.0)


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
            integral_type='GAIN_KI',
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
            integral_type='GAIN_KI',
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
            ki_current=50.0,
            limit_min=1.0,
            limit_max=100.0,
        )
        for v in obs:
            assert -1.0 <= v <= 1.0

    def test_normalization_zero_span(self):
        from smart_pid_core.domain.services.rl_engine import RLEngine

        engine = RLEngine()
        obs = engine._normalize_observation(
            error=10.0, delta_error=5.0, span=0.0, co=50.0, integral_val=0.0,
            ki_current=10.0, limit_min=1.0, limit_max=100.0,
        )
        assert obs[0] == 0.0
        assert obs[1] == 0.0

    def test_normalization_typical_values(self):
        from smart_pid_core.domain.services.rl_engine import RLEngine

        engine = RLEngine()
        # ki_current=10 is the geometric midpoint of [1, 100] -> ti_norm == 0
        obs = engine._normalize_observation(
            error=10.0, delta_error=-5.0, span=100.0, co=50.0, integral_val=50.0,
            ki_current=10.0, limit_min=1.0, limit_max=100.0,
        )
        assert obs[0] == pytest.approx(0.1)   # 10/100
        assert obs[1] == pytest.approx(-0.05)  # -5/100
        assert obs[2] == pytest.approx(0.0)   # (50-50)/50
        assert obs[3] == pytest.approx(0.5)   # 50/100
        assert obs[4] == pytest.approx(0.0)   # geometric midpoint of [1, 100]

    def test_ti_norm_at_limit_min(self):
        from smart_pid_core.domain.services.rl_engine import RLEngine

        engine = RLEngine()
        obs = engine._normalize_observation(
            error=0.0, delta_error=0.0, span=100.0, co=50.0, integral_val=0.0,
            ki_current=1.0, limit_min=1.0, limit_max=100.0,
        )
        assert obs[4] == pytest.approx(-1.0)

    def test_ti_norm_at_limit_max(self):
        from smart_pid_core.domain.services.rl_engine import RLEngine

        engine = RLEngine()
        obs = engine._normalize_observation(
            error=0.0, delta_error=0.0, span=100.0, co=50.0, integral_val=0.0,
            ki_current=100.0, limit_min=1.0, limit_max=100.0,
        )
        assert obs[4] == pytest.approx(1.0)

    def test_ti_norm_at_geometric_midpoint(self):
        from smart_pid_core.domain.services.rl_engine import RLEngine

        engine = RLEngine()
        obs = engine._normalize_observation(
            error=0.0, delta_error=0.0, span=100.0, co=50.0, integral_val=0.0,
            ki_current=10.0, limit_min=1.0, limit_max=100.0,
        )
        assert obs[4] == pytest.approx(0.0)

    def test_ti_norm_zero_when_limit_min_is_zero(self):
        from smart_pid_core.domain.services.rl_engine import RLEngine

        engine = RLEngine()
        obs = engine._normalize_observation(
            error=0.0, delta_error=0.0, span=100.0, co=50.0, integral_val=0.0,
            ki_current=50.0, limit_min=0.0, limit_max=100.0,
        )
        assert obs[4] == pytest.approx(0.0)


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
            integral_type='GAIN_KI',
        )
        assert len(engine._replay_buffer) == 0

        # Second call: has previous observation, stores transition
        engine.compute_gamma(
            error=3.0, delta_error=-2.0, ki_current=1.05, span=100.0,
            co=52.0, integral_val=5.0,
            objective=ControlObjective.SP_TRACKING,
            speed=ProcessSpeed.MEDIUM,
            limit_min=0.1, limit_max=100.0,
            integral_type='GAIN_KI',
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
                integral_type='GAIN_KI',
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
            integral_type='GAIN_KI',
        )
        assert -1.0 <= decision.gamma <= 1.0
        assert 0.1 <= decision.new_ki <= 100.0
        assert len(decision.reasoning) > 0


class TestFallbackOscillationDetector:
    """Fallback policy must detect oscillation and back off integral action."""

    def test_oscillating_error_produces_negative_gamma(self):
        """When error sign flips rapidly, gamma should be negative (back off)."""
        from smart_pid_core.domain.services.rl_engine import _FallbackPolicy

        fp = _FallbackPolicy()
        # Feed alternating positive/negative errors to trigger oscillation
        errors = [0.3, -0.3, 0.3, -0.3, 0.3, -0.3, 0.3, -0.3,
                  0.3, -0.3, 0.3, -0.3, 0.3, -0.3]
        prev = 0.0
        last_gamma = 0.0
        for err in errors:
            de = err - prev
            last_gamma = fp.predict([err, de, 0.0, 0.0])
            prev = err
        # After many sign reversals, gamma should be negative (damping)
        assert last_gamma < 0.0

    def test_steady_error_no_oscillation(self):
        """With steady error (no oscillation), normal P+D policy applies."""
        from smart_pid_core.domain.services.rl_engine import _FallbackPolicy

        fp = _FallbackPolicy()
        # Feed constant positive error — no sign changes
        for _ in range(20):
            gamma = fp.predict([0.2, 0.0, 0.0, 0.0])
        # Positive error → positive gamma (normal behavior)
        assert gamma > 0.0

    def test_oscillation_increases_ti_for_time_ti(self):
        """In TIME_TI mode, oscillation detection should cause Ti to increase."""
        from smart_pid_core.domain.services.rl_engine import RLEngine

        engine = RLEngine()
        ti = 1.0  # Start low (unstable)
        # Oscillating errors
        errors = [0.3, -0.3] * 20
        prev_err = 0.0
        for err in errors:
            de = err - prev_err
            decision = engine.compute_gamma(
                error=err * 100, delta_error=de * 100,
                ki_current=ti, span=100.0,
                co=50.0, integral_val=0.0,
                objective=ControlObjective.SP_TRACKING,
                speed=ProcessSpeed.MEDIUM,
                limit_min=0.1, limit_max=100.0,
                integral_type="TIME_TI",
            )
            ti = decision.new_ki
            prev_err = err
        # Ti should have increased significantly from 1.0
        assert ti > 5.0, f"Ti={ti} should have increased from 1.0 with oscillation"


class TestStatsReward:
    """compute_reward_from_stats() -- windowed-KPI reward, and its wiring."""

    def _stats(self, **overrides):
        base = {
            "sample_count": 50,
            "mean_abs_error": 1.0,
            "osc": 0.1,
            "tv_per_sample": 2.0,
            "recent_pk_pk_error": 1.0,
        }
        base.update(overrides)
        return base

    def test_sample_count_too_small_returns_none(self):
        from smart_pid_core.domain.services.rl_engine import compute_reward_from_stats

        stats = self._stats(sample_count=5)
        reward = compute_reward_from_stats(
            stats, span=100.0, objective=ControlObjective.SP_TRACKING
        )
        assert reward is None

    def test_zero_span_returns_none(self):
        from smart_pid_core.domain.services.rl_engine import compute_reward_from_stats

        stats = self._stats()
        reward = compute_reward_from_stats(
            stats, span=0.0, objective=ControlObjective.SP_TRACKING
        )
        assert reward is None

    @pytest.mark.parametrize(
        "objective",
        [
            ControlObjective.SP_TRACKING,
            ControlObjective.DISTURBANCE_REJECTION,
            ControlObjective.SURGE_LEVEL,
        ],
    )
    def test_worse_kpis_give_strictly_lower_reward(self, objective):
        from smart_pid_core.domain.services.rl_engine import compute_reward_from_stats

        good = self._stats(mean_abs_error=0.1, osc=0.0, tv_per_sample=0.5)
        bad = self._stats(mean_abs_error=20.0, osc=0.9, tv_per_sample=40.0)
        r_good = compute_reward_from_stats(good, span=100.0, objective=objective)
        r_bad = compute_reward_from_stats(bad, span=100.0, objective=objective)
        assert r_good is not None
        assert r_bad is not None
        assert r_bad < r_good

    def test_compute_gamma_uses_stats_reward_when_provided(self):
        from smart_pid_core.domain.services.rl_engine import (
            RLEngine,
            compute_reward_from_stats,
        )

        engine = RLEngine()
        engine.compute_gamma(
            error=5.0, delta_error=1.0, ki_current=1.0, span=100.0,
            co=50.0, integral_val=0.0,
            objective=ControlObjective.SP_TRACKING,
            speed=ProcessSpeed.MEDIUM,
            limit_min=0.1, limit_max=100.0,
            integral_type='GAIN_KI',
        )
        stats = self._stats(mean_abs_error=0.1, osc=0.0, tv_per_sample=0.5)
        engine.compute_gamma(
            error=3.0, delta_error=-2.0, ki_current=1.05, span=100.0,
            co=52.0, integral_val=5.0,
            objective=ControlObjective.SP_TRACKING,
            speed=ProcessSpeed.MEDIUM,
            limit_min=0.1, limit_max=100.0,
            integral_type='GAIN_KI',
            stats=stats,
        )
        stored_reward = engine._replay_buffer[-1][2]
        expected = compute_reward_from_stats(
            stats, span=100.0, objective=ControlObjective.SP_TRACKING
        )
        assert stored_reward == pytest.approx(expected)

    def test_save_state_includes_version_2(self, tmp_path):
        from smart_pid_core.domain.services.rl_engine import RLEngine

        engine = RLEngine()
        state = engine.save_state(tmp_path)
        assert state["version"] == 2

    def test_load_state_discards_version_1_state(self, tmp_path):
        from smart_pid_core.domain.services.rl_engine import RLEngine

        engine = RLEngine()
        old_state = {
            "algorithm": "SAC",
            "model_path": "",
            "is_trained": False,
            "step_count": 10,
            "reward_steps": 5,
            "total_reward": 1.0,
            "replay_buffer": [
                {
                    "obs": [0.0, 0.0, 0.0, 0.0, 0.0],
                    "action": 0.0,
                    "reward": 0.0,
                    "next_obs": [0.0, 0.0, 0.0, 0.0, 0.0],
                    "done": False,
                }
            ],
            "fallback": {"integral": 0.0, "error_signs": [], "recent_errors": []},
        }
        engine.load_state(old_state, tmp_path)
        assert len(engine._replay_buffer) == 0


class TestPolicyGate:
    """The neural policy must not drive Ti until it has demonstrably trained."""

    def test_untrained_model_uses_fallback(self):
        from smart_pid_core.domain.services.rl_engine import RLEngine

        engine = RLEngine()
        engine._model = object()  # any non-None stub; untrained
        engine._train_success_count = 0
        engine._is_trained = False

        decision = engine.compute_gamma(
            error=5.0, delta_error=0.0, ki_current=1.0, span=100.0,
            co=50.0, integral_val=0.0,
            objective=ControlObjective.SP_TRACKING,
            speed=ProcessSpeed.MEDIUM,
            limit_min=0.1, limit_max=100.0,
            integral_type='GAIN_KI',
        )
        assert decision.reasoning.startswith("RL(fallback)")

    def test_sufficiently_trained_model_is_used(self):
        from smart_pid_core.domain.services.rl_engine import RLEngine

        class _StubModel:
            def predict(self, obs, deterministic=False):
                return [0.2], None

        engine = RLEngine()
        engine._model = _StubModel()
        engine._train_success_count = 3

        decision = engine.compute_gamma(
            error=5.0, delta_error=0.0, ki_current=1.0, span=100.0,
            co=50.0, integral_val=0.0,
            objective=ControlObjective.SP_TRACKING,
            speed=ProcessSpeed.MEDIUM,
            limit_min=0.1, limit_max=100.0,
            integral_type='GAIN_KI',
        )
        assert decision.reasoning.startswith("RL(SAC)")

    def test_loaded_model_with_zero_online_trains_is_used(self):
        """A model restored from disk (is_trained=True) is trusted with 0 online rounds."""
        from smart_pid_core.domain.services.rl_engine import RLEngine

        class _StubModel:
            def predict(self, obs, deterministic=False):
                return [0.2], None

        engine = RLEngine()
        engine._model = _StubModel()
        engine._is_trained = True
        engine._train_success_count = 0

        decision = engine.compute_gamma(
            error=5.0, delta_error=0.0, ki_current=1.0, span=100.0,
            co=50.0, integral_val=0.0,
            objective=ControlObjective.SP_TRACKING,
            speed=ProcessSpeed.MEDIUM,
            limit_min=0.1, limit_max=100.0,
            integral_type='GAIN_KI',
        )
        assert decision.reasoning.startswith("RL(SAC)")

    def test_constructor_params_propagate(self):
        from smart_pid_core.domain.services.rl_engine import RLEngine

        engine = RLEngine(
            fallback_kp=0.9, fallback_kd=0.4, train_interval=7, learning_rate=1e-3,
        )
        assert engine._fallback._kp == pytest.approx(0.9)
        assert engine._fallback._kd == pytest.approx(0.4)
        assert engine._train_interval == 7
        assert engine._learning_rate == pytest.approx(1e-3)

    def test_train_failure_logs_warning_once_then_debug(self, caplog, monkeypatch):
        from smart_pid_core.domain.services.rl_engine import RLEngine

        engine = RLEngine()
        monkeypatch.setattr(engine, "_check_sb3", lambda: True)

        def _boom():
            raise RuntimeError("boom")

        monkeypatch.setattr(engine, "_online_train_sb3", _boom)

        with caplog.at_level("DEBUG"):
            engine._try_online_train()
            engine._try_online_train()

        warnings = [r for r in caplog.records if r.levelname == "WARNING"]
        assert len(warnings) == 1

    def test_model_predict_failure_discards_model_and_falls_back(self):
        """A stale/incompatible model must not wedge the loop into permanent errors."""
        from smart_pid_core.domain.services.rl_engine import RLEngine

        class _BrokenModel:
            def predict(self, obs, deterministic=False):
                raise ValueError("shape mismatch")

        engine = RLEngine()
        engine._model = _BrokenModel()
        engine._train_success_count = 3

        decision = engine.compute_gamma(
            error=5.0, delta_error=0.0, ki_current=1.0, span=100.0,
            co=50.0, integral_val=0.0,
            objective=ControlObjective.SP_TRACKING,
            speed=ProcessSpeed.MEDIUM,
            limit_min=0.1, limit_max=100.0,
            integral_type='GAIN_KI',
        )
        assert decision is not None
        assert decision.reasoning.startswith("RL(fallback)")
        assert engine._model is None
