from __future__ import annotations
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

    def test_jwt_secret_required(self) -> None:
        import pytest
        with pytest.raises(Exception):
            CoreSettings()  # type: ignore[call-arg]
