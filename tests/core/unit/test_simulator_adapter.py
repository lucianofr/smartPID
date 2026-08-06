"""Tests for SimulatorAdapter — TelemetrySource + ControlWriter."""
from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

from smart_pid_core.adapters.inbound.sim_persistence import persist_sim_config
from smart_pid_core.adapters.inbound.simulator_adapter import (
    SimulatorAdapter,
    bind_opcua_client,
)
from smart_pid_core.adapters.outbound.sqlite_repo import SQLiteRepository
from smart_pid_core.config import CoreSettings
from smart_pid_domain.enums import ProcessPresetName
from smart_pid_domain.models.controller import TagBindings


@pytest.fixture
def settings() -> CoreSettings:
    return CoreSettings(
        jwt_secret="test-secret-key-minimum-32-bytes!",
        simulator_enabled=True,
        simulator_interval_ms=50,
    )  # type: ignore[call-arg]


@pytest.fixture
def adapter(settings: CoreSettings) -> SimulatorAdapter:
    def _make_mock_server(port: int = 4849, **_kwargs: object) -> MagicMock:
        return _mock_opcua_server(port=port)

    with patch(
        "smart_pid_core.adapters.inbound.simulator_adapter.OPCUAServer",
        side_effect=_make_mock_server,
    ):
        a = SimulatorAdapter(settings=settings)
        yield a
        a.stop()


def _mock_opcua_server(port: int = 4849) -> MagicMock:
    """Create a mock OPCUAServer with the same interface."""
    mock = MagicMock()
    mock.is_running = False
    mock.controller_node_ids = {}
    mock.port = port
    mock.endpoint = f"opc.tcp://0.0.0.0:{port}"

    def _start() -> None:
        mock.is_running = True

    def _stop() -> None:
        mock.is_running = False

    def _register(cid: int) -> dict[str, str]:
        node_ids = {"pv": f"ns=2;s=PV_{cid}", "sp": f"ns=2;s=SP_{cid}", "co": f"ns=2;s=CO_{cid}"}
        mock.controller_node_ids[cid] = node_ids
        return node_ids

    mock.start.side_effect = _start
    mock.stop.side_effect = _stop
    mock.register_controller.side_effect = _register
    return mock


class TestSimulatorAdapterInit:
    def test_no_queue_attribute(self, adapter: SimulatorAdapter) -> None:
        assert not hasattr(adapter, "queue")

    def test_not_running_initially(self, adapter: SimulatorAdapter) -> None:
        assert not adapter.is_running


class TestSimulatorAdapterPresets:
    def test_set_preset_flow(self, adapter: SimulatorAdapter) -> None:
        adapter.register_controller(1)
        adapter.set_preset(1, ProcessPresetName.FLOW)
        status = adapter.get_controller_status(1)
        assert status.preset == "FLOW"
        assert status.gain == 1.2
        assert status.tau1 == 3.0
        assert status.tau2 is None

    def test_set_preset_temperature(self, adapter: SimulatorAdapter) -> None:
        adapter.register_controller(1)
        adapter.set_preset(1, ProcessPresetName.TEMPERATURE)
        status = adapter.get_controller_status(1)
        assert status.preset == "TEMPERATURE"
        assert status.tau2 == 20.0

    def test_set_parameters_custom(self, adapter: SimulatorAdapter) -> None:
        adapter.register_controller(1)
        adapter.set_parameters(1, gain=3.0, tau1=15.0, tau2=8.0, dead_time=4.0)
        status = adapter.get_controller_status(1)
        assert status.gain == 3.0
        assert status.tau2 == 8.0
        assert status.preset == "CUSTOM"

    def test_set_parameters_preserves_pv_continuity(
        self, adapter: SimulatorAdapter,
    ) -> None:
        """PV must not snap to zero when parameters change while simulating.

        Prevents the UX regression where the user sees PV reset on Apply
        and concludes the parameter change had no effect.
        """
        adapter.register_controller(1)
        ctrl = adapter._controllers[1]  # noqa: SLF001
        ctrl.last_co = 50.0
        # Drive to steady state with defaults (K=1.2, tau1=3s): PV -> 60
        for _ in range(300):
            adapter._tick(0.1)  # noqa: SLF001
        pv_before = ctrl.live_pv
        assert pv_before > 55.0  # confirm we reached near steady state

        # Change process parameters (e.g., slow it way down)
        adapter.set_parameters(1, gain=5.0, tau1=120.0, tau2=40.0, dead_time=30.0)
        # One tick with new params: PV should stay close to previous value
        adapter._tick(0.1)  # noqa: SLF001
        pv_after = ctrl.live_pv
        # Allow a small transient but no collapse to zero
        assert abs(pv_after - pv_before) < 5.0, (
            f"PV snapped from {pv_before:.2f} to {pv_after:.2f} on parameter change"
        )


