"""SVGOverlayWidget — display SVG diagrams with positioned text overlays."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class SVGOverlayWidget(QWidget):
    """Widget that renders an SVG and allows positioned text overlays on top."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._svg_widget: QSvgWidget | None = None
        self._overlays: dict[str, QLabel] = {}

        # Use a layout but overlays are positioned absolutely over the SVG
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)

    def load_svg(self, path: str) -> None:
        """Load an SVG file into the widget."""
        if self._svg_widget is not None:
            self._svg_widget.deleteLater()

        self._svg_widget = QSvgWidget(path, self)
        self._layout.addWidget(self._svg_widget)

    def add_overlay(self, tag: str, x: int, y: int, text: str) -> None:
        """Add a text overlay at position (x, y) over the SVG."""
        if tag in self._overlays:
            self.remove_overlay(tag)

        label = QLabel(text, self)
        label.setStyleSheet(
            "background-color: rgba(0, 0, 0, 180); color: white; "
            "padding: 2px 6px; border-radius: 3px; font-size: 11px;"
        )
        label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        label.move(x, y)
        label.adjustSize()
        label.show()
        label.raise_()
        self._overlays[tag] = label

    def update_overlay(self, tag: str, text: str) -> None:
        """Update the text of an existing overlay."""
        if tag in self._overlays:
            self._overlays[tag].setText(text)
            self._overlays[tag].adjustSize()

    def remove_overlay(self, tag: str) -> None:
        """Remove an overlay by tag."""
        if tag in self._overlays:
            self._overlays[tag].deleteLater()
            del self._overlays[tag]

    def clear_overlays(self) -> None:
        """Remove all overlays."""
        for label in self._overlays.values():
            label.deleteLater()
        self._overlays.clear()
