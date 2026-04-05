"""Guardrail clamping for tuning parameter write-back."""
from __future__ import annotations


def clamp_tuning_change(current: float, recommended: float, max_pct: float) -> float:
    """Clamp a tuning parameter change to at most max_pct% of current value."""
    max_delta = abs(current) * (max_pct / 100.0)
    delta = recommended - current
    clamped_delta = max(min(delta, max_delta), -max_delta)
    return current + clamped_delta


def clamp_tuning_params(
    *,
    current_kp: float,
    current_ti: float,
    current_td: float,
    rec_kp: float,
    rec_ti: float,
    rec_td: float,
    max_pct: float,
) -> tuple[float, float, float]:
    """Clamp all three PID tuning parameters."""
    return (
        clamp_tuning_change(current_kp, rec_kp, max_pct),
        clamp_tuning_change(current_ti, rec_ti, max_pct),
        clamp_tuning_change(current_td, rec_td, max_pct),
    )