class TestSimulatorAdapterDisturbances:
    def test_inject_step(self, adapter: SimulatorAdapter) -> None:
        adapter.register_controller(1)
        adapter.inject_step(1, amplitude=5.0)
        status = adapter.get_controller_status(1)
        assert status.step_active is True
        assert status.step_amplitude == 5.0

    def test_inject_noise(self, adapter: SimulatorAdapter) -> None:
        adapter.register_controller(1)
        adapter.inject_noise(1, amplitude=0.5)
        status = adapter.get_controller_status(1)
        assert status.noise_active is True
        assert status.noise_amplitude == 0.5

    def test_clear_disturbance(self, adapter: SimulatorAdapter) -> None:
        adapter.register_controller(1)
        adapter.inject_step(1, amplitude=5.0)
        adapter.inject_noise(1, amplitude=0.5)
        adapter.clear_disturbance(1)
        status = adapter.get_controller_status(1)
        assert status.step_active is False
        assert status.noise_active is False


class TestSimulatorAdapterWriteOutput:
    def test_write_output_stores_co(self, adapter: SimulatorAdapter) -> None:
        adapter.register_controller(1)
        adapter.write_output(1, 42.0)
        assert adapter._controllers[1].last_co == 42.0


class TestSimulatorAdapterRunning:
    def test_start_stop_lifecycle(self, adapter: SimulatorAdapter) -> None:
        adapter.register_controller(1)
        adapter.set_preset(1, ProcessPresetName.FLOW)
        adapter.start()
        assert adapter.is_running
        time.sleep(0.15)
        adapter.stop()
        assert not adapter.is_running

    def test_write_parameter_is_noop(self, adapter: SimulatorAdapter) -> None:
        """write_parameter satisfies ControlWriter protocol but is a no-op for simulator."""
        adapter.register_controller(1)
        adapter.write_parameter(1, "gain", 2.0)  # Should not raise


