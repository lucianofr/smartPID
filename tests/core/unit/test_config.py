from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from smart_pid_core.config import CoreSettings


class TestCoreSettings:
    @patch.dict(os.environ, {"SPID_JWT_SECRET": "test-secret-key-minimum-32-bytes!"}, clear=True)
    def test_defaults(self) -> None:
        settings = CoreSettings(_env_file=None)
        assert settings.api_port == 8000
        assert settings.api_host == "0.0.0.0"
        assert settings.zmq_internal_url == "inproc://bus"
        assert settings.zmq_publish_port == 5555
        assert settings.db_flush_interval_s == 5.0
        assert settings.db_retention_process_days == 7
        assert settings.db_retention_alarm_days == 30
        assert settings.simulator_enabled is False
        assert settings.log_level == "INFO"

    @patch.dict(os.environ, {"SPID_JWT_SECRET": "test-secret-key-minimum-32-bytes!"}, clear=True)
    def test_opcua_retry_max_s_default(self) -> None:
        settings = CoreSettings(_env_file=None)
        assert settings.opcua_retry_max_s == 30.0

    @patch.dict(os.environ, {"SPID_JWT_SECRET": "test-secret-key-minimum-32-bytes!"}, clear=True)
    def test_opcua_retry_max_s_override(self) -> None:
        settings = CoreSettings(
            _env_file=None,
            opcua_retry_max_s=15.0,
        )
        assert settings.opcua_retry_max_s == 15.0

    @patch.dict(os.environ, {}, clear=True)
    def test_jwt_secret_required(self) -> None:
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            CoreSettings(_env_file=None)  # type: ignore[call-arg]


class TestExecutionMode:
    @patch.dict(os.environ, {"SPID_JWT_SECRET": "test-secret"}, clear=True)
    def test_default_monitor(self) -> None:
        s = CoreSettings(_env_file=None)
        assert s.execution_mode == "monitor"

    @patch.dict(
        os.environ,
        {"SPID_JWT_SECRET": "test-secret", "SPID_EXECUTION_MODE": "execute"},
        clear=True,
    )
    def test_set_execute(self) -> None:
        s = CoreSettings(_env_file=None)
        assert s.execution_mode == "execute"
