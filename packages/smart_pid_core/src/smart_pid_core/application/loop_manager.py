"""Loop Manager — lifecycle management for controller PID loops."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from smart_pid_core.application.workers.ai_worker import AIWorker
from smart_pid_core.application.workers.monitor_worker import MonitorWorker
from smart_pid_core.application.workers.pid_worker import PIDWorker
from smart_pid_core.application.workers.stats_worker import StatsWorker
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
    pid_worker: PIDWorker | None = None
    engine: PIDEngine | None = None
    mode_manager: ModeManager | None = None
    stats_worker: StatsWorker | None = None
    ai_worker: AIWorker | None = None
    monitor_worker: MonitorWorker | None = None


class LoopManager:
    """Manages the lifecycle of PID control loops."""

    def __init__(self, bus: EventBus, execution_mode: str = "execute") -> None:
        self._bus = bus
        self._execution_mode = execution_mode
        self._loops: dict[int, LoopContext] = {}

    def start_loop(self, controller: Controller) -> None:
        if controller.id in self._loops:
            return

        # Stats worker — always active
        stats_worker = StatsWorker(bus=self._bus, controller=controller)

        # AI worker — only if engine != NONE
        ai_worker = AIWorker(bus=self._bus, controller=controller)

        if self._execution_mode == "monitor":
            monitor_worker = MonitorWorker(
                bus=self._bus,
                controller_id=controller.id,
                scan_rate_ms=controller.scan_rate_ms,
            )
            ctx = LoopContext(
                controller=controller,
                monitor_worker=monitor_worker,
                stats_worker=stats_worker,
                ai_worker=ai_worker,
            )
            self._loops[controller.id] = ctx
            monitor_worker.start()
            stats_worker.start()
            ai_worker.start()
        else:
            engine = PIDEngine()
            mode_manager = ModeManager()
            pid_worker = PIDWorker(
                bus=self._bus, controller=controller,
                engine=engine, mode_manager=mode_manager,
            )
            ctx = LoopContext(
                controller=controller, pid_worker=pid_worker,
                engine=engine, mode_manager=mode_manager,
                stats_worker=stats_worker, ai_worker=ai_worker,
            )
            self._loops[controller.id] = ctx
            pid_worker.start()
            stats_worker.start()
            ai_worker.start()  # No-op if engine=NONE

    def stop_loop(self, controller_id: int) -> None:
        ctx = self._loops.pop(controller_id, None)
        if ctx is None:
            return
        if ctx.ai_worker:
            ctx.ai_worker.stop()
        if ctx.stats_worker:
            ctx.stats_worker.stop()
        if ctx.monitor_worker:
            ctx.monitor_worker.stop()
        if ctx.pid_worker:
            ctx.pid_worker.stop()

    def stop_all(self) -> None:
        for controller_id in list(self._loops.keys()):
            self.stop_loop(controller_id)

    def is_loop_running(self, controller_id: int) -> bool:
        ctx = self._loops.get(controller_id)
        if ctx is None:
            return False
        if ctx.pid_worker is not None:
            return ctx.pid_worker.is_alive()
        if ctx.monitor_worker is not None:
            return ctx.monitor_worker.is_alive()
        return False

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
        if self._execution_mode == "monitor":
            raise DomainError(
                "Cannot set setpoint in monitor mode — PID is controlled by external DCS"
            )
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
        if self._execution_mode == "monitor":
            raise DomainError(
                "Cannot set mode in monitor mode — PID is controlled by external DCS"
            )
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

    def get_stats_workers(self) -> dict[int, StatsWorker]:
        """Return dict of controller_id -> StatsWorker for REST API."""
        return {
            cid: ctx.stats_worker
            for cid, ctx in self._loops.items()
            if ctx.stats_worker is not None
        }

    def get_ai_workers(self) -> dict[int, AIWorker]:
        """Return dict of controller_id -> AIWorker for REST API."""
        return {
            cid: ctx.ai_worker
            for cid, ctx in self._loops.items()
            if ctx.ai_worker is not None and ctx.ai_worker.is_alive()
        }

    def set_output(self, controller_id: int, value: float) -> None:
        """Set CO value in MAN mode only. Validates against out_limits."""
        if self._execution_mode == "monitor":
            raise DomainError(
                "Cannot set output in monitor mode — PID is controlled by external DCS"
            )
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