class TestSimulatorAdapterOPCUA:
    """Tests for OPC-UA integration in SimulatorAdapter."""

    @pytest.fixture
    def mock_adapter(self, settings: CoreSettings) -> SimulatorAdapter:
        def _make_mock_server(port: int = 4849, **_kwargs: object) -> MagicMock:
            return _mock_opcua_server(port=port)

        with patch(
            "smart_pid_core.adapters.inbound.simulator_adapter.OPCUAServer",
            side_effect=_make_mock_server,
        ):
            a = SimulatorAdapter(settings=settings)
            yield a
            a.stop()

    def test_opcua_server_attribute(self, mock_adapter: SimulatorAdapter) -> None:
        assert hasattr(mock_adapter, "_opcua_server")
        assert mock_adapter._opcua_server is not None

    def test_start_starts_opcua_server(self, mock_adapter: SimulatorAdapter) -> None:
        mock_adapter.register_controller(1)
        mock_adapter.start_opcua()
        mock_adapter.start()
        assert mock_adapter._opcua_server.is_running
        mock_adapter.stop()
        mock_adapter.stop_opcua()

    def test_stop_stops_opcua_server(self, mock_adapter: SimulatorAdapter) -> None:
        mock_adapter.register_controller(1)
        mock_adapter.start_opcua()
        mock_adapter.start()
        mock_adapter.stop()
        mock_adapter.stop_opcua()
        assert not mock_adapter._opcua_server.is_running

    def test_register_controller_creates_opcua_nodes(
        self, mock_adapter: SimulatorAdapter,
    ) -> None:
        mock_adapter.register_controller(1)
        mock_adapter._opcua_server.register_controller.assert_called_once_with(1)
        assert 1 in mock_adapter._opcua_server.controller_node_ids

    def test_tick_calls_update_values(self, mock_adapter: SimulatorAdapter) -> None:
        mock_adapter.register_controller(1)
        mock_adapter._tick(0.1)
        mock_adapter._opcua_server.update_values.assert_called_once()
        call_kwargs = mock_adapter._opcua_server.update_values.call_args
        assert call_kwargs.kwargs["controller_id"] == 1
        values = call_kwargs.kwargs["values"]
        assert "pv" in values
        assert "process_input" in values
        assert "process_output" in values
        assert "disturbance_output" in values
        # PID config (kp/ti/td/pid_structure/pid_enabled) must NOT be echoed
        # every tick — doing so races with external writes from the AI
        # optimizer / HMI and reverts their tuning updates.
        assert "kp" not in values
        assert "ti" not in values
        assert "td" not in values
        assert "pid_structure" not in values
        assert "pid_enabled" not in values

    def test_set_pid_params_syncs_to_opcua(
        self, mock_adapter: SimulatorAdapter,
    ) -> None:
        """Regression: tuning changes must propagate to OPC-UA via the sync
        helper, since _tick no longer echoes kp/ti/td every cycle.
        """
        mock_adapter.register_controller(1)
        mock_adapter._opcua_server.update_values.reset_mock()
        mock_adapter.set_pid_params(1, kp=2.5, ti=15.6590, td=0.1)
        mock_adapter._opcua_server.update_values.assert_called_once()
        call_kwargs = mock_adapter._opcua_server.update_values.call_args
        assert call_kwargs.kwargs["controller_id"] == 1
        values = call_kwargs.kwargs["values"]
        assert values["kp"] == 2.5
        assert values["ti"] == 15.6590
        assert values["td"] == 0.1

    def test_on_opcua_write_updates_co(self, mock_adapter: SimulatorAdapter) -> None:
        mock_adapter.register_controller(1)
        mock_adapter._on_opcua_write(1, "co", 75.0)
        assert mock_adapter._controllers[1].last_co == 75.0

    def test_on_opcua_write_updates_sp(self, mock_adapter: SimulatorAdapter) -> None:
        mock_adapter.register_controller(1)
        mock_adapter._on_opcua_write(1, "sp", 60.0)
        assert mock_adapter._controllers[1].sp == 60.0

    def test_on_opcua_write_ignores_unknown_controller(
        self, mock_adapter: SimulatorAdapter,
    ) -> None:
        mock_adapter._on_opcua_write(999, "co", 50.0)  # Should not raise

    def test_opcua_ti_write_marks_controller_dirty(
        self, mock_adapter: SimulatorAdapter,
    ) -> None:
        """Regression: Fuzzy/RL Ti updates arriving via OPC-UA must be flagged
        for background persistence. Otherwise fuzzy-tuned Ti is lost on restart.
        """
        mock_adapter.register_controller(1)
        assert mock_adapter.consume_dirty_cids() == []
        mock_adapter._on_opcua_write(1, "ti", 13.5)
        assert mock_adapter._controllers[1].pid_params.reset == 13.5
        dirty = mock_adapter.consume_dirty_cids()
        assert dirty == [1]
        # Consume clears the set — second call is empty.
        assert mock_adapter.consume_dirty_cids() == []

    def test_opcua_co_write_does_not_mark_dirty(
        self, mock_adapter: SimulatorAdapter,
    ) -> None:
        """CO is transient runtime state — do not thrash DB every scan."""
        mock_adapter.register_controller(1)
        mock_adapter._on_opcua_write(1, "co", 42.0)
        assert mock_adapter.consume_dirty_cids() == []

    def test_opcua_persistable_params_all_mark_dirty(
        self, mock_adapter: SimulatorAdapter,
    ) -> None:
        mock_adapter.register_controller(1)
        for param, value in (
            ("kp", 2.0), ("ti", 5.0), ("td", 0.1),
            ("mode", 1), ("pid_structure", 2), ("pid_sp", 55.0),
        ):
            mock_adapter._on_opcua_write(1, param, value)
        assert mock_adapter.consume_dirty_cids() == [1]


