"""Tests for HMI configuration."""
from smart_pid_hmi.config import HMISettings


def test_default_settings():
    settings = HMISettings()
    assert settings.server_url == "http://localhost:8000"
    assert settings.zmq_url == "tcp://localhost:5555"
    assert settings.theme == "isa101"
    assert settings.mock_mode is False
    assert settings.refresh_ms == 33


def test_override_via_env(monkeypatch):
    monkeypatch.setenv("SPID_HMI_SERVER_URL", "http://10.0.0.1:9000")
    monkeypatch.setenv("SPID_HMI_MOCK_MODE", "true")
    settings = HMISettings()
    assert settings.server_url == "http://10.0.0.1:9000"
    assert settings.mock_mode is True
