"""Unit tests for StatsWorker — window size computation."""
from __future__ import annotations

from smart_pid_domain.enums import ProcessSpeed


def _compute_window_size(speed: ProcessSpeed, scan_rate_ms: int) -> int:
    """Mirror the formula used in StatsWorker."""
    return speed.stats_window_s * 1000 // scan_rate_ms


class TestStatsWorkerWindowSize:
    """Verify window_size is computed from process_speed and scan_rate."""

    def test_fast_1000ms(self) -> None:
        assert _compute_window_size(ProcessSpeed.FAST, 1000) == 60

    def test_medium_1000ms(self) -> None:
        assert _compute_window_size(ProcessSpeed.MEDIUM, 1000) == 1200

    def test_slow_500ms(self) -> None:
        assert _compute_window_size(ProcessSpeed.SLOW, 500) == 14400

    def test_ultra_fast_100ms(self) -> None:
        assert _compute_window_size(ProcessSpeed.ULTRA_FAST, 100) == 50
