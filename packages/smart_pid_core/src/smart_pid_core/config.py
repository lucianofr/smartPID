"""Backend daemon settings loaded from environment / .env file."""
from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class CoreSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="SPID_")

    # OPC-UA
    opcua_endpoint: str = "opc.tcp://localhost:4840"
    opcua_timeout_s: int = 5

    # ZeroMQ
    zmq_internal_url: str = "inproc://bus"
    zmq_publish_port: int = 5555

    # FastAPI
    api_port: int = 8000
    api_host: str = "0.0.0.0"

    # JWT
    jwt_secret: str
    jwt_expiry_hours: int = 8

    # Database
    db_path: Path = Path("./project.spid")
    db_flush_interval_s: float = 5.0
    db_retention_process_days: int = 7
    db_retention_alarm_days: int = 30
    db_batch_size: int = 500

    # Simulator
    simulator_enabled: bool = False
    simulator_port: int = 4841
    simulator_interval_ms: int = 100

    # Logging
    log_level: str = "INFO"
