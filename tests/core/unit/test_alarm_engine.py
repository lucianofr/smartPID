"""Tests for AlarmEngine — alarm detection, hysteresis, deviation suppression."""
from __future__ import annotations

from smart_pid_core.domain.services.alarm_engine import AlarmEngine
from smart_pid_domain.enums import AlarmPriority, AlarmType
from smart_pid_domain.models.alarm_config import AlarmConfig

_BASE_CONFIG = AlarmConfig(
    hihi_enabled=True, hihi_value=90.0, hihi_priority=AlarmPriority.CRITICAL,
    hi_enabled=True, hi_value=80.0, hi_priority=AlarmPriority.WARNING,
    lo_enabled=True, lo_value=20.0, lo_priority=AlarmPriority.WARNING,
    lolo_enabled=True, lolo_value=10.0, lolo_priority=AlarmPriority.CRITICAL,
    dv_hi_enabled=True, dv_hi_value=15.0, dv_hi_priority=AlarmPriority.ADVISORY,
    dv_lo_enabled=True, dv_lo_value=15.0, dv_lo_priority=AlarmPriority.ADVISORY,
    deadband_percent=2.0,
)


class TestProcessAlarms:
    def test_hihi_triggers(self):
        engine = AlarmEngine()
        transitions = engine.evaluate(
            1, pv=95.0, sp=50.0, alarm_config=_BASE_CONFIG, sp_ramping=False,
        )
        triggered = [t for t in transitions if t.alarm_type == AlarmType.HIHI]
        assert len(triggered) == 1
        assert triggered[0].transition == "TRIGGERED"
        assert triggered[0].priority == AlarmPriority.CRITICAL

    def test_hi_triggers(self):
        engine = AlarmEngine()
        transitions = engine.evaluate(
            1, pv=85.0, sp=50.0, alarm_config=_BASE_CONFIG, sp_ramping=False,
        )
        triggered_types = {t.alarm_type for t in transitions if t.transition == "TRIGGERED"}
        assert AlarmType.HI in triggered_types

    def test_lo_triggers(self):
        engine = AlarmEngine()
        transitions = engine.evaluate(
            1, pv=15.0, sp=50.0, alarm_config=_BASE_CONFIG, sp_ramping=False,
        )
        triggered_types = {t.alarm_type for t in transitions if t.transition == "TRIGGERED"}
        assert AlarmType.LO in triggered_types

    def test_lolo_triggers(self):
        engine = AlarmEngine()
        transitions = engine.evaluate(
            1, pv=5.0, sp=50.0, alarm_config=_BASE_CONFIG, sp_ramping=False,
        )
        triggered_types = {t.alarm_type for t in transitions if t.transition == "TRIGGERED"}
        assert AlarmType.LOLO in triggered_types

    def test_no_alarm_in_normal_range(self):
        engine = AlarmEngine()
        transitions = engine.evaluate(
            1, pv=50.0, sp=50.0, alarm_config=_BASE_CONFIG, sp_ramping=False,
        )
        assert len(transitions) == 0

    def test_disabled_alarm_does_not_trigger(self):
        config = AlarmConfig(
            hihi_enabled=False, hihi_value=90.0, hihi_priority=AlarmPriority.CRITICAL,
            hi_enabled=False, hi_value=80.0, hi_priority=AlarmPriority.WARNING,
            lo_enabled=False, lo_value=20.0, lo_priority=AlarmPriority.WARNING,
            lolo_enabled=False, lolo_value=10.0, lolo_priority=AlarmPriority.CRITICAL,
            dv_hi_enabled=False, dv_hi_value=15.0, dv_hi_priority=AlarmPriority.ADVISORY,
            dv_lo_enabled=False, dv_lo_value=15.0, dv_lo_priority=AlarmPriority.ADVISORY,
            deadband_percent=2.0,
        )
        engine = AlarmEngine()
        transitions = engine.evaluate(
            1, pv=95.0, sp=50.0, alarm_config=config, sp_ramping=False,
        )
        assert len(transitions) == 0


