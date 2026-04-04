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


_HIGH_ALARMS = (AlarmType.HIHI, AlarmType.HI)
_LOW_ALARMS = (AlarmType.LO, AlarmType.LOLO)


class AlarmEngine:
    """Evaluates process values against alarm limits with hysteresis."""

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

            if atype in _HIGH_ALARMS:
                triggered = pv >= limit
                cleared = pv < (limit - deadband)
            else:  # LOW alarms
                triggered = pv <= limit
                cleared = pv > (limit + deadband)

            t = self._check_transition(
                state, triggered, cleared, controller_id, atype, priority, pv, limit, now,
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
                triggered = deviation >= limit
                cleared = deviation < (limit - deadband)
                t = self._check_transition(
                    state, triggered, cleared, controller_id, atype, priority, pv, limit, now,
                )
                if t is not None:
                    transitions.append(t)

        return transitions

    def _get_state(self, controller_id: int, alarm_type: AlarmType) -> _PointState:
        key = (controller_id, alarm_type)
        if key not in self._states:
            self._states[key] = _PointState()
        return self._states[key]

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
    ) -> AlarmTransition | None:
        if triggered and not state.active:
            state.active = True
            return AlarmTransition(
                controller_id=controller_id,
                alarm_type=alarm_type,
                priority=priority,
                transition="TRIGGERED",
                value=value,
                limit=limit,
                timestamp=timestamp,
            )
        if cleared and state.active:
            state.active = False
            return AlarmTransition(
                controller_id=controller_id,
                alarm_type=alarm_type,
                priority=priority,
                transition="CLEARED",
                value=value,
                limit=limit,
                timestamp=timestamp,
            )
        return None
