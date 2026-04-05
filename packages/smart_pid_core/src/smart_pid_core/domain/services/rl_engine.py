"""Reinforcement Learning engine for Ki optimization.

Uses stable-baselines3 (SAC or PPO) with lazy imports.
Falls back to a proportional baseline policy when sb3 is unavailable or untrained.
"""
from __future__ import annotations

import logging
import math
from collections import deque
from typing import TYPE_CHECKING

from smart_pid_core.domain.services.fuzzy_engine import SPEED_FACTORS, AIDecision

if TYPE_CHECKING:
    from pathlib import Path

    from smart_pid_domain.enums import ControlObjective, ProcessSpeed

logger = logging.getLogger(__name__)

# Observation space bounds for normalization: [error, delta_error, CO, integral_val]
# Each normalized to [-1, 1]
OBS_DIM = 4
ACTION_DIM = 1

# Reward weighting constants
_IAE_WEIGHT = 1.0
_TV_PENALTY = 0.3
_ITAE_WEIGHT = 0.5
_DEADBAND_FRACTION = 0.02  # 2% of span for surge level deadband


def compute_reward_sp_tracking(
    error: float,
    delta_error: float,
    co: float,
    prev_co: float | None,
    step: int,
) -> float:
    """Reward for SP_TRACKING / DISTURBANCE_REJECTION objectives.

    Minimizes IAE/ITAE and penalizes total variation (valve chattering).

    Args:
        error: Normalized error in [-1, 1].
        delta_error: Normalized delta_error in [-1, 1].
        co: Current controller output in [0, 100].
        prev_co: Previous controller output (None on first step).
        step: Time step count for ITAE weighting.

    Returns:
        Reward value (higher is better).
    """
    # IAE component: penalize absolute error
    iae_penalty = -_IAE_WEIGHT * abs(error)

    # ITAE component: penalize errors that persist over time
    itae_penalty = -_ITAE_WEIGHT * abs(error) * (step + 1) * 0.01

    # TV penalty: penalize large CO changes (valve chattering)
    tv_penalty = 0.0
    if prev_co is not None:
        tv_penalty = -_TV_PENALTY * abs(co - prev_co) / 100.0

    return iae_penalty + itae_penalty + tv_penalty


def compute_reward_surge_level(
    error: float,
    delta_error: float,
    co: float,
    prev_co: float | None,
    span: float,
) -> float:
    """Reward for SURGE_LEVEL objective.

    Rewards valve stability, penalizes IAE only outside deadband.

    Args:
        error: Normalized error in [-1, 1].
        delta_error: Normalized delta_error in [-1, 1].
        co: Current controller output in [0, 100].
        prev_co: Previous controller output (None on first step).
        span: Process span for deadband calculation.

    Returns:
        Reward value (higher is better).
    """
    # Valve stability reward: small CO changes are good
    stability_reward = 0.0
    if prev_co is not None:
        co_change = abs(co - prev_co) / 100.0
        # Reward = 1.0 when no change, decays with change magnitude
        stability_reward = 1.0 * math.exp(-5.0 * co_change)

    # IAE penalty only outside deadband
    deadband = _DEADBAND_FRACTION  # Normalized deadband
    iae_penalty = (
        -_IAE_WEIGHT * (abs(error) - deadband) if abs(error) > deadband else 0.0
    )

    return stability_reward + iae_penalty


class _FallbackPolicy:
    """Simple proportional policy used when sb3 is not available.

    Maps observation to gamma using a proportional-derivative strategy:
    gamma = -Kp * error - Kd * delta_error

    This provides a reasonable baseline that increases Ki when error is
    positive (process below setpoint) and decreases Ki when error is
    negative.
    """

    def __init__(self, kp: float = 0.5, kd: float = 0.2) -> None:
        self._kp = kp
        self._kd = kd

    def predict(self, observation: list[float]) -> float:
        """Return gamma in [-1, 1] based on error and delta_error."""
        error = observation[0]  # Normalized error
        delta_error = observation[1]  # Normalized delta error

        gamma = self._kp * error + self._kd * delta_error
        return max(-1.0, min(1.0, gamma))


