"""HMI configuration via pydantic-settings.

Settings are loaded in this priority (highest wins):
  1. Environment variables  (SPID_HMI_SERVER_HOST, …)
  2. Config file            (hmi.env next to this module)
  3. Built-in defaults      (below)

On first run the config file is created automatically with the defaults
so the user can tweak server/port without touching env vars.

The config file lives alongside the application code so it works
identically on Linux, macOS and Windows without relying on a
platform-specific home directory.
"""
from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

APP_DIR = Path.home() / ".smart-pid"
_PKG_DIR = Path(__file__).resolve().parent
CONFIG_FILE = _PKG_DIR / "hmi.env"

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
    """Create the default config file if it does not exist yet."""
    if not CONFIG_FILE.exists():
        CONFIG_FILE.write_text(_DEFAULT_CONFIG_CONTENT)
    return CONFIG_FILE


class HMISettings(BaseSettings):
    """Desktop HMI client settings.

    Loaded from env vars (SPID_HMI_ prefix) and ``~/.smart-pid/hmi.env``.
    """

    model_config = SettingsConfigDict(
        env_prefix="SPID_HMI_",
        env_file=str(CONFIG_FILE),
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
