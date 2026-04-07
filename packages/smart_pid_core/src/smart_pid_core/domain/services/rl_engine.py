"""Reinforcement Learning engine for Ki optimization.

Uses stable-baselines3 (SAC or PPO) with lazy imports.
Falls back to a proportional baseline policy when sb3 is unavailable or untrained.
"""
from __future__ import annotations

import logging
import math
from collections import deque
from typing import TYPE_CHECKING

from smart_pid_core.domain.services.fuzzy_engine import AIDecision

if TYPE_CHECKING:
    from pathlib import Path

    from smart_pid_domain.enums import ControlObjective, ProcessSpeed

logger = logging.getLogger(__name__)

# Observation space bounds for normalization: [error, delta_error, CO, integral_val]
# Each normalized to [-1, 1]
OBS_DIM = 4
ACTION_DIM = 1

# ── Reward Design Philosophy ─────────────────────────────────────────
#
# Each control objective defines a DIFFERENT reward function because the
# RL agent must learn fundamentally different behaviors:
#
# ┌─────────────────────┬──────────────────┬──────────────┬────────────┐
# │ Objective           │ Primary KPI      │ Secondary    │ TV Weight  │
# ├─────────────────────┼──────────────────┼──────────────┼────────────┤
# │ SP Tracking         │ IAE (fast resp.) │ Overshoot    │ Moderate   │
# │ Disturbance Reject. │ ISE (kill offset)│ ITAE (time)  │ Low        │
# │ Surge Level         │ TV (valve calm)  │ Deadband IAE │ Dominant   │
# └─────────────────────┴──────────────────┴──────────────┴────────────┘
#
# All errors are normalized to [-1, +1] of span before entering here.

_SURGE_DEADBAND = 0.02  # 2% of span — free floating zone


def compute_reward_sp_tracking(
    error: float,
    delta_error: float,
    co: float,
    prev_co: float | None,
    step: int,
) -> float:
    """Reward for SP_TRACKING (Setpoint Following).

    Goal: reach new setpoint fast with ZERO overshoot.
    Strategy:
      - IAE: penalize distance from target (drives fast response)
      - Overshoot detector: extra penalty when error flips sign
        (PV crossed SP → overshoot happening)
      - Moderate TV: some valve movement is OK for speed, but
        excessive chattering wastes the actuator
    KPIs: IAE, rise time, overshoot %
    """
    # IAE — primary driver for fast convergence
    iae = -1.0 * abs(error)

    # Overshoot penalty: if error and delta_error have opposite signs,
    # PV is moving AWAY from SP after having crossed it
    overshoot = 0.0
    if error * delta_error < 0 and abs(error) < 0.1:
        overshoot = -2.0 * abs(delta_error)

    # TV — moderate penalty (allow valve movement for speed)
    tv = 0.0
    if prev_co is not None:
        tv = -0.3 * abs(co - prev_co) / 100.0

    # Small bonus for being very close to setpoint
    settle_bonus = 0.5 if abs(error) < 0.005 else 0.0

    return iae + overshoot + tv + settle_bonus


def compute_reward_disturbance_rejection(
    error: float,
    delta_error: float,
    co: float,
    prev_co: float | None,
    step: int,
) -> float:
    """Reward for DISTURBANCE_REJECTION (Regulatory Control).

    Goal: SP is fixed. Kill offset FAST when disturbances hit.
    Strategy:
      - ISE: squared error penalizes ANY residual offset heavily
        (small persistent errors are worse than brief large ones)
      - ITAE: time-weighted — the longer offset persists, the worse
      - Very low TV: allow aggressive valve action to fight disturbances
      - Bonus for error recovery speed (delta_error toward zero)
    KPIs: ISE, ITAE, time to recover to ±0.5% of span
    """
    # ISE — squared error makes the agent extremely aggressive near zero
    ise = -2.0 * error * error

    # ITAE — time-weighted penalty for lingering offset
    itae = -0.8 * abs(error) * min((step + 1) * 0.01, 5.0)

    # Recovery bonus: reward when error is shrinking (delta_error opposing error)
    recovery = 0.0
    if abs(error) > 0.01 and error * delta_error < 0:
        recovery = 0.3 * abs(delta_error)

    # Minimal TV — let the valve fight the disturbance freely
    tv = 0.0
    if prev_co is not None:
        tv = -0.05 * abs(co - prev_co) / 100.0

    return ise + itae + recovery + tv


