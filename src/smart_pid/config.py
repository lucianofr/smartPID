"""Application settings via pydantic-settings."""
from __future__ import annotations

from enum import StrEnum
from pathlib import Path  # noqa: TCH003 — pydantic needs at runtime

from pydantic_settings import BaseSettings, SettingsConfigDict


class LogLevel(StrEnum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="SPID_",
    )

    # Application
    app_name: str = "Smart PID Edge Optimizer"
    app_version: str = "0.1.0"
    log_level: LogLevel = LogLevel.INFO

    # OPC-UA
    opcua_endpoint: str = "opc.tcp://localhost:4840"
    opcua_timeout_ms: int = 5000
    opcua_reconnect_interval_s: float = 5.0

    # Database
    db_retention_process_days: int = 7
    db_retention_alarm_days: int = 30
    db_flush_interval_s: float = 5.0
    db_batch_size: int = 500

    # Simulator
    simulator_port: int = 4841
    simulator_enabled: bool = False

    # UI
    theme: str = "dark"
    chart_fps: int = 30
    chart_max_points: int = 50000

    # Paths
    last_project_path: Path | None = None


settings = Settings()