class TestBindOpcuaClientPrecedence:
    """A configured project tag mapping outranks the twin's minted nodes.

    The twin owns the address space only for loops it created itself. A loop
    imported from a real project carries its own ``tag_bindings``, and which
    ``CTRL_n`` folder the twin happens to mint for that id shifts between
    boots — so letting the twin win silently pointed the faceplate at another
    loop's tags.
    """

    @staticmethod
    def _sim(nodes: dict[int, dict[str, str]]) -> MagicMock:
        sim = MagicMock()
        sim.opcua_node_ids.side_effect = lambda cid: nodes.get(cid, {})
        return sim

    def test_mapped_controller_registers_from_its_tag_bindings(self) -> None:
        opcua = MagicMock()
        sim = self._sim({1: {"pv": "twin;pv", "kp": "twin;kp"}})
        tb = TagBindings(node_id_pv="proj;pv", node_id_kp="proj;kp")

        bound = bind_opcua_client(opcua, sim, [1], {1: tb})

        assert bound == [], "a mapped loop must not be bound to the twin"
        kwargs = opcua.register_controller.call_args.kwargs
        assert kwargs["node_id_pv"] == "proj;pv"
        assert kwargs["node_id_kp"] == "proj;kp"

    def test_unmapped_controller_still_falls_through_to_the_twin(self) -> None:
        opcua = MagicMock()
        sim = self._sim({1: {"pv": "twin;pv", "kp": "twin;kp"}})

        bound = bind_opcua_client(opcua, sim, [1], {1: TagBindings()})

        assert bound == [1]
        kwargs = opcua.register_controller.call_args.kwargs
        assert kwargs["node_id_pv"] == "twin;pv"
        assert kwargs["node_id_kp"] == "twin;kp"

    def test_twin_only_loop_binds_when_no_bindings_are_supplied(self) -> None:
        """POST /simulator/loops has no project controller behind the id."""
        opcua = MagicMock()
        sim = self._sim({7: {"pv": "twin;pv"}})

        assert bind_opcua_client(opcua, sim, [7]) == [7]

    def test_an_unmapped_kp_is_left_unmapped_rather_than_borrowed(self) -> None:
        """The faceplate must show "sem dados", not another loop's gain."""
        opcua = MagicMock()
        sim = self._sim({1: {"pv": "twin;pv", "kp": "twin;kp"}})
        tb = TagBindings(node_id_pv="proj;pv", node_id_kp="")

        bind_opcua_client(opcua, sim, [1], {1: tb})

        assert opcua.register_controller.call_args.kwargs["node_id_kp"] == ""


