"""Backend daemon settings loaded from environment / .env file."""
from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class CoreSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="SPID_")

    # OPC-UA
    opcua_endpoint: str = "opc.tcp://localhost:4840"
    opcua_timeout_s: int = 5
    opcua_retry_max_s: float = 30.0

    # ZeroMQ
    zmq_internal_url: str = "inproc://bus"
    zmq_publish_port: int = 5555

    # FastAPI
    api_port: int = 8000
    # Loopback by default: a control-plane daemon should not be reachable off-host
    # unless explicitly opted in via SPID_API_HOST=0.0.0.0.
    api_host: str = "127.0.0.1"

    # Network hardening (TD-004). Env vars accept a JSON array, e.g.
    # SPID_CORS_ALLOW_ORIGINS='["http://127.0.0.1:5173"]'.
    cors_allow_origins: list[str] = ["http://127.0.0.1:5173", "http://localhost:5173"]
    trusted_hosts: list[str] = ["127.0.0.1", "localhost"]

    # Web HMI (single-origin SPA served by the backend). When set and the path
    # exists, the built Vite bundle is mounted at "/" after all routers/WS.
    web_dist_dir: str | None = None
    # Origins accepted on the /ws/realtime handshake (Origin header allow-list).
    allowed_ws_origins: tuple[str, ...] = ("http://127.0.0.1:5173",)

    # JWT
    jwt_secret: str
    jwt_expiry_hours: int = 8

    # Database
    db_path: Path = Path("./project.spid")
    db_flush_interval_s: float = 5.0
    db_retention_process_days: int = 7
    db_retention_alarm_days: int = 30
    db_batch_size: int = 500

    # User database (app-level, separate from project)
    users_db_path: Path = Path.home() / ".smart-pid" / "users.db"

    # Project files directory (backend-managed)
    projects_dir: Path = Path.home() / ".smart-pid" / "projects"

    # Maximum size (bytes) accepted for a .spid project import upload.
    # Protects the single-process daemon from memory-exhaustion / disk-fill DoS.
    max_upload_bytes: int = 50 * 1024 * 1024  # 50 MB

    # Simulator
    simulator_enabled: bool = False
    simulator_port: int = 4849
    simulator_interval_ms: int = 100

    # Logging
    log_level: str = "INFO"

    # Execution
    execution_mode: str = "monitor"
