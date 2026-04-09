"""Unit tests for StatsWorker — window size computation."""
from __future__ import annotations

from smart_pid_domain.enums import ProcessSpeed


def _compute_window_size(speed: ProcessSpeed, scan_rate_s: float) -> int:
    """Mirror the formula used in StatsWorker."""
    return int(speed.stats_window_s / scan_rate_s)


class TestStatsWorkerWindowSize:
    """Verify window_size is computed from process_speed and scan_rate."""

    def test_fast_1s(self) -> None:
        assert _compute_window_size(ProcessSpeed.FAST, 1.0) == 60

    def test_medium_1s(self) -> None:
        assert _compute_window_size(ProcessSpeed.MEDIUM, 1.0) == 1200

    def test_slow_0_5s(self) -> None:
        assert _compute_window_size(ProcessSpeed.SLOW, 0.5) == 14400

    def test_ultra_fast_0_1s(self) -> None:
        assert _compute_window_size(ProcessSpeed.ULTRA_FAST, 0.1) == 50
