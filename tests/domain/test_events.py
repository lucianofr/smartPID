from __future__ import annotations
from datetime import datetime, timezone
from uuid import UUID
from smart_pid_domain.enums import ConnectionState, SignalStatus
from smart_pid_domain.events import (
    ControlActionComputed, SystemStateChanged, TelemetryReceived,
)
from smart_pid_domain.models.telemetry import TelemetryFrame


class TestTelemetryReceived:
    def test_auto_generates_event_id(self) -> None:
        now = datetime.now(tz=timezone.utc)
        frame = TelemetryFrame(
            controller_id=1, pv=50.0, sp=50.0, co=25.0,
            integral_val=1.0, timestamp=now, status=SignalStatus.GOOD,
        )
        event = TelemetryReceived(controller_id=1, frame=frame)
        assert isinstance(event.event_id, UUID)

    def test_is_frozen(self) -> None:
        now = datetime.now(tz=timezone.utc)
        frame = TelemetryFrame(
            controller_id=1, pv=50.0, sp=50.0, co=25.0,
            integral_val=1.0, timestamp=now, status=SignalStatus.GOOD,
        )
        event = TelemetryReceived(controller_id=1, frame=frame)
        import pytest
        with pytest.raises(AttributeError):
            event.controller_id = 2  # type: ignore[misc]


class TestControlActionComputed:
    def test_construction(self) -> None:
        now = datetime.now(tz=timezone.utc)
        event = ControlActionComputed(
            controller_id=1, co=45.0, integral_val=1.5,
            delta_cv=0.5, timestamp=now,
        )
        assert event.delta_cv == 0.5


class TestSystemStateChanged:
    def test_construction(self) -> None:
        event = SystemStateChanged(
            new_state=ConnectionState.RECONNECTING,
            reason="Network timeout",
        )
        assert event.new_state == ConnectionState.RECONNECTING
