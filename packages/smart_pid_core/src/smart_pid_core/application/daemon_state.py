"""Daemon-level state persistence — remembers active project across restarts."""
from __future__ import annotations

import json
from pathlib import Path


class DaemonState:
    """Persists daemon state to ~/.smart-pid/daemon_state.json."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or (Path.home() / ".smart-pid" / "daemon_state.json")
        self._active_project: str | None = None
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            self._active_project = data.get("active_project")
        except (json.JSONDecodeError, OSError):
            pass

    @property
    def active_project(self) -> str | None:
        return self._active_project

    def set_active_project(self, name: str | None) -> None:
        self._active_project = name
        self._save()

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        data = {"active_project": self._active_project}
        self._path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8",
        )