class RLEngine:
    """RL-based Ki optimizer using SAC or PPO.

    Pure domain service -- lazy imports sb3 only when training or loading.
    When sb3 is unavailable or no model is trained, falls back to a
    proportional baseline policy.
    """

    def __init__(self, algorithm: str = "SAC") -> None:
        self._algorithm = algorithm
        self._model = None
        self._sb3_available: bool | None = None
        self._is_trained = False
        self._episode_count = 0
        self._total_reward = 0.0
        self._step_count = 0

        # Experience buffer for online training
        self._last_observation: list[float] | None = None
        self._last_action: float | None = None
        self._prev_co: float | None = None

        # Replay buffer for online training (stores transitions)
        self._replay_buffer: deque[tuple[list[float], float, float, list[float], bool]] = (
            deque(maxlen=10_000)
        )

        # Fallback policy
        self._fallback = _FallbackPolicy()

        # Training config
        self._train_batch_size = 64
        self._train_interval = 32  # Train every N steps
        self._min_buffer_size = 128  # Minimum transitions before training

    @property
    def algorithm(self) -> str:
        return self._algorithm

    @property
    def is_trained(self) -> bool:
        return self._is_trained

    @property
    def episode_count(self) -> int:
        return self._episode_count

    @property
    def step_count(self) -> int:
        return self._step_count

    @property
    def avg_reward(self) -> float:
        if self._episode_count == 0:
            return 0.0
        return self._total_reward / self._episode_count

    def _check_sb3(self) -> bool:
        """Check if stable-baselines3 is available (cached)."""
        if self._sb3_available is None:
            try:
                import stable_baselines3  # noqa: F401

                self._sb3_available = True
            except ImportError:
                self._sb3_available = False
        return self._sb3_available

    def _normalize_observation(
        self,
        error: float,
        delta_error: float,
        span: float,
        co: float,
        integral_val: float,
    ) -> list[float]:
        """Normalize observation to [-1, 1] range."""
        if span > 0:
            error_norm = max(-1.0, min(1.0, error / span))
            delta_error_norm = max(-1.0, min(1.0, delta_error / span))
        else:
            error_norm = 0.0
            delta_error_norm = 0.0
        co_norm = max(-1.0, min(1.0, (co - 50.0) / 50.0))  # [0,100] -> [-1,1]
        integral_norm = max(-1.0, min(1.0, integral_val / 100.0))
        return [error_norm, delta_error_norm, co_norm, integral_norm]

    def compute_reward(
        self,
        error: float,
        delta_error: float,
        co: float,
        span: float,
        objective: ControlObjective,
    ) -> float:
        """Compute reward based on control objective.

        Args:
            error: Normalized error in [-1, 1].
            delta_error: Normalized delta_error in [-1, 1].
            co: Controller output in [0, 100].
            span: Process span.
            objective: Control objective for reward shaping.

        Returns:
            Reward value.
        """
        from smart_pid_domain.enums import ControlObjective as CO

        if objective == CO.SURGE_LEVEL:
            return compute_reward_surge_level(
                error, delta_error, co, self._prev_co, span
            )
        else:
            # SP_TRACKING and DISTURBANCE_REJECTION use same reward
            return compute_reward_sp_tracking(
                error, delta_error, co, self._prev_co, self._step_count
            )

    def compute_gamma(
        self,
        error: float,
        delta_error: float,
        ki_current: float,
        span: float,
        co: float,
        integral_val: float,
        objective: ControlObjective,
        speed: ProcessSpeed,
        limit_min: float,
        limit_max: float,
    ) -> AIDecision:
        """Compute gamma from RL model or fallback policy.

        Args:
            error: Raw error in engineering units.
            delta_error: Raw delta_error in engineering units.
            ki_current: Current Ki value.
            span: Process span for normalization.
            co: Controller output [0, 100].
            integral_val: Current integral accumulator.
            objective: Control objective for reward shaping.
            speed: Process speed for speed factor.
            limit_min: Minimum allowed Ki.
            limit_max: Maximum allowed Ki.

        Returns:
            AIDecision with gamma, new Ki, reasoning, and debug info.
        """
        observation = self._normalize_observation(
            error, delta_error, span, co, integral_val
        )

        # Compute reward for the previous step (if we have prior observation)
        if self._last_observation is not None:
            reward = self.compute_reward(
                observation[0], observation[1], co, span, objective
            )
            self._total_reward += reward
            self._episode_count += 1

            # Store transition in replay buffer
            self._replay_buffer.append((
                self._last_observation,
                self._last_action if self._last_action is not None else 0.0,
                reward,
                observation,
                False,  # not terminal
            ))

        # Get action from model or fallback
        if self._model is not None:
            import numpy as np

            obs_array = np.array(observation, dtype=np.float32)
            action, _ = self._model.predict(obs_array, deterministic=True)
            gamma = (
                float(action[0]) if hasattr(action, "__getitem__") else float(action)
            )
            gamma = max(-1.0, min(1.0, gamma))
            reasoning = (
                f"RL({self._algorithm}): obs={_fmt_obs(observation)}, "
                f"gamma={gamma:.4f}"
            )
        else:
            # Fallback: proportional baseline policy
            gamma = self._fallback.predict(observation)
            reasoning = (
                f"RL(fallback): obs={_fmt_obs(observation)}, "
                f"gamma={gamma:.4f}"
            )

        # Store for next step's reward computation
        self._last_observation = observation
        self._last_action = gamma
        self._prev_co = co
        self._step_count += 1

        # Attempt online training periodically
        if (
            self._step_count % self._train_interval == 0
            and len(self._replay_buffer) >= self._min_buffer_size
        ):
            self._try_online_train()

        # Update Ki
        sv = SPEED_FACTORS[speed]
        new_ki = ki_current * (1.0 + gamma * sv)
        new_ki = max(limit_min, min(limit_max, new_ki))

        reasoning += f", Sv={sv}, Ki: {ki_current:.4f} -> {new_ki:.4f}"

        return AIDecision(
            gamma=gamma,
            new_ki=new_ki,
            reasoning=reasoning,
            membership_values=None,
        )

    def update(self, reward: float, observation: list[float] | None = None) -> None:
        """Manually inject a reward signal and optional new observation.

        This allows external callers to provide reward feedback.
        The transition is stored in the replay buffer for training.
        """
        self._episode_count += 1
        self._total_reward += reward

        if self._last_observation is not None:
            next_obs = observation if observation is not None else self._last_observation
            self._replay_buffer.append((
                self._last_observation,
                self._last_action if self._last_action is not None else 0.0,
                reward,
                next_obs,
                observation is None,  # terminal if no next observation
            ))

        if observation is not None:
            self._last_observation = observation

    def _try_online_train(self) -> None:
        """Attempt online training with collected experience."""
        if not self._check_sb3():
            return

        try:
            self._online_train_sb3()
        except Exception:
            logger.debug("rl_online_train_failed", exc_info=True)

    def _online_train_sb3(self) -> None:
        """Run a few gradient steps with sb3 model."""
        import numpy as np

        if self._model is None:
            self._init_sb3_model()

        if self._model is None:
            return

        # For SAC/PPO, we use the built-in replay buffer
        # Add transitions from our buffer
        buffer_list = list(self._replay_buffer)
        if len(buffer_list) < self._train_batch_size:
            return

        for obs, action, reward, next_obs, done in buffer_list[-self._train_batch_size :]:
            try:
                obs_arr = np.array(obs, dtype=np.float32)
                next_obs_arr = np.array(next_obs, dtype=np.float32)
                action_arr = np.array([action], dtype=np.float32)
                self._model.replay_buffer.add(
                    obs_arr,
                    next_obs_arr,
                    action_arr,
                    np.array([reward], dtype=np.float32),
                    np.array([done], dtype=np.float32),
                    [{}],
                )
            except (AttributeError, TypeError):
                # PPO doesn't have replay_buffer; skip online training for PPO
                return

        # Train a few gradient steps
        self._model.train(gradient_steps=4, batch_size=self._train_batch_size)
        self._is_trained = True
        logger.debug(
            "rl_online_train step=%d buffer=%d",
            self._step_count,
            len(self._replay_buffer),
        )

    def _init_sb3_model(self) -> None:
        """Initialize a new sb3 model for online training."""
        try:
            import gymnasium as gym
            import numpy as np
            from gymnasium import spaces

            obs_space = spaces.Box(
                low=-1.0, high=1.0, shape=(OBS_DIM,), dtype=np.float32
            )
            action_space = spaces.Box(
                low=-1.0, high=1.0, shape=(ACTION_DIM,), dtype=np.float32
            )

            # Create a dummy env spec for sb3
            class _DummyEnv(gym.Env):
                observation_space = obs_space
                action_space = action_space

                def reset(self, *, seed=None, options=None):
                    return np.zeros(OBS_DIM, dtype=np.float32), {}

                def step(self, action):
                    return (
                        np.zeros(OBS_DIM, dtype=np.float32),
                        0.0,
                        False,
                        False,
                        {},
                    )

            env = _DummyEnv()

            if self._algorithm == "SAC":
                from stable_baselines3 import SAC

                self._model = SAC(
                    "MlpPolicy",
                    env,
                    learning_rate=3e-4,
                    buffer_size=10_000,
                    batch_size=self._train_batch_size,
                    verbose=0,
                )
            else:
                from stable_baselines3 import PPO

                self._model = PPO(
                    "MlpPolicy",
                    env,
                    learning_rate=3e-4,
                    verbose=0,
                )
            logger.info("rl_model_initialized algorithm=%s", self._algorithm)
        except ImportError:
            logger.debug("sb3/gymnasium not available, using fallback policy")

    def save_model(self, path: Path) -> None:
        """Save trained model to disk."""
        if self._model is None:
            raise RuntimeError("No model to save")
        path.parent.mkdir(parents=True, exist_ok=True)
        self._model.save(str(path))
        logger.info(
            "rl_model_saved path=%s episodes=%d", str(path), self._episode_count
        )

    def load_model(self, path: Path) -> None:
        """Load a previously trained model."""
        if not path.exists():
            raise FileNotFoundError(f"Model not found: {path}")
        if not self._check_sb3():
            raise ImportError(
                "stable-baselines3 not installed. "
                "Install with: pip install smart-pid-core[ai]"
            )
        if self._algorithm == "SAC":
            from stable_baselines3 import SAC

            self._model = SAC.load(str(path))
        else:
            from stable_baselines3 import PPO

            self._model = PPO.load(str(path))
        self._is_trained = True
        logger.info("rl_model_loaded path=%s", str(path))

    def reset(self) -> None:
        """Reset engine state for a new episode."""
        self._last_observation = None
        self._last_action = None
        self._prev_co = None
        self._step_count = 0


def _fmt_obs(obs: list[float]) -> str:
    """Format observation for logging."""
    return f"[{', '.join(f'{v:.3f}' for v in obs)}]"
