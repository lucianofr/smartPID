"""ConnectionPage — login and server URL entry."""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from smart_pid_hmi.themes.base import ThemeBase


class ConnectionPage(QWidget):
    """Initial screen for login and server URL configuration."""

    login_requested = Signal(str, str, str)  # (server_url, username, password)

    def __init__(
        self,
        theme: ThemeBase,
        default_url: str = "http://localhost:8000",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._theme = theme

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(12)

        # Title
        title = QLabel("Smart PID \u2014 Connect")
        title.setStyleSheet(
            f"font-size: {theme.font_size_title + 4}px; font-weight: bold; "
            f"color: {theme.fg_primary}; background: transparent;"
        )
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Server URL
        url_label = QLabel("Server URL")
        url_label.setStyleSheet(f"color: {theme.fg_secondary}; background: transparent;")
        layout.addWidget(url_label)
        self._url_input = QLineEdit(default_url)
        self._url_input.setFixedWidth(300)
        layout.addWidget(self._url_input)

        # Username
        user_label = QLabel("Username")
        user_label.setStyleSheet(f"color: {theme.fg_secondary}; background: transparent;")
        layout.addWidget(user_label)
        self._user_input = QLineEdit()
        self._user_input.setFixedWidth(300)
        self._user_input.setPlaceholderText("username")
        layout.addWidget(self._user_input)

        # Password
        pass_label = QLabel("Password")
        pass_label.setStyleSheet(f"color: {theme.fg_secondary}; background: transparent;")
        layout.addWidget(pass_label)
        self._pass_input = QLineEdit()
        self._pass_input.setFixedWidth(300)
        self._pass_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._pass_input.setPlaceholderText("password")
        layout.addWidget(self._pass_input)

        # Connect button
        self._connect_btn = QPushButton("Connect")
        self._connect_btn.setFixedWidth(300)
        self._connect_btn.clicked.connect(self._on_connect)
        layout.addWidget(self._connect_btn)

        # Status / error label
        self._status_label = QLabel("")
        self._status_label.setStyleSheet(
            f"color: {theme.alarm_critical}; background: transparent;"
        )
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_label.setVisible(False)
        layout.addWidget(self._status_label)

    def _on_connect(self) -> None:
        self.clear_error()
        self.login_requested.emit(
            self._url_input.text(),
            self._user_input.text(),
            self._pass_input.text(),
        )

    def show_error(self, message: str) -> None:
        self._status_label.setText(message)
        self._status_label.setVisible(True)

    def clear_error(self) -> None:
        self._status_label.setText("")
        self._status_label.setVisible(False)
