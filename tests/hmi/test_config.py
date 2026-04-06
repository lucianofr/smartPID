"""Tests for HMI configuration."""
from smart_pid_hmi.config import HMISettings, ensure_config_file


def test_default_settings():
    settings = HMISettings()
    assert settings.server_host == "localhost"
    assert settings.server_port == 8000
    assert settings.server_url == "http://localhost:8000"
    assert settings.zmq_url == "tcp://localhost:5555"
    assert settings.theme == "isa101"
    assert settings.mock_mode is False
    assert settings.refresh_ms == 33


def test_override_via_env(monkeypatch):
    monkeypatch.setenv("SPID_HMI_SERVER_HOST", "10.0.0.1")
    monkeypatch.setenv("SPID_HMI_SERVER_PORT", "9000")
    monkeypatch.setenv("SPID_HMI_MOCK_MODE", "true")
    settings = HMISettings()
    assert settings.server_url == "http://10.0.0.1:9000"
    assert settings.mock_mode is True


def test_server_url_property():
    settings = HMISettings(server_host="192.168.1.50", server_port=3000)
    assert settings.server_url == "http://192.168.1.50:3000"


def test_ensure_config_file_creates_file(tmp_path, monkeypatch):
    """ensure_config_file creates the hmi.env when it doesn't exist."""
    import smart_pid_hmi.config as cfg

    fake_dir = tmp_path / "smart-pid"
    fake_file = fake_dir / "hmi.env"
    monkeypatch.setattr(cfg, "APP_DIR", fake_dir)
    monkeypatch.setattr(cfg, "CONFIG_FILE", fake_file)

    result = ensure_config_file()
    assert result == fake_file
    assert fake_file.exists()
    content = fake_file.read_text()
    assert "SPID_HMI_SERVER_HOST" in content
    assert "SPID_HMI_SERVER_PORT" in content


def test_ensure_config_file_does_not_overwrite(tmp_path, monkeypatch):
    """ensure_config_file preserves existing file."""
    import smart_pid_hmi.config as cfg

    fake_dir = tmp_path / "smart-pid"
    fake_dir.mkdir()
    fake_file = fake_dir / "hmi.env"
    fake_file.write_text("SPID_HMI_SERVER_HOST=myserver\n")
    monkeypatch.setattr(cfg, "APP_DIR", fake_dir)
    monkeypatch.setattr(cfg, "CONFIG_FILE", fake_file)

    ensure_config_file()
    assert fake_file.read_text() == "SPID_HMI_SERVER_HOST=myserver\n"
