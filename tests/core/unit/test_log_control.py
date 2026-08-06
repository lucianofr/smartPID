"""Tests for LogLevelController — runtime, set-based log level selection."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from smart_pid_core.application.daemon_state import DaemonState
from smart_pid_core.application.log_control import (
    LOG_LEVEL_NAMES,
    LevelSetFilter,
    LogLevelController,
    levels_at_or_above,
)

if TYPE_CHECKING:
    from collections.abc import Iterator


def _record(level: int, message: str) -> logging.LogRecord:
    return logging.LogRecord("test", level, __file__, 1, message, None, None)


def _file_handler(tmp_path: Path) -> tuple[logging.FileHandler, Path]:
    path = tmp_path / "smartpid.log"
    return logging.FileHandler(path, encoding="utf-8"), path


def _emit_all_levels(handler: logging.Handler) -> None:
    for name in LOG_LEVEL_NAMES:
        handler.handle(_record(getattr(logging, name), f"line-{name}"))
    handler.flush()


@pytest.fixture(autouse=True)
def _restore_root_logger_state() -> Iterator[None]:
    """Undo the global logging state a controller mutates.

    A controller adopts the root handlers so no sink can ignore the
    selection — including pytest's own ``caplog`` handler. Left attached, a
    stale filter silences records in unrelated tests later in the session.
    """
    root = logging.getLogger()
    original = root.level
    yield
    root.setLevel(original)
    for handler in root.handlers:
        for leaked in [f for f in handler.filters if isinstance(f, LevelSetFilter)]:
            handler.removeFilter(leaked)
    logging.getLogger("asyncua").setLevel(logging.NOTSET)


def test_skips_a_middle_level(tmp_path: Path) -> None:
    """WARNING+CRITICAL selected, ERROR skipped: only WARNING and CRITICAL land."""
    handler, path = _file_handler(tmp_path)
    try:
        LogLevelController([handler], ["WARNING", "CRITICAL"])
        _emit_all_levels(handler)
    finally:
        handler.close()

    assert path.read_text(encoding="utf-8").splitlines() == ["line-WARNING", "line-CRITICAL"]


def test_unchecking_info_keeps_error(tmp_path: Path) -> None:
    """The operator's actual complaint: turn INFO off, keep WARNING/ERROR."""
    handler, path = _file_handler(tmp_path)
    try:
        controller = LogLevelController([handler], LOG_LEVEL_NAMES)
        controller.set_levels(["WARNING", "ERROR", "CRITICAL"])
        _emit_all_levels(handler)
    finally:
        handler.close()

    lines = path.read_text(encoding="utf-8").splitlines()
    assert "line-INFO" not in lines
    assert "line-ERROR" in lines
    assert "line-WARNING" in lines
    assert "line-CRITICAL" in lines


def test_empty_selection_emits_nothing(tmp_path: Path) -> None:
    handler, path = _file_handler(tmp_path)
    try:
        LogLevelController([handler], [])
        _emit_all_levels(handler)
    finally:
        handler.close()

    assert path.read_text(encoding="utf-8") == ""


def test_unknown_level_name_raises_and_keeps_previous_selection(tmp_path: Path) -> None:
    handler, _ = _file_handler(tmp_path)
    try:
        controller = LogLevelController([handler], ["INFO", "ERROR"])
        with pytest.raises(ValueError, match="NOTALEVEL"):
            controller.set_levels(["INFO", "NOTALEVEL"])
        assert controller.levels == ("INFO", "ERROR")
    finally:
        handler.close()


def test_set_levels_normalizes_case_order_and_duplicates(tmp_path: Path) -> None:
    handler, _ = _file_handler(tmp_path)
    try:
        controller = LogLevelController([handler], ["INFO"])
        result = controller.set_levels(["error", "warning", "ERROR", "Warning"])
        assert result == ("WARNING", "ERROR")
        assert controller.levels == ("WARNING", "ERROR")
    finally:
        handler.close()


def test_custom_level_number_follows_its_info_bucket(tmp_path: Path) -> None:
    """Level 25 (between INFO=20 and WARNING=30) rides on the INFO checkbox."""
    handler, path = _file_handler(tmp_path)
    custom_level = 25
    try:
        controller = LogLevelController([handler], ["INFO"])
        handler.handle(_record(custom_level, "custom-enabled"))
        controller.set_levels(["WARNING", "ERROR", "CRITICAL"])
        handler.handle(_record(custom_level, "custom-disabled"))
        handler.flush()
    finally:
        handler.close()

    text = path.read_text(encoding="utf-8")
    assert "custom-enabled" in text
    assert "custom-disabled" not in text


def test_on_change_receives_normalized_tuple(tmp_path: Path) -> None:
    handler, _ = _file_handler(tmp_path)
    received: list[tuple[str, ...]] = []
    try:
        controller = LogLevelController([handler], ["INFO"], on_change=received.append)
        controller.set_levels(["error", "debug"])
    finally:
        handler.close()

    assert received == [("DEBUG", "ERROR")]


def test_levels_at_or_above_info_excludes_debug() -> None:
    assert levels_at_or_above(logging.INFO) == ("INFO", "WARNING", "ERROR", "CRITICAL")


def test_daemon_state_round_trips_log_levels(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    state = DaemonState(path)
    state.set_log_levels(["WARNING", "ERROR"])
    assert state.log_levels == ("WARNING", "ERROR")

    reloaded = DaemonState(path)
    assert reloaded.log_levels == ("WARNING", "ERROR")


def test_daemon_state_file_missing_log_levels_key_loads_as_none(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    path.write_text('{"active_project": "foo"}', encoding="utf-8")
    state = DaemonState(path)
    assert state.log_levels is None
