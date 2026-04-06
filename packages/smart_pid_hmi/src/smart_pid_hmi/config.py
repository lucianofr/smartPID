"""HMI configuration via pydantic-settings.

Settings are loaded in this priority (highest wins):
  1. Environment variables  (SPID_HMI_SERVER_HOST, …)
  2. Config file            (~/.config/smart-pid/hmi.env)
  3. Built-in defaults      (below)

On first run the config file is created automatically with the defaults
so the user can tweak server/port without touching env vars.
"""
from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

CONFIG_DIR = Path.home() / ".config" / "smart-pid"
CONFIG_FILE = CONFIG_DIR / "hmi.env"

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
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if not CONFIG_FILE.exists():
        CONFIG_FILE.write_text(_DEFAULT_CONFIG_CONTENT)
    return CONFIG_FILE


class HMISettings(BaseSettings):
    """Desktop HMI client settings.

    Loaded from env vars (SPID_HMI_ prefix) and ``~/.config/smart-pid/hmi.env``.
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
    app_state_path: Path = CONFIG_DIR / "app.json"

    @property
    def server_url(self) -> str:
        """Build the full server URL from host and port."""
        return f"http://{self.server_host}:{self.server_port}"
