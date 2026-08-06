"""A level checked in the Settings page must take effect without a redeploy.

The first implementation configured structlog with
``make_filtering_bound_logger(boot_level)``, which bakes the boot-time level
into the bound logger's methods. Enabling DEBUG at runtime moved the root
logger and the handler filter but never that wrapper, so the daemon's OWN
events stayed silent until the next deploy. These tests exercise the whole
stack the way ``main()`` wires it and fail if that regression returns.
"""
from __future__ import annotations

import logging
from collections.abc import MutableMapping
from pathlib import Path
from typing import Any

import structlog

from smart_pid_core.application.log_control import LogLevelController, levels_at_or_above


def _configure_like_main(handlers: list[logging.Handler], boot_level: int) -> None:
    """Mirror `main()`'s logging setup exactly."""
    root = logging.getLogger()
    for existing in list(root.handlers):
        root.removeHandler(existing)
    for handler in handlers:
        root.addHandler(handler)
    root.setLevel(boot_level)
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.contextvars.merge_contextvars,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.dev.ConsoleRenderer(colors=False),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
    )


class _Boot:
    """A daemon booted at `boot_level`, with its sink and controller."""

    def __init__(self, tmp_path: Path, boot_level: int = logging.INFO) -> None:
        self.path = tmp_path / "smartpid.log"
        self.handler = logging.FileHandler(self.path, encoding="utf-8")
        _configure_like_main([self.handler], boot_level)
        self.controller = LogLevelController(
            [self.handler], levels_at_or_above(boot_level)
        )

    def emitted(self) -> str:
        self.handler.flush()
        return self.path.read_text(encoding="utf-8")

    def close(self) -> None:
        self.handler.close()
        logging.getLogger().removeHandler(self.handler)
        logging.getLogger("asyncua").setLevel(logging.NOTSET)
        logging.getLogger().setLevel(logging.WARNING)
        structlog.reset_defaults()


def test_checking_debug_reaches_the_daemons_own_events(tmp_path: Path) -> None:
    """The regression: booted at INFO, DEBUG checked at runtime, no redeploy."""
    boot = _Boot(tmp_path, logging.INFO)
    try:
        structlog.get_logger("daemon").debug("before_change")
        assert "before_change" not in boot.emitted(), "DEBUG leaked before it was enabled"

        boot.controller.set_levels(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
        structlog.get_logger("daemon").debug("after_change")

        assert "after_change" in boot.emitted(), (
            "structlog event still gated by the boot-time level - a redeploy "
            "would be needed, which is exactly what this control exists to avoid"
        )
    finally:
        boot.close()


def test_unchecking_info_silences_the_daemons_own_events(tmp_path: Path) -> None:
    """The operator's actual complaint: too many INFO records on the volume."""
    boot = _Boot(tmp_path, logging.INFO)
    try:
        structlog.get_logger("daemon").info("noisy_before")
        assert "noisy_before" in boot.emitted()

        boot.controller.set_levels(["WARNING", "ERROR", "CRITICAL"])
        structlog.get_logger("daemon").info("noisy_after")
        structlog.get_logger("daemon").warning("fault_after")

        emitted = boot.emitted()
        assert "noisy_after" not in emitted, "INFO still written after being unchecked"
        assert "fault_after" in emitted, "unchecking INFO must not hide faults"
    finally:
        boot.close()


def test_disabled_level_is_dropped_before_rendering(tmp_path: Path) -> None:
    """Unchecking a level must save the formatting work, not just the write.

    The operator disabled INFO because the daemon was loading the host, so a
    filter that renders every record and discards it at the handler would miss
    the point.
    """
    boot = _Boot(tmp_path, logging.INFO)
    rendered: list[str] = []

    def _spy(
        _logger: object, _name: str, event_dict: MutableMapping[str, Any]
    ) -> MutableMapping[str, Any]:
        rendered.append(str(event_dict.get("event")))
        return event_dict

    try:
        structlog.configure(
            processors=[
                structlog.stdlib.filter_by_level,
                _spy,
                structlog.dev.ConsoleRenderer(colors=False),
            ],
            wrapper_class=structlog.stdlib.BoundLogger,
            logger_factory=structlog.stdlib.LoggerFactory(),
        )
        boot.controller.set_levels(["WARNING", "ERROR", "CRITICAL"])
        structlog.get_logger("daemon").info("skipped_event")
        assert rendered == [], "disabled level still ran the processor chain"

        structlog.get_logger("daemon").warning("kept_event")
        assert rendered == ["kept_event"]
    finally:
        boot.close()


def test_noisy_logger_clamp_follows_the_selection(tmp_path: Path) -> None:
    """asyncua tracks the checkbox, not the boot environment."""
    boot = _Boot(tmp_path, logging.INFO)
    asyncua = logging.getLogger("asyncua")
    try:
        assert asyncua.level == logging.WARNING, "per-read spam not clamped at boot"

        boot.controller.set_levels(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
        assert asyncua.level == logging.NOTSET, "checking DEBUG must lift the clamp live"

        boot.controller.set_levels(["WARNING", "ERROR", "CRITICAL"])
        assert asyncua.level == logging.WARNING, "unchecking DEBUG must re-clamp live"
    finally:
        boot.close()


def test_stdlib_module_loggers_follow_the_selection_too(tmp_path: Path) -> None:
    """Workers use `logging.getLogger(__name__)`, not structlog."""
    boot = _Boot(tmp_path, logging.INFO)
    worker = logging.getLogger("smart_pid_core.application.workers.io_worker")
    try:
        boot.controller.set_levels(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
        worker.debug("worker_debug_after")
        assert "worker_debug_after" in boot.emitted()

        boot.controller.set_levels(["ERROR", "CRITICAL"])
        worker.info("worker_info_after")
        worker.error("worker_error_after")
        emitted = boot.emitted()
        assert "worker_info_after" not in emitted
        assert "worker_error_after" in emitted
    finally:
        boot.close()
