"""Guardrail clamping for tuning parameter write-back."""
from __future__ import annotations

import math

from smart_pid_domain.enums import ExecutionMode
from smart_pid_domain.models.controller import KP_MIN

__all__ = [
    "KP_MIN",
    "clamp_tuning_absolute",
    "clamp_tuning_change",
    "clamp_tuning_params",
]



def _finite_or(value: float, fallback: float) -> float:
    """``value`` when it is a real number, ``fallback`` when it is nan or inf."""
    return value if math.isfinite(value) else fallback

def clamp_tuning_absolute(
    *,
    kp: float | None,
    ti: float | None,
    td: float | None,
    execution_mode: ExecutionMode,
    ti_min: float,
    ti_max: float,
) -> tuple[float | None, float | None, float | None]:
    """Force tuning values into the range the loop's own configuration allows.

    Complements ``clamp_tuning_change``, which bounds how far a value may move
    per write but not where it may land: a 10 %-per-write rate limit still walks
    Kp to zero over enough writes without ever tripping.

    ``None`` means "not part of this write" and passes through untouched, so a
    partial ``TuningCommand`` does not materialise floors for absent fields.

    ===== ================ ==============================
    Term  DDC              SUPERVISORY
    ===== ================ ==============================
    Kp    >= KP_MIN        >= KP_MIN
    Ti    >= 0 (0 = off)   within ``ti_min``..``ti_max``
    Td    >= 0 (0 = off)   >= 0 (0 = off)
    ===== ================ ==============================

    Ti splits on who runs the PID. Under DDC the engine is ours and reads
    ``reset == 0`` as "integral disabled", which is a legitimate P-only loop.
    Under SUPERVISORY the gains land in a DCS block instead, and the operator
    has already declared the admissible Ti span through the loop's optimizer
    limits — the band the AI worker is held to. Honouring it here keeps the
    manual write path from being the way around the operator's own bounds.

    ``ti_min > ti_max`` is reachable (the two config fields are validated
    independently), so the floor is applied last and wins.

    Nothing handed in is trusted, neither the values nor the bounds. Both arrive
    from persisted configuration: the DTO guard stops new non-finite rows, but the
    read path stays open on purpose so rows written before it existed still load,
    and this is the code that consumes them on every tuning write. Argument order
    alone is not protection — ``max(KP_MIN, nan)`` happens to return ``KP_MIN``
    because ``nan > KP_MIN`` is false, but ``max(nan, x)`` returns ``nan`` and
    ``max(KP_MIN, inf)`` returns ``inf``. A non-finite Ti also arrives with no
    non-finite bound in sight: ``write_tuning`` feeds this the result of
    ``clamp_tuning_change(current.reset, ...)``, and a legacy ``current.reset`` of
    ``inf`` computes ``inf + -inf``, which is ``nan``.

    An unusable bound is dropped rather than raised on: this is the last step
    before a DCS block, and refusing to tune at all would turn one bad legacy row
    into a permanent failure on a route the operator needs. Losing one side of the
    band keeps the other, and losing both degrades SUPERVISORY to the physical
    floor that DDC uses. The caller's own asked-vs-allowed comparison still logs
    whenever the value actually moves.
    """
    clamped_ti: float | None
    if ti is None:
        clamped_ti = None
    elif execution_mode is ExecutionMode.SUPERVISORY:
        lo = _finite_or(ti_min, 0.0)
        hi = _finite_or(ti_max, math.inf)
        clamped_ti = max(lo, min(hi, _finite_or(ti, lo)))
    else:
        clamped_ti = max(0.0, _finite_or(ti, 0.0))
    return (
        None if kp is None else max(KP_MIN, _finite_or(kp, KP_MIN)),
        clamped_ti,
        None if td is None else max(0.0, _finite_or(td, 0.0)),
    )


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
