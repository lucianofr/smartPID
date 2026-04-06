"""HMI configuration via pydantic-settings."""
from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings


class HMISettings(BaseSettings):
    """Desktop HMI client settings, loaded from env vars with SPID_HMI_ prefix."""

    model_config = {"env_prefix": "SPID_HMI_"}

    server_url: str = "http://localhost:8000"
    zmq_url: str = "tcp://localhost:5555"
    theme: str = "isa101"
    mock_mode: bool = False
    refresh_ms: int = 33
    app_state_path: Path = Path.home() / ".config" / "smart-pid" / "app.json"
