"""Tests for SVGOverlayWidget."""
from PySide6.QtWidgets import QLabel

from smart_pid_hmi.widgets.svg_overlay import SVGOverlayWidget


def test_creation(qtbot):
    widget = SVGOverlayWidget()
    qtbot.addWidget(widget)
    assert widget is not None


def test_load_svg(qtbot, tmp_path):
    svg_file = tmp_path / "test.svg"
    svg_file.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="200" height="200">'
        '<rect width="200" height="200" fill="gray"/>'
        "</svg>"
    )
    widget = SVGOverlayWidget()
    qtbot.addWidget(widget)
    widget.load_svg(str(svg_file))
    assert widget._svg_widget is not None


def test_add_overlay(qtbot):
    widget = SVGOverlayWidget()
    qtbot.addWidget(widget)
    widget.add_overlay("tag1", 10, 20, "PV: 50.0")
    assert "tag1" in widget._overlays
    label = widget._overlays["tag1"]
    assert isinstance(label, QLabel)
    assert label.text() == "PV: 50.0"


def test_update_overlay(qtbot):
    widget = SVGOverlayWidget()
    qtbot.addWidget(widget)
    widget.add_overlay("tag1", 10, 20, "PV: 50.0")
    widget.update_overlay("tag1", "PV: 60.0")
    assert widget._overlays["tag1"].text() == "PV: 60.0"


def test_remove_overlay(qtbot):
    widget = SVGOverlayWidget()
    qtbot.addWidget(widget)
    widget.add_overlay("tag1", 10, 20, "PV: 50.0")
    widget.remove_overlay("tag1")
    assert "tag1" not in widget._overlays


def test_clear_overlays(qtbot):
    widget = SVGOverlayWidget()
    qtbot.addWidget(widget)
    widget.add_overlay("tag1", 10, 20, "PV: 50.0")
    widget.add_overlay("tag2", 30, 40, "SP: 55.0")
    widget.clear_overlays()
    assert len(widget._overlays) == 0
