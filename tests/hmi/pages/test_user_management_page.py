"""Tests for UserManagementPage."""
from __future__ import annotations

from PySide6.QtWidgets import QApplication

from smart_pid_hmi.pages.user_management_page import (
    CreateUserDialog,
    EditUserDialog,
    UserManagementPage,
)
from smart_pid_hmi.themes.isa101 import ISA101Theme

app = QApplication.instance() or QApplication([])


def test_page_creation():
    theme = ISA101Theme()
    page = UserManagementPage(theme=theme)
    assert page is not None
    assert page.user_table.columnCount() == 5


def test_populate_users():
    theme = ISA101Theme()
    page = UserManagementPage(theme=theme)
    users = [
        {
            "id": 1,
            "username": "admin",
            "role": "ADMIN",
            "active": True,
            "created_at": "2026-01-01",
        },
        {
            "id": 2,
            "username": "op1",
            "role": "OPERATOR",
            "active": False,
            "created_at": "2026-01-02",
        },
    ]
    page.populate_users(users)
    assert page.user_table.rowCount() == 2


def test_create_dialog_fields():
    dialog = CreateUserDialog()
    assert dialog._username_edit.text() == ""
    assert dialog._password_edit.text() == ""
    assert dialog._role_combo.currentText() == "OPERATOR"


def test_create_dialog_validation():
    dialog = CreateUserDialog()
    # Empty fields — get_data returns None
    assert dialog.get_data() is None


def test_create_dialog_valid_data():
    dialog = CreateUserDialog()
    dialog._username_edit.setText("newuser")
    dialog._password_edit.setText("secret")
    dialog._role_combo.setCurrentText("SUPERVISOR")
    data = dialog.get_data()
    assert data == ("newuser", "secret", "SUPERVISOR")


def test_edit_dialog_prepopulated():
    dialog = EditUserDialog(current_role="SUPERVISOR")
    assert dialog._role_combo.currentText() == "SUPERVISOR"
    assert dialog._password_edit.text() == ""


def test_edit_dialog_returns_data():
    dialog = EditUserDialog(current_role="OPERATOR")
    dialog._role_combo.setCurrentText("ADMIN")
    dialog._password_edit.setText("newpass")
    data = dialog.get_data()
    assert data == ("ADMIN", "newpass")


def test_edit_dialog_empty_password_returns_none():
    dialog = EditUserDialog(current_role="OPERATOR")
    dialog._role_combo.setCurrentText("SUPERVISOR")
    data = dialog.get_data()
    assert data == ("SUPERVISOR", None)
