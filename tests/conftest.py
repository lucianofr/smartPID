"""Root test configuration for the Smart PID platform."""
from __future__ import annotations

import pytest

from smart_pid_domain.models.controller import PIDParams


@pytest.fixture
def sample_pid_params() -> PIDParams:
    return PIDParams(gain=1.5, reset=10.0, rate=2.0, alpha=0.125, deadband=0.0)
