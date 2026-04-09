"""Tests for AI settings groups in SettingsPage (Fuzzy, RL, AI Worker)."""
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDoubleSpinBox, QGroupBox, QSpinBox

from smart_pid_hmi.pages.settings_page import SettingsPage
from smart_pid_hmi.themes.isa101 import ISA101Theme
from smart_pid_hmi.themes.manager import ThemeManager


def _make_manager():
    mgr = ThemeManager()
    mgr.register(ISA101Theme())
    mgr.set_theme("isa101")
    return mgr


class TestTwoColumnLayout:
    """Settings page has left/right column layout."""

    def test_has_left_and_right_columns(self, qtbot):
        page = SettingsPage(theme_manager=_make_manager())
        qtbot.addWidget(page)
        assert page._left_column is not None
        assert page._right_column is not None

    def test_existing_groups_in_left_column(self, qtbot):
        page = SettingsPage(theme_manager=_make_manager())
        qtbot.addWidget(page)
        # Project, Appearance, Connection, Performance, OPC-UA should be on the left
        left_groups = page._left_column.findChildren(QGroupBox)
        group_titles = {g.title() for g in left_groups}
        assert "Project" in group_titles
        assert "Appearance" in group_titles
        assert "Connection" in group_titles

    def test_ai_groups_in_right_column(self, qtbot):
        page = SettingsPage(theme_manager=_make_manager())
        qtbot.addWidget(page)
        right_groups = page._right_column.findChildren(QGroupBox)
        group_titles = {g.title() for g in right_groups}
        assert "Fuzzy Engine" in group_titles
        assert "RL Engine" in group_titles
        assert "AI Worker" in group_titles


class TestFuzzySettingsGroup:
    """Fuzzy Engine settings group with relevant parameters."""

    def test_speed_factor_spinbox_exists(self, qtbot):
        page = SettingsPage(theme_manager=_make_manager())
        qtbot.addWidget(page)
        spin = page.findChild(QDoubleSpinBox, "fuzzy_speed_factor")
        assert spin is not None
        assert spin.value() == 0.15  # default FAST

    def test_speed_factor_has_tooltip(self, qtbot):
        page = SettingsPage(theme_manager=_make_manager())
        qtbot.addWidget(page)
        spin = page.findChild(QDoubleSpinBox, "fuzzy_speed_factor")
        assert spin.toolTip() != ""
        assert "Sv" in spin.toolTip() or "aggressiveness" in spin.toolTip().lower()

    def test_limit_min_spinbox_exists(self, qtbot):
        page = SettingsPage(theme_manager=_make_manager())
        qtbot.addWidget(page)
        spin = page.findChild(QDoubleSpinBox, "fuzzy_limit_min")
        assert spin is not None
        assert spin.value() == 0.1

    def test_limit_max_spinbox_exists(self, qtbot):
        page = SettingsPage(theme_manager=_make_manager())
        qtbot.addWidget(page)
        spin = page.findChild(QDoubleSpinBox, "fuzzy_limit_max")
        assert spin is not None
        assert spin.value() == 100.0

    def test_limit_min_has_tooltip(self, qtbot):
        page = SettingsPage(theme_manager=_make_manager())
        qtbot.addWidget(page)
        spin = page.findChild(QDoubleSpinBox, "fuzzy_limit_min")
        assert "minimum" in spin.toolTip().lower() or "clamp" in spin.toolTip().lower()

    def test_limit_max_has_tooltip(self, qtbot):
        page = SettingsPage(theme_manager=_make_manager())
        qtbot.addWidget(page)
        spin = page.findChild(QDoubleSpinBox, "fuzzy_limit_max")
        assert "maximum" in spin.toolTip().lower() or "clamp" in spin.toolTip().lower()

    def test_dead_time_spinbox_exists(self, qtbot):
        page = SettingsPage(theme_manager=_make_manager())
        qtbot.addWidget(page)
        spin = page.findChild(QDoubleSpinBox, "fuzzy_dead_time")
        assert spin is not None
        assert spin.value() == 1.0

    def test_dead_time_has_tooltip(self, qtbot):
        page = SettingsPage(theme_manager=_make_manager())
        qtbot.addWidget(page)
        spin = page.findChild(QDoubleSpinBox, "fuzzy_dead_time")
        assert "dead time" in spin.toolTip().lower()


class TestRLSettingsGroup:
    """RL Engine settings group with relevant parameters."""

    def test_fallback_kp_spinbox_exists(self, qtbot):
        page = SettingsPage(theme_manager=_make_manager())
        qtbot.addWidget(page)
        spin = page.findChild(QDoubleSpinBox, "rl_fallback_kp")
        assert spin is not None
        assert spin.value() == 0.5

    def test_fallback_kd_spinbox_exists(self, qtbot):
        page = SettingsPage(theme_manager=_make_manager())
        qtbot.addWidget(page)
        spin = page.findChild(QDoubleSpinBox, "rl_fallback_kd")
        assert spin is not None
        assert spin.value() == 0.2

    def test_learning_rate_spinbox_exists(self, qtbot):
        page = SettingsPage(theme_manager=_make_manager())
        qtbot.addWidget(page)
        spin = page.findChild(QDoubleSpinBox, "rl_learning_rate")
        assert spin is not None

    def test_train_interval_spinbox_exists(self, qtbot):
        page = SettingsPage(theme_manager=_make_manager())
        qtbot.addWidget(page)
        spin = page.findChild(QSpinBox, "rl_train_interval")
        assert spin is not None
        assert spin.value() == 32

    def test_fallback_kp_has_tooltip(self, qtbot):
        page = SettingsPage(theme_manager=_make_manager())
        qtbot.addWidget(page)
        spin = page.findChild(QDoubleSpinBox, "rl_fallback_kp")
        assert "fallback" in spin.toolTip().lower() or "proportional" in spin.toolTip().lower()

    def test_fallback_kd_has_tooltip(self, qtbot):
        page = SettingsPage(theme_manager=_make_manager())
        qtbot.addWidget(page)
        spin = page.findChild(QDoubleSpinBox, "rl_fallback_kd")
        assert "fallback" in spin.toolTip().lower() or "derivative" in spin.toolTip().lower()

    def test_learning_rate_has_tooltip(self, qtbot):
        page = SettingsPage(theme_manager=_make_manager())
        qtbot.addWidget(page)
        spin = page.findChild(QDoubleSpinBox, "rl_learning_rate")
        assert "learning" in spin.toolTip().lower()

    def test_train_interval_has_tooltip(self, qtbot):
        page = SettingsPage(theme_manager=_make_manager())
        qtbot.addWidget(page)
        spin = page.findChild(QSpinBox, "rl_train_interval")
        assert "train" in spin.toolTip().lower() or "interval" in spin.toolTip().lower()