class TestSimulatorAdapterConfigPersistence:
    """Tests for get_config_dict and load_sim_config round-trip."""

    def test_get_config_dict_defaults(self, adapter: SimulatorAdapter) -> None:
        adapter.register_controller(1)
        cfg = adapter.get_config_dict(1)
        assert cfg["controller_id"] == 1
        assert cfg["preset"] == "FLOW"
        assert cfg["gain"] == 1.2
        assert cfg["tau1"] == 3.0
        assert cfg["tau2"] == 0.0  # None -> 0.0 for DB
        assert cfg["dead_time"] == 1.0
        assert cfg["pid_enabled"] is True
        assert cfg["pid_kp"] == 1.0
        assert cfg["pid_ti"] == 10.0
        assert cfg["pid_td"] == 0.0
        assert cfg["pid_mode"] == 0
        assert cfg["auto_sp_enabled"] is False
        assert cfg["auto_sp_min_pct"] == 30.0
        assert cfg["auto_sp_max_pct"] == 70.0
        assert cfg["auto_dist_enabled"] is False
        assert cfg["auto_dist_max_pct"] == 10.0

    def test_get_config_dict_after_mutations(self, adapter: SimulatorAdapter) -> None:
        adapter.register_controller(1)
        adapter.set_preset(1, ProcessPresetName.TEMPERATURE)
        adapter.set_pid_params(1, kp=2.5, ti=8.0, td=0.5)
        adapter.set_pid_mode(1, 1)
        from smart_pid_domain.dtos.simulator import AutoDisturbanceRequest, AutoSPRequest
        adapter.set_auto_sp(1, AutoSPRequest(enabled=True, sp_min_pct=20.0, sp_max_pct=90.0))
        adapter.set_auto_disturbance(
            1, AutoDisturbanceRequest(enabled=True, max_amplitude_pct=15.0),
        )
        cfg = adapter.get_config_dict(1)
        assert cfg["preset"] == "TEMPERATURE"
        assert cfg["pid_enabled"] is True
        assert cfg["pid_kp"] == 2.5
        assert cfg["pid_ti"] == 8.0
        assert cfg["pid_td"] == 0.5
        assert cfg["pid_mode"] == 1
        assert cfg["auto_sp_enabled"] is True
        assert cfg["auto_sp_min_pct"] == 20.0
        assert cfg["auto_sp_max_pct"] == 90.0
        assert cfg["auto_dist_enabled"] is True
        assert cfg["auto_dist_max_pct"] == 15.0

    def test_load_sim_config_round_trip(self, adapter: SimulatorAdapter) -> None:
        adapter.register_controller(1)
        # Simulate a saved config dict (as from DB)
        saved_cfg = {
            "controlador_id": 1,
            "preset": "PRESSURE",
            "gain": 0.5,
            "tau1": 30.0,
            "tau2": 10.0,
            "dead_time": 5.0,
            "pid_enabled": True,
            "pid_kp": 3.0,
            "pid_ti": 15.0,
            "pid_td": 1.0,
            "pid_mode": 1,
            "auto_sp_enabled": True,
            "auto_sp_min_pct": 10.0,
            "auto_sp_max_pct": 95.0,
            "auto_dist_enabled": True,
            "auto_dist_max_pct": 20.0,
        }
        adapter.load_sim_config(saved_cfg)
        # Verify via get_config_dict
        cfg = adapter.get_config_dict(1)
        assert cfg["preset"] == "PRESSURE"
        assert cfg["gain"] == 0.5
        assert cfg["tau1"] == 30.0
        assert cfg["tau2"] == 10.0
        assert cfg["dead_time"] == 5.0
        assert cfg["pid_enabled"] is True
        assert cfg["pid_kp"] == 3.0
        assert cfg["pid_ti"] == 15.0
        assert cfg["pid_td"] == 1.0
        assert cfg["pid_mode"] == 1
        assert cfg["auto_sp_enabled"] is True
        assert cfg["auto_sp_min_pct"] == 10.0
        assert cfg["auto_sp_max_pct"] == 95.0
        assert cfg["auto_dist_enabled"] is True
        assert cfg["auto_dist_max_pct"] == 20.0

    def test_get_config_dict_unknown_controller_raises(
        self, adapter: SimulatorAdapter,
    ) -> None:
        with pytest.raises(KeyError):
            adapter.get_config_dict(999)

    def test_load_sim_config_restores_unregistered_loop(
        self, adapter: SimulatorAdapter,
    ) -> None:
        """A standalone loop's row must rebuild the loop, not be discarded.

        Boot registers only ids that have a Controladores row, so a loop
        made by ``create_loop`` is never registered before its config is
        replayed. Dropping it here is what made every restart look like
        the simulator had been wiped.
        """
        assert not adapter.has_controller(999)
        adapter.load_sim_config({
            "controlador_id": 999, "preset": "PRESSURE", "gain": 0.5,
            "tau1": 30.0, "tau2": 10.0, "dead_time": 5.0,
            "pid_kp": 3.0, "pid_ti": 15.0, "pid_td": 1.0, "pid_mode": 1,
            "pv_min": -50.0, "pv_max": 250.0,
        })
        assert adapter.has_controller(999)
        cfg = adapter.get_config_dict(999)
        assert cfg["preset"] == "PRESSURE"
        assert cfg["gain"] == 0.5
        assert cfg["pid_kp"] == 3.0
        # The span drives auto-excitation and PV clamping, so a wrong one
        # silently changes what the twin simulates.
        assert cfg["pv_min"] == -50.0
        assert cfg["pv_max"] == 250.0

    def test_load_sim_config_keeps_registered_pv_scale(
        self, adapter: SimulatorAdapter,
    ) -> None:
        """Controladores.pv_scale wins for a loop a project controller owns."""
        adapter.register_controller(1, pv_min=0.0, pv_max=500.0)
        adapter.load_sim_config({
            "controlador_id": 1, "preset": "X", "gain": 1.0,
            "tau1": 1.0, "tau2": 0.0, "dead_time": 1.0,
            "pv_min": -50.0, "pv_max": 250.0,
        })
        cfg = adapter.get_config_dict(1)
        assert (cfg["pv_min"], cfg["pv_max"]) == (0.0, 500.0)


