"""Tests for HMI configuration loading."""
from __future__ import annotations

import importlib
import sys
import sysconfig
from pathlib import Path

import pytest

# Warm up sysconfig / zoneinfo on the real platform before any test patches
# ``sys.platform`` to "win32".  Otherwise lazy init inside these modules
# would try to import ``_sysconfigdata__win32_x86_64-linux-gnu`` and fail.
sysconfig.get_config_vars()
import zoneinfo  # noqa: E402,F401  (ensures TZPATH cache is populated)


def _reload_config(monkeypatch: pytest.MonkeyPatch, home: Path, appdata: Path | None):
    """Reload the config module with patched home/APPDATA for isolation."""
    monkeypatch.setenv("HOME", str(home))
    if appdata is not None:
        monkeypatch.setenv("APPDATA", str(appdata))
    else:
        monkeypatch.delenv("APPDATA", raising=False)
    # Path.home() on POSIX does not honour $HOME reliably (pwd-based lookup);
    # patch it directly so the module picks up the isolated tmp path.
    monkeypatch.setattr(Path, "home", lambda: home)
    # Drop any leaking SPID_HMI_* env vars that would override file-based values.
    for key in list(__import__("os").environ):
        if key.startswith("SPID_HMI_"):
            monkeypatch.delenv(key, raising=False)
    # Force a reimport so module-level path constants pick up the new env
    sys.modules.pop("smart_pid_hmi.config", None)
    cfg = importlib.import_module("smart_pid_hmi.config")
    # Redirect the packaged config to an isolated tmp location so tests never
    # read the real developer copy bundled with the installed package.
    pkg_dir = home / "_pkg"
    pkg_dir.mkdir(exist_ok=True)
    isolated_pkg = pkg_dir / "hmi.env"
    monkeypatch.setattr(cfg, "PACKAGE_CONFIG_FILE", isolated_pkg, raising=True)
    monkeypatch.setattr(cfg, "CONFIG_FILE", isolated_pkg, raising=True)
    # Rebuild the HMISettings model_config to point at the isolated tuple.
    cfg.HMISettings.model_config["env_file"] = (
        str(isolated_pkg),
        str(cfg.USER_CONFIG_FILE),
    )
    return cfg


def test_user_config_dir_on_windows(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "platform", "win32")
    appdata = tmp_path / "AppData" / "Roaming"
    appdata.mkdir(parents=True)
    cfg = _reload_config(monkeypatch, tmp_path, appdata)
    assert cfg.USER_CONFIG_FILE == appdata / "SmartPID" / "hmi.env"  # noqa: SIM300


def test_user_config_dir_on_linux(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "platform", "linux")
    cfg = _reload_config(monkeypatch, tmp_path, appdata=None)
    assert cfg.USER_CONFIG_FILE == tmp_path / ".smart-pid" / "hmi.env"  # noqa: SIM300


def test_user_config_overrides_packaged(monkeypatch, tmp_path):
    """User-level hmi.env must override the packaged defaults."""
    monkeypatch.setattr(sys, "platform", "linux")
    user_dir = tmp_path / ".smart-pid"
    user_dir.mkdir()
    (user_dir / "hmi.env").write_text(
        "SPID_HMI_SERVER_HOST=remote-backend\n"
        "SPID_HMI_SERVER_PORT=9000\n"
        "SPID_HMI_ZMQ_URL=tcp://remote-backend:5555\n"
    )
    cfg = _reload_config(monkeypatch, tmp_path, appdata=None)
    cfg.ensure_config_file()  # creates the packaged defaults
    settings = cfg.HMISettings()
    assert settings.server_host == "remote-backend"
    assert settings.server_port == 9000
    assert settings.zmq_url == "tcp://remote-backend:5555"


def test_packaged_defaults_used_when_no_user_config(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "platform", "linux")
    cfg = _reload_config(monkeypatch, tmp_path, appdata=None)
    cfg.ensure_config_file()
    settings = cfg.HMISettings()
    assert settings.server_host == "localhost"
    assert settings.server_port == 8000
