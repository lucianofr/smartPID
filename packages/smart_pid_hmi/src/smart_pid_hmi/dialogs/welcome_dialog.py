"""WelcomeDialog — shown on first run or when last project is unavailable."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class WelcomeDialog(QDialog):
    """Modal dialog for project selection on startup."""

    def __init__(
        self,
        recent_projects: list[dict] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Smart PID Edge Optimizer")
        self.setModal(True)
        self.setMinimumSize(420, 400)
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint
        )

        self.result_action: str | None = None
        self.result_path: str | None = None
        self.result_name: str | None = None

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Title
        title = QLabel("\u2699 Smart PID Edge Optimizer")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        layout.addWidget(title)

        subtitle = QLabel("Project Management")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("font-size: 13px; color: #888;")
        layout.addWidget(subtitle)

        # Buttons
        btn_layout = QVBoxLayout()
        btn_layout.setSpacing(8)

        new_btn = QPushButton("New Project")
        new_btn.setObjectName("welcome_new_btn")
        new_btn.setMinimumHeight(40)
        new_btn.clicked.connect(self._on_new)
        btn_layout.addWidget(new_btn)

        open_btn = QPushButton("Open Project")
        open_btn.setObjectName("welcome_open_btn")
        open_btn.setMinimumHeight(40)
        open_btn.clicked.connect(self._on_open)
        btn_layout.addWidget(open_btn)

        layout.addLayout(btn_layout)

        # Recent projects
        recent_label = QLabel("RECENT PROJECTS")
        recent_label.setStyleSheet(
            "font-size: 11px; color: #888; letter-spacing: 1px;"
        )
        layout.addWidget(recent_label)

        self._recent_list = QListWidget()
        self._recent_list.setObjectName("recent_list")
        self._recent_list.itemDoubleClicked.connect(self._on_recent_selected)
        recent = recent_projects or []
        for proj in recent:
            item = QListWidgetItem(
                f"{proj['name']}  ({proj.get('controller_count', 0)} loops)\n"
                f"{proj['path']}"
            )
            item.setData(Qt.ItemDataRole.UserRole, proj["path"])
            self._recent_list.addItem(item)
        layout.addWidget(self._recent_list)

    def _on_new(self) -> None:
        name, ok = QInputDialog.getText(self, "New Project", "Project name:")
        if not ok or not name.strip():
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save New Project", "", "Smart PID Project (*.spid)",
        )
        if not path:
            return
        if not path.endswith(".spid"):
            path += ".spid"
        self.result_action = "new"
        self.result_name = name.strip()
        self.result_path = path
        self.accept()

    def _on_open(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Project", "", "Smart PID Project (*.spid)",
        )
        if not path:
            return
        self.result_action = "open"
        self.result_path = path
        self.accept()

    def _on_recent_selected(self, item: QListWidgetItem) -> None:
        path = item.data(Qt.ItemDataRole.UserRole)
        if path:
            self.result_action = "open"
            self.result_path = path
            self.accept()
