"""Unit tests for SimulatorAdapter auto-excitation logic."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from smart_pid_core.adapters.inbound.simulator_adapter import (
    SimulatorAdapter,
    min_auto_sp_period_s,
)
from smart_pid_core.config import CoreSettings
from smart_pid_domain.dtos.simulator import AutoDisturbanceRequest, AutoSPRequest
from smart_pid_domain.enums import ProcessPresetName


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

    def test_period_below_the_settling_floor_is_raised(
        self, adapter: SimulatorAdapter,
    ) -> None:
        """A step the process cannot answer is a permanent transient, not excitation.

        It pins CO at a limit after every step, makes the trend read as a square
        wave however well the loop is tuned, and starves the optimizer's
        steady-state FOPDT retune, which only identifies while the loop settles.
        """
        adapter.set_auto_sp(1, AutoSPRequest(enabled=True, period_s=1.0))
        status = adapter.get_controller_status(1)
        assert status.auto_sp is not None
        floor = min_auto_sp_period_s(status.tau1, status.tau2, status.dead_time)
        assert floor > 1.0
        # The stored value IS the effective one, so the HMI reads the correction.
        assert status.auto_sp.period_s == floor

    def test_period_above_the_floor_is_left_alone(self, adapter: SimulatorAdapter) -> None:
        """The floor only raises. An operator asking for slower excitation gets it."""
        adapter.set_auto_sp(1, AutoSPRequest(enabled=True, period_s=600.0))
        status = adapter.get_controller_status(1)
        assert status.auto_sp is not None
        assert status.auto_sp.period_s == 600.0

    def test_slowing_the_process_re_derives_the_floor(
        self, adapter: SimulatorAdapter,
    ) -> None:
        """The floor tracks the model, so a period that cleared it can stop doing so."""
        adapter.set_auto_sp(1, AutoSPRequest(enabled=True, period_s=40.0))
        before = adapter.get_controller_status(1)
        assert before.auto_sp is not None
        assert before.auto_sp.period_s == 40.0  # clears the default FLOW floor

        adapter.set_parameters(1, gain=2.0, tau1=30.0, tau2=15.0, dead_time=5.0)
        after = adapter.get_controller_status(1)
        assert after.auto_sp is not None
        assert after.auto_sp.period_s == min_auto_sp_period_s(30.0, 15.0, 5.0)
        assert after.auto_sp.period_s > 40.0

    def test_switching_preset_re_derives_the_floor(self, adapter: SimulatorAdapter) -> None:
        adapter.set_auto_sp(1, AutoSPRequest(enabled=True, period_s=40.0))
        adapter.set_preset(1, ProcessPresetName.TEMPERATURE)
        status = adapter.get_controller_status(1)
        assert status.auto_sp is not None
        assert status.auto_sp.period_s == min_auto_sp_period_s(
            status.tau1, status.tau2, status.dead_time,
        )

    def test_a_persisted_short_period_is_raised_on_load(
        self, adapter: SimulatorAdapter,
    ) -> None:
        """Clamped, not rejected: a project saved before the floor existed — or
        saved against a faster model — must still load."""
        cfg = adapter.get_config_dict(1)
        cfg["controlador_id"] = cfg.pop("controller_id")
        cfg["auto_sp_enabled"] = True
        cfg["auto_sp_period_s"] = 2.0
        cfg["tau1"] = 22.2
        cfg["tau2"] = 10.5
        cfg["dead_time"] = 5.1
        adapter.load_sim_config(cfg)
        status = adapter.get_controller_status(1)
        assert status.auto_sp is not None
        assert status.auto_sp.period_s == min_auto_sp_period_s(22.2, 10.5, 5.1)


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
        # A requested period is raised to what the process can settle, so the
        # tick loop has to run out the EFFECTIVE period, not the asked-for one.
        adapter.set_auto_sp(
            1, AutoSPRequest(enabled=True, sp_min_pct=40.0, sp_max_pct=60.0, period_s=1.0)
        )
        with adapter._lock:
            ctrl = adapter._controllers[1]
            initial_sp = ctrl.sp
            period = ctrl.auto_sp_period_s
        assert period == min_auto_sp_period_s(ctrl.tau1, ctrl.tau2, ctrl.dead_time)
        dt = 0.1
        for _ in range(int(period / dt) + 2):
            adapter._tick(dt)
        with adapter._lock:
            ctrl = adapter._controllers[1]
            # elapsed reset after firing, and the new SP landed inside the band
            assert ctrl.auto_sp_elapsed_s < ctrl.auto_sp_period_s
            assert ctrl.sp != initial_sp
            span = ctrl.pv_max - ctrl.pv_min
            assert ctrl.pv_min + 40.0 / 100.0 * span <= ctrl.sp <= ctrl.pv_min + 60.0 / 100.0 * span

    def test_auto_dist_fires_after_period(self, adapter: SimulatorAdapter) -> None:
        adapter.set_auto_disturbance(
            1, AutoDisturbanceRequest(enabled=True, max_amplitude_pct=20.0, period_s=1.0)
        )
        dt = 0.1
        for _ in range(int(1.0 / dt) + 2):
            adapter._tick(dt)
        with adapter._lock:
            ctrl = adapter._controllers[1]
            assert ctrl.auto_dist_elapsed_s < ctrl.auto_dist_period_s
            assert ctrl.step_active is True
            max_amp = 20.0 / 100.0 * (ctrl.pv_max - ctrl.pv_min)
            assert abs(ctrl.step_amplitude) <= max_amp

    def test_period_controls_cadence(self, adapter: SimulatorAdapter) -> None:
        """A longer period must NOT fire before it elapses."""
        adapter.set_auto_disturbance(
            1, AutoDisturbanceRequest(enabled=True, max_amplitude_pct=20.0, period_s=5.0)
        )
        dt = 0.1
        for _ in range(20):  # 2.0s — below the 5.0s period
            adapter._tick(dt)
        with adapter._lock:
            assert adapter._controllers[1].step_active is False

    def test_zero_span_skips_excitation(self, adapter: SimulatorAdapter) -> None:
        """If pv_min == pv_max, no excitation should happen."""
        with adapter._lock:
            adapter._controllers[1].pv_min = 50.0
            adapter._controllers[1].pv_max = 50.0
        adapter.set_auto_sp(1, AutoSPRequest(enabled=True, period_s=1.0))
        with adapter._lock:
            initial_sp = adapter._controllers[1].sp
        dt = 0.1
        for _ in range(int(1.0 / dt) + 2):
            adapter._tick(dt)
        with adapter._lock:
            assert adapter._controllers[1].sp == initial_sp
