"""FaceplateWidget — detailed operation panel for selected controller."""
from __future__ import annotations

import time
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from smart_pid_hmi.widgets.analog_bar import AnalogBarWidget

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget

    from smart_pid_hmi.themes.base import ThemeBase


def _theme_attr(theme: ThemeBase, attr: str, fallback: str) -> str:
    """Return theme attribute if non-empty, else fallback."""
    val = getattr(theme, attr, "")
    return val if val else fallback


# Badge color schemes: (background, text_color)
_FP_AI_ENGINE_COLORS: dict[str, tuple[str, str]] = {
    "FUZZY": ("#4A148C", "#CE93D8"),  # purple
    "RL": ("#006064", "#80DEEA"),     # teal
    "NONE": ("#424242", "#9E9E9E"),   # gray
}
_FP_AI_DEFAULT = ("#424242", "#9E9E9E")


def _separator(theme: ThemeBase) -> QFrame:
    """Create a horizontal separator line."""
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setFixedHeight(1)
    line.setStyleSheet(
        f"background-color: {theme.border}; border: none;"
    )
    return line


class FaceplateWidget(QFrame):
    """Detailed control panel for a single controller."""

    setpoint_requested = Signal(int, float)    # (controller_id, value)
    mode_requested = Signal(int, str)          # (controller_id, mode)
    output_requested = Signal(int, float)      # (controller_id, value)
    optimizer_run_requested = Signal(int)      # (controller_id)
    optimizer_stop_requested = Signal(int)     # (controller_id)
    gains_changed = Signal(int, dict)          # (controller_id, {gain, reset, rate})

    def __init__(
        self, theme: ThemeBase, parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._theme = theme
        self._controller_id: int | None = None
        self._active_mode: str = ""
        self._separators: list[QFrame] = []

        self.setFrameShape(QFrame.Shape.NoFrame)
        self._apply_frame_style(theme)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        # -- Header --
        self._tag_label = QLabel("\u2014")
        self._tag_label.setStyleSheet(
            f"font-size: {theme.font_size_title + 2}px; "
            f"font-weight: bold; "
            f"color: {theme.fg_primary}; background: transparent;"
        )
        self._ai_engine_badge = QLabel("NONE")
        self._current_ai_engine = "NONE"
        self._apply_ai_engine_badge(theme)
        header = QHBoxLayout()
        header.addWidget(self._tag_label)
        header.addStretch()
        header.addWidget(self._ai_engine_badge)
        layout.addLayout(header)

        # -- Separator --
        sep1 = _separator(theme)
        self._separators.append(sep1)
        layout.addWidget(sep1)

        # -- Bars (created with defaults, replaced on controller select) --
        self._bar_pv = AnalogBarWidget("PV", "", 0.0, 100.0, theme)
        self._bar_sp = AnalogBarWidget("SP", "", 0.0, 100.0, theme)
        self._bar_co = AnalogBarWidget("CO", "%", 0.0, 100.0, theme)
        layout.addWidget(self._bar_pv)
        layout.addWidget(self._bar_sp)
        layout.addWidget(self._bar_co)

        # -- Separator --
        sep2 = _separator(theme)
        self._separators.append(sep2)
        layout.addWidget(sep2)

        # -- SP input --
        sp_row = QHBoxLayout()
        sp_row.setSpacing(8)
        sp_lbl = QLabel("SP Local:")
        sp_lbl.setStyleSheet(
            f"color: {theme.fg_secondary}; background: transparent; "
            f"font-size: {theme.font_size_label}px; font-weight: bold;"
        )
        sp_lbl.setFixedWidth(70)
        sp_row.addWidget(sp_lbl)
        self._sp_input = QLineEdit()
        self._sp_input.setPlaceholderText("Enter SP")
        self._apply_input_style(self._sp_input, theme)
        self._sp_input.returnPressed.connect(self._on_sp_enter)
        sp_row.addWidget(self._sp_input)
        layout.addLayout(sp_row)

        # -- CO input --
        co_row = QHBoxLayout()
        co_row.setSpacing(8)
        co_lbl = QLabel("CO (MAN):")
        co_lbl.setStyleSheet(
            f"color: {theme.fg_secondary}; background: transparent; "
            f"font-size: {theme.font_size_label}px; font-weight: bold;"
        )
        co_lbl.setFixedWidth(70)
        co_row.addWidget(co_lbl)
        self._co_input = QLineEdit()
        self._co_input.setPlaceholderText("Enter CO")
        self._apply_input_style(self._co_input, theme)
        self._co_input.returnPressed.connect(self._on_co_enter)
        co_row.addWidget(self._co_input)
        layout.addLayout(co_row)

        # -- Separator --
        sep3 = _separator(theme)
        self._separators.append(sep3)
        layout.addWidget(sep3)

        # -- PID Mode toggle buttons --
        mode_row = QHBoxLayout()
        mode_row.setSpacing(8)
        mode_lbl = QLabel("PID Mode:")
        mode_lbl.setStyleSheet(
            f"color: {theme.fg_secondary}; background: transparent; "
            f"font-size: {theme.font_size_label}px; font-weight: bold;"
        )
        mode_row.addWidget(mode_lbl)
        self._btn_auto = QPushButton("AUTO")
        self._btn_man = QPushButton("MAN")
        self._btn_auto.setFixedHeight(32)
        self._btn_man.setFixedHeight(32)
        self._btn_auto.clicked.connect(lambda: self._on_mode("AUTO"))
        self._btn_man.clicked.connect(lambda: self._on_mode("MAN"))
        self._apply_toggle_style(theme)
        mode_row.addWidget(self._btn_auto)
        mode_row.addWidget(self._btn_man)
        mode_row.addStretch()
        layout.addLayout(mode_row)

        # -- Separator --
        sep4 = _separator(theme)
        self._separators.append(sep4)
        layout.addWidget(sep4)

        # -- AI Optimizer buttons (RUN / STOP) --
        opt_row = QHBoxLayout()
        opt_row.setSpacing(8)
        opt_lbl = QLabel("AI Optimizer:")
        opt_lbl.setStyleSheet(
            f"color: {theme.fg_secondary}; background: transparent; "
            f"font-size: {theme.font_size_label}px; font-weight: bold;"
        )
        opt_row.addWidget(opt_lbl)
        self._opt_label = opt_lbl
        self._btn_opt_run = QPushButton("RUN")
        self._btn_opt_stop = QPushButton("STOP")
        self._ai_running = False
        for btn in (self._btn_opt_run, self._btn_opt_stop):
            btn.setFixedHeight(28)
        self._btn_opt_run.clicked.connect(self._on_opt_run)
        self._btn_opt_stop.clicked.connect(self._on_opt_stop)
        self._apply_optimizer_style(theme)
        opt_row.addWidget(self._btn_opt_run)
        opt_row.addWidget(self._btn_opt_stop)
        opt_row.addStretch()
        layout.addLayout(opt_row)

        # -- Separator --
        sep5 = _separator(theme)
        self._separators.append(sep5)
        layout.addWidget(sep5)

        # -- PID Gains (editable) --
        self._integral_type = "TIME_TI"  # updated on controller select
        self._gains_write_time: float = 0.0  # suppress updates after user write
        self._sp_write_time: float = 0.0  # suppress SP updates after user write
        self._co_write_time: float = 0.0  # suppress CO updates after user write

        gains_row1 = QHBoxLayout()
        gains_row1.setSpacing(6)
        self._kp_lbl = QLabel("Kp:")
        self._kp_lbl.setFixedWidth(28)
        self._kp_lbl.setStyleSheet(self._gains_label_css(theme))
        self._kp_input = QLineEdit()
        self._kp_input.setPlaceholderText("Kp")
        self._apply_input_style(self._kp_input, theme)
        self._kp_input.returnPressed.connect(self._on_gains_changed)
        gains_row1.addWidget(self._kp_lbl)
        gains_row1.addWidget(self._kp_input)
        layout.addLayout(gains_row1)

        gains_row2 = QHBoxLayout()
        gains_row2.setSpacing(6)
        self._ti_lbl = QLabel("Ti:")
        self._ti_lbl.setFixedWidth(28)
        self._ti_lbl.setStyleSheet(self._gains_label_css(theme))
        self._ti_input = QLineEdit()
        self._ti_input.setPlaceholderText("Ti")
        self._apply_input_style(self._ti_input, theme)
        self._ti_input.returnPressed.connect(self._on_gains_changed)
        gains_row2.addWidget(self._ti_lbl)
        gains_row2.addWidget(self._ti_input)

        self._td_lbl = QLabel("Td:")
        self._td_lbl.setFixedWidth(28)
        self._td_lbl.setStyleSheet(self._gains_label_css(theme))
        self._td_input = QLineEdit()
        self._td_input.setPlaceholderText("Td")
        self._apply_input_style(self._td_input, theme)
        self._td_input.returnPressed.connect(self._on_gains_changed)
        gains_row2.addWidget(self._td_lbl)
        gains_row2.addWidget(self._td_input)
        layout.addLayout(gains_row2)

        # -- Separator --
        sep7 = _separator(theme)
        self._separators.append(sep7)
        layout.addWidget(sep7)

        # -- Performance section --
        perf_title = QLabel("Performance")
        perf_title.setStyleSheet(
            f"color: {theme.fg_secondary}; background: transparent;"
            f" font-size: {theme.font_size_label}px; font-weight: bold;"
        )
        layout.addWidget(perf_title)
        self._perf_title = perf_title

        # AI Period / Stats Window badges
        info_row = QHBoxLayout()
        info_row.setSpacing(6)
        badge_css = (
            f"color: {theme.fg_secondary}; background: {theme.bg_card};"
            f" font-size: {theme.font_size_label}px;"
            f" border-radius: 3px; padding: 2px 6px;"
            f" border: 1px solid {theme.border};"
        )
        self._ai_period_label = QLabel("AI: \u2014")
        self._ai_period_label.setStyleSheet(badge_css)
        info_row.addWidget(self._ai_period_label)
        self._stats_window_label = QLabel("Stats: \u2014")
        self._stats_window_label.setStyleSheet(badge_css)
        info_row.addWidget(self._stats_window_label)
        info_row.addStretch()
        layout.addLayout(info_row)

        # Stats as vertical list (label: value per row)
        stats_form = QFormLayout()
        stats_form.setSpacing(1)
        stats_form.setContentsMargins(0, 2, 0, 0)

        self._stat_labels: dict[str, QLabel] = {}
        stat_val_css = self._stat_val_css(theme)
        stat_lbl_css = self._stat_lbl_css(theme)
        for name in ("IAE", "ITAE", "ISE", "MSE", "StdDev", "TV",
                      "2\u03c3/Rng", "2\u03c3/SP"):
            lbl = QLabel(name)
            lbl.setStyleSheet(stat_lbl_css)
            val = QLabel("\u2014")
            val.setStyleSheet(stat_val_css)
            val.setAlignment(Qt.AlignmentFlag.AlignRight)
            stats_form.addRow(lbl, val)
            self._stat_labels[name] = val

        layout.addLayout(stats_form)
        layout.addStretch()

    def _apply_ai_engine_badge(self, theme: ThemeBase) -> None:
        """Style the AI engine badge in the header."""
        engine = self._current_ai_engine.upper()
        label = "AI RL" if engine == "RL" else engine
        bg, fg = _FP_AI_ENGINE_COLORS.get(engine, _FP_AI_DEFAULT)
        self._ai_engine_badge.setText(label)
        self._ai_engine_badge.setStyleSheet(
            f"font-size: {theme.font_size_label}px; "
            f"color: {fg}; "
            f"background-color: {bg}; padding: 2px 8px; "
            f"border-radius: 3px; border: none; font-weight: bold;"
        )

    def set_ai_engine(self, engine: str) -> None:
        """Update the AI engine badge text."""
        self._current_ai_engine = engine.upper()
        self._apply_ai_engine_badge(self._theme)

    def _apply_frame_style(self, theme: ThemeBase) -> None:
        bg = _theme_attr(theme, "bg_card", theme.bg_secondary)
        br = _theme_attr(theme, "border_radius", "0px")
        self.setStyleSheet(
            f"FaceplateWidget {{ background-color: {bg}; "
            f"border: 1px solid {theme.border}; "
            f"border-radius: {br}; }}"
        )

    def _apply_input_style(
        self, widget: QLineEdit, theme: ThemeBase,
    ) -> None:
        bg = _theme_attr(theme, "bg_input", theme.bg_widget)
        br = _theme_attr(theme, "border_radius", "0px")
        focus = _theme_attr(theme, "border_focus", theme.fg_secondary)
        widget.setStyleSheet(
            f"QLineEdit {{ "
            f"background-color: {bg}; "
            f"color: {theme.fg_primary}; "
            f"border: 1px solid {theme.border}; "
            f"border-radius: {br}; "
            f"padding: 4px 8px; "
            f"font-size: {theme.font_size_normal}px; }} "
            f"QLineEdit:focus {{ "
            f"border: 1px solid {focus}; }}"
        )

    def _apply_toggle_style(self, theme: ThemeBase) -> None:
        """Style mode buttons as flat toggle switches."""
        accent = _theme_attr(theme, "accent", theme.fg_secondary)
        br = _theme_attr(theme, "border_radius", "0px")
        bg_dim = _theme_attr(theme, "bg_input", theme.bg_widget)
        fg_muted = _theme_attr(theme, "fg_muted", theme.fg_secondary)
        for btn, is_active in [
            (self._btn_auto, self._active_mode == "AUTO"),
            (self._btn_man, self._active_mode == "MAN"),
        ]:
            if is_active:
                btn.setStyleSheet(
                    f"QPushButton {{ "
                    f"background-color: {accent}; "
                    f"color: {theme.fg_primary}; "
                    f"border: 1px solid {accent}; "
                    f"border-radius: {br}; "
                    f"padding: 4px 16px; "
                    f"font-weight: bold; "
                    f"font-size: {theme.font_size_normal}px; }}"
                )
            else:
                btn.setStyleSheet(
                    f"QPushButton {{ "
                    f"background-color: {bg_dim}; "
                    f"color: {fg_muted}; "
                    f"border: 1px solid {theme.border}; "
                    f"border-radius: {br}; "
                    f"padding: 4px 16px; "
                    f"font-size: {theme.font_size_normal}px; }}"
                )

    def apply_theme(self, theme: ThemeBase) -> None:
        """Update cached theme reference for dynamic theme switching."""
        self._theme = theme
        self._apply_frame_style(theme)
        self._apply_ai_engine_badge(theme)
        self._bar_pv.apply_theme(theme)
        self._bar_sp.apply_theme(theme)
        self._bar_co.apply_theme(theme)
        self._apply_input_style(self._sp_input, theme)
        self._apply_input_style(self._co_input, theme)
        self._apply_toggle_style(theme)
        self._apply_optimizer_style(theme)
        self._opt_label.setStyleSheet(
            f"color: {theme.fg_secondary}; background: transparent; "
            f"font-size: {theme.font_size_label}px; font-weight: bold;"
        )
        for sep in self._separators:
            sep.setStyleSheet(
                f"background-color: {theme.border}; border: none;"
            )
        gains_css = self._gains_label_css(theme)
        self._kp_lbl.setStyleSheet(gains_css)
        self._ti_lbl.setStyleSheet(gains_css)
        self._td_lbl.setStyleSheet(gains_css)
        self._apply_input_style(self._kp_input, theme)
        self._apply_input_style(self._ti_input, theme)
        self._apply_input_style(self._td_input, theme)
        stat_val_css = self._stat_val_css(theme)
        for lbl in self._stat_labels.values():
            lbl.setStyleSheet(stat_val_css)
        self._perf_title.setStyleSheet(
            f"color: {theme.fg_secondary}; background: transparent;"
            f" font-size: {theme.font_size_label}px; font-weight: bold;"
        )
        badge_css = (
            f"color: {theme.fg_secondary}; background: {theme.bg_card};"
            f" font-size: {theme.font_size_label}px;"
            f" border-radius: 3px; padding: 2px 6px;"
            f" border: 1px solid {theme.border};"
        )
        self._ai_period_label.setStyleSheet(badge_css)
        self._stats_window_label.setStyleSheet(badge_css)
        self.update()

    def on_controller_selected(
        self,
        controller_id: int,
        tag_name: str,
        min_val: float,
        max_val: float,
        pid_gains: dict | None = None,
        ai_engine: str = "NONE",
        tss_s: float | None = None,
    ) -> None:
        self._controller_id = controller_id
        self._tag_label.setText(tag_name)
        self._current_ai_engine = ai_engine.upper()
        self._apply_ai_engine_badge(self._theme)
        self._active_mode = ""
        self._apply_toggle_style(self._theme)
        # Reset bars with new range
        for bar in [self._bar_pv, self._bar_sp]:
            bar._min = min_val  # noqa: SLF001
            bar._max = max_val  # noqa: SLF001
            bar.set_value(0.0)
        self._bar_co.set_value(0.0)
        # Update PID gains fields
        if pid_gains:
            self.update_gains(pid_gains)
        else:
            self._kp_input.setText("")
            self._ti_input.setText("")
            self._td_input.setText("")
        # Update AI Period / Stats Window from TSS
        self._update_tss_info(tss_s)

    def on_telemetry(self, controller_id: int, frame: dict) -> None:
        if (
            self._controller_id is None
            or controller_id != self._controller_id
        ):
            return
        self._bar_pv.set_value(frame.get("pv", 0.0))
        self._bar_pv.set_sp_marker(frame.get("sp"))
        self._bar_sp.set_value(frame.get("sp", 0.0))
        self._bar_co.set_value(frame.get("co", 0.0))
        mode = frame.get("mode")
        if mode and str(mode).upper() not in ("UNKNOWN", ""):
            mode_str = str(mode).upper()
            if mode_str != self._active_mode:
                self._active_mode = mode_str
                self._apply_toggle_style(self._theme)

        # Update SP/CO input fields (skip if user is editing or just wrote)
        now = time.monotonic()
        sp = frame.get("sp")
        if sp is not None and not self._sp_input.hasFocus() and now - self._sp_write_time >= 3.0:
            self._sp_input.setText(f"{sp:.1f}")
        co = frame.get("co")
        if co is not None and not self._co_input.hasFocus() and now - self._co_write_time >= 3.0:
            self._co_input.setText(f"{co:.1f}")

        # Update gains from live OPC-UA reads (if present in frame)
        kp = frame.get("kp")
        if kp is not None:
            self.update_gains({
                "gain": kp,
                "reset": frame.get("ti", 0.0),
                "rate": frame.get("td", 0.0),
            })

    def _on_sp_enter(self) -> None:
        if self._controller_id is None:
            return
        try:
            val = float(self._sp_input.text())
            self._sp_write_time = time.monotonic()
            self.setpoint_requested.emit(self._controller_id, val)
        except ValueError:
            pass

    def _on_co_enter(self) -> None:
        if self._controller_id is None:
            return
        try:
            val = float(self._co_input.text())
            self._co_write_time = time.monotonic()
            self.output_requested.emit(self._controller_id, val)
        except ValueError:
            pass

    @staticmethod
    def _gains_label_css(theme: ThemeBase) -> str:
        return (
            f"color: {theme.fg_secondary}; background: transparent;"
            f" font-size: {theme.font_size_label}px; font-weight: bold;"
        )

    def update_gains(self, gains: dict) -> None:
        """Update PID gains input fields.

        Args:
            gains: dict with keys 'gain', 'reset', 'rate',
                   and optionally 'integral_type' (TIME_TI or GAIN_KI).
        """
        integral_type = gains.get("integral_type", "TIME_TI")
        self._integral_type = integral_type

        # Update labels based on integral type
        if integral_type == "GAIN_KI":
            self._ti_lbl.setText("Ki:")
            self._td_lbl.setText("Kd:")
        else:
            self._ti_lbl.setText("Ti:")
            self._td_lbl.setText("Td:")

        # Set values in inputs (don't overwrite if user is editing or just wrote)
        now = time.monotonic()
        if now - self._gains_write_time < 3.0:
            return  # Suppress updates for 3s after user write
        if not self._kp_input.hasFocus():
            self._kp_input.setText(f"{gains.get('gain', 0.0):.3f}")
        if not self._ti_input.hasFocus():
            self._ti_input.setText(f"{gains.get('reset', 0.0):.3f}")
        if not self._td_input.hasFocus():
            self._td_input.setText(f"{gains.get('rate', 0.0):.3f}")

    def update_live_params(self, params: dict) -> None:
        """Update faceplate fields from 1-second REST polling.

        Args:
            params: dict with keys 'sp', 'co', 'gain', 'reset', 'rate',
                    and optionally 'integral_type'.
        """
        now = time.monotonic()
        sp = params.get("sp")
        if sp is not None and not self._sp_input.hasFocus() and now - self._sp_write_time >= 3.0:
            self._sp_input.setText(f"{sp:.1f}")
        co = params.get("co")
        if co is not None and not self._co_input.hasFocus() and now - self._co_write_time >= 3.0:
            self._co_input.setText(f"{co:.1f}")
        # Update gains with integral_type for label switching
        if params.get("gain") is not None:
            self.update_gains({
                "gain": params["gain"],
                "reset": params.get("reset", 0.0),
                "rate": params.get("rate", 0.0),
                "integral_type": params.get("integral_type", self._integral_type),
            })

    def _on_gains_changed(self) -> None:
        """User pressed Enter on a gains field — emit new values."""
        if self._controller_id is None:
            return
        try:
            gain = float(self._kp_input.text())
            reset = float(self._ti_input.text())
            rate = float(self._td_input.text())
        except ValueError:
            return
        self._gains_write_time = time.monotonic()
        self.gains_changed.emit(self._controller_id, {
            "gain": gain, "reset": reset, "rate": rate,
        })

    def _update_tss_info(self, tss_s: float | None) -> None:
        """Update the AI Period and Stats Window badges from TSS."""
        if tss_s is None:
            self._ai_period_label.setText("AI: \u2014")
            self._stats_window_label.setText("Stats: \u2014")
        else:
            self._ai_period_label.setText(f"AI: {self._fmt_dur(3.0 * tss_s)}")
            self._stats_window_label.setText(f"Stats: {self._fmt_dur(5.0 * tss_s)}")

    @staticmethod
    def _fmt_dur(seconds: float) -> str:
        if seconds < 60:
            return f"{seconds:.0f}s"
        if seconds < 3600:
            return f"{seconds / 60:.1f}min"
        return f"{seconds / 3600:.1f}h"

    @staticmethod
    def _stat_lbl_css(theme: ThemeBase) -> str:
        return (
            f"color: {theme.fg_secondary}; background: transparent;"
            f" font-size: {theme.font_size_label}px;"
        )

    @staticmethod
    def _stat_val_css(theme: ThemeBase) -> str:
        return (
            f"color: {theme.fg_primary}; background: transparent;"
            f" font-size: {theme.font_size_label}px;"
            f" font-family: 'Fira Code', monospace;"
        )

    def update_stats(self, stats: dict) -> None:
        """Update performance metrics grid.

        Args:
            stats: dict with keys matching metric names
                   (IAE, ITAE, ISE, MSE, StdDev, TV, 2sigma_range, 2sigma_sp).
        """
        key_map = {
            "IAE": "iae", "ITAE": "itae", "ISE": "ise", "MSE": "mse",
            "StdDev": "std_dev", "TV": "total_variation",
            "2\u03c3/Rng": "variability_range",
            "2\u03c3/SP": "variability_sp",
        }
        for label_name, val_label in self._stat_labels.items():
            key = key_map.get(label_name, label_name.lower())
            val = stats.get(key)
            if val is not None:
                if label_name in ("2\u03c3/Rng", "2\u03c3/SP"):
                    val_label.setText(f"{val * 100:.1f}%")
                else:
                    val_label.setText(f"{val:.1f}")
            else:
                val_label.setText("\u2014")

    def _apply_optimizer_style(self, theme: ThemeBase) -> None:
        """Style optimizer buttons — highlight active state."""
        bg_dim = _theme_attr(theme, "bg_input", theme.bg_widget)
        br = _theme_attr(theme, "border_radius", "0px")
        accent = _theme_attr(theme, "accent", theme.fg_secondary)
        base = (
            f"border: 1px solid {theme.border}; "
            f"border-radius: {br}; "
            f"padding: 2px 10px; "
            f"font-size: {theme.font_size_label}px;"
        )
        if self._ai_running:
            self._btn_opt_run.setStyleSheet(
                f"QPushButton {{ {base} background-color: {accent};"
                f" color: {theme.bg_primary}; font-weight: bold; }}"
            )
            self._btn_opt_stop.setStyleSheet(
                f"QPushButton {{ {base} background-color: {bg_dim};"
                f" color: {theme.fg_secondary}; }}"
            )
        else:
            self._btn_opt_run.setStyleSheet(
                f"QPushButton {{ {base} background-color: {bg_dim};"
                f" color: {theme.fg_secondary}; }}"
            )
            self._btn_opt_stop.setStyleSheet(
                f"QPushButton {{ {base} background-color: {theme.alarm_critical};"
                f" color: {theme.bg_primary}; font-weight: bold; }}"
            )

    def set_ai_running(self, running: bool) -> None:
        """Update AI optimizer running state and restyle buttons."""
        self._ai_running = running
        self._apply_optimizer_style(self._theme)

    def _on_opt_run(self) -> None:
        if self._controller_id is not None:
            self.optimizer_run_requested.emit(self._controller_id)

    def _on_opt_stop(self) -> None:
        if self._controller_id is not None:
            self.optimizer_stop_requested.emit(self._controller_id)

    def _on_mode(self, mode: str) -> None:
        if self._controller_id is not None:
            self.mode_requested.emit(self._controller_id, mode)