class TestAIWorkerSettingsGroup:
    """AI Worker settings — period based on ProcessSpeed."""

    def test_ai_period_spinbox_exists(self, qtbot):
        page = SettingsPage(theme_manager=_make_manager())
        qtbot.addWidget(page)
        spin = page.findChild(QSpinBox, "ai_period")
        assert spin is not None

    def test_ai_period_default_value(self, qtbot):
        """Default period matches MEDIUM process speed (1800s)."""
        page = SettingsPage(theme_manager=_make_manager())
        qtbot.addWidget(page)
        spin = page.findChild(QSpinBox, "ai_period")
        assert spin.value() == 1800

    def test_ai_period_has_tooltip(self, qtbot):
        page = SettingsPage(theme_manager=_make_manager())
        qtbot.addWidget(page)
        spin = page.findChild(QSpinBox, "ai_period")
        assert "period" in spin.toolTip().lower() or "cycle" in spin.toolTip().lower()

    def test_ai_period_suffix(self, qtbot):
        page = SettingsPage(theme_manager=_make_manager())
        qtbot.addWidget(page)
        spin = page.findChild(QSpinBox, "ai_period")
        assert spin.suffix() == " s"

    def test_ai_period_range(self, qtbot):
        """AI period allows 1s to 86400s (24h)."""
        page = SettingsPage(theme_manager=_make_manager())
        qtbot.addWidget(page)
        spin = page.findChild(QSpinBox, "ai_period")
        assert spin.minimum() == 1
        assert spin.maximum() == 86400


class TestAISettingsLoadFromController:
    """Loading AI settings from a controller dict."""

    def test_load_ai_settings(self, qtbot):
        page = SettingsPage(theme_manager=_make_manager())
        qtbot.addWidget(page)
        page.load_ai_settings({
            "speed_factor": 0.30,
            "limit_min": 0.5,
            "limit_max": 50.0,
            "dead_time_l": 2.5,
            "ai_period_s": 30,
            "rl_fallback_kp": 0.8,
            "rl_fallback_kd": 0.3,
            "rl_learning_rate": 1e-3,
            "rl_train_interval": 64,
        })
        assert page._fuzzy_speed_factor.value() == pytest.approx(0.30)
        assert page._fuzzy_limit_min.value() == pytest.approx(0.5)
        assert page._fuzzy_limit_max.value() == pytest.approx(50.0)
        assert page._fuzzy_dead_time.value() == pytest.approx(2.5)
        assert page._ai_period.value() == 30
        assert page._rl_fallback_kp.value() == pytest.approx(0.8)
        assert page._rl_fallback_kd.value() == pytest.approx(0.3)
        assert page._rl_learning_rate.value() == pytest.approx(1e-3)
        assert page._rl_train_interval.value() == 64

    def test_get_ai_settings(self, qtbot):
        """get_ai_settings() returns current values as a dict."""
        page = SettingsPage(theme_manager=_make_manager())
        qtbot.addWidget(page)
        settings = page.get_ai_settings()
        assert "speed_factor" in settings
        assert "limit_min" in settings
        assert "ai_period_s" in settings
        assert "rl_fallback_kp" in settings


class TestAISettingsApplyCancel:
    """AI settings participate in Apply/Cancel pattern."""

    def test_changing_ai_field_enables_apply(self, qtbot):
        page = SettingsPage(theme_manager=_make_manager())
        qtbot.addWidget(page)
        assert not page._apply_btn.isEnabled()
        page._fuzzy_speed_factor.setValue(0.50)
        assert page._apply_btn.isEnabled()

    def test_cancel_reverts_ai_fields(self, qtbot):
        page = SettingsPage(theme_manager=_make_manager())
        qtbot.addWidget(page)
        original = page._fuzzy_speed_factor.value()
        page._fuzzy_speed_factor.setValue(0.99)
        page._cancel_btn.click()
        assert page._fuzzy_speed_factor.value() == pytest.approx(original)

    def test_apply_emits_ai_settings_changed(self, qtbot):
        page = SettingsPage(theme_manager=_make_manager())
        qtbot.addWidget(page)
        received = []
        page.ai_settings_changed.connect(received.append)
        page._fuzzy_speed_factor.setValue(0.50)
        page._apply_btn.click()
        assert len(received) == 1
        assert received[0]["speed_factor"] == pytest.approx(0.50)
