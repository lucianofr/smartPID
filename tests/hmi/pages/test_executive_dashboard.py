"""Tests for ExecutiveDashboardPage."""
from PySide6.QtWidgets import QLabel, QPushButton, QTableWidget, QWidget

from smart_pid_hmi.pages.executive_dashboard import (
    ExecutiveDashboardPage,
    _ControllerCard,
    _FlowLayout,
)


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


# --- _ControllerCard tests ---


def _make_controller_data(**overrides) -> dict:
    """Helper: minimal controller data dict with sensible defaults."""
    base = {
        "name": "FIC-101",
        "mode": "AUTO",
        "execution_mode": "DDC",
        "pv": 50.0,
        "sp": 50.0,
        "sp_hi_lim": 100.0,
        "sp_lo_lim": 0.0,
        "ai_config": {
            "engine": "NONE",
            "objective": "DISTURBANCE_REJECTION",
        },
    }
    base.update(overrides)
    return base


def test_controller_card_creation(qtbot):
    card = _ControllerCard()
    qtbot.addWidget(card)
    assert card is not None


def test_controller_card_shows_name_and_mode(qtbot):
    card = _ControllerCard()
    qtbot.addWidget(card)
    card.update_data(_make_controller_data(name="TIC-301", mode="MAN"))
    assert card._name_label.text() == "TIC-301"
    assert card._mode_badge.text() == "MAN"


def test_controller_card_shows_process_values(qtbot):
    card = _ControllerCard()
    qtbot.addWidget(card)
    card.update_data(_make_controller_data(pv=72.5, sp=70.0))
    assert card._pv_value.text() == "72.5"
    assert card._sp_value.text() == "70.0"


def test_controller_card_shows_error_pct(qtbot):
    card = _ControllerCard()
    qtbot.addWidget(card)
    card.update_data(_make_controller_data(
        pv=55.0, sp=50.0, sp_hi_lim=100.0, sp_lo_lim=0.0,
    ))
    assert card._error_value.text() == "5.0%"


def test_controller_card_shows_ai_info_fuzzy(qtbot):
    card = _ControllerCard()
    qtbot.addWidget(card)
    card.update_data(_make_controller_data(
        ai_config={"engine": "FUZZY", "objective": "SP_TRACKING"},
        ai_state="RUN",
        ai_gamma=0.12,
    ))
    assert card._engine_badge.text() == "FUZZY"
    assert card._objective_value.text() == "SP_TRACKING"
    assert card._ai_state_value.text() == "RUN"
    assert card._gamma_value.text() == "0.12"


def test_controller_card_ai_none_shows_disabled(qtbot):
    card = _ControllerCard()
    qtbot.addWidget(card)
    card.update_data(_make_controller_data(
        ai_config={"engine": "NONE", "objective": "DISTURBANCE_REJECTION"},
    ))
    assert card._engine_badge.text() == "NONE"
    assert card._ai_state_value.text() == "Disabled"
    assert card._gamma_value.text() == "\u2014"


def test_controller_card_shows_execution_mode(qtbot):
    card = _ControllerCard()
    qtbot.addWidget(card)
    card.update_data(_make_controller_data(execution_mode="SUPERVISORY"))
    assert card._exec_badge.text() == "SUPERVISORY"


def test_controller_card_shows_performance_metrics(qtbot):
    card = _ControllerCard()
    qtbot.addWidget(card)
    card.update_data(_make_controller_data(
        iae=12.5, itae=45.2, ise=8.1, mse=2.3,
        std_dev=1.8, total_variation=34.1,
        variability_sp=3.6, variability_range=1.2,
    ))
    assert card._perf_values["IAE"].text() == "12.5"
    assert card._perf_values["ITAE"].text() == "45.2"
    assert card._perf_values["ISE"].text() == "8.1"
    assert card._perf_values["MSE"].text() == "2.3"
    assert card._perf_values["Std Dev"].text() == "1.8"
    assert card._perf_values["TV"].text() == "34.1"
    assert card._perf_values["Var/SP"].text() == "3.6%"
    assert card._perf_values["Var/Rng"].text() == "1.2%"


def test_controller_card_placeholder_when_no_stats(qtbot):
    card = _ControllerCard()
    qtbot.addWidget(card)
    card.update_data(_make_controller_data())  # no stats keys
    assert card._perf_values["IAE"].text() == "\u2014"
    assert card._perf_values["TV"].text() == "\u2014"
