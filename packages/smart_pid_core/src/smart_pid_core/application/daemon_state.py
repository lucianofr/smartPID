"""Daemon-level state persistence — durable app-level state for the daemon.

Currently covers the active project (restored across restarts) and the
operator's log-level selection (restored across restarts and applied
immediately at runtime by ``LogLevelController``).
"""
from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path


class DaemonState:
    """Persists daemon state to ``path`` (default ``~/.smart-pid/daemon_state.json``).

    Deployments MUST pass a path on durable storage: the default lands in a
    container's writable layer, where a redeploy silently discards it and the
    daemon boots having forgotten which project was open.
    """

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or (Path.home() / ".smart-pid" / "daemon_state.json")
        self._active_project: str | None = None
        self._log_levels: tuple[str, ...] | None = None
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            self._active_project = data.get("active_project")
            log_levels = data.get("log_levels")
            self._log_levels = tuple(log_levels) if log_levels is not None else None
        except (json.JSONDecodeError, OSError):
            pass

    @property
    def active_project(self) -> str | None:
        return self._active_project

    def set_active_project(self, name: str | None) -> None:
        self._active_project = name
        self._save()

    @property
    def log_levels(self) -> tuple[str, ...] | None:
        """The operator's chosen log levels, or ``None`` when never set —
        callers then fall back to the ``SPID_LOG_LEVEL`` threshold.
        """
        return self._log_levels

    def set_log_levels(self, names: Iterable[str] | None) -> None:
        self._log_levels = tuple(names) if names is not None else None
        self._save()

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "active_project": self._active_project,
            "log_levels": (
                list(self._log_levels) if self._log_levels is not None else None
            ),
        }
        self._path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8",
        )

