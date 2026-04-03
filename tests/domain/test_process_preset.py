"""Tests for ProcessPreset frozen dataclass and PRESETS registry."""
from __future__ import annotations

import pytest

from smart_pid_domain.enums import ProcessPresetName
from smart_pid_domain.models.process_preset import PRESETS, ProcessPreset


class TestProcessPreset:
    def test_all_presets_registered(self) -> None:
        for name in ProcessPresetName:
            if name == ProcessPresetName.CUSTOM:
                continue
            assert name in PRESETS, f"Preset {name} not registered"

    def test_preset_is_frozen(self) -> None:
        preset = PRESETS[ProcessPresetName.FLOW]
        with pytest.raises(AttributeError):
            preset.gain = 999.0  # type: ignore[misc]

    def test_flow_preset_is_foptd(self) -> None:
        p = PRESETS[ProcessPresetName.FLOW]
        assert p.tau2 is None
        assert p.gain == 1.2
        assert p.tau1 == 3.0
        assert p.dead_time == 1.0

    def test_pressure_preset_is_foptd(self) -> None:
        p = PRESETS[ProcessPresetName.PRESSURE]
        assert p.tau2 is None
        assert p.gain == 0.8

    def test_level_preset_is_soptd(self) -> None:
        p = PRESETS[ProcessPresetName.LEVEL]
        assert p.tau2 is not None
        assert p.gain == 2.0
        assert p.tau1 == 30.0
        assert p.tau2 == 15.0

    def test_temperature_preset_is_soptd(self) -> None:
        p = PRESETS[ProcessPresetName.TEMPERATURE]
        assert p.tau2 is not None
        assert p.gain == 1.5
        assert p.tau2 == 20.0
