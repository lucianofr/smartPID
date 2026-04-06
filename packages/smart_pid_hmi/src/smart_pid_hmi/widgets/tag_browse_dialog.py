"""OPC-UA Tag Browser dialog — tree view for selecting NodeIDs."""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget


class TagBrowseDialog(QDialog):
    """Modal dialog for browsing OPC-UA address space and selecting a NodeID.

    Works in two modes:
    - **Online**: calls ``browse_fn(node_id) -> list[dict]`` to browse a live
      OPC-UA server (each dict has keys: node_id, display_name, node_class).
    - **Offline**: shows an empty tree with a message to connect to the server.

    Usage::

        dlg = TagBrowseDialog(browse_fn=api_client.browse_opcua, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            selected_node_id = dlg.selected_node_id
    """

    def __init__(
        self,
        browse_fn: callable | None = None,
        search_fn: callable | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("OPC-UA Tag Browser")
        self.setMinimumSize(500, 400)
        self._browse_fn = browse_fn
        self._search_fn = search_fn
        self._selected_node_id: str = ""

        layout = QVBoxLayout(self)

        # Search bar
        search_row = QHBoxLayout()
        search_row.setSpacing(6)
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Search tags...")
        self._search_input.returnPressed.connect(self._on_search)
        search_row.addWidget(self._search_input)
        self._search_btn = QPushButton("Search")
        self._search_btn.clicked.connect(self._on_search)
        search_row.addWidget(self._search_btn)
        layout.addLayout(search_row)

        # Tree view
        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(["Name", "Node ID", "Class"])
        self._tree.header().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch,
        )
        self._tree.header().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents,
        )
        self._tree.header().setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents,
        )
        self._tree.itemExpanded.connect(self._on_item_expanded)
        self._tree.itemDoubleClicked.connect(self._on_item_double_clicked)
        layout.addWidget(self._tree)

        # Selected node display
        sel_row = QHBoxLayout()
        sel_row.addWidget(QLabel("Selected:"))
        self._selected_label = QLineEdit()
        self._selected_label.setReadOnly(True)
        self._selected_label.setPlaceholderText("Double-click a node to select")
        sel_row.addWidget(self._selected_label)
        layout.addLayout(sel_row)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        # Load root nodes
        self._load_root()

    @property
    def selected_node_id(self) -> str:
        return self._selected_node_id

    def _load_root(self) -> None:
        """Browse root nodes (Objects folder)."""
        if self._browse_fn is None:
            item = QTreeWidgetItem(["Connect to server to browse tags"])
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self._tree.addTopLevelItem(item)
            return
        self._browse_node("i=85", None)  # Objects folder

    def _browse_node(
        self, node_id: str, parent_item: QTreeWidgetItem | None,
    ) -> None:
        """Browse children of a node and add to tree."""
        if self._browse_fn is None:
            return
        try:
            children = self._browse_fn(node_id)
        except Exception:
            return

        for child in children:
            nid = child.get("node_id", "")
            name = child.get("display_name", nid)
            nclass = child.get("node_class", "")
            item = QTreeWidgetItem([name, nid, nclass])
            item.setData(0, Qt.ItemDataRole.UserRole, nid)
            # Add dummy child to make expandable (lazy loading)
            if nclass in ("Object", "Folder", ""):
                dummy = QTreeWidgetItem(["Loading..."])
                item.addChild(dummy)
            if parent_item is None:
                self._tree.addTopLevelItem(item)
            else:
                parent_item.addChild(item)

    def _on_item_expanded(self, item: QTreeWidgetItem) -> None:
        """Lazy load: replace dummy child with real children on expand."""
        if item.childCount() == 1 and item.child(0).text(0) == "Loading...":
            item.removeChild(item.child(0))
            node_id = item.data(0, Qt.ItemDataRole.UserRole)
            if node_id:
                self._browse_node(node_id, item)

    def _on_item_double_clicked(self, item: QTreeWidgetItem, _col: int) -> None:
        """Select node on double click."""
        node_id = item.data(0, Qt.ItemDataRole.UserRole)
        if node_id:
            self._selected_node_id = node_id
            self._selected_label.setText(node_id)

    def _on_search(self) -> None:
        """Search for tags matching query."""
        query = self._search_input.text().strip()
        if not query or self._search_fn is None:
            return
        try:
            results = self._search_fn(query)
        except Exception:
            return
        self._tree.clear()
        for r in results:
            nid = r.get("node_id", "")
            name = r.get("display_name", nid)
            nclass = r.get("node_class", "")
            item = QTreeWidgetItem([name, nid, nclass])
            item.setData(0, Qt.ItemDataRole.UserRole, nid)
            self._tree.addTopLevelItem(item)

    def accept(self) -> None:
        # If nothing selected via double-click, try current item
        if not self._selected_node_id:
            current = self._tree.currentItem()
            if current:
                nid = current.data(0, Qt.ItemDataRole.UserRole)
                if nid:
                    self._selected_node_id = nid
        super().accept()