def compute_reward_surge_level(
    error: float,
    delta_error: float,
    co: float,
    prev_co: float | None,
    step: int,
) -> float:
    """Reward for SURGE_LEVEL (Buffer Tank / Averaging Level Control).

    Goal: keep the valve CALM. PV may float freely within a deadband.
    Only react when PV approaches dangerous limits.
    Strategy:
      - Valve stability is the PRIMARY metric (TV dominance)
      - Error inside deadband → zero penalty (let PV float)
      - Error outside deadband → escalating penalty (approaching limits)
      - CO direction change penalty (chattering is the worst outcome)
    KPIs: TV, valve reversals, time inside deadband
    """
    # Valve stability — DOMINANT reward component
    stability = 0.0
    if prev_co is not None:
        co_change = abs(co - prev_co) / 100.0
        # Exponential reward: 1.0 when perfectly still, decays with movement
        stability = 1.5 * math.exp(-8.0 * co_change)
        # Extra penalty for valve direction reversal (chattering)
        if hasattr(compute_reward_surge_level, "_prev_delta_co"):
            prev_delta = compute_reward_surge_level._prev_delta_co
            curr_delta = co - prev_co
            if prev_delta * curr_delta < 0:  # sign changed = reversal
                stability -= 0.5
        compute_reward_surge_level._prev_delta_co = co - prev_co

    # Deadband: zero penalty inside ±2% of span
    error_penalty = 0.0
    abs_err = abs(error)
    if abs_err > _SURGE_DEADBAND:
        # Quadratic escalation outside deadband — gentle near edge, aggressive at limits
        excess = abs_err - _SURGE_DEADBAND
        error_penalty = -3.0 * excess * excess

    return stability + error_penalty


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
        self._reward_steps = 0
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
    def reward_steps(self) -> int:
        return self._reward_steps

    @property
    def step_count(self) -> int:
        return self._step_count

    @property
    def avg_reward(self) -> float:
        if self._reward_steps == 0:
            return 0.0
        return self._total_reward / self._reward_steps

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
                error, delta_error, co, self._prev_co, self._step_count
            )
        elif objective == CO.DISTURBANCE_REJECTION:
            return compute_reward_disturbance_rejection(
                error, delta_error, co, self._prev_co, self._step_count
            )
        else:
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
        integral_type: str = "TIME_TI",
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
            self._reward_steps += 1

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

        # Update Ki/Ti — invert gamma for Ti (increasing Ti slows response)
        sv = speed.speed_factor
        effective_gamma = gamma if integral_type == "GAIN_KI" else -gamma
        new_val = ki_current * (1.0 + effective_gamma * sv)
        new_val = max(limit_min, min(limit_max, new_val))

        param_label = "Ki" if integral_type == "GAIN_KI" else "Ti"
        reasoning += (
            f", Sv={sv}, {param_label}: {ki_current:.4f} -> {new_val:.4f}"
        )

        return AIDecision(
            gamma=gamma,
            new_ki=new_val,
            reasoning=reasoning,
            membership_values=None,
        )

    def update(self, reward: float, observation: list[float] | None = None) -> None:
        """Manually inject a reward signal and optional new observation.

        This allows external callers to provide reward feedback.
        The transition is stored in the replay buffer for training.
        """
        self._reward_steps += 1
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
        """Run online training with sb3 model (SAC or PPO)."""
        import numpy as np

        if self._model is None:
            self._init_sb3_model()

        if self._model is None:
            return

        buffer_list = list(self._replay_buffer)
        if len(buffer_list) < self._train_batch_size:
            return

        if self._algorithm == "SAC":
            self._train_sac(buffer_list, np)
        else:
            self._train_ppo(buffer_list, np)

        self._is_trained = True
        logger.debug(
            "rl_online_train algo=%s step=%d buffer=%d",
            self._algorithm, self._step_count, len(self._replay_buffer),
        )

    def _train_sac(self, buffer_list: list, np) -> None:  # noqa: ANN001
        """Off-policy SAC: add transitions to replay buffer and run gradient steps."""
        for obs, action, reward, next_obs, done in buffer_list[-self._train_batch_size:]:
            self._model.replay_buffer.add(
                np.array(obs, dtype=np.float32),
                np.array(next_obs, dtype=np.float32),
                np.array([action], dtype=np.float32),
                np.array([reward], dtype=np.float32),
                np.array([done], dtype=np.float32),
                [{}],
            )
        self._model.train(gradient_steps=4, batch_size=self._train_batch_size)

    def _train_ppo(self, buffer_list: list, np) -> None:  # noqa: ANN001
        """On-policy PPO: fill rollout buffer and call learn().

        PPO uses a RolloutBuffer (on-policy), not a ReplayBuffer.
        We collect the last N transitions as a mini-rollout.
        """
        rollout = self._model.rollout_buffer
        rollout.reset()

        batch = buffer_list[-self._train_batch_size:]
        for obs, action, reward, _next_obs, _done in batch:
            rollout.add(
                obs=np.array(obs, dtype=np.float32).reshape(1, -1),
                action=np.array([action], dtype=np.float32).reshape(1, -1),
                reward=np.array([reward], dtype=np.float32),
                episode_start=np.array([False]),
                value=self._model.policy.predict_values(
                    self._model.policy.obs_to_tensor(
                        np.array(obs, dtype=np.float32).reshape(1, -1)
                    )[0]
                ),
                log_prob=np.array([0.0], dtype=np.float32),
            )

        # Compute returns and advantages
        last_obs = np.array(batch[-1][3], dtype=np.float32).reshape(1, -1)
        last_value = self._model.policy.predict_values(
            self._model.policy.obs_to_tensor(last_obs)[0]
        )
        rollout.compute_returns_and_advantage(
            last_values=last_value, dones=np.array([False]),
        )

        # Run PPO update
        self._model.train()

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
            "rl_model_saved path=%s episodes=%d", str(path), self._reward_steps
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
