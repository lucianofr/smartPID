"""KPI-driven extremum-seeking optimizer for the PID integral term.

Marketed as RL: reward-guided online search. Instead of a neural
policy, the engine runs a direct adaptive-step search over the
windowed-KPI reward computed from the StatsWorker snapshot
(IAE/MAE, oscillation score, TV). It probes the integral term,
judges each probe against the reward, converges on the value that
maximizes it, holds there (gamma = 0), and re-arms the search only
when the KPIs measurably degrade or the loop starts oscillating.
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING


@dataclass(frozen=True)
class AIDecision:
    """Result of an RL Ki optimization computation."""

    gamma: float
    new_ki: float
    reasoning: str
    membership_values: dict[str, dict[str, float]] | None = None

if TYPE_CHECKING:
    from smart_pid_domain.enums import ControlObjective, ProcessSpeed

logger = logging.getLogger(__name__)


def compute_reward_from_stats(
    stats: dict[str, float],
    span: float,
    objective: ControlObjective,
) -> float | None:
    """Reward computed from a StatsWorker window (IAE/oscillation/TV KPIs).

    Sees everything that happened between AI decisions — oscillation,
    valve travel, mean error — instead of a single instantaneous
    sample (fixes reward aliasing). Returns None when the window is
    too small or span is invalid, so the caller holds off until a
    meaningful window exists.
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


