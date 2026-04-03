"""Loop Manager — lifecycle management for controller PID loops."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from smart_pid_core.application.workers.pid_worker import PIDWorker
from smart_pid_core.domain.services.pid_engine import PIDEngine
from smart_pid_core.domain.services.pid_mode_manager import ModeManager
from smart_pid_domain.enums import ControllerMode
from smart_pid_domain.exceptions import ControllerNotFoundError, DomainError

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

    def get_controller(self, controller_id: int) -> Controller:
        """Return controller config. Raises ControllerNotFoundError if not found."""
        ctx = self._loops.get(controller_id)
        if ctx is None:
            raise ControllerNotFoundError(controller_id)
        return ctx.controller

    def set_setpoint(self, controller_id: int, value: float) -> None:
        """Set SP value. Validates against sp_limits."""
        ctx = self._loops.get(controller_id)
        if ctx is None:
            raise ControllerNotFoundError(controller_id)
        c = ctx.controller
        if value > c.sp_hi_lim:
            raise DomainError(f"SP {value} above high limit {c.sp_hi_lim}")
        if value < c.sp_lo_lim:
            raise DomainError(f"SP {value} below low limit {c.sp_lo_lim}")
        ctx.pid_worker.set_sp(value)

    def set_mode(self, controller_id: int, mode: ControllerMode) -> None:
        """Request mode transition. Raises DomainError if rejected."""
        ctx = self._loops.get(controller_id)
        if ctx is None:
            raise ControllerNotFoundError(controller_id)
        from smart_pid_core.domain.services.pid_mode_manager import BlockStatus

        transition = ctx.mode_manager.request_mode(
            current=ctx.pid_worker.current_mode,
            target=mode,
            permitted=ctx.controller.permitted_modes,
            block_status=BlockStatus(),
        )
        if not transition.accepted:
            raise DomainError(transition.rejection_reason)
        ctx.pid_worker.set_mode(mode)

    def set_output(self, controller_id: int, value: float) -> None:
        """Set CO value in MAN mode only. Validates against out_limits."""
        ctx = self._loops.get(controller_id)
        if ctx is None:
            raise ControllerNotFoundError(controller_id)
        if ctx.pid_worker.current_mode != ControllerMode.MAN:
            raise DomainError("Output can only be set in MAN mode")
        c = ctx.controller
        if value > c.out_hi_lim:
            raise DomainError(f"Output {value} above high limit {c.out_hi_lim}")
        if value < c.out_lo_lim:
            raise DomainError(f"Output {value} below low limit {c.out_lo_lim}")
        ctx.pid_worker.set_output(value)
