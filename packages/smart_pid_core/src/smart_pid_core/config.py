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
    # OpenAPI schema and docs UI (/docs, /redoc, /openapi.json) are disabled by
    # default: unauthenticated recon surface with no reason to be public on a
    # production deployment. Opt in for local dev / TestSprite MCP workflows.
    expose_openapi: bool = False

    # Network hardening (TD-004). Env vars accept a JSON array, e.g.
    # SPID_CORS_ALLOW_ORIGINS='["http://127.0.0.1:5173"]'.
    cors_allow_origins: list[str] = ["http://127.0.0.1:5173", "http://localhost:5173"]
    trusted_hosts: list[str] = ["127.0.0.1", "localhost"]

    # Web HMI (single-origin SPA served by the backend). When set and the path
    # exists, the built Vite bundle is mounted at "/" after all routers/WS.
    web_dist_dir: str | None = None
    # Origins accepted on the /ws/realtime handshake (Origin header allow-list).
    allowed_ws_origins: tuple[str, ...] = ("http://127.0.0.1:5173", "http://localhost:5173")

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
    #
    # This is an abuse ceiling, NOT a memory guard. The upload is streamed into
    # a staging file one chunk at a time and never materialised in RAM, so the
    # resident cost of an import is one chunk whatever the archive weighs. The
    # default therefore only has to clear what GET /project/download can emit:
    # a plant with a few months of Log_Processo history is comfortably past the
    # old 50 MB value, which made the documented download -> import round-trip
    # impossible for every project with real history (E2E-040).
    max_upload_bytes: int = 2 * 1024 * 1024 * 1024  # 2 GiB

    # Free space (bytes) that must remain on the projects filesystem for an
    # import to be accepted. This, not max_upload_bytes, is the disk-fill
    # guard: a per-request cap never bounded total usage, since N sequential
    # uploads of (cap - 1) bytes fill any volume. This refuses the upload with
    # 507 as soon as the volume gets tight, however many requests it took.
    min_free_disk_bytes: int = 1 * 1024 * 1024 * 1024  # 1 GiB

    # Simulator
    simulator_enabled: bool = False
    simulator_port: int = 4849
    simulator_interval_ms: int = 100

    # Logging
    log_level: str = "INFO"

    # Execution
    execution_mode: str = "monitor"

    # Optimizer steady-state guardrail. Daemon-wide default, in percent of SP:
    # while |PV - SP| stays inside it the optimizer skips the loop instead of
    # moving Ki/Ti. A loop with its own Controller.stability_band_pct wins.
    stability_band_pct: float = 2.0
