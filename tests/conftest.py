"""Shared test fixtures for Smart PID."""
from __future__ import annotations

import pytest


@pytest.fixture
def sample_pid_params() -> dict:
    """Standard PID parameters for testing."""
    return {
        "gain": 1.5,
        "reset": 10.0,
        "rate": 2.0,
        "alpha": 0.125,
        "deadband": 0.0,
    }
