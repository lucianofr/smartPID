"""Integration test: MockTelemetrySource -> BusBridge -> ControllerCardWidget."""

from smart_pid_hmi.bus_bridge import BusBridge
from smart_pid_hmi.services.mock_service import MockTelemetrySource
from smart_pid_hmi.themes.isa101 import ISA101Theme
from smart_pid_hmi.widgets.controller_card import ControllerCardWidget


def test_mock_to_bridge_to_card(qtbot):
    """Full pipeline: mock generates data -> bridge emits -> card updates."""
    theme = ISA101Theme()

    source = MockTelemetrySource(interval_ms=50)
    bridge = BusBridge(queue=source.queue, refresh_ms=20)

    card = ControllerCardWidget(
        controller_id=1, tag_name="FIC-101",
        min_val=0.0, max_val=100.0, theme=theme,
    )
    qtbot.addWidget(card)

    bridge.telemetry_received.connect(card.on_telemetry)

    source.start()
    bridge.start()

    # Wait for at least one telemetry update to reach the card
    with qtbot.waitSignal(bridge.telemetry_received, timeout=2000):
        pass

    # Card should have updated PV
    assert card._bar_pv.value != 0.0

    bridge.stop()
    source.stop()


def test_mock_api_login_and_list(qtbot):
    """Verify mock API login + list_controllers returns valid data."""
    from smart_pid_hmi.services.mock_service import MockAPIClient
    from smart_pid_hmi.services.session import Session

    client = MockAPIClient()
    session = Session()

    resp = client.login("admin", "pass")
    session.store_token(resp.access_token)
    assert session.is_authenticated

    controllers = client.list_controllers()
    assert len(controllers) == 3
    assert all(c.id > 0 for c in controllers)