class TestSimulatorPIDInternal:
    """Tests for internal PID controller in simulator."""

    def test_pid_defaults_to_man(self, adapter: SimulatorAdapter) -> None:
        adapter.register_controller(1)
        assert adapter._controllers[1].pid_mode == 0

    def test_set_pid_params(self, adapter: SimulatorAdapter) -> None:
        adapter.register_controller(1)
        adapter.set_pid_params(1, kp=2.0, ti=5.0, td=1.0)
        p = adapter._controllers[1].pid_params
        assert p.gain == 2.0
        assert p.reset == 5.0
        assert p.rate == 1.0

    def test_set_pid_mode_auto(self, adapter: SimulatorAdapter) -> None:
        adapter.register_controller(1)
        adapter.set_pid_mode(1, mode=1)
        assert adapter._controllers[1].pid_mode == 1

    def test_set_pid_mode_man(self, adapter: SimulatorAdapter) -> None:
        adapter.register_controller(1)
        adapter.set_pid_mode(1, mode=1)
        adapter.set_pid_mode(1, mode=0)
        assert adapter._controllers[1].pid_mode == 0

    def test_man_to_auto_is_bumpless(self, adapter: SimulatorAdapter) -> None:
        """MAN -> AUTO must reseed the integrator from the CO the operator left.

        The transfer used to ride on ``enable_pid()``; the twin's PID is always
        on now, so ``set_pid_mode`` owns it. Without it the first AUTO scan
        unwinds from a stale integrator and steps the valve.
        """
        adapter.register_controller(1)
        adapter.write_output(1, 40.0)
        adapter._tick(0.1)  # give the transfer a live PV to seed from
        adapter.set_pid_mode(1, mode=1)
        assert adapter._controllers[1].pid_state.cv == pytest.approx(40.0)

    def test_get_pid_status(self, adapter: SimulatorAdapter) -> None:
        adapter.register_controller(1)
        adapter.set_pid_params(1, kp=3.0, ti=8.0, td=0.5)
        adapter.set_pid_mode(1, mode=1)
        status = adapter.get_pid_status(1)
        assert status["enabled"] is True
        assert status["kp"] == 3.0
        assert status["ti"] == 8.0
        assert status["td"] == 0.5
        assert status["mode"] == 1

    def test_tick_defaults_to_man_co_unchanged(self, adapter: SimulatorAdapter) -> None:
        """A freshly registered loop is in MAN, so the tick must leave CO alone."""
        adapter.register_controller(1)
        adapter.write_output(1, 25.0)
        adapter._tick(0.1)
        assert adapter._controllers[1].last_co == 25.0

    def test_tick_pid_man_mode_co_unchanged(self, adapter: SimulatorAdapter) -> None:
        """In MAN mode the twin's PID must not touch CO."""
        adapter.register_controller(1)
        adapter.set_pid_mode(1, mode=0)  # MAN
        adapter.write_output(1, 25.0)
        adapter._tick(0.1)
        assert adapter._controllers[1].last_co == 25.0

    def test_tick_pid_auto_computes_co(self, adapter: SimulatorAdapter) -> None:
        """In AUTO, CO is computed by PIDEngine."""
        adapter.register_controller(1)
        adapter.set_pid_mode(1, mode=1)  # AUTO
        adapter._controllers[1].sp = 50.0
        adapter._controllers[1].last_co = 0.0
        # Run several ticks — CO should move toward correcting the error
        for _ in range(10):
            adapter._tick(0.1)
        co = adapter._controllers[1].last_co
        assert co > 0.0, f"Expected CO > 0 after PID AUTO ticks, got {co}"

    def test_controller_sim_status_includes_pid(self, adapter: SimulatorAdapter) -> None:
        adapter.register_controller(1)
        adapter.set_pid_params(1, kp=2.0, ti=5.0, td=0.5)
        status = adapter.get_controller_status(1)
        assert status.pid_kp == 2.0
        assert status.pid_ti == 5.0
        assert status.pid_td == 0.5

    def test_on_opcua_write_kp(self, adapter: SimulatorAdapter) -> None:
        adapter.register_controller(1)
        adapter._on_opcua_write(1, "kp", 3.5)
        assert adapter._controllers[1].pid_params.gain == 3.5

    def test_on_opcua_write_ti(self, adapter: SimulatorAdapter) -> None:
        adapter.register_controller(1)
        adapter._on_opcua_write(1, "ti", 8.0)
        assert adapter._controllers[1].pid_params.reset == 8.0

    def test_on_opcua_write_td(self, adapter: SimulatorAdapter) -> None:
        adapter.register_controller(1)
        adapter._on_opcua_write(1, "td", 2.0)
        assert adapter._controllers[1].pid_params.rate == 2.0

    def test_on_opcua_write_pid_mode(self, adapter: SimulatorAdapter) -> None:
        adapter.register_controller(1)
        adapter._on_opcua_write(1, "mode", 1.0)
        assert adapter._controllers[1].pid_mode == 1

    def test_on_opcua_write_pid_sp(self, adapter: SimulatorAdapter) -> None:
        adapter.register_controller(1)
        adapter._on_opcua_write(1, "pid_sp", 75.0)
        assert adapter._controllers[1].sp == 75.0