class TestHysteresis:
    def test_hihi_does_not_clear_without_deadband(self):
        """HIHI at 90.0, deadband 2% = 1.8. Must drop below 88.2 to clear."""
        engine = AlarmEngine()
        engine.evaluate(1, pv=95.0, sp=50.0, alarm_config=_BASE_CONFIG, sp_ramping=False)
        transitions = engine.evaluate(
            1, pv=89.0, sp=50.0, alarm_config=_BASE_CONFIG, sp_ramping=False,
        )
        cleared = [
            t for t in transitions
            if t.alarm_type == AlarmType.HIHI and t.transition == "CLEARED"
        ]
        assert len(cleared) == 0

    def test_hihi_clears_below_deadband(self):
        engine = AlarmEngine()
        engine.evaluate(1, pv=95.0, sp=50.0, alarm_config=_BASE_CONFIG, sp_ramping=False)
        transitions = engine.evaluate(
            1, pv=87.0, sp=50.0, alarm_config=_BASE_CONFIG, sp_ramping=False,
        )
        cleared = [
            t for t in transitions
            if t.alarm_type == AlarmType.HIHI and t.transition == "CLEARED"
        ]
        assert len(cleared) == 1

    def test_lo_clears_above_deadband(self):
        """LO at 20.0, deadband 2% = 0.4. Must rise above 20.4 to clear."""
        engine = AlarmEngine()
        engine.evaluate(1, pv=15.0, sp=50.0, alarm_config=_BASE_CONFIG, sp_ramping=False)
        transitions = engine.evaluate(
            1, pv=20.2, sp=50.0, alarm_config=_BASE_CONFIG, sp_ramping=False,
        )
        cleared = [
            t for t in transitions
            if t.alarm_type == AlarmType.LO and t.transition == "CLEARED"
        ]
        assert len(cleared) == 0
        transitions = engine.evaluate(
            1, pv=21.0, sp=50.0, alarm_config=_BASE_CONFIG, sp_ramping=False,
        )
        cleared = [
            t for t in transitions
            if t.alarm_type == AlarmType.LO and t.transition == "CLEARED"
        ]
        assert len(cleared) == 1


class TestDeviationAlarms:
    def test_dv_hi_triggers(self):
        engine = AlarmEngine()
        transitions = engine.evaluate(
            1, pv=70.0, sp=50.0, alarm_config=_BASE_CONFIG, sp_ramping=False,
        )
        triggered = [t for t in transitions if t.alarm_type == AlarmType.DV_HI]
        assert len(triggered) == 1
        assert triggered[0].transition == "TRIGGERED"

    def test_dv_lo_triggers(self):
        engine = AlarmEngine()
        transitions = engine.evaluate(
            1, pv=30.0, sp=50.0, alarm_config=_BASE_CONFIG, sp_ramping=False,
        )
        triggered = [t for t in transitions if t.alarm_type == AlarmType.DV_LO]
        assert len(triggered) == 1

    def test_deviation_suppressed_during_sp_ramp(self):
        engine = AlarmEngine()
        transitions = engine.evaluate(
            1, pv=70.0, sp=50.0, alarm_config=_BASE_CONFIG, sp_ramping=True,
        )
        dv_transitions = [
            t for t in transitions
            if t.alarm_type in (AlarmType.DV_HI, AlarmType.DV_LO)
        ]
        assert len(dv_transitions) == 0


class TestMultiController:
    def test_independent_state_per_controller(self):
        engine = AlarmEngine()
        t1 = engine.evaluate(
            1, pv=95.0, sp=50.0, alarm_config=_BASE_CONFIG, sp_ramping=False,
        )
        assert any(t.alarm_type == AlarmType.HIHI for t in t1)
        t2 = engine.evaluate(
            2, pv=50.0, sp=50.0, alarm_config=_BASE_CONFIG, sp_ramping=False,
        )
        assert len(t2) == 0


class TestNoRetrigger:
    def test_already_active_alarm_does_not_retrigger(self):
        engine = AlarmEngine()
        t1 = engine.evaluate(
            1, pv=95.0, sp=50.0, alarm_config=_BASE_CONFIG, sp_ramping=False,
        )
        hihi_count = sum(1 for t in t1 if t.alarm_type == AlarmType.HIHI)
        assert hihi_count == 1
        t2 = engine.evaluate(
            1, pv=96.0, sp=50.0, alarm_config=_BASE_CONFIG, sp_ramping=False,
        )
        hihi_count = sum(1 for t in t2 if t.alarm_type == AlarmType.HIHI)
        assert hihi_count == 0


