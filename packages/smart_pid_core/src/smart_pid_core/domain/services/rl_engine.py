"""Reinforcement Learning engine for Ki optimization.

Uses stable-baselines3 (SAC or PPO) with lazy imports.
Falls back to zero-gamma when no model is trained.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from smart_pid_domain.enums import ControlObjective, ProcessSpeed

from smart_pid_core.domain.services.fuzzy_engine import AIDecision, SPEED_FACTORS

logger = logging.getLogger(__name__)


class RLEngine:
    """RL-based Ki optimizer using SAC or PPO.

    Pure domain service — lazy imports sb3 only when training or loading a model.
    """

    def __init__(self, algorithm: str = "SAC") -> None:
        self._algorithm = algorithm
        self._model = None
        self._is_trained = False
        self._episode_count = 0
        self._total_reward = 0.0
        self._last_observation: list[float] | None = None
        self._last_action: float | None = None

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
    def avg_reward(self) -> float:
        if self._episode_count == 0:
            return 0.0
        return self._total_reward / self._episode_count

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
        """Compute gamma from RL model or return zero if untrained."""
        # Normalize observation
        if span > 0:
            error_norm = error / span
            delta_error_norm = delta_error / span
        else:
            error_norm = 0.0
            delta_error_norm = 0.0
        co_norm = co / 100.0
        integral_norm = integral_val / 100.0

        observation = [error_norm, delta_error_norm, co_norm, integral_norm]

        if self._model is None:
            gamma = 0.0
            reasoning = f"RL({self._algorithm}): no trained model, gamma=0.0"
        else:
            import numpy as np

            obs_array = np.array(observation, dtype=np.float32)
            action, _ = self._model.predict(obs_array, deterministic=True)
            gamma = float(action[0]) if hasattr(action, "__getitem__") else float(action)
            gamma = max(-1.0, min(1.0, gamma))
            reasoning = (
                f"RL({self._algorithm}): obs={observation}, " f"gamma={gamma:.4f}"
            )

        # Store for training update
        self._last_observation = observation
        self._last_action = gamma

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
        """Update RL model with reward signal. No-op if model not initialized."""
        if self._model is None:
            return
        self._episode_count += 1
        self._total_reward += reward

    def save_model(self, path: Path) -> None:
        """Save trained model to disk."""
        if self._model is None:
            raise RuntimeError("No model to save")
        path.parent.mkdir(parents=True, exist_ok=True)
        self._model.save(str(path))
        logger.info("rl_model_saved path=%s episodes=%d", str(path), self._episode_count)

    def load_model(self, path: Path) -> None:
        """Load a previously trained model."""
        if not path.exists():
            raise FileNotFoundError(f"Model not found: {path}")
        self._load_sb3()
        if self._algorithm == "SAC":
            from stable_baselines3 import SAC

            self._model = SAC.load(str(path))
        else:
            from stable_baselines3 import PPO

            self._model = PPO.load(str(path))
        self._is_trained = True
        logger.info("rl_model_loaded path=%s", str(path))

    def _load_sb3(self) -> None:
        """Lazy import of stable-baselines3."""
        try:
            import stable_baselines3  # noqa: F401
        except ImportError as e:
            raise ImportError(
                "stable-baselines3 not installed. "
                "Install with: pip install smart-pid-core[ai]"
            ) from e
