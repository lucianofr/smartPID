"""Verify PIDWorker no longer accepts or uses AlarmEngine."""
import inspect

from smart_pid_core.application.workers.pid_worker import PIDWorker


def test_pid_worker_no_alarm_engine_param():
    """PIDWorker.__init__ must not accept alarm_engine parameter."""
    sig = inspect.signature(PIDWorker.__init__)
    assert "alarm_engine" not in sig.parameters


def test_loop_manager_no_alarm_engine_param():
    """LoopManager.__init__ must not accept alarm_engine parameter."""
    from smart_pid_core.application.loop_manager import LoopManager
    sig = inspect.signature(LoopManager.__init__)
    assert "alarm_engine" not in sig.parameters