class TestSeedActive:
    def test_seed_active_allows_clearing(self):
        """Seeded active alarm should generate CLEARED when PV recovers."""
        engine = AlarmEngine()
        engine.seed_active(1, AlarmType.LO)
        # PV=50 is well above LO limit=20, should clear
        transitions = engine.evaluate(
            1, pv=50.0, sp=50.0, alarm_config=_BASE_CONFIG, sp_ramping=False,
        )
        cleared = [t for t in transitions if t.alarm_type == AlarmType.LO
                   and t.transition == "CLEARED"]
        assert len(cleared) == 1

    def test_seed_active_no_retrigger(self):
        """Seeded active alarm should NOT re-trigger on same condition."""
        engine = AlarmEngine()
        engine.seed_active(1, AlarmType.LO)
        # PV=15 is below LO limit=20, but alarm is already active — no retrigger
        transitions = engine.evaluate(
            1, pv=15.0, sp=50.0, alarm_config=_BASE_CONFIG, sp_ramping=False,
        )
        lo_triggered = [t for t in transitions if t.alarm_type == AlarmType.LO
                        and t.transition == "TRIGGERED"]
        assert len(lo_triggered) == 0

    def test_unseeded_alarm_does_not_clear(self):
        """Without seeding, engine cannot clear an alarm it never triggered."""
        engine = AlarmEngine()
        # PV=50 is above LO limit=20 — but engine state is inactive, so no CLEARED
        transitions = engine.evaluate(
            1, pv=50.0, sp=50.0, alarm_config=_BASE_CONFIG, sp_ramping=False,
        )
        cleared = [t for t in transitions if t.alarm_type == AlarmType.LO
                   and t.transition == "CLEARED"]
        assert len(cleared) == 0


class TestSpanBasedDeadband:
    def test_deadband_uses_span_when_pv_range_provided(self):
        """Deadband should be calculated as % of span, not % of limit (Bug #11)."""
        engine = AlarmEngine()
        config = AlarmConfig(
            hi_enabled=True, hi_value=90.0, hi_priority=AlarmPriority.WARNING,
            deadband_percent=2.0,  # 2% of span
        )
        # Span = 200 - 0 = 200, deadband = 200 * 2% = 4.0
        # Clear threshold = 90.0 - 4.0 = 86.0

        # Trigger at PV=91
        t1 = engine.evaluate(1, pv=91.0, sp=50.0, alarm_config=config,
                             sp_ramping=False, pv_range=(0.0, 200.0))
        assert len(t1) == 1
        assert t1[0].transition == "TRIGGERED"

        # PV=87 — still above 86.0, should NOT clear
        t2 = engine.evaluate(1, pv=87.0, sp=50.0, alarm_config=config,
                             sp_ramping=False, pv_range=(0.0, 200.0))
        assert len(t2) == 0

        # PV=85 — below 86.0, should clear
        t3 = engine.evaluate(1, pv=85.0, sp=50.0, alarm_config=config,
                             sp_ramping=False, pv_range=(0.0, 200.0))
        assert len(t3) == 1
        assert t3[0].transition == "CLEARED"

    def test_deadband_zero_limit_with_span(self):
        """When limit=0.0, deadband must NOT be zero if pv_range is provided (Bug #11)."""
        engine = AlarmEngine()
        config = AlarmConfig(
            lo_enabled=True, lo_value=0.0, lo_priority=AlarmPriority.WARNING,
            deadband_percent=1.0,  # 1% of span
        )
        # Span = 100, deadband = 1.0. Clear threshold = 0.0 + 1.0 = 1.0

        # Trigger at PV=0
        t1 = engine.evaluate(1, pv=0.0, sp=50.0, alarm_config=config,
                             sp_ramping=False, pv_range=(0.0, 100.0))
        assert len(t1) == 1

        # PV=0.5 — still below 1.0, should NOT clear
        t2 = engine.evaluate(1, pv=0.5, sp=50.0, alarm_config=config,
                             sp_ramping=False, pv_range=(0.0, 100.0))
        assert len(t2) == 0

        # PV=1.5 — above 1.0, should clear
        t3 = engine.evaluate(1, pv=1.5, sp=50.0, alarm_config=config,
                             sp_ramping=False, pv_range=(0.0, 100.0))
        assert len(t3) == 1
        assert t3[0].transition == "CLEARED"

    def test_deadband_fallback_without_pv_range(self):
        """Without pv_range, deadband falls back to abs(limit) * percent."""
        engine = AlarmEngine()
        config = AlarmConfig(
            hi_enabled=True, hi_value=100.0, hi_priority=AlarmPriority.WARNING,
            deadband_percent=2.0,
        )
        # Fallback: deadband = abs(100) * 2% = 2.0. Clear = 100 - 2 = 98.

        t1 = engine.evaluate(1, pv=101.0, sp=50.0, alarm_config=config,
                             sp_ramping=False)
        assert len(t1) == 1

        t2 = engine.evaluate(1, pv=98.5, sp=50.0, alarm_config=config,
                             sp_ramping=False)
        assert len(t2) == 0  # Still above 98

        t3 = engine.evaluate(1, pv=97.0, sp=50.0, alarm_config=config,
                             sp_ramping=False)
        assert len(t3) == 1
        assert t3[0].transition == "CLEARED"
