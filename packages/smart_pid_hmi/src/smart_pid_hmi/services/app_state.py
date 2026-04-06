"""App-level state persistence — last project name, theme preference."""
from __future__ import annotations

import json
from pathlib import Path


class AppStateManager:
    """Manages ~/.config/smart-pid/app.json for cross-session state."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or (Path.home() / ".config" / "smart-pid" / "app.json")
        self._last_project_name: str | None = None
        self._last_theme: str | None = None
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            self._last_project_name = data.get("last_project_name")
            self._last_theme = data.get("last_theme")
        except (json.JSONDecodeError, OSError):
            pass

    @property
    def last_project_name(self) -> str | None:
        return self._last_project_name

    @property
    def last_theme(self) -> str | None:
        return self._last_theme

    def set_last_project_name(self, name: str) -> None:
        self._last_project_name = name

    def set_last_theme(self, name: str) -> None:
        self._last_theme = name

    def save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "last_project_name": self._last_project_name,
            "last_theme": self._last_theme,
        }
        self._path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8",
        )