class TestSimulatorAdapterDecoupledLifecycle:
    """Tests for independent OPC-UA and simulation loop lifecycle."""

    def test_start_opcua_independent(self, adapter: SimulatorAdapter) -> None:
        """OPC-UA server can be started without simulation loop."""
        adapter.start_opcua()
        assert adapter.opcua_running is True
        assert adapter.is_running is False  # sim loop NOT started
        adapter.stop_opcua()
        assert adapter.opcua_running is False

    def test_stop_opcua_independent(self, adapter: SimulatorAdapter) -> None:
        """Stopping OPC-UA does not stop simulation loop."""
        adapter.start_opcua()
        adapter.start()
        assert adapter.is_running is True
        assert adapter.opcua_running is True
        adapter.stop_opcua()
        assert adapter.opcua_running is False
        assert adapter.is_running is True  # sim loop still running
        adapter.stop()

    def test_start_stop_sim_loop_independent(self, adapter: SimulatorAdapter) -> None:
        """Starting/stopping sim loop does not affect OPC-UA server."""
        adapter.start_opcua()
        assert adapter.opcua_running is True
        adapter.start()
        assert adapter.is_running is True
        adapter.stop()
        assert adapter.is_running is False
        assert adapter.opcua_running is True  # OPC-UA still running
        adapter.stop_opcua()

    def test_opcua_port_property(self, adapter: SimulatorAdapter) -> None:
        assert adapter.opcua_port == adapter._settings.simulator_port

    def test_opcua_endpoint_property(self, adapter: SimulatorAdapter) -> None:
        port = adapter._settings.simulator_port
        assert adapter.opcua_endpoint == f"opc.tcp://0.0.0.0:{port}"


