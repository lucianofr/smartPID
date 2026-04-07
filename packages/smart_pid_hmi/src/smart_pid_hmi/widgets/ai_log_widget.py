"""AI Log Widget — displays AI tuning decisions on the dashboard."""
from __future__ import annotations

from collections import deque
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QScrollArea, QVBoxLayout, QWidget

if TYPE_CHECKING:
    from smart_pid_hmi.themes.base import ThemeBase

_MAX_ENTRIES = 200


class AILogWidget(QWidget):
    """Scrollable log box showing AI tuning decisions (Fuzzy/RL)."""

    def __init__(self, theme: ThemeBase, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._theme = theme
        self._entries: deque[str] = deque(maxlen=_MAX_ENTRIES)
        self._controller_id: int | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        self._header = QLabel("AI TUNING LOG")
        self._header.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self._header.setFixedHeight(28)
        layout.addWidget(self._header)

        # Scroll area with log content
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff,
        )
        self._scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        self._log_label = QLabel("")
        self._log_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
        )
        self._log_label.setWordWrap(True)
        self._log_label.setTextFormat(Qt.TextFormat.PlainText)
        self._scroll.setWidget(self._log_label)
        layout.addWidget(self._scroll)

        self._apply_style()

    def _apply_style(self) -> None:
        t = self._theme
        font = getattr(t, "font_family", "monospace")
        fs = getattr(t, "font_size_normal", 12)
        self._header.setStyleSheet(
            f"background: #111111; color: #CCCCCC;"
            f" font-family: '{font}'; font-size: {fs}px;"
            " font-weight: bold; padding: 2px 6px;"
            f" border-bottom: 1px solid #333333;"
        )
        self._scroll.setStyleSheet("background: #000000;")
        self._log_label.setStyleSheet(
            f"background: #000000; color: #FFFFFF;"
            f" font-family: '{font}'; font-size: {fs}px;"
            " padding: 4px 6px;"
        )

    def on_controller_selected(self, controller_id: int) -> None:
        """Switch to show logs for a different controller."""
        self._controller_id = controller_id
        self._entries.clear()
        self._log_label.setText("")

    def on_ai_action(self, controller_id: int, action: dict) -> None:
        """Display an AI tuning decision from ACTION.AI.* events."""
        if controller_id != self._controller_id:
            return
        engine = action.get("engine", "?")
        gamma = action.get("gamma", 0.0)
        new_ki = action.get("new_ki", 0.0)
        reasoning = action.get("reasoning", "")
        ts = action.get("timestamp", "")[:19]
        self._append(f"[{ts}] {engine} \u03b3={gamma:+.4f} Ki={new_ki:.4f} \u2014 {reasoning}")

    def _append(self, text: str) -> None:
        self._entries.append(text)
        self._log_label.setText("\n".join(self._entries))
        # Auto-scroll to bottom
        vbar = self._scroll.verticalScrollBar()
        if vbar:
            vbar.setValue(vbar.maximum())

    def apply_theme(self, theme: ThemeBase) -> None:
        """Re-apply theme."""
        self._theme = theme
        self._apply_style()
