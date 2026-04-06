"""Tests for ExecutiveDashboardPage."""
from PySide6.QtWidgets import QLabel, QPushButton, QTableWidget, QWidget

from smart_pid_hmi.pages.executive_dashboard import ExecutiveDashboardPage, _FlowLayout


def test_creation(qtbot):
    page = ExecutiveDashboardPage()
    qtbot.addWidget(page)
    assert page is not None


def test_has_title(qtbot):
    page = ExecutiveDashboardPage()
    qtbot.addWidget(page)
    title = page.findChild(QLabel, "title_label")
    assert title is not None
    assert title.text() == "Executive Dashboard"


def test_has_kpi_labels(qtbot):
    page = ExecutiveDashboardPage()
    qtbot.addWidget(page)
    assert page._kpi_total is not None
    assert page._kpi_auto is not None
    assert page._kpi_alarms is not None
    assert page._kpi_ai is not None


def test_has_performance_table(qtbot):
    page = ExecutiveDashboardPage()
    qtbot.addWidget(page)
    table = page.findChild(QTableWidget, "performance_table")
    assert table is not None
    assert table.columnCount() == 7


def test_update_kpis(qtbot):
    page = ExecutiveDashboardPage()
    qtbot.addWidget(page)
    page.update_kpis(total=10, in_auto=7, active_alarms=3, ai_active=2)
    assert page._kpi_total.text() == "10"
    assert page._kpi_auto.text() == "7"
    assert page._kpi_alarms.text() == "3"
    assert page._kpi_ai.text() == "2"


def test_update_performance_table(qtbot):
    page = ExecutiveDashboardPage()
    qtbot.addWidget(page)
    rows = [
        {
            "loop": "FIC-101",
            "mode": "AUTO",
            "pv": 45.2,
            "sp": 50.0,
            "error_pct": 9.6,
            "iae": 12.5,
            "status": "GOOD",
        },
        {
            "loop": "TIC-201",
            "mode": "MAN",
            "pv": 80.0,
            "sp": 80.0,
            "error_pct": 0.0,
            "iae": 0.1,
            "status": "GOOD",
        },
    ]
    page.update_performance_table(rows)
    table = page.findChild(QTableWidget, "performance_table")
    assert table.rowCount() == 2
    assert table.item(0, 0).text() == "FIC-101"
    assert table.item(1, 1).text() == "MAN"


def test_flow_layout_add_and_count(qtbot):
    container = QWidget()
    qtbot.addWidget(container)
    layout = _FlowLayout(container, h_spacing=10, v_spacing=10)
    layout.addWidget(QPushButton("A"))
    layout.addWidget(QPushButton("B"))
    layout.addWidget(QPushButton("C"))
    assert layout.count() == 3


def test_flow_layout_item_at(qtbot):
    container = QWidget()
    qtbot.addWidget(container)
    layout = _FlowLayout(container, h_spacing=10, v_spacing=10)
    btn = QPushButton("A")
    layout.addWidget(btn)
    assert layout.itemAt(0).widget() is btn
    assert layout.itemAt(1) is None