class TestSimulatorAdapterRegistrationLifecycle:
    """``has_controller`` / ``unregister_controller`` — the delete-side pair.

    ``DELETE /controllers/{id}`` used to leave the simulation state behind, so
    the tick loop kept integrating a process model for a controller that no
    longer existed and ``/simulator/*`` kept answering for it.
    """

    def test_has_controller_reflects_registration(
        self, adapter: SimulatorAdapter,
    ) -> None:
        assert adapter.has_controller(7) is False
        adapter.register_controller(7)
        assert adapter.has_controller(7) is True

    def test_unregister_removes_state_and_reports_removal(
        self, adapter: SimulatorAdapter,
    ) -> None:
        adapter.register_controller(7)
        assert adapter.unregister_controller(7) is True
        assert adapter.has_controller(7) is False
        assert 7 not in adapter._controllers

    def test_unregister_unknown_controller_is_a_no_op(
        self, adapter: SimulatorAdapter,
    ) -> None:
        assert adapter.unregister_controller(999) is False

    def test_unregister_drops_pending_persist(
        self, adapter: SimulatorAdapter,
    ) -> None:
        """A queued dirty id must not outlive the controller.

        The main-loop flusher drains ``consume_dirty_cids()`` and persists each
        id, which would otherwise write a ``Configuracao_Simulador`` row back
        for a controller that has just been deleted.
        """
        adapter.register_controller(7)
        adapter._on_opcua_write(7, "kp", 2.0)
        assert 7 in adapter._dirty_cids

        adapter.unregister_controller(7)
        assert adapter.consume_dirty_cids() == []

    def test_unregistered_controller_stops_ticking(
        self, adapter: SimulatorAdapter,
    ) -> None:
        adapter.register_controller(7)
        adapter.write_output(7, 50.0)
        adapter._tick(0.1)
        # live_process_input is written on every tick (unlike live_pv, which
        # stays 0 until the 1.0s default dead time elapses), so it is the
        # cheapest proof the loop actually visited this controller.
        assert adapter._controllers[7].live_process_input == 50.0

        adapter.unregister_controller(7)
        adapter._tick(0.1)  # must not raise on the now-empty controller set
        assert adapter.get_status() == {}

    def test_unregister_leaves_other_controllers_alone(
        self, adapter: SimulatorAdapter,
    ) -> None:
        adapter.register_controller(1)
        adapter.register_controller(2)
        adapter.unregister_controller(1)
        assert adapter.has_controller(2) is True



class TestStandaloneLoopSurvivesRestart:
    """The reported defect: a redeploy wiped the operator's simulator loops.

    The SQLite row was always intact on the persistent volume -- boot read
    it back and dropped it, because nothing had registered the id first.
    Composes the real repo with the real adapter: the fault lives exactly
    where the two meet, so neither alone reproduces it.
    """

    @staticmethod
    def _restart(settings: CoreSettings) -> SimulatorAdapter:
        """A fresh adapter, as a redeploy would build: empty, nothing known."""
        with patch(
            "smart_pid_core.adapters.inbound.simulator_adapter.OPCUAServer",
            side_effect=lambda port=4849, **_k: _mock_opcua_server(port=port),
        ):
            return SimulatorAdapter(settings=settings)

    async def test_loop_and_its_tuning_come_back(
        self, tmp_path, settings: CoreSettings, adapter: SimulatorAdapter,
    ) -> None:
        repo = SQLiteRepository(tmp_path / "restart.spid")
        await repo.initialize()
        fresh = None
        try:
            # No Controladores row is created: this is a loop no malha owns.
            cid = adapter.create_loop(pv_min=-50.0, pv_max=250.0)
            adapter.set_pid_params(cid, kp=3.0, ti=15.0, td=1.0)
            assert await persist_sim_config(adapter, repo, cid)

            fresh = self._restart(settings)
            assert not fresh.has_controller(cid), "restart must start empty"
            for cfg in await repo.list_sim_configs():
                fresh.load_sim_config(cfg)

            assert fresh.has_controller(cid), "the loop was erased by the restart"
            got = fresh.get_config_dict(cid)
            assert got["pid_kp"] == 3.0
            assert got["pid_ti"] == 15.0
            assert (got["pv_min"], got["pv_max"]) == (-50.0, 250.0)
        finally:
            if fresh is not None:
                fresh.stop()
            await repo.close()

    async def test_deleted_loop_does_not_return(
        self, tmp_path, settings: CoreSettings, adapter: SimulatorAdapter,
    ) -> None:
        """Deleting must reach the file, or restore resurrects the loop."""
        repo = SQLiteRepository(tmp_path / "deleted.spid")
        await repo.initialize()
        fresh = None
        try:
            cid = adapter.create_loop()
            assert await persist_sim_config(adapter, repo, cid)

            adapter.unregister_controller(cid)
            await repo.delete_sim_config(cid)

            fresh = self._restart(settings)
            for cfg in await repo.list_sim_configs():
                fresh.load_sim_config(cfg)
            assert not fresh.has_controller(cid)
        finally:
            if fresh is not None:
                fresh.stop()
            await repo.close()