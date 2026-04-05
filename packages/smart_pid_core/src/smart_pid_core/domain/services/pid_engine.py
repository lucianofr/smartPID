"""PID controller engine using velocity (incremental) form.

Equation (derivative on PV):
    delta_cv = Gain * [(e_n - e_n-1) + (dt/Reset)*e_n - Rate*(PV_n - 2*PV_n-1 + PV_n-2)/dt]
    cv_new = cv_current + delta_cv

Derivative filter: alpha (default Rate/8).
Anti-windup: local (output saturation) + directional (downstream limit bits via BKCAL_IN).
Bumpless transfer: reinitializes state to match current output on mode change.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from smart_pid_domain.enums import LimitBits
from smart_pid_domain.models.signal import FFSignal, FFSignalStatus

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
    pv_filtered: float = 0.0
    sp_filtered: float = 0.0


@dataclass(frozen=True)
class PIDResult:
    """Output of a single PID computation."""

    cv: float
    delta_cv: float
    error: float
    bkcal_out: FFSignal
    new_state: PIDState


class PIDEngine:
    """Stateless PID engine. All state is passed in and returned explicitly."""

    def compute(
        self,
        params: PIDParams,
        state: PIDState,
        pv: FFSignal,
        sp: FFSignal,
        bkcal_in: FFSignal,
        dt: float,
        out_limits: tuple[float, float],
        direct_acting: bool = False,
        arw_limits: tuple[float, float] | None = None,
        *,
        pv_ftime: float = 0.0,
        sp_ftime: float = 0.0,
        ff_enable: bool = False,
        ff_val: float = 0.0,
        ff_gain: float = 1.0,
        low_cutoff_enabled: bool = False,
        low_cut: float = 0.0,
        out_scale_span: float = 0.0,
    ) -> PIDResult:
        """Execute one PID scan. Returns new CV, BKCAL_OUT, and updated state."""
        lo, hi = out_limits
        arw_lo, arw_hi = arw_limits if arw_limits is not None else (lo, hi)

        pv_val = pv.value
        sp_val = sp.value

        # --- Low cutoff: force PV to 0 when below threshold ---
        if low_cutoff_enabled and pv_val < low_cut:
            pv_val = 0.0

        # --- PV filter: first-order exponential ---
        if pv_ftime > 0 and dt > 0:
            alpha_pv = dt / (pv_ftime + dt)
            pv_val = alpha_pv * pv_val + (1.0 - alpha_pv) * state.pv_filtered
        pv_filtered = pv_val

        # --- SP filter: first-order exponential ---
        if sp_ftime > 0 and dt > 0:
            alpha_sp = dt / (sp_ftime + dt)
            sp_val = alpha_sp * sp_val + (1.0 - alpha_sp) * state.sp_filtered
        sp_filtered = sp_val

        # Error calculation
        error = pv_val - sp_val if direct_acting else sp_val - pv_val

        # --- Proportional term (acts on error change) ---
        p_term = params.gain * (error - state.error_prev)

        # --- Integral term ---
        i_term = 0.0
        if params.reset > 0 and dt > 0:
            # Check deadband
            in_deadband = abs(error) < params.deadband if params.deadband > 0 else False

            # Local anti-windup: suppress integral if saturated AND error drives further
            local_windup_block = (
                state.is_saturated
                and (
                    (state.cv >= arw_hi and error > 0)
                    or (state.cv <= arw_lo and error < 0)
                )
            )

            if not in_deadband and not local_windup_block:
                i_term = params.gain * (dt / params.reset) * error

                # Directional anti-windup from downstream (BKCAL_IN limit bits)
                limit = bkcal_in.status.limit_bits
                if (
                    limit == LimitBits.CONSTANT
                    or (limit == LimitBits.HIGH_LIMITED and i_term > 0)
                    or (limit == LimitBits.LOW_LIMITED and i_term < 0)
                ):
                    i_term = 0.0

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
            d2_pv = pv_val - 2.0 * state.pv_prev + state.pv_prev2
            d_raw = -params.gain * params.rate * (d2_pv / dt)
            # Apply derivative filter (exponential smoothing)
            alpha = min(max(params.alpha, 0.05), 1.0)
            d_term = alpha * d_raw + (1.0 - alpha) * state.derivative_filtered

        # --- Total increment ---
        delta_cv = p_term + i_term + d_term

        # --- Apply to output (with optional feedforward) ---
        cv_new = state.cv + delta_cv
        if ff_enable:
            cv_new += ff_val * ff_gain

        # --- Compute effective output limits (with optional 10% over-range) ---
        if out_scale_span > 0:
            overrange = 0.1 * out_scale_span
            eff_lo = lo - overrange
            eff_hi = hi + overrange
        else:
            eff_lo = lo
            eff_hi = hi

        # --- Clamp output ---
        is_saturated = False
        if cv_new > eff_hi:
            cv_new = eff_hi
            is_saturated = True
        elif cv_new < eff_lo:
            cv_new = eff_lo
            is_saturated = True

        new_state = PIDState(
            cv=cv_new,
            error_prev=error,
            pv_prev=pv_val,
            pv_prev2=state.pv_prev,
            sp_working=sp_val,
            derivative_filtered=d_term,
            is_saturated=is_saturated,
            pv_filtered=pv_filtered,
            sp_filtered=sp_filtered,
        )

        # --- Generate BKCAL_OUT ---
        bkcal_out = self._make_bkcal_out(cv_new, eff_lo, eff_hi, is_saturated)

        return PIDResult(
            cv=cv_new,
            delta_cv=delta_cv,
            error=error,
            bkcal_out=bkcal_out,
            new_state=new_state,
        )

    def compute_iman_tracking(
        self,
        state: PIDState,
        pv: FFSignal,
        sp: FFSignal,
        bkcal_in: FFSignal,
        direct_acting: bool = False,
    ) -> PIDResult:
        """IMAN tracking: force CV to match BKCAL_IN value exactly.

        Used during cascade initialization handshake (IR phase).
        The integral accumulator is forced directly -- no PID calculation.
        PV history is updated to prevent derivative kick on return to active mode.
        """
        pv_val = pv.value
        sp_val = sp.value
        error = pv_val - sp_val if direct_acting else sp_val - pv_val
        tracking_value = bkcal_in.value

        new_state = PIDState(
            cv=tracking_value,
            error_prev=error,
            pv_prev=pv_val,
            pv_prev2=state.pv_prev,
            sp_working=sp_val,
            derivative_filtered=0.0,
            is_saturated=False,
        )

        from smart_pid_domain.enums import InitSubStatus, SignalSeverity

        bkcal_out = FFSignal(
            value=tracking_value,
            status=FFSignalStatus(
                severity=SignalSeverity.GOOD,
                sub_status=InitSubStatus.IA,
            ),
            timestamp=bkcal_in.timestamp,
        )

        return PIDResult(
            cv=tracking_value,
            delta_cv=0.0,
            error=error,
            bkcal_out=bkcal_out,
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

    def _make_bkcal_out(
        self, cv: float, lo: float, hi: float, is_saturated: bool,
    ) -> FFSignal:
        """Build BKCAL_OUT signal reflecting current output and saturation state."""
        if not is_saturated:
            return FFSignal.good(cv)
        if cv >= hi:
            return FFSignal.with_limits(cv, LimitBits.HIGH_LIMITED)
        return FFSignal.with_limits(cv, LimitBits.LOW_LIMITED)
