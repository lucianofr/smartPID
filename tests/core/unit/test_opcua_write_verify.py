"""Unit tests for OPC-UA write read-back verification + retry."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

from smart_pid_core.adapters.outbound.opcua_adapter import OPCUAAdapter
from smart_pid_core.config import CoreSettings
from smart_pid_domain.enums import ConnectionState


def _make_online_adapter() -> OPCUAAdapter:
    """Return an OPCUAAdapter forced to ONLINE with zero verify delay so
    asyncio tests don't have to sleep for real.
    """
    settings = CoreSettings(
        jwt_secret="test-secret-key-minimum-32-bytes!",
        opcua_endpoint="opc.tcp://localhost:49999",
    )  # type: ignore[call-arg]
    adapter = OPCUAAdapter(settings=settings)
    adapter._state = ConnectionState.ONLINE  # pretend connected
    # Make verify nearly instant for tests
    adapter._VERIFY_DELAY_S = 0.0  # type: ignore[misc]
    return adapter


def _mock_client_with_read_sequence(values: list[float]) -> MagicMock:
    """Build a mock asyncua.Client whose read_value returns ``values`` in order.

    write_value is recorded so tests can assert retry behaviour.
    """
    iterator = iter(values)

    async def read_value() -> float:
        return next(iterator)

    node = MagicMock()
    node.read_value = AsyncMock(side_effect=read_value)
    node.write_value = AsyncMock()

    client = MagicMock()
    client.get_node = MagicMock(return_value=node)
    return client


class TestVerifyWriteFloat:
    def test_value_matches_on_first_read_returns_true(self):
        adapter = _make_online_adapter()
        client = _mock_client_with_read_sequence([13.5])  # matches expected
        node = client.get_node.return_value

        ok = asyncio.run(
            adapter._async_verify_write_float(client, "ns=2;s=Ti", 13.5),
        )
        assert ok is True
        # No retry write happened
        assert node.write_value.await_count == 0

    def test_small_drift_within_tolerance_is_ok(self):
        adapter = _make_online_adapter()
        # Expected 13.5, actual 13.503 → diff 0.003, tolerance 0.5% of 13.5 = 0.0675
        client = _mock_client_with_read_sequence([13.503])

        ok = asyncio.run(
            adapter._async_verify_write_float(client, "ns=2;s=Ti", 13.5),
        )
        assert ok is True

    def test_mismatch_retries_write_then_succeeds(self):
        adapter = _make_online_adapter()
        # First read returns stale value, second read (after retry write) matches
        client = _mock_client_with_read_sequence([10.0, 13.5])
        node = client.get_node.return_value

        ok = asyncio.run(
            adapter._async_verify_write_float(client, "ns=2;s=Ti", 13.5),
        )
        assert ok is True
        assert node.write_value.await_count == 1, "expected one retry write"

    def test_exhausted_retries_returns_false(self):
        adapter = _make_online_adapter()
        # Value never matches — 3 reads (initial + 2 retries)
        client = _mock_client_with_read_sequence([10.0, 10.0, 10.0])
        node = client.get_node.return_value

        ok = asyncio.run(
            adapter._async_verify_write_float(client, "ns=2;s=Ti", 13.5),
        )
        assert ok is False
        # _VERIFY_MAX_RETRIES = 2 → 2 rewrites attempted
        assert node.write_value.await_count == 2

    def test_goes_offline_mid_check_aborts_gracefully(self):
        adapter = _make_online_adapter()
        client = _mock_client_with_read_sequence([13.5])

        async def scenario() -> bool:
            # Simulate disconnect before the first read
            adapter._state = ConnectionState.OFFLINE
            return await adapter._async_verify_write_float(
                client, "ns=2;s=Ti", 13.5,
            )

        ok = asyncio.run(scenario())
        assert ok is False


class TestVerifyWriteInt:
    def test_int_match_returns_true(self):
        adapter = _make_online_adapter()
        client = _mock_client_with_read_sequence([2])  # AUTO mode int
        node = client.get_node.return_value

        ok = asyncio.run(
            adapter._async_verify_write_int(client, "ns=2;s=Mode", 2),
        )
        assert ok is True
        assert node.write_value.await_count == 0

    def test_int_mismatch_retries_then_succeeds(self):
        adapter = _make_online_adapter()
        # Stale mode=1 first, then correct mode=2
        client = _mock_client_with_read_sequence([1, 2])
        node = client.get_node.return_value

        ok = asyncio.run(
            adapter._async_verify_write_int(client, "ns=2;s=Mode", 2),
        )
        assert ok is True
        assert node.write_value.await_count == 1

    def test_int_exact_match_required(self):
        """Floats don't match ints when comparing mode. 2.0 vs 2 → ok; 1.9 vs 2 → retry."""
        adapter = _make_online_adapter()
        # 2.0 reads back as int(2.0) = 2, matches 2
        client = _mock_client_with_read_sequence([2.0])
        ok = asyncio.run(
            adapter._async_verify_write_int(client, "ns=2;s=Mode", 2),
        )
        assert ok is True


class TestToleranceBoundary:
    def test_just_inside_tolerance_ok(self):
        adapter = _make_online_adapter()
        # Expected 100.0 → tolerance = max(0.001, 100 * 0.005) = 0.5
        # Actual 100.499 is within.
        client = _mock_client_with_read_sequence([100.499])
        ok = asyncio.run(
            adapter._async_verify_write_float(client, "n", 100.0),
        )
        assert ok is True

    def test_just_outside_tolerance_retries(self):
        adapter = _make_online_adapter()
        # 100.6 is outside tolerance of 0.5
        client = _mock_client_with_read_sequence([100.6, 100.6, 100.6])
        node = client.get_node.return_value
        ok = asyncio.run(
            adapter._async_verify_write_float(client, "n", 100.0),
        )
        assert ok is False
        assert node.write_value.await_count == 2
