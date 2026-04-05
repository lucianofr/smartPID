"""Test MonitorWorker STATUS message includes mode field — Gap #53."""
from __future__ import annotations

from smart_pid_core.application.workers.monitor_worker import MonitorWorker


class TestMonitorWorkerEnrich:
    def test_enrich_includes_mode_field(self) -> None:
        """STATUS message should carry the mode from TELEMETRY."""
        telem = {
            "controller_id": 1,
            "pv": {"value": 50.0, "severity": "GOOD", "limit_bits": "NONE"},
            "sp": {"value": 50.0, "severity": "GOOD", "limit_bits": "NONE"},
            "co": {"value": 45.0, "severity": "GOOD", "limit_bits": "NONE"},
            "mode": "AUTO",
            "timestamp": 1234567890.0,
        }
        status_msg = MonitorWorker._enrich(telem)
        assert status_msg["mode"] == "AUTO"

    def test_enrich_defaults_mode_when_missing(self) -> None:
        """If TELEMETRY has no mode, STATUS should default to UNKNOWN."""
        telem = {
            "controller_id": 1,
            "pv": 50.0,
            "sp": 50.0,
            "co": {"value": 45.0},
            "timestamp": 1234567890.0,
        }
        status_msg = MonitorWorker._enrich(telem)
        assert status_msg["mode"] == "UNKNOWN"
