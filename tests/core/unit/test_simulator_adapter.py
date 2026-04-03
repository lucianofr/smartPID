"""Tests for SimulatorAdapter — TelemetrySource + ControlWriter."""
from __future__ import annotations

import time
from queue import SimpleQueue

import pytest

from smart_pid_core.adapters.inbound.simulator_adapter import SimulatorAdapter
from smart_pid_core.config import CoreSettings
from smart_pid_domain.enums import ProcessPresetName


@pytest.fixture
def settings() -> CoreSettings:
    return CoreSettings(
        jwt_secret="test-secret-key-minimum-32-bytes!",
        simulator_enabled=True,
        simulator_interval_ms=50,
    )  # type: ignore[call-arg]


@pytest.fixture
def adapter(settings: CoreSettings) -> SimulatorAdapter:
    a = SimulatorAdapter(settings=settings)
    yield a
    a.stop()


class TestSimulatorAdapterInit:
    def test_queue_is_simple_queue(self, adapter: SimulatorAdapter) -> None:
        assert isinstance(adapter.queue, SimpleQueue)

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
    def test_start_stop_produces_telemetry(self, adapter: SimulatorAdapter) -> None:
        adapter.register_controller(1)
        adapter.set_preset(1, ProcessPresetName.FLOW)
        adapter.start()
        assert adapter.is_running
        time.sleep(0.15)
        adapter.stop()
        assert not adapter.is_running
        frames = []
        while not adapter.queue.empty():
            frames.append(adapter.queue.get_nowait())
        assert len(frames) >= 1
        assert frames[0].controller_id == 1

    def test_write_parameter_is_noop(self, adapter: SimulatorAdapter) -> None:
        """write_parameter satisfies ControlWriter protocol but is a no-op for simulator."""
        adapter.register_controller(1)
        adapter.write_parameter(1, "gain", 2.0)  # Should not raise
