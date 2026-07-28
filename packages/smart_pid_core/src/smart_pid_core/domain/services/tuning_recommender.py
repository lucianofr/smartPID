"""IMC / lambda tuning — FOPDT identification and full PID synthesis.

This is the *full retune* path (Kp **and** Ti **and** Td together), which is a
much larger intervention than the continuous integral nudge the AI engines
apply every ``3 × tss``.  A proposal produced here is never written directly:
it is surfaced as a :class:`~smart_pid_domain.models.tuning.TuningRecommendation`
and applied only after explicit operator confirmation, clamped server-side.

Pure domain service — deterministic, no I/O, no clock reads, no logging.
``None`` from either entry point means "no defensible recommendation".

Method
------
The process is modelled as first-order plus dead time (FOPDT)::

    G(s) = K · e^(−L·s) / (τ·s + 1)

and the controller is synthesised with the classic IMC-PID rules for a FOPDT
plant with a first-order Padé approximation of the dead time (Rivera, Morari &
Skogestad, *Internal Model Control: PID Controller Design*, 1986; reproduced as
the "PID" row of Seborg's IMC tuning table)::

    Kc = (2τ + L) / (2·K·(λ + L))
    Ti = τ + L/2
    Td = τ·L / (2τ + L)

λ (the closed-loop time constant) is the single tuning knob: small λ is
aggressive, large λ is sluggish but robust.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from smart_pid_domain.enums import ControlObjective

# --- FOPDT identification ------------------------------------------------
# A FOPDT step response is within e^(-n) of its final value n time constants
# after the dead time has elapsed.  "Time to steady state" is conventionally
# the 98 % point, and e^(-4) ≈ 1.8 %, so tss ≈ L + 4τ.
_SETTLING_TAU_MULTIPLES = 4.0
# Below this the process barely responds to the valve and Kc = f(1/K) explodes.
# 0.01 %PV per %CO means a full 0-100 % stroke moves PV by 1 % of span.
_MIN_ABS_GAIN = 0.01
_MIN_TAU_S = 1e-3

# --- λ selection ---------------------------------------------------------
# λ as a multiple of τ, per control objective.  λ = τ is the textbook robust
# default; λ = τ/3 is the usual "tight" choice; λ = 3τ is the averaging-level
# setting that lets a surge tank absorb the surge instead of passing it on.
_LAMBDA_TAU_FACTOR = {
    ControlObjective.DISTURBANCE_REJECTION: 1.0 / 3.0,
    ControlObjective.SP_TRACKING: 1.0,
    ControlObjective.SURGE_LEVEL: 3.0,
}
# Rivera/Morari robustness bound: λ below 0.8·L makes the loop intolerant of
# dead-time error, which is exactly the parameter that is least well known.
_LAMBDA_DEAD_TIME_FLOOR = 0.8

# --- material-difference gate --------------------------------------------
# A proposal is only worth an operator's attention if at least one parameter
# moves by ≥ 10 % of the larger of (current, recommended).  The symmetric
# denominator keeps the measure bounded in [0, 1] and well defined when a
# parameter is currently zero (Td on a PI loop): switching derivative action
# on or off scores 1.0 and is always material.
_MATERIAL_CHANGE_FRAC = 0.10
_ZERO_TOL = 1e-9


@dataclass(frozen=True)
class FOPDTModel:
    """First-order-plus-dead-time process model."""

    gain: float          # steady-state process gain, %PV per %CO
    tau_s: float         # first-order time constant, seconds
    dead_time_s: float   # transport delay L, seconds


@dataclass(frozen=True)
class TuningProposal:
    """A full PID retune proposal derived from a :class:`FOPDTModel`."""

    kp: float
    ti: float
    td: float
    lambda_s: float
    reason: str          # pt-BR, names the method and the lambda actually used


def _rel_change(current: float, recommended: float) -> float:
    """Symmetric relative change, bounded in [0, 1] for same-sign values.

    Returns 0.0 when both values are effectively zero, so an untouched
    ``Td = 0`` on a PI loop does not register as a change.
    """
    scale = max(abs(current), abs(recommended))
    if scale <= _ZERO_TOL:
        return 0.0
    return abs(recommended - current) / scale


def identify_fopdt(
    *, tss_s: float, dead_time_s: float, gain: float,
) -> FOPDTModel | None:
    """Build a FOPDT model from the loop's configured dynamics and a measured gain.

    τ is *derived*, not measured: for a FOPDT plant the step response reaches
    98 % of its final value roughly ``L + 4τ`` after the step, and the loop's
    configured ``tss_s`` is exactly that 98 % settling time.  Inverting gives::

        τ = (tss_s − L) / 4

    ``gain`` must be a genuinely observed steady-state gain in %PV per %CO —
    callers that cannot measure one must not substitute a placeholder; pass a
    value that fails the guards below (or do not call this at all) so the
    result is ``None`` and no recommendation is produced.

    Returns ``None`` when the model is not identifiable:

    * any input is NaN or infinite;
    * ``tss_s`` is not positive, or ``dead_time_s`` is negative;
    * the dead time consumes the whole settling time (``τ ≤ 0``), which means
      the loop is dead-time dominant beyond what this rule can resolve;
    * the process gain is too small to invert (``|K| < 0.01 %PV/%CO``).
    """
    if not all(math.isfinite(v) for v in (tss_s, dead_time_s, gain)):
        return None
    if tss_s <= 0.0 or dead_time_s < 0.0:
        return None
    if abs(gain) < _MIN_ABS_GAIN:
        return None

    tau_s = (tss_s - dead_time_s) / _SETTLING_TAU_MULTIPLES
    if tau_s < _MIN_TAU_S:
        return None

    return FOPDTModel(gain=gain, tau_s=tau_s, dead_time_s=dead_time_s)


def recommend_pid(
    *,
    model: FOPDTModel,
    objective: ControlObjective,
    current_kp: float,
    current_ti: float,
    current_td: float,
    limit_min: float,
    limit_max: float,
) -> TuningProposal | None:
    """Synthesise Kp/Ti/Td from ``model`` by IMC/lambda tuning.

    λ is picked from ``objective`` — ``τ/3`` for DISTURBANCE_REJECTION (the
    integral must be fast enough to reject load upsets), ``τ`` for SP_TRACKING
    (the robust default; setpoint moves can be ramped instead of chased), and
    ``3τ`` for SURGE_LEVEL (averaging level control must absorb the surge, not
    fight it) — then floored at ``0.8·L`` for dead-time robustness.

    The synthesised Ti is clamped to ``[limit_min, limit_max]``, the same
    integral guardrail the continuous optimizer obeys.  An inverted window is
    normalised rather than honoured literally, so the result can never fall
    outside the intended band.

    ``Kp`` is returned as a magnitude: this codebase carries the loop's action
    direction in ``ControlOpts.direct_acting``, not in the sign of Kp, so a
    reverse-acting process (negative ``model.gain``) yields the same positive
    gain magnitude.

    Returns ``None`` when the synthesis is not defensible or the result is not
    materially different from the current tuning — i.e. when no parameter moves
    by at least 10 % (see ``_MATERIAL_CHANGE_FRAC``).  That gate is what stops
    the producer emitting a stream of near-identical proposals; callers can
    reuse it to compare a fresh proposal against the last one they emitted by
    passing the previous proposal as ``current_*``.
    """
    inputs = (
        model.gain, model.tau_s, model.dead_time_s,
        current_kp, current_ti, current_td, limit_min, limit_max,
    )
    if not all(math.isfinite(v) for v in inputs):
        return None
    if model.tau_s < _MIN_TAU_S or model.dead_time_s < 0.0:
        return None
    abs_gain = abs(model.gain)
    if abs_gain < _MIN_ABS_GAIN:
        return None

    tau_factor = _LAMBDA_TAU_FACTOR.get(objective)
    if tau_factor is None:
        return None
    lambda_s = max(
        tau_factor * model.tau_s,
        _LAMBDA_DEAD_TIME_FLOOR * model.dead_time_s,
    )
    if lambda_s <= 0.0:
        return None

    two_tau_plus_l = 2.0 * model.tau_s + model.dead_time_s
    kp = two_tau_plus_l / (2.0 * abs_gain * (lambda_s + model.dead_time_s))
    ti = model.tau_s + model.dead_time_s / 2.0
    td = model.tau_s * model.dead_time_s / two_tau_plus_l

    lo, hi = min(limit_min, limit_max), max(limit_min, limit_max)
    ti = min(max(ti, lo), hi)

    if not all(math.isfinite(v) for v in (kp, ti, td)):
        return None

    material = max(
        _rel_change(current_kp, kp),
        _rel_change(current_ti, ti),
        _rel_change(current_td, td),
    )
    if material < _MATERIAL_CHANGE_FRAC:
        return None

    # `g` rather than a fixed number of decimals: a fast flow loop has tau in
    # tens of milliseconds and a distillation column has it in hours, and a
    # fixed format silently prints "0.0 s" for one of them.
    reason = (
        f"Sintonia IMC/lambda sobre modelo FOPDT "
        f"(K={model.gain:+.4g} %PV/%CO, tau={model.tau_s:.4g} s, "
        f"L={model.dead_time_s:.4g} s); objetivo {objective.value} "
        f"-> lambda={lambda_s:.4g} s. "
        f"Kp {current_kp:.4g}->{kp:.4g}, Ti {current_ti:.4g}->{ti:.4g} s, "
        f"Td {current_td:.4g}->{td:.4g} s."
    )
    return TuningProposal(kp=kp, ti=ti, td=td, lambda_s=lambda_s, reason=reason)
