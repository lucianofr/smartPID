"""TwinTelemetry — telemetry for simulator loops that no malha owns.

A simulator loop can exist with no project controller behind it: the twin mints
a default loop (id 0) on start, and ``POST /simulator/loops`` creates loops on
purpose, because the simulator is a standalone module for tuning experiments.

Nothing sampled those loops. ``IOWorker`` scans the ids in ``Controladores``
and ``STATUS.{id}`` is published by the PID/Monitor worker that ``LoopManager``
starts per malha — so a twin-only loop integrated its model, moved its OPC-UA
nodes, and reached no consumer at all: the ``/trend`` ring stayed empty (a
chart with no seed), no realtime frame reached the HMI (a chart with no live
trace), and the historian recorded nothing. On a deployment with zero malhas —
the simulator's own use case — every trend on the Sim page was permanently
blank while the control panel, fed by ``GET /simulator/status``, looked alive.

This attaches the two pieces a malha would have brought, and only to loops no
control loop owns: the IO scan (``TELEMETRY.{id}``) and a ``MonitorWorker``
(``TELEMETRY`` -> ``STATUS.{id}``). Ownership is re-checked on every
``reconcile``, so a malha created for an id that already had a twin takes the
loop over instead of leaving two producers on the same STATUS topic.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Protocol

from smart_pid_core.application.workers.monitor_worker import MonitorWorker

if TYPE_CHECKING:
    from smart_pid_core.application.event_bus import EventBus
    from smart_pid_core.application.loop_manager import LoopManager
    from smart_pid_core.application.workers.io_worker import IOWorker

logger = logging.getLogger(__name__)


class _TwinLoops(Protocol):
    """The slice of ``SimulatorAdapter`` this needs."""

    def controller_ids(self) -> list[int]: ...


#: STATUS cadence for an attached loop, matching ``Controller.scan_rate_s``'s
#: own default — the rate a malha's PID/Monitor worker publishes at, and the
#: rate the HMI is built around. The IO scan underneath still runs at the
#: simulator interval (10 Hz), so the ``/trend`` ring keeps its resolution;
#: publishing the pen tip 10x/s only multiplied realtime traffic per loop, and
#: three twin loops were enough to leave the browser draining a backlog.
DEFAULT_TWIN_SCAN_RATE_S: float = 1.0


class TwinTelemetry:
    """Keeps unowned simulator loops publishing TELEMETRY and STATUS."""

    def __init__(
        self,
        bus: EventBus,
        io_worker: IOWorker,
        loop_manager: LoopManager,
        simulator_adapter: _TwinLoops,
        scan_rate_s: float = DEFAULT_TWIN_SCAN_RATE_S,
    ) -> None:
        self._bus = bus
        self._io = io_worker
        self._loops = loop_manager
        self._twin = simulator_adapter
        self._scan_rate_s = scan_rate_s
        self._monitors: dict[int, MonitorWorker] = {}

    @property
    def attached_ids(self) -> frozenset[int]:
        return frozenset(self._monitors)

    def reconcile(self) -> None:
        """Attach every unowned twin loop, release the rest.

        Cheap enough (dict lookups over a handful of ids) to run on the
        daemon's existing 2 s simulator tick, which is what makes this
        self-healing: a malha created, deleted, or swapped by a project open
        changes ownership without any route having to remember to call here.
        """
        twin_ids = set(self._twin.controller_ids())
        for cid in twin_ids:
            if self._loops.is_loop_running(cid):
                self._detach(cid)
            else:
                self._attach(cid)
        for cid in self.attached_ids - twin_ids:
            self._detach(cid)

    def stop_all(self) -> None:
        for cid in list(self._monitors):
            self._detach(cid)

    def _attach(self, cid: int) -> None:
        if cid in self._monitors:
            return
        self._io.add_controller(cid)
        worker = MonitorWorker(bus=self._bus, controller_id=cid, scan_rate_s=self._scan_rate_s)
        worker.start()
        self._monitors[cid] = worker
        logger.info("twin_telemetry_attached controller_id=%d", cid)

    def _detach(self, cid: int) -> None:
        worker = self._monitors.pop(cid, None)
        if worker is None:
            return
        worker.stop()
        # The IO scan is only ours while no control loop needs it: when a malha
        # took the loop over, its own registration must survive this release.
        if not self._loops.is_loop_running(cid):
            self._io.remove_controller(cid)
        logger.info("twin_telemetry_detached controller_id=%d", cid)
