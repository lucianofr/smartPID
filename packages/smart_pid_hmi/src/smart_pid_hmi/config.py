"""HMI configuration via pydantic-settings.

Settings are loaded in this priority (highest wins):
  1. Environment variables           (SPID_HMI_SERVER_HOST, …)
  2. User-level config file          ($APPDATA\\SmartPID\\hmi.env on Windows,
                                      ~/.smart-pid/hmi.env elsewhere)
  3. Packaged config file            (hmi.env next to this module, created
                                      on first run with built-in defaults)
  4. Built-in defaults               (class attributes below)

The user-level file is where the Windows installer writes the operator's
answers ("backend host", etc.); on Linux/macOS it is a hand-editable file
that overrides the packaged defaults without requiring the user to modify
files inside the installed package.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

APP_DIR = Path.home() / ".smart-pid"
_PKG_DIR = Path(__file__).resolve().parent
PACKAGE_CONFIG_FILE = _PKG_DIR / "hmi.env"
CONFIG_FILE = PACKAGE_CONFIG_FILE  # kept for backward compatibility


def _user_config_dir() -> Path:
    """Resolve the per-user config directory for SmartPID.

    Windows: ``%APPDATA%\\SmartPID`` — matches the Windows installer layout.
    Other:   ``~/.smart-pid`` — matches ``APP_DIR`` used elsewhere.
    """
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA")
        if appdata:
            return Path(appdata) / "SmartPID"
    return Path.home() / ".smart-pid"


USER_CONFIG_FILE = _user_config_dir() / "hmi.env"

_DEFAULT_CONFIG_CONTENT = """\
# Smart PID HMI — connection settings
# Edit this file to change defaults.  Environment variables (SPID_HMI_*)
# override any value set here.

SPID_HMI_SERVER_HOST=localhost
SPID_HMI_SERVER_PORT=8000
SPID_HMI_ZMQ_URL=tcp://localhost:5555
SPID_HMI_THEME=isa101
SPID_HMI_MOCK_MODE=false
SPID_HMI_REFRESH_MS=33
"""


def ensure_config_file() -> Path:
    """Create the packaged default config file if it does not exist yet.

    Reads ``CONFIG_FILE`` from the module namespace at call time so tests can
    monkeypatch it to a temp path. In production ``CONFIG_FILE`` points at
    ``PACKAGE_CONFIG_FILE`` (the hmi.env shipped with the package).
    """
    # Re-resolve through the module so monkeypatched CONFIG_FILE is honoured.
    import sys as _sys

    target: Path = _sys.modules[__name__].CONFIG_FILE
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(_DEFAULT_CONFIG_CONTENT)
    return target


class HMISettings(BaseSettings):
    """Desktop HMI client settings.

    Loaded from env vars (``SPID_HMI_`` prefix), then the user-level
    ``hmi.env`` (if present), then the packaged ``hmi.env``.
    """

    model_config = SettingsConfigDict(
        env_prefix="SPID_HMI_",
        # Tuple: later files override earlier ones in pydantic-settings.
        env_file=(str(PACKAGE_CONFIG_FILE), str(USER_CONFIG_FILE)),
        env_file_encoding="utf-8",
    )

    server_host: str = "localhost"
    server_port: int = 8000
    zmq_url: str = "tcp://localhost:5555"
    theme: str = "isa101"
    mock_mode: bool = False
    refresh_ms: int = 33
    app_state_path: Path = APP_DIR / "app.json"

    @property
    def server_url(self) -> str:
        """Build the full server URL from host and port."""
        return f"http://{self.server_host}:{self.server_port}"
