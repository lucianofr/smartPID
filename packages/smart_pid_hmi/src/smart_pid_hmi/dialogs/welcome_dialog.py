"""WelcomeDialog — project selection shown after login."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class _NameInputDialog(QDialog):
    """Themed input dialog for project name."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("New Project")
        self.setModal(True)
        self.setMinimumWidth(320)
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint
        )

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        layout.addWidget(QLabel("Project name:"))
        self._input = QLineEdit()
        self._input.setObjectName("name_input")
        layout.addWidget(self._input)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        ok_btn = QPushButton("OK")
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(self.accept)
        btn_row.addWidget(ok_btn)
        layout.addLayout(btn_row)

    @property
    def text(self) -> str:
        return self._input.text()


class WelcomeDialog(QDialog):
    """Modal dialog for project selection — shown after login."""

    def __init__(
        self,
        projects: list[dict] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Smart PID Edge Optimizer")
        self.setModal(True)
        self.setMinimumSize(420, 400)
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint
        )

        self.result_action: str | None = None  # "new", "open", "import"
        self.result_name: str | None = None  # project name (new/open)
        self.result_path: str | None = None  # local file path (import only)

        self._projects = list(projects or [])

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Title
        title = QLabel("\u2699 Smart PID Edge Optimizer")
        title.setObjectName("welcome_title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setProperty("heading", True)
        layout.addWidget(title)

        subtitle = QLabel("Project Management")
        subtitle.setObjectName("welcome_subtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setProperty("muted", True)
        layout.addWidget(subtitle)

        # Buttons
        btn_layout = QVBoxLayout()
        btn_layout.setSpacing(8)

        new_btn = QPushButton("New Project")
        new_btn.setObjectName("welcome_new_btn")
        new_btn.setMinimumHeight(40)
        new_btn.clicked.connect(self._on_new)
        btn_layout.addWidget(new_btn)

        import_btn = QPushButton("Import from File (.spid)")
        import_btn.setObjectName("welcome_import_btn")
        import_btn.setMinimumHeight(40)
        import_btn.clicked.connect(self._on_import)
        btn_layout.addWidget(import_btn)

        layout.addLayout(btn_layout)

        # Available projects from backend
        available_label = QLabel("AVAILABLE PROJECTS")
        available_label.setObjectName("welcome_available_label")
        available_label.setProperty("muted", True)
        layout.addWidget(available_label)

        self._project_list = QListWidget()
        self._project_list.setObjectName("project_list")
        self._project_list.itemDoubleClicked.connect(self._on_project_selected)
        self._populate_list()
        layout.addWidget(self._project_list)

        # Delete button
        delete_row = QHBoxLayout()
        delete_row.addStretch()
        delete_btn = QPushButton("Delete Selected")
        delete_btn.setObjectName("welcome_delete_btn")
        delete_btn.clicked.connect(self._on_delete)
        delete_row.addWidget(delete_btn)
        layout.addLayout(delete_row)

    def _populate_list(self) -> None:
        self._project_list.clear()
        for proj in self._projects:
            count = proj.get("controller_count", 0)
            name = proj["name"]
            item = QListWidgetItem(f"{name}  ({count} loops)")
            item.setData(Qt.ItemDataRole.UserRole, name)
            self._project_list.addItem(item)

    def set_projects(self, projects: list[dict]) -> None:
        """Update the project list (e.g. after a delete)."""
        self._projects = list(projects)
        self._populate_list()

    def _on_new(self) -> None:
        dlg = _NameInputDialog(parent=self)
        if dlg.exec() != QDialog.DialogCode.Accepted or not dlg.text.strip():
            return
        self.result_action = "new"
        self.result_name = dlg.text.strip()
        self.accept()

    def _on_import(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Import Project", "", "Smart PID Project (*.spid)",
        )
        if not path:
            return
        self.result_action = "import"
        self.result_path = path
        # Use filename stem as default name
        from pathlib import Path as P
        self.result_name = P(path).stem
        self.accept()

    def _on_project_selected(self, item: QListWidgetItem) -> None:
        name = item.data(Qt.ItemDataRole.UserRole)
        if name:
            self.result_action = "open"
            self.result_name = name
            self.accept()

    def _on_delete(self) -> None:
        item = self._project_list.currentItem()
        if item is None:
            return
        name = item.data(Qt.ItemDataRole.UserRole)
        if name:
            self.result_action = "delete"
            self.result_name = name
            # Don't accept — caller handles delete and refreshes list