class RLEngine:
    """KPI-guided extremum-seeking optimizer for Ti/Ki.

    Probes the integral term with an adaptive step and judges each
    probe against the windowed-KPI reward (compute_reward_from_stats).
    Converges on the value that maximizes the reward, holds there
    (gamma = 0), and re-arms the search when the KPIs degrade or the
    loop oscillates. The public worker interface (compute_gamma
    signature, update law, clamps) is unchanged.
    """

    # ── Seeker tuning constants ──────────────────────────────────────
    _STEP_INIT = 0.4        # |gamma| inicial; Ti muda step*Sv por sonda (Sv=0.08–0.5)
    _STEP_MIN = 0.05        # piso do passo após pioras sucessivas
    _STEP_MAX = 1.0         # teto do passo após melhoras sucessivas
    _STEP_SHRINK = 0.5      # ao piorar: inverte direção e reduz passo
    _STEP_GROW = 1.25       # ao melhorar: acelera
    # Deadband de comparação de reward (escala do reward clampado [-5, 2]).
    # Dimensionado pelo delta de reward de uma sonda: |Δr| ≈ w_mae·0.08·g·Sv
    # ≈ 0.024·g em MEDIUM (Sv=0.15). Precisa ser menor que o delta de uma
    # sonda de passo 0.2 (≈0.0048) para julgar a descida inicial, e maior
    # que o do passo mínimo 0.05 (≈0.0012) para o passo encolhido contar
    # flat e o hold disparar no ótimo.
    _TOL = 0.003
    _HOLD_AFTER_FLATS = 3       # julgamentos "flat" consecutivos -> convergiu
    _HOLD_AFTER_REVERSALS = 4   # inversões consecutivas -> bracketing do ótimo -> convergiu
    _RESTART_DELTA = 0.25       # queda abaixo do hold_reward que rearma a busca
    _RESTART_DEBOUNCE = 2       # nº de chamadas degradadas consecutivas para rearmar
    _HOLD_EMA_ALPHA = 0.1       # hold_reward segue lentamente o regime atual
    _OSC_EMERGENCY = 0.5        # osc (score 0..1 do StatsWorker) >= 0.5 -> damping imediato
    _OSC_EMERGENCY_GAMMA = 0.8  # gamma = -0.8 -> Ti sobe 6.4%–40% por ciclo (na faixa do fuzzy AM)
    _OSC_RESUME_DIR_THR = 0.3   # ao sair do hold: osc >= 0.3 -> retomar na direção -1 (damping)
    _DWELL_DECISIONS = 1        # pula 1 decisão após mover: janela 5×TSS renova
                                # em 2 períodos de 3×TSS
    _EXTERNAL_CHANGE_FRAC = 0.02  # ki_current difere >2% do esperado -> retune externo, soft reset

    def __init__(self) -> None:
        # Search state (resettable via reset()). Start probing toward
        # stronger integral action: most industrial loops arrive
        # over-damped; if the guess is wrong one worsening judgment
        # flips the direction, and the OSC emergency covers loops that
        # are already oscillating.
        self._direction: int = 1
        self._gamma_step: float = self._STEP_INIT
        self._holding: bool = False
        self._hold_reward: float = 0.0
        self._hold_degrade_count: int = 0
        self._pending_judge: bool = False
        self._r_before: float | None = None
        self._dwell: int = 0
        self._flat_count: int = 0
        self._reversal_streak: int = 0
        self._expected_ki: float | None = None
        self._last_objective: ControlObjective | None = None
        # Counters
        self._step_count = 0
        self._reward_steps = 0
        self._total_reward = 0.0

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

    def _soft_reset(self) -> None:
        """Reset search state without touching the probe direction."""
        self._pending_judge = False
        self._r_before = None
        self._dwell = 0
        self._holding = False
        self._flat_count = 0
        self._reversal_streak = 0
        self._gamma_step = self._STEP_INIT

    @staticmethod
    def _apply_update_law(
        gamma: float,
        ki_current: float,
        speed: ProcessSpeed,
        limit_min: float,
        limit_max: float,
        integral_type: str,
    ) -> float:
        """Shared Ti/Ki update law (identical to fuzzy and web).

        Gamma axis: +1 = strengthen integral action (Ti↓ / Ki↑),
        −1 = weaken it (Ti↑ / Ki↓).
        """
        sv: float = speed.speed_factor
        effective_gamma = gamma if integral_type == "GAIN_KI" else -gamma
        new_val = ki_current * (1.0 + effective_gamma * sv)
        return max(limit_min, min(limit_max, new_val))

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
        applied: bool = True,
    ) -> AIDecision:
        """Compute the next probe (or hold) from the windowed KPI reward.

        Args:
            error: Raw error in engineering units (reasoning only).
            delta_error: Kept for call-site compatibility; unused by the
                search (the windowed KPI reward already reflects it).
            ki_current: Current Ti/Ki value.
            span: Process span for reward normalization.
            co: Kept for call-site compatibility; unused by the search.
            integral_val: Kept for call-site compatibility; unused by
                the search.
            objective: Control objective for reward shaping.
            speed: Process speed for speed factor.
            limit_min: Minimum allowed Ti/Ki.
            limit_max: Maximum allowed Ti/Ki.
            integral_type: "GAIN_KI" or "TIME_TI".
            stats: Latest StatsWorker window snapshot (IAE/oscillation/TV
                KPIs). The search reward is computed from this window;
                without it the engine waits (gamma = 0).
            applied: Whether the returned suggestion will actually be
                written to the loop. Un-applied suggestions never arm a
                judgment — a suggestion that never reached the plant is
                not a measurement.

        Returns:
            AIDecision with gamma, new Ti/Ki, reasoning, and debug info.
        """
        self._step_count += 1
        param_label = "Ki" if integral_type == "GAIN_KI" else "Ti"

        if stats is None:
            return AIDecision(
                gamma=0.0,
                new_ki=ki_current,
                reasoning="RL(seek): waiting for KPI window",
            )
        reward = compute_reward_from_stats(stats, span, objective)
        if reward is None:
            return AIDecision(
                gamma=0.0,
                new_ki=ki_current,
                reasoning="RL(seek): waiting for KPI window",
            )

        self._reward_steps += 1
        self._total_reward += reward

        # Objective change: the reward landscape shifted under the search.
        if self._last_objective is not None and objective != self._last_objective:
            self._soft_reset()
        self._last_objective = objective

        # External retune: someone moved Ti/Ki behind the search's back.
        note = ""
        if (
            applied
            and self._expected_ki is not None
            and abs(ki_current - self._expected_ki)
            > self._EXTERNAL_CHANGE_FRAC * self._expected_ki
        ):
            self._soft_reset()
            note = "external Ti change, "

        # Oscillation emergency: an oscillating loop does not wait for
        # hold/dwell bookkeeping.
        osc = stats.get("osc", 0.0)
        if osc >= self._OSC_EMERGENCY:
            gamma = -self._OSC_EMERGENCY_GAMMA
            new_val = self._apply_update_law(
                gamma, ki_current, speed, limit_min, limit_max, integral_type
            )
            self._direction = -1
            self._gamma_step = self._STEP_INIT
            self._holding = False
            self._pending_judge = False
            self._flat_count = 0
            self._reversal_streak = 0
            self._dwell = self._DWELL_DECISIONS
            if applied:
                self._expected_ki = new_val
            return AIDecision(
                gamma=gamma,
                new_ki=new_val,
                reasoning=(
                    f"RL(seek): {note}osc emergency (osc={osc:.2f}), damping"
                    f", Sv={speed.speed_factor}, "
                    f"{param_label}: {ki_current:.4f} -> {new_val:.4f}"
                ),
            )

        if self._holding:
            self._hold_reward = (
                (1.0 - self._HOLD_EMA_ALPHA) * self._hold_reward
                + self._HOLD_EMA_ALPHA * reward
            )
            if reward < self._hold_reward - self._RESTART_DELTA:
                self._hold_degrade_count += 1
            else:
                self._hold_degrade_count = 0
            if self._hold_degrade_count >= self._RESTART_DEBOUNCE:
                # KPIs degraded for long enough: leave hold and probe.
                self._holding = False
                self._gamma_step = self._STEP_INIT
                self._direction = -1 if osc >= self._OSC_RESUME_DIR_THR else 1
                self._flat_count = 0
                self._reversal_streak = 0
                self._hold_degrade_count = 0
                self._r_before = None
                self._pending_judge = False
                self._dwell = 0
                # Fall through: probe immediately.
            else:
                return AIDecision(
                    gamma=0.0,
                    new_ki=ki_current,
                    reasoning=(
                        f"RL(seek): holding "
                        f"(r={reward:.3f}, hold={self._hold_reward:.3f})"
                    ),
                )

        if self._dwell > 0:
            self._dwell -= 1
            return AIDecision(
                gamma=0.0,
                new_ki=ki_current,
                reasoning="RL(seek): settling window",
            )

        judge_note = ""
        if self._pending_judge and self._r_before is not None:
            delta = reward - self._r_before
            if delta > self._TOL:
                self._reversal_streak = 0
                self._flat_count = 0
                self._gamma_step = min(
                    self._gamma_step * self._STEP_GROW, self._STEP_MAX
                )
                judge_note = f"judge: improved (dr={delta:+.3f}), "
            elif delta < -self._TOL:
                self._direction *= -1
                self._gamma_step = max(
                    self._gamma_step * self._STEP_SHRINK, self._STEP_MIN
                )
                self._reversal_streak += 1
                self._flat_count = 0
                judge_note = f"judge: worsened (dr={delta:+.3f}), "
            else:
                self._flat_count += 1
                self._reversal_streak = 0
                judge_note = f"judge: flat (dr={delta:+.3f}), "
            self._pending_judge = False
            if (
                self._reversal_streak >= self._HOLD_AFTER_REVERSALS
                or self._flat_count >= self._HOLD_AFTER_FLATS
            ):
                self._holding = True
                self._hold_reward = reward
                self._hold_degrade_count = 0
                return AIDecision(
                    gamma=0.0,
                    new_ki=ki_current,
                    reasoning=(
                        f"RL(seek): {note}{judge_note}converged: holding at "
                        f"{param_label}={ki_current:.4f}"
                    ),
                )

        gamma = self._direction * self._gamma_step
        new_val = self._apply_update_law(
            gamma, ki_current, speed, limit_min, limit_max, integral_type
        )

        if not applied:
            # Suggestion only: do not arm a judgment. An un-applied
            # suggestion is not a measurement.
            return AIDecision(
                gamma=gamma,
                new_ki=new_val,
                reasoning=(
                    f"RL(seek): {note}{judge_note}suggestion only "
                    f"(auto-apply off) gamma={gamma:+.3f}, "
                    f"Sv={speed.speed_factor}, "
                    f"{param_label}: {ki_current:.4f} -> {new_val:.4f}"
                ),
            )

        if new_val == ki_current:
            # Clamp no-op at the limit: nothing moved, count as flat.
            self._flat_count += 1
            self._reversal_streak = 0
            if self._flat_count >= self._HOLD_AFTER_FLATS:
                self._holding = True
                self._hold_reward = reward
                self._hold_degrade_count = 0
                return AIDecision(
                    gamma=0.0,
                    new_ki=ki_current,
                    reasoning=(
                        f"RL(seek): {note}converged: holding at "
                        f"{param_label}={ki_current:.4f}"
                    ),
                )
            return AIDecision(
                gamma=0.0,
                new_ki=ki_current,
                reasoning=(
                    f"RL(seek): {note}at {param_label} limit "
                    f"{ki_current:.4f}, no room to move"
                ),
            )

        self._r_before = reward
        self._pending_judge = True
        self._dwell = self._DWELL_DECISIONS
        self._expected_ki = new_val
        return AIDecision(
            gamma=gamma,
            new_ki=new_val,
            reasoning=(
                f"RL(seek): {note}{judge_note}probe gamma={gamma:+.3f} "
                f"err={error:+.3f} r={reward:.3f}, Sv={speed.speed_factor}, "
                f"{param_label}: {ki_current:.4f} -> {new_val:.4f}"
            ),
        )

    def reset(self) -> None:
        """Reset engine state for a new episode."""
        self._soft_reset()
        self._direction = 1
        self._hold_reward = 0.0
        self._hold_degrade_count = 0
        self._expected_ki = None
        self._last_objective = None
        self._step_count = 0

    def save_state(self, model_dir: Path) -> dict:
        """Persist engine state. Returns metadata dict for DB.

        Version 3: the seeker's entire state is the dict below — no
        model weights, no replay buffer. *model_dir* stays in the
        signature for call-site compatibility and is ignored.
        """
        return {
            "version": 3,
            "step_count": self._step_count,
            "reward_steps": self._reward_steps,
            "total_reward": self._total_reward,
            "seek": {
                "direction": self._direction,
                "step": self._gamma_step,
                "holding": self._holding,
                "hold_reward": self._hold_reward,
                "hold_degrade_count": self._hold_degrade_count,
                "pending_judge": self._pending_judge,
                "r_before": self._r_before,
                "dwell": self._dwell,
                "flat_count": self._flat_count,
                "reversal_streak": self._reversal_streak,
                "expected_ki": self._expected_ki,
                "objective": (
                    self._last_objective.value if self._last_objective else None
                ),
            },
        }

    def load_state(self, state: dict, model_dir: Path | None = None) -> None:
        """Restore engine state from a previously saved dict.

        *model_dir* is kept in the signature for call-site compatibility
        and ignored (version 3 has no model files).
        """
        if state.get("version") != 3:
            # Older state predates the extremum-seeking core — discard
            # rather than resume with a replay buffer / fallback policy
            # that no longer exist.
            logger.info("rl_state_version_mismatch — discarding persisted RL state")
            return

        from smart_pid_domain.enums import ControlObjective as CO

        self._step_count = state.get("step_count", 0)
        self._reward_steps = state.get("reward_steps", 0)
        self._total_reward = state.get("total_reward", 0.0)

        seek = state.get("seek", {})
        self._direction = int(seek.get("direction", 1))
        self._gamma_step = float(seek.get("step", self._STEP_INIT))
        self._holding = bool(seek.get("holding", False))
        self._hold_reward = float(seek.get("hold_reward", 0.0))
        self._hold_degrade_count = int(seek.get("hold_degrade_count", 0))
        self._pending_judge = bool(seek.get("pending_judge", False))
        r_before = seek.get("r_before")
        self._r_before = float(r_before) if r_before is not None else None
        self._dwell = int(seek.get("dwell", 0))
        self._flat_count = int(seek.get("flat_count", 0))
        self._reversal_streak = int(seek.get("reversal_streak", 0))
        expected_ki = seek.get("expected_ki")
        self._expected_ki = float(expected_ki) if expected_ki is not None else None
        self._last_objective = None
        obj_val = seek.get("objective")
        if obj_val is not None:
            try:
                self._last_objective = CO(obj_val)
            except ValueError:
                logger.info("rl_state_unknown_objective %s", obj_val)

        logger.info(
            "rl_state_restored steps=%d holding=%s",
            self._step_count, self._holding,
        )
