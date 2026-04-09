"""AlarmWorker — daemon thread evaluating alarms from telemetry bus."""
from __future__ import annotations

import asyncio
import logging
import threading
import time
from typing import TYPE_CHECKING, Any

import msgpack

from smart_pid_core.domain.services.alarm_engine import AlarmEngine
from smart_pid_domain.enums import AlarmType
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
        event_loop: asyncio.AbstractEventLoop | None = None,
    ) -> None:
        self._bus = bus
        self._alarm_configs = alarm_configs
        self._alarm_repo = alarm_repo
        self._event_loop = event_loop
        self._engine = AlarmEngine()
        self._controller_meta: dict[int, tuple[str, str]] = {}  # cid -> (name, description)
        self._pv_ranges: dict[int, tuple[float, float]] = {}     # cid -> (pv_min, pv_max)
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

    def _schedule_persist(self, transition: AlarmTransition) -> None:
        """Schedule async persistence from the sync worker thread."""
        if self._alarm_repo is None or self._event_loop is None:
            return
        asyncio.run_coroutine_threadsafe(
            self._persist_alarm(transition), self._event_loop,
        )

    def seed_active_alarms(self, active_alarms: list[dict]) -> None:
        """Seed the engine with alarms that are active in the DB.

        Must be called before start() so the engine can generate CLEARED
        transitions for alarms that were active before the daemon restarted.
        """
        for alarm in active_alarms:
            cid = alarm.get("controller_id", 0)
            atype_str = alarm.get("alarm_type", "")
            try:
                atype = AlarmType(atype_str)
            except ValueError:
                continue
            self._engine.seed_active(cid, atype)

    def update_controller_meta(
        self, controller_id: int, name: str, description: str,
    ) -> None:
        """Update controller name/description for event enrichment."""
        self._controller_meta[controller_id] = (name, description)

    def update_pv_range(
        self, controller_id: int, pv_min: float, pv_max: float,
    ) -> None:
        """Update PV instrument range for span-based deadband."""
        self._pv_ranges[controller_id] = (pv_min, pv_max)

    def remove_controller(self, controller_id: int) -> None:
        """Clean up all state for a removed controller."""
        self._alarm_configs.pop(controller_id, None)
        self._controller_meta.pop(controller_id, None)
        self._pv_ranges.pop(controller_id, None)
        self._engine.remove_controller(controller_id)

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

                pv_raw = data.get("pv", 0.0)
                pv = pv_raw["value"] if isinstance(pv_raw, dict) else float(pv_raw)
                sp_raw = data.get("sp", 0.0)
                sp = sp_raw["value"] if isinstance(sp_raw, dict) else float(sp_raw)
                sp_ramping = data.get("sp_ramping", False)

                pv_range = self._pv_ranges.get(cid)

                transitions = self._engine.evaluate(
                    cid,
                    pv=pv,
                    sp=sp,
                    alarm_config=config,
                    sp_ramping=sp_ramping,
                    pv_range=pv_range,
                )

                for t in transitions:
                    name, desc = self._controller_meta.get(
                        t.controller_id, ("?", ""),
                    )
                    alarm_data = {
                        "controller_id": t.controller_id,
                        "controller_name": name,
                        "controller_description": desc,
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
                    self._schedule_persist(t)
            except (msgpack.UnpackException, KeyError, ValueError) as exc:
                logger.warning("AlarmWorker: failed to process frame: %s", exc)
