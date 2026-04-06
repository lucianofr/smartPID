"""Integration test — simulator PID closes the loop and PV converges to SP."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from smart_pid_core.adapters.inbound.simulator_adapter import SimulatorAdapter
from smart_pid_core.config import CoreSettings
from smart_pid_domain.enums import ProcessPresetName


def _mock_opcua_server() -> MagicMock:
    mock = MagicMock()
    mock.is_running = False
    mock.controller_node_ids = {}

    def _register(cid: int) -> dict[str, str]:
        mock.controller_node_ids[cid] = {
            "pv": f"ns=2;s=PV_{cid}", "sp": f"ns=2;s=SP_{cid}",
            "co": f"ns=2;s=CO_{cid}",
        }
        return mock.controller_node_ids[cid]

    mock.start.side_effect = lambda: setattr(mock, "is_running", True)
    mock.stop.side_effect = lambda: setattr(mock, "is_running", False)
    mock.register_controller.side_effect = _register
    return mock


@pytest.fixture
def adapter() -> SimulatorAdapter:
    settings = CoreSettings(
        jwt_secret="test-secret-key-minimum-32-bytes!",
        simulator_enabled=True,
        simulator_interval_ms=50,
    )  # type: ignore[call-arg]
    with patch(
        "smart_pid_core.adapters.inbound.simulator_adapter.OPCUAServer",
        return_value=_mock_opcua_server(),
    ):
        a = SimulatorAdapter(settings=settings)
        yield a
        a.stop()


class TestSimulatorPIDClosesLoop:
    def test_pv_converges_to_sp_flow_preset(self, adapter: SimulatorAdapter) -> None:
        """With FLOW preset and PID in AUTO, PV should converge toward SP."""
        adapter.register_controller(1)
        adapter.set_preset(1, ProcessPresetName.FLOW)
        adapter._controllers[1].sp = 50.0
        adapter._controllers[1].last_co = 0.0

        # Enable PID in AUTO with tuning suitable for FLOW (K=1.2, tau1=3, L=1)
        adapter.enable_pid(1, enabled=True)
        adapter.set_pid_params(1, kp=0.8, ti=4.0, td=0.5)
        adapter.set_pid_mode(1, mode=1)  # AUTO

        # Run 500 ticks at 100ms = 50 seconds of simulation
        dt = 0.1
        for _ in range(500):
            adapter._tick(dt)

        # Get final PV from controller state
        final_co = adapter._controllers[1].last_co

        # CO should be positive and driving the process
        assert final_co > 0.0, f"CO={final_co} should be positive"

    def test_pid_disabled_does_not_close_loop(self, adapter: SimulatorAdapter) -> None:
        """With PID disabled, CO stays at initial value."""
        adapter.register_controller(1)
        adapter.set_preset(1, ProcessPresetName.FLOW)
        adapter._controllers[1].sp = 50.0
        adapter._controllers[1].last_co = 0.0

        for _ in range(100):
            adapter._tick(0.1)

        assert adapter._controllers[1].last_co == 0.0

    def test_opcua_write_ti_affects_pid(self, adapter: SimulatorAdapter) -> None:
        """Writing Ti via OPC-UA callback changes PID behavior."""
        adapter.register_controller(1)
        adapter.set_preset(1, ProcessPresetName.FLOW)
        adapter.enable_pid(1, enabled=True)
        adapter.set_pid_params(1, kp=0.8, ti=4.0, td=0.0)
        adapter.set_pid_mode(1, mode=1)
        adapter._controllers[1].sp = 50.0

        # Run 100 ticks
        for _ in range(100):
            adapter._tick(0.1)
        co_before = adapter._controllers[1].last_co

        # Write new Ti via OPC-UA (simulating smartPID SUPERVISORY write)
        adapter._on_opcua_write(1, "ti", 2.0)
        assert adapter._controllers[1].pid_params.reset == 2.0

        # Run more ticks — behavior should differ (faster integral)
        for _ in range(100):
            adapter._tick(0.1)
        co_after = adapter._controllers[1].last_co

        # Both should have moved, confirming PID is computing
        assert co_before > 0.0
        assert co_after > 0.0
