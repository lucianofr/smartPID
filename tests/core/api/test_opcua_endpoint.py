"""Tests for OPC-UA endpoint persistence and connect-with-endpoint."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest


class TestOPCUAAdapterSetEndpoint:
    """OPCUAAdapter.set_endpoint() stops adapter and updates endpoint."""

    def test_set_endpoint_updates_endpoint(self):
        from smart_pid_core.adapters.outbound.opcua_adapter import OPCUAAdapter

        settings = MagicMock()
        settings.opcua_endpoint = "opc.tcp://old:4840"
        settings.opcua_timeout_s = 5.0
        settings.opcua_retry_max_s = 60.0
        adapter = OPCUAAdapter(settings)

        assert adapter.endpoint == "opc.tcp://old:4840"

        adapter.set_endpoint("opc.tcp://new:4840")

        assert adapter.endpoint == "opc.tcp://new:4840"

    def test_set_endpoint_stops_adapter(self):
        from smart_pid_core.adapters.outbound.opcua_adapter import OPCUAAdapter
        from smart_pid_domain.enums import ConnectionState

        settings = MagicMock()
        settings.opcua_endpoint = "opc.tcp://old:4840"
        settings.opcua_timeout_s = 5.0
        settings.opcua_retry_max_s = 60.0
        adapter = OPCUAAdapter(settings)

        adapter.set_endpoint("opc.tcp://new:4840")

        assert adapter.state == ConnectionState.OFFLINE
