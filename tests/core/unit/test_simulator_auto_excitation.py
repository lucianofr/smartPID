"""Unit tests for SimulatorAdapter auto-excitation logic."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from smart_pid_core.adapters.inbound.simulator_adapter import SimulatorAdapter
from smart_pid_core.config import CoreSettings
from smart_pid_domain.dtos.simulator import AutoDisturbanceRequest, AutoSPRequest


@pytest.fixture
def settings() -> CoreSettings:
    return CoreSettings(
        jwt_secret="test-secret-key-minimum-32-bytes!",
        simulator_enabled=True,
        simulator_interval_ms=50,
    )  # type: ignore[call-arg]


def _mock_opcua_server() -> MagicMock:
    mock = MagicMock()
    mock.is_running = False
    mock.controller_node_ids = {}

    def _register(cid: int) -> dict[str, str]:
        node_ids = {"pv": f"ns=2;s=PV_{cid}", "sp": f"ns=2;s=SP_{cid}", "co": f"ns=2;s=CO_{cid}"}
        mock.controller_node_ids[cid] = node_ids
        return node_ids

    mock.start.side_effect = lambda: setattr(mock, "is_running", True)
    mock.stop.side_effect = lambda: setattr(mock, "is_running", False)
    mock.register_controller.side_effect = _register
    return mock


@pytest.fixture
def adapter(settings: CoreSettings) -> SimulatorAdapter:
    with patch(
        "smart_pid_core.adapters.inbound.simulator_adapter.OPCUAServer",
        return_value=_mock_opcua_server(),
    ):
        a = SimulatorAdapter(settings=settings)
        a.register_controller(1)
        yield a  # type: ignore[misc]
        a.stop()


class TestSetAutoSP:
    def test_set_auto_sp_updates_fields(self, adapter: SimulatorAdapter) -> None:
        req = AutoSPRequest(enabled=True, sp_min_pct=20.0, sp_max_pct=80.0)
        adapter.set_auto_sp(1, req)
        status = adapter.get_controller_status(1)
        assert status.auto_sp is not None
        assert status.auto_sp.enabled is True
        assert status.auto_sp.sp_min_pct == 20.0
        assert status.auto_sp.sp_max_pct == 80.0

    def test_disable_resets_elapsed(self, adapter: SimulatorAdapter) -> None:
        # enable first to accumulate some time
        adapter.set_auto_sp(1, AutoSPRequest(enabled=True))
        # manually set elapsed (access internal state)
        with adapter._lock:
            adapter._controllers[1].auto_sp_elapsed_s = 99.0
        # disable
        adapter.set_auto_sp(1, AutoSPRequest(enabled=False))
        with adapter._lock:
            assert adapter._controllers[1].auto_sp_elapsed_s == 0.0


class TestSetAutoDisturbance:
    def test_set_auto_dist_updates_fields(self, adapter: SimulatorAdapter) -> None:
        req = AutoDisturbanceRequest(enabled=True, max_amplitude_pct=15.0)
        adapter.set_auto_disturbance(1, req)
        status = adapter.get_controller_status(1)
        assert status.auto_disturbance is not None
        assert status.auto_disturbance.enabled is True
        assert status.auto_disturbance.max_amplitude_pct == 15.0

    def test_disable_resets_elapsed(self, adapter: SimulatorAdapter) -> None:
        adapter.set_auto_disturbance(1, AutoDisturbanceRequest(enabled=True))
        with adapter._lock:
            adapter._controllers[1].auto_dist_elapsed_s = 99.0
        adapter.set_auto_disturbance(1, AutoDisturbanceRequest(enabled=False))
        with adapter._lock:
            assert adapter._controllers[1].auto_dist_elapsed_s == 0.0


class TestAutoExcitationTick:
    def test_auto_sp_fires_after_period(self, adapter: SimulatorAdapter) -> None:
        adapter.set_auto_sp(1, AutoSPRequest(enabled=True, sp_min_pct=40.0, sp_max_pct=60.0))
        # get tau1 to know the period
        with adapter._lock:
            tau1 = adapter._controllers[1].tau1
        period = max(10.0 * tau1, 1.0)
        # run enough ticks to exceed the period
        dt = 0.1
        ticks = int(period / dt) + 2
        for _ in range(ticks):
            adapter._tick(dt)
        # what we can assert: elapsed was reset (i.e., back below period)
        with adapter._lock:
            assert adapter._controllers[1].auto_sp_elapsed_s < period

    def test_auto_dist_fires_after_period(self, adapter: SimulatorAdapter) -> None:
        adapter.set_auto_disturbance(
            1, AutoDisturbanceRequest(enabled=True, max_amplitude_pct=20.0)
        )
        with adapter._lock:
            tau1 = adapter._controllers[1].tau1
        period = max(10.0 * tau1, 1.0)
        dt = 0.1
        ticks = int(period / dt) + 2
        for _ in range(ticks):
            adapter._tick(dt)
        with adapter._lock:
            assert adapter._controllers[1].auto_dist_elapsed_s < period
            assert adapter._controllers[1].step_active is True

    def test_zero_span_skips_excitation(self, adapter: SimulatorAdapter) -> None:
        """If pv_min == pv_max, no excitation should happen."""
        with adapter._lock:
            adapter._controllers[1].pv_min = 50.0
            adapter._controllers[1].pv_max = 50.0
        adapter.set_auto_sp(1, AutoSPRequest(enabled=True))
        with adapter._lock:
            initial_sp = adapter._controllers[1].sp
            tau1 = adapter._controllers[1].tau1
        period = max(10.0 * tau1, 1.0)
        dt = 0.1
        ticks = int(period / dt) + 2
        for _ in range(ticks):
            adapter._tick(dt)
        with adapter._lock:
            assert adapter._controllers[1].sp == initial_sp

    def test_minimum_period_guard(self, adapter: SimulatorAdapter) -> None:
        """tau1=0 should not produce zero period (minimum 1.0s)."""
        with adapter._lock:
            adapter._controllers[1].tau1 = 0.0
        adapter.set_auto_sp(1, AutoSPRequest(enabled=True))
        # Should not raise and period should be clamped to 1.0
        dt = 0.1
        for _ in range(15):  # 1.5s — more than 1.0s period
            adapter._tick(dt)
        with adapter._lock:
            assert adapter._controllers[1].auto_sp_elapsed_s < 1.0 + dt
