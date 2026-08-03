"""AlarmWorker — daemon thread evaluating alarms from telemetry bus."""
from __future__ import annotations

import asyncio
import contextlib
import logging
import threading
import time
from typing import TYPE_CHECKING, Any

import msgpack

from smart_pid_core.domain.services.alarm_engine import AlarmEngine
from smart_pid_domain.enums import AlarmType
from smart_pid_domain.models.alarm_config import AlarmConfig

if TYPE_CHECKING:
    from smart_pid_core.application.event_bus import (
        BusPublisher,
        BusSubscriber,
        EventBus,
    )
    from smart_pid_domain.models.alarm_config import AlarmTransition

logger = logging.getLogger(__name__)


async def load_alarm_configs(session_factory) -> dict[int, AlarmConfig]:  # noqa: ANN001
    """Load alarm configurations from Configuracao_Alarmes table.

    Only rows whose controller still EXISTS are loaded, and only
    controllers with at least one ENABLED alarm get an entry.

    Both filters are load-bearing. ``Configuracao_Alarmes`` is keyed by
    ``controlador_id``, and SQLite hands out ``max(id) + 1``, so a row left
    behind by a deleted loop is inherited by whatever loop next takes that
    id. That is how a freshly created FIC-101 with nothing configured
    started announcing a HI alarm at 80: the limit belonged to a loop that
    had been deleted. Dropping all-disabled controllers then keeps the
    worker from evaluating a config whose every branch is a no-op, so
    "has an entry here" reads as "has something to check".
    """
    from sqlalchemy import text

    from smart_pid_domain.enums import AlarmPriority
    from smart_pid_domain.models.alarm_config import AlarmConfig as _AC

    configs: dict[int, _AC] = {}
    try:
        async with session_factory() as session:
            result = await session.execute(
                text(
                    "SELECT ca.* FROM Configuracao_Alarmes ca "
                    "JOIN Controladores c ON c.id = ca.controlador_id "
                    "ORDER BY ca.controlador_id"
                )
            )
            rows = result.mappings().all()
    except Exception:
        logger.debug("alarm_configs_not_loaded", exc_info=True)
        return configs

    by_controller: dict[int, dict] = {}
    for row in rows:
        cid = row["controlador_id"]
        if cid not in by_controller:
            by_controller[cid] = {}
        atype = row["tipo_alarme"]
        by_controller[cid][atype] = {
            "enabled": bool(row["habilitado"]),
            "value": row["limite"],
            "priority": AlarmPriority(row["prioridade"]),
            "hysteresis": row["histerese"],
            "delay_on_s": row["delay_on_s"] if "delay_on_s" in row.keys() else 0.0,  # noqa: SIM118
            "delay_off_s": row["delay_off_s"] if "delay_off_s" in row.keys() else 0.0,  # noqa: SIM118
        }

    for cid, alarms in by_controller.items():

        def _get(
            name: str,
            default_priority: AlarmPriority = AlarmPriority.WARNING,
            _alarms: dict = alarms,
        ) -> tuple[bool, float, AlarmPriority, float, float]:
            a = _alarms.get(name, {})
            return (
                a.get("enabled", False),
                a.get("value", 0.0),
                a.get("priority", default_priority),
                a.get("delay_on_s", 0.0),
                a.get("delay_off_s", 0.0),
            )

        hihi_e, hihi_v, hihi_p, hihi_don, hihi_doff = _get("HIHI", AlarmPriority.CRITICAL)
        hi_e, hi_v, hi_p, hi_don, hi_doff = _get("HI")
        lo_e, lo_v, lo_p, lo_don, lo_doff = _get("LO")
        lolo_e, lolo_v, lolo_p, lolo_don, lolo_doff = _get("LOLO", AlarmPriority.CRITICAL)
        dvhi_e, dvhi_v, dvhi_p, dvhi_don, dvhi_doff = _get("DV_HI", AlarmPriority.ADVISORY)
        dvlo_e, dvlo_v, dvlo_p, dvlo_don, dvlo_doff = _get("DV_LO", AlarmPriority.ADVISORY)
        deadband = max((a.get("hysteresis", 0.0) for a in alarms.values()), default=0.0)

        if not any(
            (hihi_e, hi_e, lo_e, lolo_e, dvhi_e, dvlo_e),
        ):
            # Every alarm on this loop is switched off. Registering the
            # config anyway would leave the worker evaluating six disabled
            # branches per frame and, worse, make "the loop has a config"
            # stop meaning "the loop has something to announce".
            continue

        configs[cid] = _AC(
            hihi_enabled=hihi_e,
            hihi_value=hihi_v,
            hihi_priority=hihi_p,
            hihi_delay_on_s=hihi_don,
            hihi_delay_off_s=hihi_doff,
            hi_enabled=hi_e,
            hi_value=hi_v,
            hi_priority=hi_p,
            hi_delay_on_s=hi_don,
            hi_delay_off_s=hi_doff,
            lo_enabled=lo_e,
            lo_value=lo_v,
            lo_priority=lo_p,
            lo_delay_on_s=lo_don,
            lo_delay_off_s=lo_doff,
            lolo_enabled=lolo_e,
            lolo_value=lolo_v,
            lolo_priority=lolo_p,
            lolo_delay_on_s=lolo_don,
            lolo_delay_off_s=lolo_doff,
            dv_hi_enabled=dvhi_e,
            dv_hi_value=dvhi_v,
            dv_hi_priority=dvhi_p,
            dv_hi_delay_on_s=dvhi_don,
            dv_hi_delay_off_s=dvhi_doff,
            dv_lo_enabled=dvlo_e,
            dv_lo_value=dvlo_v,
            dv_lo_priority=dvlo_p,
            dv_lo_delay_on_s=dvlo_don,
            dv_lo_delay_off_s=dvlo_doff,
            deadband_percent=deadband,
        )
    return configs


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

    def reload_project(
        self,
        alarm_configs: dict[int, AlarmConfig],
        controllers: list[Any],
        active_alarms: list[dict],
    ) -> None:
        """Swap every per-project cache when the daemon opens another project.

        All of this worker's state is keyed by controller id, and those ids are
        only unique WITHIN a project. Carrying them across a switch makes the
        engine evaluate the previous project's limits against the new project's
        controllers -- alarms fire for a project that configures none, and the
        banner lights up with no matching row. Rebuild instead of merge: a
        config the new project does not define has to disappear, not linger.
        """
        self._engine = AlarmEngine()
        self._alarm_configs.clear()
        self._alarm_configs.update(alarm_configs)
        self._controller_meta.clear()
        self._pv_ranges.clear()
        for ctrl in controllers:
            self.update_controller_meta(ctrl.id, ctrl.name, ctrl.description)
            self.update_pv_range(ctrl.id, ctrl.pv_scale.eu_min, ctrl.pv_scale.eu_max)
        # Seed only genuinely-active rows so the engine can still emit CLEARED
        # for an alarm that was standing when the project was last closed.
        self.seed_active_alarms([a for a in active_alarms if a.get("cleared_at") is None])

    def update_config(self, controller_id: int, config: AlarmConfig) -> None:
        """Update alarm config for a controller (thread-safe via GIL).

        Switching every alarm off DROPS the entry rather than storing an
        all-disabled config, mirroring what ``load_alarm_configs`` does at
        startup. Without the symmetry a loop the operator had just silenced
        would keep a live config until the next daemon restart.
        """
        if not any((
            config.hihi_enabled, config.hi_enabled,
            config.lo_enabled, config.lolo_enabled,
            config.dv_hi_enabled, config.dv_lo_enabled,
        )):
            self._alarm_configs.pop(controller_id, None)
            self._engine.remove_controller(controller_id)
            return
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

        try:
            self._loop(sub, pub)
        finally:
            # ZMQ sockets must be closed by the thread that created them,
            # otherwise EventBus.stop()'s ctx.destroy() blocks in
            # zmq_ctx_term() closing them cross-thread (see PIDWorker._run).
            for sock in (sub, pub):
                with contextlib.suppress(Exception):
                    sock.close()

    def _loop(self, sub: BusSubscriber, pub: BusPublisher) -> None:
        """Evaluate alarms until stopped. Socket lifetime is _run's job."""
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
