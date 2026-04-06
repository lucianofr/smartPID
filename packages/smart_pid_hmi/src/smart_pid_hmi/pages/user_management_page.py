"""UserManagementPage — admin-only page for user CRUD operations."""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from smart_pid_hmi.themes.base import ThemeBase

_COLUMNS = ["Username", "Role", "Active", "Created At", "Actions"]
_ROLES = ["OPERATOR", "SUPERVISOR", "ADMIN"]


class CreateUserDialog(QDialog):
    """Dialog for creating a new user."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Create User")
        self.setMinimumWidth(400)
        self.setMinimumHeight(220)

        layout = QFormLayout(self)

        self._username_edit = QLineEdit()
        self._username_edit.setPlaceholderText("Username")
        layout.addRow("Username:", self._username_edit)

        self._password_edit = QLineEdit()
        self._password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._password_edit.setPlaceholderText("Password")
        layout.addRow("Password:", self._password_edit)

        self._role_combo = QComboBox()
        self._role_combo.addItems(_ROLES)
        self._role_combo.setCurrentText("OPERATOR")
        layout.addRow("Role:", self._role_combo)

        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
        )
        for btn in self._buttons.buttons():
            btn.setIcon(QIcon())
        self._buttons.accepted.connect(self.accept)
        self._buttons.rejected.connect(self.reject)
        layout.addRow(self._buttons)

    def get_data(self) -> tuple[str, str, str] | None:
        """Return (username, password, role) or None if validation fails."""
        username = self._username_edit.text().strip()
        password = self._password_edit.text()
        if not username or not password:
            return None
        return (username, password, self._role_combo.currentText())


class EditUserDialog(QDialog):
    """Dialog for editing user role and optionally resetting password."""

    def __init__(
        self,
        current_role: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Edit User")
        self.setMinimumWidth(400)
        self.setMinimumHeight(200)

        layout = QFormLayout(self)

        self._role_combo = QComboBox()
        self._role_combo.addItems(_ROLES)
        self._role_combo.setCurrentText(current_role)
        layout.addRow("Role:", self._role_combo)

        self._password_edit = QLineEdit()
        self._password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._password_edit.setPlaceholderText("Leave empty to keep current")
        layout.addRow("New Password:", self._password_edit)

        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
        )
        for btn in self._buttons.buttons():
            btn.setIcon(QIcon())
        self._buttons.accepted.connect(self.accept)
        self._buttons.rejected.connect(self.reject)
        layout.addRow(self._buttons)

    def get_data(self) -> tuple[str, str | None]:
        """Return (role, password_or_None)."""
        password = self._password_edit.text()
        return (self._role_combo.currentText(), password if password else None)


class UserManagementPage(QWidget):
    """Admin page for managing users: list, create, edit, deactivate/reactivate."""

    user_create_requested = Signal(str, str, str)  # username, password, role
    user_update_requested = Signal(int, str, str, object)  # id, role, password, active
    user_deactivate_requested = Signal(int)  # user_id
    user_reactivate_requested = Signal(int)  # user_id
    refresh_requested = Signal()

    def __init__(self, theme: ThemeBase, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._theme = theme
        self._users: list[dict] = []

        layout = QVBoxLayout(self)

        # Header row
        header = QHBoxLayout()
        title = QLabel("User Management")
        title.setStyleSheet(
            f"font-size: {theme.font_size_title}px; font-weight: bold; "
            f"color: {theme.fg_primary};"
        )
        header.addWidget(title)
        header.addStretch()
        self._create_btn = QPushButton("+ New User")
        self._create_btn.clicked.connect(self._on_create_clicked)
        header.addWidget(self._create_btn)
        layout.addLayout(header)

        # User table
        self.user_table = QTableWidget(0, len(_COLUMNS))
        self.user_table.setHorizontalHeaderLabels(_COLUMNS)
        header_view = self.user_table.horizontalHeader()
        header_view.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        header_view.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.user_table.verticalHeader().setDefaultSectionSize(40)
        self.user_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.user_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.user_table)

        # Status bar
        self._status_label = QLabel("Ready")
        self._status_label.setStyleSheet(f"color: {theme.fg_secondary};")
        layout.addWidget(self._status_label)

    def set_status(self, msg: str) -> None:
        """Update the status label text."""
        self._status_label.setText(msg)

    def populate_users(self, users: list[dict]) -> None:
        """Fill the table from a list of user dicts."""
        self._users = users
        self.user_table.setRowCount(0)
        for user in users:
            row = self.user_table.rowCount()
            self.user_table.insertRow(row)

            self.user_table.setItem(row, 0, QTableWidgetItem(user.get("username", "")))
            self.user_table.setItem(row, 1, QTableWidgetItem(user.get("role", "")))

            active = user.get("active", True)
            active_item = QTableWidgetItem("Yes" if active else "No")
            active_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.user_table.setItem(row, 2, active_item)

            self.user_table.setItem(
                row, 3, QTableWidgetItem(user.get("created_at", ""))
            )

            # Action buttons in a widget
            actions = QWidget()
            actions_layout = QHBoxLayout(actions)
            actions_layout.setContentsMargins(2, 2, 2, 2)

            edit_btn = QPushButton("Edit")
            user_id = user.get("id", 0)
            edit_btn.clicked.connect(
                lambda checked, uid=user_id, r=row: self._on_edit_clicked(uid, r)
            )
            actions_layout.addWidget(edit_btn)

            if active:
                toggle_btn = QPushButton("Deactivate")
                toggle_btn.clicked.connect(
                    lambda checked, uid=user_id: self._on_deactivate_clicked(uid),
                )
            else:
                toggle_btn = QPushButton("Reactivate")
                toggle_btn.clicked.connect(
                    lambda checked, uid=user_id: self.user_reactivate_requested.emit(
                        uid
                    ),
                )
            actions_layout.addWidget(toggle_btn)

            self.user_table.setCellWidget(row, 4, actions)

    def _on_create_clicked(self) -> None:
        dialog = CreateUserDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            if data is not None:
                self.user_create_requested.emit(*data)

    def _on_edit_clicked(self, user_id: int, row: int) -> None:
        role_item = self.user_table.item(row, 1)
        current_role = role_item.text() if role_item else "OPERATOR"
        dialog = EditUserDialog(current_role=current_role, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            role, password = dialog.get_data()
            self.user_update_requested.emit(user_id, role, password or "", None)

    def _on_deactivate_clicked(self, user_id: int) -> None:
        reply = QMessageBox.question(
            self,
            "Confirm Deactivation",
            "Deactivate this user? They will no longer be able to log in.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.user_deactivate_requested.emit(user_id)

    def apply_theme(self, theme: ThemeBase) -> None:
        """Update theme references when the global theme changes."""
        self._theme = theme
