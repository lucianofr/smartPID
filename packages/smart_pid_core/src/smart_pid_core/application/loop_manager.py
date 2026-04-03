"""Loop Manager — lifecycle management for controller PID loops."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from smart_pid_core.application.workers.pid_worker import PIDWorker
from smart_pid_core.domain.services.pid_engine import PIDEngine
from smart_pid_core.domain.services.pid_mode_manager import ModeManager

if TYPE_CHECKING:
    from smart_pid_core.application.event_bus import EventBus
    from smart_pid_domain.models.controller import Controller


@dataclass
class LoopContext:
    """Holds references to all active components for one control loop."""
    controller: Controller
    pid_worker: PIDWorker
    engine: PIDEngine = field(default_factory=PIDEngine)
    mode_manager: ModeManager = field(default_factory=ModeManager)


class LoopManager:
    """Manages the lifecycle of PID control loops."""

    def __init__(self, bus: EventBus) -> None:
        self._bus = bus
        self._loops: dict[int, LoopContext] = {}

    def start_loop(self, controller: Controller) -> None:
        if controller.id in self._loops:
            return
        engine = PIDEngine()
        mode_manager = ModeManager()
        pid_worker = PIDWorker(
            bus=self._bus, controller=controller, engine=engine, mode_manager=mode_manager
        )
        ctx = LoopContext(
            controller=controller, pid_worker=pid_worker, engine=engine, mode_manager=mode_manager
        )
        self._loops[controller.id] = ctx
        pid_worker.start()

    def stop_loop(self, controller_id: int) -> None:
        ctx = self._loops.pop(controller_id, None)
        if ctx is None:
            return
        ctx.pid_worker.stop()

    def stop_all(self) -> None:
        for controller_id in list(self._loops.keys()):
            self.stop_loop(controller_id)

    def is_loop_running(self, controller_id: int) -> bool:
        ctx = self._loops.get(controller_id)
        return ctx is not None and ctx.pid_worker.is_alive()

    def get_context(self, controller_id: int) -> LoopContext | None:
        return self._loops.get(controller_id)
