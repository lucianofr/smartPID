"""CheckableComboBox — QComboBox with checkboxes for multi-select filtering."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import QComboBox, QStyledItemDelegate, QWidget


class _CheckDelegate(QStyledItemDelegate):
    """Delegate that prevents the combo from closing on click."""

    def editorEvent(self, event, model, option, index):  # noqa: N802, ANN001, ANN201
        # Let default handling toggle the check state
        return super().editorEvent(event, model, option, index)


class CheckableComboBox(QComboBox):
    """ComboBox where each item has a checkbox for multi-selection.

    Emits ``selection_changed`` whenever the checked set changes.
    The display text shows a comma-joined summary of checked items,
    or "All" when everything (or nothing) is checked.
    """

    selection_changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._model = QStandardItemModel(self)
        self.setModel(self._model)
        self.setItemDelegate(_CheckDelegate(self))
        self._model.dataChanged.connect(self._on_data_changed)
        self._updating = False

    # --- Public API ---

    def add_items(self, items: list[str], *, check_all: bool = True) -> None:
        """Populate the combo with *items*. If *check_all*, all start checked."""
        self._updating = True
        self._model.clear()
        for text in items:
            item = QStandardItem(text)
            item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            item.setData(
                Qt.CheckState.Checked if check_all else Qt.CheckState.Unchecked,
                Qt.ItemDataRole.CheckStateRole,
            )
            self._model.appendRow(item)
        self._updating = False
        self._refresh_text()

    def checked_items(self) -> list[str]:
        """Return list of currently checked item texts."""
        result: list[str] = []
        for row in range(self._model.rowCount()):
            item = self._model.item(row)
            if item and item.checkState() == Qt.CheckState.Checked:
                result.append(item.text())
        return result

    def all_checked(self) -> bool:
        """True if every item is checked (equivalent to no filter)."""
        for row in range(self._model.rowCount()):
            item = self._model.item(row)
            if item and item.checkState() != Qt.CheckState.Checked:
                return False
        return True

    # --- Internals ---

    def _on_data_changed(self) -> None:
        if self._updating:
            return
        self._refresh_text()
        self.selection_changed.emit()

    def _refresh_text(self) -> None:
        checked = self.checked_items()
        total = self._model.rowCount()
        if len(checked) == total or len(checked) == 0:
            text = "All"
        elif len(checked) <= 3:
            text = ", ".join(checked)
        else:
            text = f"{len(checked)} selected"
        self.setCurrentText(text)
        # Override display via lineEdit for editable, or repaint for read-only
        self.setToolTip(", ".join(checked) if checked else "All")
        # Force repaint of the combo display
        self.setEditable(True)
        le = self.lineEdit()
        if le:
            le.setText(text)
            le.setReadOnly(True)
            le.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def hidePopup(self) -> None:  # noqa: N802
        """Keep popup open while clicking checkboxes — close on outside click."""
        # Only close if mouse is outside the popup view
        super().hidePopup()
