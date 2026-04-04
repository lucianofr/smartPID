"""ThemeManager — register, switch, and notify on theme changes."""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Signal

if TYPE_CHECKING:
    from smart_pid_hmi.themes.base import ThemeBase


class ThemeManager(QObject):
    """Manages registered themes and emits signals on theme switch."""

    theme_changed = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._themes: dict[str, ThemeBase] = {}
        self._current: ThemeBase | None = None

    def register(self, theme: ThemeBase) -> None:
        """Register a theme instance. Uses theme.name as key."""
        self._themes[theme.name] = theme

    def set_theme(self, name: str) -> None:
        """Switch to a registered theme by name.

        Raises KeyError if not registered.
        Does not emit theme_changed if already on that theme.
        """
        if name not in self._themes:
            raise KeyError(name)
        if self._current is not None and self._current.name == name:
            return
        self._current = self._themes[name]
        self.theme_changed.emit(name)

    @property
    def current(self) -> ThemeBase:
        """Return the current active theme. Raises RuntimeError if none set."""
        if self._current is None:
            raise RuntimeError("No theme set")
        return self._current

    def available_themes(self) -> list[str]:
        """Return sorted list of registered theme names."""
        return sorted(self._themes.keys())

    def get(self, name: str) -> ThemeBase:
        """Get a specific theme by name. Raises KeyError if not found."""
        return self._themes[name]
