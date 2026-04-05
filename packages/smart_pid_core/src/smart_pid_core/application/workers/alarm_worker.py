"""AlarmWorker — daemon thread evaluating alarms from telemetry bus."""
from __future__ import annotations

import logging
import threading
import time
from typing import TYPE_CHECKING, Any

import msgpack

from smart_pid_core.domain.services.alarm_engine import AlarmEngine
from smart_pid_domain.models.alarm_config import AlarmConfig

if TYPE_CHECKING:
    from smart_pid_core.application.event_bus import EventBus
    from smart_pid_domain.models.alarm_config import AlarmTransition

logger = logging.getLogger(__name__)


class AlarmWorker:
    """Subscribes to STATUS.* and evaluates alarm limits."""

    def __init__(
        self,
        bus: EventBus,
        alarm_configs: dict[int, AlarmConfig],
        alarm_repo: Any = None,
    ) -> None:
        self._bus = bus
        self._alarm_configs = alarm_configs
        self._alarm_repo = alarm_repo
        self._engine = AlarmEngine()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    async def _persist_alarm(self, transition: AlarmTransition) -> None:
        """Persist alarm transition to DB. No-op if repo is None."""
        if self._alarm_repo is None:
            return
        try:
            if transition.transition == "TRIGGERED":
                await self._alarm_repo.insert_alarm(
                    controller_id=transition.controller_id,
                    alarm_type=transition.alarm_type,
                    priority=transition.priority,
                    value=transition.value,
                    limit_value=transition.limit,
                    triggered_at=transition.timestamp,
                )
            elif transition.transition == "CLEARED":
                await self._alarm_repo.mark_cleared(
                    controller_id=transition.controller_id,
                    alarm_type=transition.alarm_type,
                    cleared_at=transition.timestamp,
                )
        except Exception:
            logger.exception("alarm_persist_error")

    def update_config(self, controller_id: int, config: AlarmConfig) -> None:
        """Update alarm config for a controller (thread-safe via GIL)."""
        self._alarm_configs[controller_id] = config

    def start(self) -> None:
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            daemon=True,
            name="alarm-worker",
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5.0)
            self._thread = None

    def is_alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def _run(self) -> None:
        sub = self._bus.create_subscriber(b"STATUS.")
        pub = self._bus.create_publisher()
        time.sleep(0.02)  # Let subscriptions propagate

        while not self._stop_event.is_set():
            msg = sub.recv(timeout_ms=100)
            if msg is None:
                continue

            topic_bytes, payload = msg
            try:
                data = msgpack.unpackb(payload)
                cid = data.get("controller_id", 0)
                config = self._alarm_configs.get(cid)
                if config is None:
                    continue

                pv = data.get("pv", 0.0)
                sp = data.get("sp", 0.0)
                sp_ramping = data.get("sp_ramping", False)

                transitions = self._engine.evaluate(
                    cid,
                    pv=pv,
                    sp=sp,
                    alarm_config=config,
                    sp_ramping=sp_ramping,
                )

                for t in transitions:
                    alarm_data = {
                        "controller_id": t.controller_id,
                        "alarm_type": str(t.alarm_type),
                        "priority": str(t.priority),
                        "transition": t.transition,
                        "value": t.value,
                        "limit": t.limit,
                        "timestamp": t.timestamp.isoformat(),
                    }
                    pub.send(
                        f"EVENT.ALARM.{t.controller_id}".encode(),
                        msgpack.packb(alarm_data),
                    )
            except (msgpack.UnpackException, KeyError, ValueError):
                pass
