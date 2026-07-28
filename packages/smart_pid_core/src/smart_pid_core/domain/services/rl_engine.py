"""Reinforcement Learning engine for Ki optimization.

Uses stable-baselines3 (SAC) with lazy imports.
Falls back to a proportional baseline policy when sb3 is unavailable or untrained.
"""
from __future__ import annotations

import logging
import math
from collections import deque
from dataclasses import dataclass
from typing import TYPE_CHECKING


@dataclass(frozen=True)
class AIDecision:
    """Result of an RL Ki optimization computation."""

    gamma: float
    new_ki: float
    reasoning: str
    membership_values: dict[str, dict[str, float]] | None = None

if TYPE_CHECKING:
    from pathlib import Path

    from smart_pid_domain.enums import ControlObjective, ProcessSpeed

logger = logging.getLogger(__name__)

# Observation space bounds for normalization:
# [error, delta_error, CO, integral_val, ti_norm]
# Each normalized to [-1, 1]. ti_norm is the actuated Ti/Ki value's
# log-scale position within [limit_min, limit_max] — without it, identical
# (error, delta_error, CO, integral_val) tuples can map to wildly different
# correct actions depending on the current Ti, breaking the Markov property.
OBS_DIM = 5
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
#
# Two reward paths feed compute_gamma:
#   1. compute_reward_from_stats() — preferred. Built from a StatsWorker
#      window (IAE/oscillation/TV KPIs covering everything that happened
#      between AI decisions).
#   2. compute_reward() / the point-sample functions below — fallback when
#      no windowed stats are available yet (aliased, instantaneous only).

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
      - IAE with time escalation: persistent error gets worse over time
      - Overshoot detector: extra penalty when error flips sign
      - Moderate TV: some valve movement is OK for speed
      - Strong bonus for convergence to drive exploration toward zero error
    KPIs: IAE, rise time, overshoot %
    """
    # IAE with time escalation — persistent errors become increasingly costly
    time_weight = min(1.0 + step * 0.02, 3.0)
    iae = -1.5 * abs(error) * time_weight

    # Overshoot penalty
    overshoot = 0.0
    if error * delta_error < 0 and abs(error) < 0.1:
        overshoot = -2.0 * abs(delta_error)

    # TV — moderate penalty
    tv = 0.0
    if prev_co is not None:
        tv = -0.3 * abs(co - prev_co) / 100.0

    # Progressive bonus: the closer to setpoint, the higher the reward
    if abs(error) < 0.005:
        settle_bonus = 1.0
    elif abs(error) < 0.02:
        settle_bonus = 0.5
    elif abs(error) < 0.05:
        settle_bonus = 0.2
    else:
        settle_bonus = 0.0

    # Improvement bonus: reward when error is shrinking
    improving = 0.0
    if abs(error) > 0.01 and error * delta_error < 0:
        improving = 0.4 * abs(delta_error)

    return iae + overshoot + tv + settle_bonus + improving


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
      - ISE with steep scaling: squared error penalizes any offset
      - ITAE with faster escalation: lingering offsets escalate quickly
      - Strong recovery bonus to reward aggressive correction
      - Very low TV: allow valve action to fight disturbances
    KPIs: ISE, ITAE, time to recover to ±0.5% of span
    """
    # ISE — squared error, scaled up for stronger signal
    ise = -3.0 * error * error

    # ITAE — faster escalation for persistent offsets
    itae = -1.2 * abs(error) * min((step + 1) * 0.03, 5.0)

    # Recovery bonus: strong reward when error is shrinking
    recovery = 0.0
    if abs(error) > 0.01 and error * delta_error < 0:
        recovery = 0.6 * abs(delta_error)

    # Convergence bonus
    settle = 0.8 if abs(error) < 0.005 else 0.0

    # Minimal TV — let the valve fight the disturbance freely
    tv = 0.0
    if prev_co is not None:
        tv = -0.05 * abs(co - prev_co) / 100.0

    return ise + itae + recovery + settle + tv


