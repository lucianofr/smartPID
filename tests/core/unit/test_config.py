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
        assert settings.api_host == "127.0.0.1"
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


class TestTrustedProxies:
    """A malformed entry must fail at boot, not silently match nothing."""

    @patch.dict(os.environ, {"SPID_JWT_SECRET": "test-secret"}, clear=True)
    def test_defaults_to_trusting_nobody(self) -> None:
        assert CoreSettings(_env_file=None).trusted_proxies == []

    @patch.dict(os.environ, {"SPID_JWT_SECRET": "test-secret"}, clear=True)
    def test_accepts_a_bare_address_and_a_cidr(self) -> None:
        s = CoreSettings(_env_file=None, trusted_proxies=["10.0.0.5", "172.16.0.0/12"])
        assert s.trusted_proxies == ["10.0.0.5", "172.16.0.0/12"]

    @patch.dict(os.environ, {"SPID_JWT_SECRET": "test-secret"}, clear=True)
    def test_rejects_a_typo(self) -> None:
        from pydantic import ValidationError

        # Accepting this would leave the daemon running while attributing every
        # session to the proxy's own address, with nothing to explain why.
        with pytest.raises(ValidationError):
            CoreSettings(_env_file=None, trusted_proxies=["traefik"])
