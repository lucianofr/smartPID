"""AlarmEngine — pure domain service for process alarm detection."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from smart_pid_domain.enums import AlarmPriority, AlarmType
from smart_pid_domain.models.alarm_config import AlarmConfig, AlarmTransition


@dataclass
class _PointState:
    """Mutable tracking state for one (controller, alarm_type) pair."""

    active: bool = False
    # Timestamp when the pending condition first became true (None = no pending)
    pending_trigger_since: datetime | None = None
    pending_clear_since: datetime | None = None


_HIGH_ALARMS = (AlarmType.HIHI, AlarmType.HI)
_LOW_ALARMS = (AlarmType.LO, AlarmType.LOLO)

# Mapping from AlarmType to the delay field names on AlarmConfig
_DELAY_FIELDS: dict[AlarmType, tuple[str, str]] = {
    AlarmType.HIHI: ("hihi_delay_on_s", "hihi_delay_off_s"),
    AlarmType.HI: ("hi_delay_on_s", "hi_delay_off_s"),
    AlarmType.LO: ("lo_delay_on_s", "lo_delay_off_s"),
    AlarmType.LOLO: ("lolo_delay_on_s", "lolo_delay_off_s"),
    AlarmType.DV_HI: ("dv_hi_delay_on_s", "dv_hi_delay_off_s"),
    AlarmType.DV_LO: ("dv_lo_delay_on_s", "dv_lo_delay_off_s"),
}


class AlarmEngine:
    """Evaluates process values against alarm limits with hysteresis and delays."""

    def __init__(self) -> None:
        self._states: dict[tuple[int, AlarmType], _PointState] = {}

    def evaluate(
        self,
        controller_id: int,
        pv: float,
        sp: float,
        alarm_config: AlarmConfig,
        sp_ramping: bool,
    ) -> list[AlarmTransition]:
        """Evaluate all alarm types for one controller. Returns transitions."""
        now = datetime.now(tz=UTC)
        transitions: list[AlarmTransition] = []

        # Process alarms (absolute limits)
        checks: list[tuple[AlarmType, bool, float, AlarmPriority]] = [
            (
                AlarmType.HIHI,
                alarm_config.hihi_enabled,
                alarm_config.hihi_value,
                alarm_config.hihi_priority,
            ),
            (
                AlarmType.HI,
                alarm_config.hi_enabled,
                alarm_config.hi_value,
                alarm_config.hi_priority,
            ),
            (
                AlarmType.LO,
                alarm_config.lo_enabled,
                alarm_config.lo_value,
                alarm_config.lo_priority,
            ),
            (
                AlarmType.LOLO,
                alarm_config.lolo_enabled,
                alarm_config.lolo_value,
                alarm_config.lolo_priority,
            ),
        ]

        for atype, enabled, limit, priority in checks:
            if not enabled:
                continue
            state = self._get_state(controller_id, atype)
            deadband = abs(limit) * alarm_config.deadband_percent / 100.0
            delay_on, delay_off = self._get_delays(atype, alarm_config)

            if atype in _HIGH_ALARMS:
                triggered = pv >= limit
                cleared = pv < (limit - deadband)
            else:  # LOW alarms
                triggered = pv <= limit
                cleared = pv > (limit + deadband)

            t = self._check_transition(
                state, triggered, cleared,
                controller_id, atype, priority, pv, limit, now,
                delay_on, delay_off,
            )
            if t is not None:
                transitions.append(t)

        # Deviation alarms (suppressed during SP ramp)
        if not sp_ramping:
            dev_checks: list[tuple[AlarmType, bool, float, AlarmPriority, float]] = [
                (
                    AlarmType.DV_HI,
                    alarm_config.dv_hi_enabled,
                    alarm_config.dv_hi_value,
                    alarm_config.dv_hi_priority,
                    pv - sp,
                ),
                (
                    AlarmType.DV_LO,
                    alarm_config.dv_lo_enabled,
                    alarm_config.dv_lo_value,
                    alarm_config.dv_lo_priority,
                    sp - pv,
                ),
            ]
            for atype, enabled, limit, priority, deviation in dev_checks:
                if not enabled:
                    continue
                state = self._get_state(controller_id, atype)
                deadband = abs(limit) * alarm_config.deadband_percent / 100.0
                delay_on, delay_off = self._get_delays(atype, alarm_config)
                triggered = deviation >= limit
                cleared = deviation < (limit - deadband)
                t = self._check_transition(
                    state, triggered, cleared,
                    controller_id, atype, priority, pv, limit, now,
                    delay_on, delay_off,
                )
                if t is not None:
                    transitions.append(t)

        return transitions

    def remove_controller(self, controller_id: int) -> None:
        """Remove all alarm states for a controller (cleanup on delete)."""
        keys_to_remove = [
            key for key in self._states if key[0] == controller_id
        ]
        for key in keys_to_remove:
            del self._states[key]

    def _get_state(self, controller_id: int, alarm_type: AlarmType) -> _PointState:
        key = (controller_id, alarm_type)
        if key not in self._states:
            self._states[key] = _PointState()
        return self._states[key]

    @staticmethod
    def _get_delays(atype: AlarmType, config: AlarmConfig) -> tuple[float, float]:
        """Return (delay_on_s, delay_off_s) for the given alarm type."""
        fields = _DELAY_FIELDS.get(atype)
        if fields is None:
            return 0.0, 0.0
        return getattr(config, fields[0], 0.0), getattr(config, fields[1], 0.0)

    def _check_transition(
        self,
        state: _PointState,
        triggered: bool,
        cleared: bool,
        controller_id: int,
        alarm_type: AlarmType,
        priority: AlarmPriority,
        value: float,
        limit: float,
        timestamp: datetime,
        delay_on: float,
        delay_off: float,
    ) -> AlarmTransition | None:
        # --- Trigger logic ---
        if triggered and not state.active:
            if delay_on <= 0:
                # No delay: trigger immediately
                state.active = True
                state.pending_trigger_since = None
                return AlarmTransition(
                    controller_id=controller_id,
                    alarm_type=alarm_type,
                    priority=priority,
                    transition="TRIGGERED",
                    value=value,
                    limit=limit,
                    timestamp=timestamp,
                )
            # Start or check delay timer
            if state.pending_trigger_since is None:
                state.pending_trigger_since = timestamp
            elif (timestamp - state.pending_trigger_since).total_seconds() >= delay_on:
                state.active = True
                state.pending_trigger_since = None
                return AlarmTransition(
                    controller_id=controller_id,
                    alarm_type=alarm_type,
                    priority=priority,
                    transition="TRIGGERED",
                    value=value,
                    limit=limit,
                    timestamp=timestamp,
                )
        elif not triggered and not state.active:
            # Condition went away before delay elapsed — reset pending
            state.pending_trigger_since = None

        # --- Clear logic ---
        if cleared and state.active:
            if delay_off <= 0:
                state.active = False
                state.pending_clear_since = None
                return AlarmTransition(
                    controller_id=controller_id,
                    alarm_type=alarm_type,
                    priority=priority,
                    transition="CLEARED",
                    value=value,
                    limit=limit,
                    timestamp=timestamp,
                )
            if state.pending_clear_since is None:
                state.pending_clear_since = timestamp
            elif (timestamp - state.pending_clear_since).total_seconds() >= delay_off:
                state.active = False
                state.pending_clear_since = None
                return AlarmTransition(
                    controller_id=controller_id,
                    alarm_type=alarm_type,
                    priority=priority,
                    transition="CLEARED",
                    value=value,
                    limit=limit,
                    timestamp=timestamp,
                )
        elif not cleared and state.active:
            # PV went back into alarm zone before delay_off elapsed — reset
            state.pending_clear_since = None

        return None
