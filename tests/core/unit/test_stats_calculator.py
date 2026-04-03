"""Unit tests for StatsCalculator — pure domain service."""
from __future__ import annotations

import math

import pytest


class TestStatsCalculatorBasic:
    def test_empty_calculator_returns_zero(self):
        from smart_pid_core.domain.services.stats_calculator import StatsCalculator

        calc = StatsCalculator(window_size=100, span=100.0, setpoint=50.0)
        assert calc.iae == 0.0
        assert calc.itae == 0.0
        assert calc.ise == 0.0
        assert calc.mse == 0.0
        assert calc.std_dev == 0.0
        assert calc.total_variation == 0.0

    def test_iae_accumulates_absolute_error(self):
        from smart_pid_core.domain.services.stats_calculator import StatsCalculator

        calc = StatsCalculator(window_size=100, span=100.0, setpoint=50.0)
        # 3 samples with errors: +5, -3, +2, dt=1.0 each
        calc.add_sample(error=5.0, co=50.0, dt=1.0)
        calc.add_sample(error=-3.0, co=50.0, dt=1.0)
        calc.add_sample(error=2.0, co=50.0, dt=1.0)
        assert calc.iae == pytest.approx(10.0)  # |5|+|-3|+|2| = 10

    def test_itae_weighs_by_time(self):
        from smart_pid_core.domain.services.stats_calculator import StatsCalculator

        calc = StatsCalculator(window_size=100, span=100.0, setpoint=50.0)
        # t=1: |e|=5, t=2: |e|=3, t=3: |e|=2
        calc.add_sample(error=5.0, co=50.0, dt=1.0)   # t=1, contrib: 1*5=5
        calc.add_sample(error=-3.0, co=50.0, dt=1.0)   # t=2, contrib: 2*3=6
        calc.add_sample(error=2.0, co=50.0, dt=1.0)    # t=3, contrib: 3*2=6
        assert calc.itae == pytest.approx(17.0)

    def test_ise_accumulates_squared_error(self):
        from smart_pid_core.domain.services.stats_calculator import StatsCalculator

        calc = StatsCalculator(window_size=100, span=100.0, setpoint=50.0)
        calc.add_sample(error=3.0, co=50.0, dt=1.0)
        calc.add_sample(error=4.0, co=50.0, dt=1.0)
        assert calc.ise == pytest.approx(25.0)  # 9+16=25

    def test_mse_is_mean_squared_error(self):
        from smart_pid_core.domain.services.stats_calculator import StatsCalculator

        calc = StatsCalculator(window_size=100, span=100.0, setpoint=50.0)
        calc.add_sample(error=3.0, co=50.0, dt=1.0)
        calc.add_sample(error=4.0, co=50.0, dt=1.0)
        assert calc.mse == pytest.approx(12.5)  # 25/2

    def test_std_dev_of_constant_is_zero(self):
        from smart_pid_core.domain.services.stats_calculator import StatsCalculator

        calc = StatsCalculator(window_size=100, span=100.0, setpoint=50.0)
        for _ in range(10):
            calc.add_sample(error=5.0, co=50.0, dt=1.0)
        assert calc.std_dev == pytest.approx(0.0)

    def test_std_dev_known_series(self):
        from smart_pid_core.domain.services.stats_calculator import StatsCalculator

        calc = StatsCalculator(window_size=100, span=100.0, setpoint=50.0)
        values = [2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0]
        for v in values:
            calc.add_sample(error=v, co=50.0, dt=1.0)
        # std dev of [2,4,4,4,5,5,7,9] = 2.0 (population)
        assert calc.std_dev == pytest.approx(2.0, abs=0.01)

    def test_total_variation_counts_co_changes(self):
        from smart_pid_core.domain.services.stats_calculator import StatsCalculator

        calc = StatsCalculator(window_size=100, span=100.0, setpoint=50.0)
        calc.add_sample(error=0.0, co=50.0, dt=1.0)
        calc.add_sample(error=0.0, co=55.0, dt=1.0)  # delta: 5
        calc.add_sample(error=0.0, co=52.0, dt=1.0)  # delta: 3
        calc.add_sample(error=0.0, co=58.0, dt=1.0)  # delta: 6
        assert calc.total_variation == pytest.approx(14.0)

    def test_variability_sp(self):
        from smart_pid_core.domain.services.stats_calculator import StatsCalculator

        calc = StatsCalculator(window_size=100, span=100.0, setpoint=50.0)
        values = [2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0]
        for v in values:
            calc.add_sample(error=v, co=50.0, dt=1.0)
        # variability_sp = 2*sigma/SP = 2*2.0/50.0 = 0.08
        assert calc.variability_sp == pytest.approx(0.08, abs=0.01)

    def test_variability_range(self):
        from smart_pid_core.domain.services.stats_calculator import StatsCalculator

        calc = StatsCalculator(window_size=100, span=100.0, setpoint=50.0)
        values = [2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0]
        for v in values:
            calc.add_sample(error=v, co=50.0, dt=1.0)
        # variability_range = 2*sigma/SPAN = 2*2.0/100.0 = 0.04
        assert calc.variability_range == pytest.approx(0.04, abs=0.01)


class TestStatsCalculatorWindow:
    def test_sliding_window_evicts_old_samples(self):
        from smart_pid_core.domain.services.stats_calculator import StatsCalculator

        calc = StatsCalculator(window_size=3, span=100.0, setpoint=50.0)
        calc.add_sample(error=10.0, co=50.0, dt=1.0)
        calc.add_sample(error=20.0, co=50.0, dt=1.0)
        calc.add_sample(error=30.0, co=50.0, dt=1.0)
        # Window: [10, 20, 30], IAE = 60
        assert calc.iae == pytest.approx(60.0)

        calc.add_sample(error=5.0, co=50.0, dt=1.0)
        # Window: [20, 30, 5], IAE recomputed from window
        assert calc.sample_count == 3

    def test_reset_clears_all(self):
        from smart_pid_core.domain.services.stats_calculator import StatsCalculator

        calc = StatsCalculator(window_size=100, span=100.0, setpoint=50.0)
        calc.add_sample(error=5.0, co=50.0, dt=1.0)
        calc.reset()
        assert calc.iae == 0.0
        assert calc.sample_count == 0
