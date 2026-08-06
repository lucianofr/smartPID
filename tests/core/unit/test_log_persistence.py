"""Log handlers — the file sink that survives a container redeploy.

Container stdout is discarded with the container, so SPID_LOG_DIR is the only
thing keeping log history across a deploy. These guard that contract.
"""
from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path
from unittest.mock import patch

from smart_pid_core.application.log_control import clamp_noisy_loggers
from smart_pid_core.config import CoreSettings
from smart_pid_core.main import LOG_BACKUP_COUNT, LOG_MAX_BYTES, build_log_handlers

_SECRET = {"SPID_JWT_SECRET": "test-secret-key-minimum-32-bytes!"}


def _settings(**overrides: object) -> CoreSettings:
    with patch.dict(os.environ, _SECRET, clear=True):
        return CoreSettings(_env_file=None, **overrides)  # type: ignore[arg-type]


def _emit(handler: logging.Handler, message: str) -> None:
    handler.emit(
        logging.LogRecord("test", logging.INFO, __file__, 1, message, None, None)
    )
    handler.flush()


def test_no_log_dir_means_stdout_only() -> None:
    handlers = build_log_handlers(_settings())
    assert len(handlers) == 1
    assert not any(isinstance(h, RotatingFileHandler) for h in handlers)


def test_log_dir_adds_rotating_file_beside_stdout(tmp_path: Path) -> None:
    handlers = build_log_handlers(_settings(log_dir=tmp_path / "logs"))

    # stdout must survive: Dokploy's log view reads it.
    assert any(
        type(h) is logging.StreamHandler for h in handlers
    ), "stdout handler dropped"

    files = [h for h in handlers if isinstance(h, RotatingFileHandler)]
    assert len(files) == 1
    assert files[0].baseFilename == str(tmp_path / "logs" / "smartpid.log")


def test_records_reach_the_file(tmp_path: Path) -> None:
    handler = next(
        h
        for h in build_log_handlers(_settings(log_dir=tmp_path / "logs"))
        if isinstance(h, RotatingFileHandler)
    )
    try:
        _emit(handler, "redeploy-survives-this")
    finally:
        handler.close()

    assert "redeploy-survives-this" in (tmp_path / "logs" / "smartpid.log").read_text()


def test_missing_log_dir_is_created(tmp_path: Path) -> None:
    target = tmp_path / "data" / "logs"
    assert not target.exists()
    _ = build_log_handlers(_settings(log_dir=target))
    assert target.is_dir(), "handler must not depend on the volume being pre-seeded"


def test_file_sink_is_capped(tmp_path: Path) -> None:
    """Logs share the data volume with the DB; unbounded growth fills it."""
    handler = next(
        h
        for h in build_log_handlers(_settings(log_dir=tmp_path / "logs"))
        if isinstance(h, RotatingFileHandler)
    )
    try:
        assert handler.maxBytes == LOG_MAX_BYTES > 0
        assert handler.backupCount == LOG_BACKUP_COUNT > 0
    finally:
        handler.close()


def test_asyncua_spam_is_clamped_at_info() -> None:
    """asyncua logs a record per OPC-UA read — 98% of the volume on a plant."""
    lg = logging.getLogger("asyncua")
    original = lg.level
    try:
        lg.setLevel(logging.NOTSET)
        clamp_noisy_loggers(("INFO", "WARNING", "ERROR", "CRITICAL"))
        assert lg.level == logging.WARNING
        assert not lg.isEnabledFor(logging.INFO), "per-read spam still enabled"
    finally:
        lg.setLevel(original)


def test_asyncua_failures_still_logged() -> None:
    lg = logging.getLogger("asyncua")
    original = lg.level
    try:
        lg.setLevel(logging.NOTSET)
        clamp_noisy_loggers(("INFO", "WARNING", "ERROR", "CRITICAL"))
        assert lg.isEnabledFor(logging.WARNING), "clamp must not hide failures"
        assert lg.isEnabledFor(logging.ERROR)
    finally:
        lg.setLevel(original)


def test_debug_keeps_protocol_tracing() -> None:
    lg = logging.getLogger("asyncua")
    original = lg.level
    try:
        lg.setLevel(logging.WARNING)
        clamp_noisy_loggers(("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"))
        assert lg.level == logging.NOTSET, "checking DEBUG must lift the clamp live"
    finally:
        lg.setLevel(original)
