from __future__ import annotations

import pytest

from smart_pid_core.config import CoreSettings


class TestCoreSettings:
    def test_defaults(self) -> None:
        settings = CoreSettings(jwt_secret="test-secret")
        assert settings.api_port == 8000
        assert settings.api_host == "0.0.0.0"
        assert settings.zmq_internal_url == "inproc://bus"
        assert settings.zmq_publish_port == 5555
        assert settings.db_flush_interval_s == 5.0
        assert settings.db_retention_process_days == 7
        assert settings.db_retention_alarm_days == 30
        assert settings.simulator_enabled is False
        assert settings.log_level == "INFO"

    def test_opcua_retry_max_s_default(self) -> None:
        settings = CoreSettings(jwt_secret="test-secret")
        assert settings.opcua_retry_max_s == 30.0

    def test_opcua_retry_max_s_override(self) -> None:
        settings = CoreSettings(jwt_secret="test-secret", opcua_retry_max_s=15.0)
        assert settings.opcua_retry_max_s == 15.0

    def test_jwt_secret_required(self) -> None:
        import pytest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            CoreSettings()  # type: ignore[call-arg]


class TestExecutionMode:
    def test_default_monitor(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SPID_JWT_SECRET", "test-secret")
        s = CoreSettings()
        assert s.execution_mode == "monitor"

    def test_set_execute(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SPID_JWT_SECRET", "test-secret")
        monkeypatch.setenv("SPID_EXECUTION_MODE", "execute")
        s = CoreSettings()
        assert s.execution_mode == "execute"
