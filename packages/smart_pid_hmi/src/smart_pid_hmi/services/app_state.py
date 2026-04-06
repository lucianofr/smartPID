"""App-level state persistence — recent projects, last project, etc."""
from __future__ import annotations

import json
from pathlib import Path

_MAX_RECENT = 5


class AppStateManager:
    """Manages ~/.config/smart-pid/app.json for cross-session state."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or (Path.home() / ".config" / "smart-pid" / "app.json")
        self._last_project: str | None = None
        self._recent: list[dict] = []
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            self._last_project = data.get("last_project")
            self._recent = data.get("recent_projects", [])
        except (json.JSONDecodeError, OSError):
            pass

    @property
    def last_project(self) -> str | None:
        return self._last_project

    @property
    def recent_projects(self) -> list[dict]:
        return list(self._recent)

    def set_last_project(self, path: str, name: str, controller_count: int) -> None:
        self._last_project = path
        self._recent = [r for r in self._recent if r.get("path") != path]
        self._recent.insert(0, {"name": name, "path": path, "controller_count": controller_count})
        self._recent = self._recent[:_MAX_RECENT]

    def prune(self) -> None:
        self._recent = [r for r in self._recent if Path(r["path"]).exists()]
        if self._last_project and not Path(self._last_project).exists():
            self._last_project = None

    def save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        data = {"last_project": self._last_project, "recent_projects": self._recent}
        self._path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
