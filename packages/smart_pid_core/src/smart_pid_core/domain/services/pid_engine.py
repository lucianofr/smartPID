"""PID controller engine using velocity (incremental) form.

Equation (derivative on PV):
    delta_cv = Gain * [(e_n - e_n-1) + (dt/Reset)*e_n - Rate*(PV_n - 2*PV_n-1 + PV_n-2)/dt]
    cv_new = cv_current + delta_cv

Derivative filter: alpha (default Rate/8).
Anti-windup: suppresses integral when output is saturated and error pushes further.
Bumpless transfer: reinitializes state to match current output on mode change.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from smart_pid_domain.models.controller import PIDParams


@dataclass
class PIDState:
    """Mutable state carried between PID scans."""

    cv: float = 0.0
    error_prev: float = 0.0
    pv_prev: float = 0.0
    pv_prev2: float = 0.0
    sp_working: float = 0.0
    derivative_filtered: float = 0.0
    is_saturated: bool = False


@dataclass(frozen=True)
class PIDResult:
    """Output of a single PID computation."""

    cv: float
    delta_cv: float
    error: float
    new_state: PIDState


    # Phase 1 deferred features (planned for Phase 3):
    # - PV filter (PV_FTIME): first-order exponential filter on PV input
    # - Feedforward (FF_VAL * FF_GAIN): additive feedforward term
    # - 10% output over-range
    # - Low cutoff: PV forced to 0.0 when below LOW_CUT
    # - Increase-to-Close: output inversion via IOOpts flag

class PIDEngine:
    """Stateless PID engine. All state is passed in and returned explicitly."""

    def compute(
        self,
        params: PIDParams,
        state: PIDState,
        pv: float,
        sp: float,
        dt: float,
        out_limits: tuple[float, float],
        direct_acting: bool = False,
        arw_limits: tuple[float, float] | None = None,
    ) -> PIDResult:
        """Execute one PID scan. Returns new CV and updated state."""
        lo, hi = out_limits
        arw_lo, arw_hi = arw_limits if arw_limits is not None else (lo, hi)

        # Error calculation
        error = pv - sp if direct_acting else sp - pv

        # --- Proportional term (acts on error change) ---
        p_term = params.gain * (error - state.error_prev)

        # --- Integral term ---
        i_term = 0.0
        if params.reset > 0 and dt > 0:
            # Check deadband
            in_deadband = abs(error) < params.deadband if params.deadband > 0 else False
            # Anti-windup: suppress integral if saturated AND error drives further
            windup_block = (
                state.is_saturated
                and (
                    (state.cv >= arw_hi and error > 0)
                    or (state.cv <= arw_lo and error < 0)
                )
            )
            if not in_deadband and not windup_block:
                i_term = params.gain * (dt / params.reset) * error
                # 16x faster reset recovery: if previously saturated and integral
                # now drives output away from saturation, accelerate recovery.
                if state.is_saturated and i_term != 0.0:
                    reducing_hi = state.cv >= arw_hi and i_term < 0
                    reducing_lo = state.cv <= arw_lo and i_term > 0
                    if reducing_hi or reducing_lo:
                        i_term *= 16.0

        # --- Derivative term (acts on PV, not error) ---
        d_term = 0.0
        if params.rate > 0 and dt > 0:
            d2_pv = pv - 2.0 * state.pv_prev + state.pv_prev2
            d_raw = -params.gain * params.rate * (d2_pv / dt)
            # Apply derivative filter (exponential smoothing)
            alpha = min(max(params.alpha, 0.05), 1.0)
            d_term = alpha * d_raw + (1.0 - alpha) * state.derivative_filtered

        # --- Total increment ---
        delta_cv = p_term + i_term + d_term

        # --- Apply to output ---
        cv_new = state.cv + delta_cv

        # --- Clamp output ---
        is_saturated = False
        if cv_new > hi:
            cv_new = hi
            is_saturated = True
        elif cv_new < lo:
            cv_new = lo
            is_saturated = True

        new_state = PIDState(
            cv=cv_new,
            error_prev=error,
            pv_prev=pv,
            pv_prev2=state.pv_prev,
            sp_working=sp,
            derivative_filtered=d_term,
            is_saturated=is_saturated,
        )

        return PIDResult(
            cv=cv_new,
            delta_cv=delta_cv,
            error=error,
            new_state=new_state,
        )

    def bumpless_transfer(
        self,
        state: PIDState,
        current_pv: float,
        current_co: float,
        params: PIDParams,
    ) -> PIDState:
        """Reinitialize PID state for seamless mode transition.

        Sets CV to match current CO so there's no output bump.
        Resets PV history to current PV to avoid derivative spike.
        """
        return PIDState(
            cv=current_co,
            error_prev=0.0,
            pv_prev=current_pv,
            pv_prev2=current_pv,
            sp_working=state.sp_working,
            derivative_filtered=0.0,
            is_saturated=False,
        )

    def apply_sp_ramp(
        self,
        sp_target: float,
        sp_current: float,
        rate_up: float,
        rate_dn: float,
        dt: float,
    ) -> float:
        """Apply SP rate limiting. Returns working SP for this scan.

        rate_up/rate_dn in engineering units per second. 0 = no limiting.
        """
        diff = sp_target - sp_current
        if diff > 0:
            if rate_up <= 0:
                return sp_target
            max_change = rate_up * dt
            return sp_current + min(diff, max_change)
        elif diff < 0:
            if rate_dn <= 0:
                return sp_target
            max_change = rate_dn * dt
            return sp_current - min(abs(diff), max_change)
        return sp_target