def compute_reward_surge_level(
    error: float,
    delta_error: float,
    co: float,
    prev_co: float | None,
    step: int,
    prev_delta_co: float | None = None,
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

    Pure function: the caller (RLEngine) is responsible for tracking
    ``prev_delta_co`` across calls per-instance. Storing it on this
    function's own `__dict__` (the old approach) would leak state across
    every controller/thread sharing the process.
    """
    # Valve stability — DOMINANT reward component
    stability = 0.0
    if prev_co is not None:
        co_change = abs(co - prev_co) / 100.0
        # Exponential reward: 1.0 when perfectly still, decays with movement
        stability = 1.5 * math.exp(-8.0 * co_change)
        # Extra penalty for valve direction reversal (chattering)
        curr_delta = co - prev_co
        if prev_delta_co is not None and prev_delta_co * curr_delta < 0:
            stability -= 0.5

    # Deadband: zero penalty inside ±2% of span
    error_penalty = 0.0
    abs_err = abs(error)
    if abs_err > _SURGE_DEADBAND:
        # Quadratic escalation outside deadband — gentle near edge, aggressive at limits
        excess = abs_err - _SURGE_DEADBAND
        error_penalty = -3.0 * excess * excess

    return stability + error_penalty


def compute_reward_from_stats(
    stats: dict[str, float],
    span: float,
    objective: ControlObjective,
) -> float | None:
    """Reward computed from a StatsWorker window (IAE/oscillation/TV KPIs).

    Unlike the point-sample reward functions above, this sees everything
    that happened between AI decisions — oscillation, valve travel, mean
    error — instead of a single instantaneous sample (fixes reward
    aliasing). Returns None when the window is too small or span is
    invalid, so the caller falls back to the point-sample reward.
    """
    from smart_pid_domain.enums import ControlObjective as CO

    if stats.get("sample_count", 0) < 10 or span <= 0:
        return None

    mae_n = stats.get("mean_abs_error", 0.0) / span  # mean |error|, fraction of span
    osc = stats.get("osc", 0.0)  # oscillation score in [0, 1]
    tv_s = stats.get("tv_per_sample", 0.0) / 100.0  # mean |ΔCO| per sample, fraction of output

    settle_bonus = 0.5 if mae_n < 0.005 else 0.0

    if objective == CO.DISTURBANCE_REJECTION:
        w_mae = 2.5  # DR: punish offset hardest
        w_osc = 1.0  # moderate oscillation penalty
        w_tv = 0.1  # let the valve fight disturbances freely
        reward = -w_mae * mae_n - w_osc * osc - w_tv * tv_s + settle_bonus
    elif objective == CO.SURGE_LEVEL:
        w_tv = 1.5  # valve calm is the dominant term
        w_excess = 3.0  # quadratic penalty once outside the error deadband
        w_osc = 0.3  # secondary oscillation penalty
        excess = max(0.0, mae_n - 0.02)
        reward = w_tv * math.exp(-8.0 * tv_s) - w_excess * excess * excess - w_osc * osc
    else:  # SP_TRACKING (default)
        w_mae = 2.0  # fast convergence to setpoint
        w_osc = 0.8  # moderate oscillation penalty
        w_tv = 0.3  # moderate TV penalty
        reward = -w_mae * mae_n - w_osc * osc - w_tv * tv_s + settle_bonus

    return max(-5.0, min(2.0, reward))


class _FallbackPolicy:
    """Proportional-derivative policy with amplitude-aware oscillation damping.

    Maps observation to gamma using a P+D strategy with integral memory
    and a sign-change counter that detects oscillation.  When the error
    sign flips rapidly the process is over-tuned (Ti too low / Ki too
    high), so the policy outputs a NEGATIVE gamma scaled by the error
    amplitude — large oscillations get strong correction, small
    oscillations get weak correction, letting the policy converge on the
    right Ti instead of overshooting to the limit.

      Normal:      gamma = Kp × error_nl + Kd × delta_error + integral
      Oscillating: gamma = −amplitude × damping_gain
    """

    _OSCILLATION_WINDOW = 12   # sign-changes counted over this many steps
    _OSCILLATION_THRESHOLD = 3  # ≥3 reversals in 12 steps → oscillating
    _DAMPING_GAIN = 1.5         # scales amplitude into gamma
    _MIN_OSC_AMPLITUDE = 0.05   # ignore oscillation below 5% of span (noise/settling)

    def __init__(self, kp: float = 0.6, kd: float = 0.2) -> None:
        self._kp = kp
        self._kd = kd
        self._ki_acc = 0.08
        self._integral = 0.0
        self._integral_limit = 0.4
        # Oscillation detector
        self._error_signs: deque[int] = deque(maxlen=self._OSCILLATION_WINDOW)
        self._recent_errors: deque[float] = deque(maxlen=self._OSCILLATION_WINDOW)

    def _sign_changes(self) -> int:
        """Count error-sign reversals in the sliding window."""
        changes = 0
        prev = 0
        for s in self._error_signs:
            if prev != 0 and s != 0 and s != prev:
                changes += 1
            if s != 0:
                prev = s
        return changes

    def _amplitude(self) -> float:
        """RMS of recent errors — measures oscillation severity."""
        if not self._recent_errors:
            return 0.0
        sum_sq = sum(e * e for e in self._recent_errors)
        return math.sqrt(sum_sq / len(self._recent_errors))

    def predict(self, observation: list[float]) -> float:
        """Return gamma in [-1, 1] based on error and delta_error."""
        error = observation[0]  # Normalized error
        delta_error = observation[1]  # Normalized delta error

        # Track error sign and amplitude for oscillation detection
        cur_sign = 1 if error > 0.005 else (-1 if error < -0.005 else 0)
        self._error_signs.append(cur_sign)
        self._recent_errors.append(error)

        # Oscillation detection: many sign reversals with significant amplitude
        reversals = self._sign_changes()
        amp = self._amplitude()
        if reversals >= self._OSCILLATION_THRESHOLD and amp >= self._MIN_OSC_AMPLITUDE:
            # Damping proportional to error amplitude:
            #   Large oscillation (amp ~0.3) → strong damping (~0.45)
            #   Moderate oscillation (amp ~0.1) → moderate damping (~0.15)
            # Below _MIN_OSC_AMPLITUDE the P+D policy handles fine-tuning.
            damping = min(0.8, self._DAMPING_GAIN * amp)
            self._integral = 0.0  # reset accumulated bias
            return -damping

        # Normal P+D policy — linear gain (symmetric for +/- error)
        gamma_pd = self._kp * error + self._kd * delta_error

        # Integral term: drives offset to zero over time
        self._integral += self._ki_acc * error
        self._integral = max(-self._integral_limit,
                             min(self._integral_limit, self._integral))
        if abs(error) < 0.01:
            self._integral *= 0.9

        gamma = gamma_pd + self._integral
        return max(-1.0, min(1.0, gamma))

    def reset(self) -> None:
        """Reset integral accumulator and oscillation history."""
        self._integral = 0.0
        self._error_signs.clear()
        self._recent_errors.clear()


class RLEngine:
    """RL-based Ki optimizer using SAC.

    Pure domain service -- lazy imports sb3 only when training or loading.
    When sb3 is unavailable or the policy has not trained enough to be
    trusted, falls back to a proportional baseline policy.
    """

    _MIN_TRAINS_BEFORE_POLICY = 3  # online training rounds before the neural policy is trusted

    def __init__(
        self,
        algorithm: str = "SAC",
        learning_rate: float = 3e-4,
        fallback_kp: float = 0.6,
        fallback_kd: float = 0.2,
        train_interval: int = 32,
    ) -> None:
        if algorithm != "SAC":
            logger.warning("rl_unsupported_algorithm %s, using SAC", algorithm)
            algorithm = "SAC"
        self._algorithm = algorithm
        self._model = None
        self._sb3_available: bool | None = None
        self._is_trained = False
        self._reward_steps = 0
        self._total_reward = 0.0
        self._step_count = 0
        self._steps_in_error = 0  # cycles the loop has spent outside the error band

        # Experience buffer for online training
        self._last_observation: list[float] | None = None
        self._last_action: float | None = None
        self._prev_co: float | None = None
        self._prev_delta_co: float | None = None

        # Replay buffer for online training (stores transitions)
        self._replay_buffer: deque[tuple[list[float], float, float, list[float], bool]] = (
            deque(maxlen=10_000)
        )

        # Fallback policy
        self._fallback = _FallbackPolicy(kp=fallback_kp, kd=fallback_kd)

        # Training config
        self._learning_rate = learning_rate
        self._train_batch_size = 64
        self._train_interval = train_interval  # Train every N steps
        self._min_buffer_size = 128  # Minimum transitions before training
        self._train_success_count = 0
        self._train_fail_logged = False

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

    def _policy_ready(self) -> bool:
        """True once the SAC policy has trained enough to be trusted.

        A freshly constructed sb3 model is randomly initialized; letting it
        drive Ti immediately makes gamma a random walk bounded only by
        limit_min/limit_max. Require several successful online-training
        rounds first (or a model loaded from a prior run, which is already
        trained and has zero online rounds yet in this process).
        """
        return self._model is not None and (
            self._train_success_count >= self._MIN_TRAINS_BEFORE_POLICY
            or (self._is_trained and self._train_success_count == 0)
        )

    def _normalize_observation(
        self,
        error: float,
        delta_error: float,
        span: float,
        co: float,
        integral_val: float,
        ki_current: float,
        limit_min: float,
        limit_max: float,
    ) -> list[float]:
        """Normalize observation to [-1, 1] range.

        5-dim: [error, delta_error, CO, integral_val, ti_norm]. ti_norm is
        the current Ti/Ki's log-scale position within [limit_min,
        limit_max] — without it, identical (error, delta_error, CO,
        integral_val) tuples can require wildly different correct actions
        depending on where Ti currently sits, breaking the Markov property.
        """
        if span > 0:
            error_norm = max(-1.0, min(1.0, error / span))
            delta_error_norm = max(-1.0, min(1.0, delta_error / span))
        else:
            error_norm = 0.0
            delta_error_norm = 0.0
        co_norm = max(-1.0, min(1.0, (co - 50.0) / 50.0))  # [0,100] -> [-1,1]
        integral_norm = max(-1.0, min(1.0, integral_val / 100.0))
        if limit_min > 0 and limit_max > limit_min:
            ratio = math.log(max(ki_current, limit_min) / limit_min)
            ti_norm = 2.0 * ratio / math.log(limit_max / limit_min) - 1.0
            ti_norm = max(-1.0, min(1.0, ti_norm))
        else:
            ti_norm = 0.0
        return [error_norm, delta_error_norm, co_norm, integral_norm, ti_norm]

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
            reward = compute_reward_surge_level(
                error, delta_error, co, self._prev_co, self._steps_in_error,
                self._prev_delta_co,
            )
            if self._prev_co is not None:
                self._prev_delta_co = co - self._prev_co
            return reward
        elif objective == CO.DISTURBANCE_REJECTION:
            return compute_reward_disturbance_rejection(
                error, delta_error, co, self._prev_co, self._steps_in_error
            )
        else:
            return compute_reward_sp_tracking(
                error, delta_error, co, self._prev_co, self._steps_in_error
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
        stats: dict[str, float] | None = None,
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
            integral_type: "GAIN_KI" or "TIME_TI".
            stats: Latest StatsWorker window snapshot (IAE/oscillation/TV
                KPIs). When present, the reward is computed from this
                window instead of the aliased instantaneous point sample.

        Returns:
            AIDecision with gamma, new Ki, reasoning, and debug info.
        """
        observation = self._normalize_observation(
            error, delta_error, span, co, integral_val, ki_current, limit_min, limit_max
        )

        # Track how long the loop has been outside a small error band —
        # event-relative (not wall-clock) time escalation for reward shaping.
        if abs(observation[0]) >= 0.01:
            self._steps_in_error += 1
        else:
            self._steps_in_error = 0

        # Compute reward for the previous step (if we have prior observation).
        # Prefer windowed loop KPIs over the aliased point-sample reward when
        # a StatsWorker snapshot is available.
        if self._last_observation is not None:
            reward = None
            if stats is not None:
                reward = compute_reward_from_stats(stats, span, objective)
            if reward is None:
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
        if self._policy_ready():
            assert self._model is not None  # _policy_ready() already checked this
            import numpy as np

            obs_array = np.array(observation, dtype=np.float32)
            try:
                action, _ = self._model.predict(obs_array, deterministic=False)
                gamma = (
                    float(action[0]) if hasattr(action, "__getitem__") else float(action)
                )
                gamma = max(-1.0, min(1.0, gamma))
                reasoning = (
                    f"RL({self._algorithm}): obs={_fmt_obs(observation)}, "
                    f"gamma={gamma:.4f}, trained={self._train_success_count}"
                )
            except Exception:
                logger.warning(
                    "rl_model_predict_failed \u2014 discarding model", exc_info=True
                )
                self._model = None
                gamma = self._fallback.predict(observation)
                reasoning = (
                    f"RL(fallback): obs={_fmt_obs(observation)}, "
                    f"gamma={gamma:.4f}, trained={self._train_success_count}"
                )
        else:
            # Fallback: proportional baseline policy
            gamma = self._fallback.predict(observation)
            reasoning = (
                f"RL(fallback): obs={_fmt_obs(observation)}, "
                f"gamma={gamma:.4f}, trained={self._train_success_count}"
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
            if not self._train_fail_logged:
                logger.warning("rl_online_train_failed", exc_info=True)
                self._train_fail_logged = True
            else:
                logger.debug("rl_online_train_failed", exc_info=True)

    def _online_train_sb3(self) -> None:
        """Run online training with the sb3 SAC model."""
        import numpy as np

        if self._model is None:
            self._init_sb3_model()

        if self._model is None:
            return

        buffer_list = list(self._replay_buffer)
        if len(buffer_list) < self._train_batch_size:
            return

        self._train_sac(buffer_list, np)
        self._train_success_count += 1
        self._is_trained = True
        logger.debug(
            "rl_online_train algo=%s step=%d buffer=%d trained=%d",
            self._algorithm, self._step_count, len(self._replay_buffer),
            self._train_success_count,
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

    def _init_sb3_model(self) -> None:
        """Initialize a new sb3 SAC model for online training."""
        try:
            import gymnasium as gym
            import numpy as np
            from gymnasium import spaces
            from stable_baselines3 import SAC
            from stable_baselines3.common.utils import configure_logger  # type: ignore

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

            self._model = SAC(
                "MlpPolicy",
                env,
                learning_rate=self._learning_rate,
                buffer_size=10_000,
                batch_size=self._train_batch_size,
                verbose=0,
            )
            # BaseAlgorithm.train() reads the `logger` property, which sb3
            # only assigns inside set_logger()/_setup_learn() (the latter
            # only called by learn()) — never in __init__. Without this,
            # the first online-train call raises AttributeError, which was
            # previously swallowed by _try_online_train's except clause.
            assert self._model is not None  # just assigned above
            self._model.set_logger(configure_logger(verbose=0))
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
        from stable_baselines3 import SAC

        self._model = SAC.load(str(path))
        self._is_trained = True
        logger.info("rl_model_loaded path=%s", str(path))

    def reset(self) -> None:
        """Reset engine state for a new episode."""
        self._last_observation = None
        self._last_action = None
        self._prev_co = None
        self._prev_delta_co = None
        self._step_count = 0
        self._steps_in_error = 0
        self._fallback.reset()

    def save_state(self, model_dir: Path) -> dict:
        """Persist model + engine state.  Returns metadata dict for DB.

        Saves sb3 model weights to *model_dir* (if trained) and returns
        a JSON-serialisable dict with replay buffer, counters, and
        fallback state so the engine can resume exactly where it left off.
        """
        model_dir.mkdir(parents=True, exist_ok=True)
        model_path = ""
        if self._model is not None:
            p = model_dir / f"rl_{self._algorithm.lower()}"
            self._model.save(str(p))
            model_path = str(p.with_suffix(".zip"))
            logger.info("rl_model_saved path=%s", model_path)

        # Serialise replay buffer (last 2000 to keep size manageable)
        buf = list(self._replay_buffer)[-2000:]
        serialised_buffer = [
            {"obs": o, "action": a, "reward": r, "next_obs": n, "done": d}
            for o, a, r, n, d in buf
        ]

        return {
            "version": 2,
            "algorithm": self._algorithm,
            "model_path": model_path,
            "is_trained": self._is_trained,
            "step_count": self._step_count,
            "reward_steps": self._reward_steps,
            "total_reward": self._total_reward,
            "replay_buffer": serialised_buffer,
            "fallback": {
                "integral": self._fallback._integral,
                "error_signs": list(self._fallback._error_signs),
                "recent_errors": list(self._fallback._recent_errors),
            },
        }

    def load_state(self, state: dict, model_dir: Path | None = None) -> None:
        """Restore engine state from a previously saved dict."""
        if state.get("version") != 2:
            # Older state predates the 5-dim observation / stats-reward /
            # policy-gate changes — discard rather than resume with a
            # replay buffer built against the old 4-dim observation space.
            logger.info("rl_state_version_mismatch \u2014 discarding persisted RL state")
            return

        self._step_count = state.get("step_count", 0)
        self._reward_steps = state.get("reward_steps", 0)
        self._total_reward = state.get("total_reward", 0.0)
        self._is_trained = state.get("is_trained", False)

        # Restore replay buffer
        buf = state.get("replay_buffer", [])
        self._replay_buffer.clear()
        for t in buf:
            self._replay_buffer.append((
                t["obs"], t["action"], t["reward"], t["next_obs"], t["done"],
            ))

        # Restore fallback state
        fb = state.get("fallback", {})
        self._fallback._integral = fb.get("integral", 0.0)
        self._fallback._error_signs.clear()
        for s in fb.get("error_signs", []):
            self._fallback._error_signs.append(s)
        self._fallback._recent_errors.clear()
        for e in fb.get("recent_errors", []):
            self._fallback._recent_errors.append(e)

        # Load sb3 model weights if available
        model_path = state.get("model_path", "")
        if model_path and model_dir is not None:
            p = Path(model_path)
            if p.exists():
                try:
                    self.load_model(p)
                    logger.info("rl_model_loaded path=%s", p)
                except Exception:
                    logger.warning("rl_model_load_failed path=%s", p, exc_info=True)

        logger.info(
            "rl_state_restored steps=%d buffer=%d trained=%s",
            self._step_count, len(self._replay_buffer), self._is_trained,
        )


def _fmt_obs(obs: list[float]) -> str:
    """Format observation for logging."""
    return f"[{', '.join(f'{v:.3f}' for v in obs)}]"
