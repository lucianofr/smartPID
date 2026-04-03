"""Shared fixtures for HMI tests."""
import pytest

from smart_pid_hmi.themes.isa101 import ISA101Theme


@pytest.fixture
def theme():
    return ISA101Theme()
