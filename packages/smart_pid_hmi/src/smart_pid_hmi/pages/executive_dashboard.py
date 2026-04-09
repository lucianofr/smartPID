"""ExecutiveDashboardPage — KPI cards and performance table."""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLayout,
    QLayoutItem,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from smart_pid_hmi.themes.base import ThemeBase

class _FlowLayout(QLayout):
    """Layout that arranges widgets in rows, wrapping when width is exceeded."""

    def __init__(
        self,
        parent: QWidget | None = None,
        h_spacing: int = 12,
        v_spacing: int = 12,
    ) -> None:
        super().__init__(parent)
        self._h_spacing = h_spacing
        self._v_spacing = v_spacing
        self._items: list[QLayoutItem] = []

    def addItem(self, item: QLayoutItem) -> None:  # noqa: N802
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int) -> QLayoutItem | None:  # noqa: N802
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index: int) -> QLayoutItem | None:  # noqa: N802
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self) -> Qt.Orientation:  # noqa: N802
        return Qt.Orientation(0)

    def hasHeightForWidth(self) -> bool:  # noqa: N802
        return True

    def heightForWidth(self, width: int) -> int:  # noqa: N802
        return self._do_layout(QRect(0, 0, width, 0), test_only=True)

    def setGeometry(self, rect: QRect) -> None:  # noqa: N802
        super().setGeometry(rect)
        self._do_layout(rect, test_only=False)

    def sizeHint(self) -> QSize:  # noqa: N802
        return self.minimumSize()

    def minimumSize(self) -> QSize:  # noqa: N802
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        m = self.contentsMargins()
        size += QSize(m.left() + m.right(), m.top() + m.bottom())
        return size

    def _do_layout(self, rect: QRect, test_only: bool) -> int:
        m = self.contentsMargins()
        effective = rect.adjusted(m.left(), m.top(), -m.right(), -m.bottom())
        x = effective.x()
        y = effective.y()
        line_height = 0

        for item in self._items:
            w = item.sizeHint().width()
            h = item.sizeHint().height()

            if x + w > effective.right() + 1 and line_height > 0:
                x = effective.x()
                y = y + line_height + self._v_spacing
                line_height = 0

            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), item.sizeHint()))

            x = x + w + self._h_spacing
            line_height = max(line_height, h)

        return y + line_height - rect.y() + m.bottom()


class _KPICard(QFrame):
    """Internal KPI display card with title and value labels."""

    def __init__(
        self,
        title: str,
        theme: ThemeBase | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._theme = theme
        self.setFrameShape(QFrame.Shape.StyledPanel)

        bg = theme.bg_card if theme else ""
        bdr = theme.border if theme else ""
        radius = theme.border_radius if theme else "0px"
        if bg:
            self.setStyleSheet(
                f"_KPICard {{ background-color: {bg};"
                f" border: 1px solid {bdr};"
                f" border-radius: {radius}; }}"
            )

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        fg2 = theme.fg_secondary if theme else ""
        self._title_label = QLabel(title)
        self._title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._title_label.setStyleSheet(
            f"font-weight: bold; font-size: 12px;"
            f" color: {fg2}; background: transparent;"
            if fg2 else "font-weight: bold; font-size: 12px;"
        )
        layout.addWidget(self._title_label)

        accent = theme.accent if theme else ""
        self._value_label = QLabel("0")
        self._value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._value_label.setStyleSheet(
            f"font-size: 24px; font-weight: bold;"
            f" color: {accent}; background: transparent;"
            if accent else "font-size: 24px; font-weight: bold;"
        )
        layout.addWidget(self._value_label)

    @property
    def value_label(self) -> QLabel:
        return self._value_label

    @property
    def title_label(self) -> QLabel:
        return self._title_label

    def set_value(self, value: str) -> None:
        self._value_label.setText(value)

    def apply_theme(self, theme: ThemeBase) -> None:
        """Re-apply theme to card."""
        self._theme = theme
        self.setStyleSheet(
            f"_KPICard {{ background-color: {theme.bg_card};"
            f" border: 1px solid {theme.border};"
            f" border-radius: {theme.border_radius}; }}"
        )
        self._title_label.setStyleSheet(
            f"font-weight: bold; font-size: 12px;"
            f" color: {theme.fg_secondary}; background: transparent;"
        )
        self._value_label.setStyleSheet(
            f"font-size: 24px; font-weight: bold;"
            f" color: {theme.accent}; background: transparent;"
        )


# Performance metric keys and their data dict field mappings
_PERF_METRICS: list[tuple[str, str, bool]] = [
    # (display_label, data_key, is_percentage)
    ("IAE", "iae", False),
    ("ITAE", "itae", False),
    ("ISE", "ise", False),
    ("MSE", "mse", False),
    ("Std Dev", "std_dev", False),
    ("TV", "total_variation", False),
    ("Var/SP", "variability_sp", True),
    ("Var/Rng", "variability_range", True),
]

_PLACEHOLDER = "\u2014"  # em-dash
_BADGE_BASE_STYLE = (
    "padding: 1px 10px; border-radius: 3px; font-size: 10px; font-weight: bold;"
)

# Badge color schemes: (background, text_color)
_MODE_COLORS: dict[str, tuple[str, str]] = {
    "AUTO": ("#1B5E20", "#A5D6A7"),
    "CAS": ("#1B5E20", "#A5D6A7"),
    "RCAS": ("#1B5E20", "#A5D6A7"),
    "MAN": ("#E65100", "#FFCC80"),
    "ROUT": ("#E65100", "#FFCC80"),
    "OOS": ("#424242", "#9E9E9E"),
    "LO": ("#424242", "#9E9E9E"),
    "IMAN": ("#424242", "#9E9E9E"),
}
_MODE_DEFAULT = ("#424242", "#9E9E9E")

_AI_ENGINE_COLORS: dict[str, tuple[str, str]] = {
    "FUZZY": ("#4A148C", "#CE93D8"),
    "RL": ("#006064", "#80DEEA"),
    "NONE": ("#424242", "#9E9E9E"),
}
_AI_ENGINE_DEFAULT = ("#424242", "#9E9E9E")

_OPT_STATE_COLORS: dict[str, tuple[str, str]] = {
    "RUN": ("#0D47A1", "#90CAF9"),
    "RUNNING": ("#0D47A1", "#90CAF9"),
    "PAUSE": ("#F57F17", "#FFF176"),
    "STOP": ("#424242", "#9E9E9E"),
    "STOPPED": ("#424242", "#9E9E9E"),
}
_OPT_STATE_DEFAULT = ("#424242", "#9E9E9E")

_EXEC_MODE_COLORS: dict[str, tuple[str, str]] = {
    "SUPERVISORY": ("#1A237E", "#9FA8DA"),
    "DDC": ("#BF360C", "#FFAB91"),
}
_EXEC_MODE_DEFAULT = ("#424242", "#9E9E9E")


class _ControllerCard(QFrame):
    """Dashboard-tile card for a single controller."""

    # Card sizing
    CARD_MIN_W = 380
    CARD_MAX_W = 450
    CARD_FIXED_H = 260

    def __init__(
        self,
        theme: ThemeBase | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._theme = theme
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setMinimumWidth(self.CARD_MIN_W)
        self.setMaximumWidth(self.CARD_MAX_W)
        self.setFixedHeight(self.CARD_FIXED_H)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

        self._build_ui()
        if theme:
            self._apply_styles(theme)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(8)

        # --- Header row ---
        header = QHBoxLayout()
        header.setSpacing(6)

        self._led = QLabel("\u25cf")  # filled circle
        self._led.setFixedWidth(14)
        header.addWidget(self._led)

        self._name_label = QLabel()
        self._name_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        header.addWidget(self._name_label)
        header.addStretch()

        self._mode_badge = QLabel()
        self._engine_badge = QLabel()
        self._opt_state_badge = QLabel()
        self._exec_badge = QLabel()
        for badge in (
            self._mode_badge,
            self._engine_badge,
            self._opt_state_badge,
            self._exec_badge,
        ):
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            badge.setFixedHeight(18)
            badge.setStyleSheet(_BADGE_BASE_STYLE)
            header.addWidget(badge)

        root.addLayout(header)

        # --- Separator ---
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFixedHeight(1)
        root.addWidget(sep)

        # --- Config row 1 (Objective, Process Speed, Scan Rate) ---
        cfg_row = QHBoxLayout()
        cfg_row.setSpacing(8)
        self._objective_value = self._make_tile("Objective", cfg_row)
        self._speed_value = self._make_tile("Process Speed", cfg_row)
        self._scan_rate_value = self._make_tile("Scan Rate", cfg_row)
        root.addLayout(cfg_row)

        # --- Config row 2 (TSS, AI Period, Stats Window) ---
        cfg_row2 = QHBoxLayout()
        cfg_row2.setSpacing(8)
        self._tss_value = self._make_tile("TSS", cfg_row2)
        self._ai_period_value = self._make_tile("AI Period", cfg_row2)
        self._stats_window_value = self._make_tile("Stats Window", cfg_row2)
        root.addLayout(cfg_row2)

        # --- Performance grid (4x2) ---
        perf_grid = QGridLayout()
        perf_grid.setSpacing(4)
        self._perf_values: dict[str, QLabel] = {}
        for i, (label, _key, _is_pct) in enumerate(_PERF_METRICS):
            row_idx = i // 4
            col_idx = i % 4
            tile = QFrame()
            tile.setObjectName("perf_tile")
            tile_layout = QVBoxLayout(tile)
            tile_layout.setContentsMargins(6, 4, 6, 4)
            tile_layout.setSpacing(2)

            lbl = QLabel(label)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet("font-size: 11px; font-weight: bold;")
            lbl.setObjectName("perf_label")
            tile_layout.addWidget(lbl)

            val = QLabel(_PLACEHOLDER)
            val.setAlignment(Qt.AlignmentFlag.AlignCenter)
            val.setStyleSheet("font-weight: bold; font-size: 11px;")
            val.setObjectName("perf_value")
            tile_layout.addWidget(val)

            self._perf_values[label] = val
            perf_grid.addWidget(tile, row_idx, col_idx)

        root.addLayout(perf_grid)

    def _make_tile(self, label_text: str, parent_layout: QHBoxLayout) -> QLabel:
        """Create a mini-tile (label + value) and add it to the parent layout."""
        tile = QFrame()
        tile.setObjectName("mini_tile")
        tile_layout = QVBoxLayout(tile)
        tile_layout.setContentsMargins(8, 6, 8, 6)
        tile_layout.setSpacing(2)

        lbl = QLabel(label_text)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet("font-size: 11px; font-weight: bold;")
        lbl.setObjectName("tile_label")
        tile_layout.addWidget(lbl)

        val = QLabel(_PLACEHOLDER)
        val.setAlignment(Qt.AlignmentFlag.AlignCenter)
        val.setStyleSheet("font-weight: bold; font-size: 16px;")
        val.setObjectName("tile_value")
        tile_layout.addWidget(val)

        parent_layout.addWidget(tile)
        return val

    def update_data(self, data: dict) -> None:
        """Update all fields from a controller data dict."""
        # Header
        name = data.get("name", "")
        mode = str(data.get("mode", ""))
        exec_mode = str(data.get("execution_mode", "DDC"))
        ai_cfg = data.get("ai_config", {})
        engine = str(ai_cfg.get("engine", "NONE")) if isinstance(ai_cfg, dict) else "NONE"
        objective = str(ai_cfg.get("objective", "")) if isinstance(ai_cfg, dict) else ""

        opt_state = str(data.get("ai_optimizer_state", "STOP")).upper()

        self._name_label.setText(name)
        self._mode_badge.setText(mode)
        self._engine_badge.setText(engine)
        self._opt_state_badge.setText(opt_state)
        self._exec_badge.setText(exec_mode)

        # LED color based on mode
        auto_modes = {"AUTO", "CAS", "RCAS", "ROUT"}
        manual_modes = {"MAN", "IMAN"}
        if mode in auto_modes:
            self._led.setStyleSheet("color: #7fff7f; font-size: 12px;")
        elif mode in manual_modes:
            self._led.setStyleSheet("color: #f0c040; font-size: 12px;")
        else:
            self._led.setStyleSheet("color: #888888; font-size: 12px;")

        # Config section
        speed = str(data.get("process_speed", _PLACEHOLDER))
        scan_rate = data.get("scan_rate_s")

        if engine == "NONE":
            self._objective_value.setText(_PLACEHOLDER)
        else:
            self._objective_value.setText(objective)

        self._speed_value.setText(speed)
        self._scan_rate_value.setText(
            f"{scan_rate:.1f} s" if scan_rate is not None else _PLACEHOLDER
        )

        # TSS-derived values
        tss = data.get("tss_s")
        if tss is not None:
            self._tss_value.setText(self._fmt_duration(tss))
            self._ai_period_value.setText(self._fmt_duration(3.0 * tss))
            self._stats_window_value.setText(self._fmt_duration(5.0 * tss))
        else:
            self._tss_value.setText(_PLACEHOLDER)
            self._ai_period_value.setText(_PLACEHOLDER)
            self._stats_window_value.setText(_PLACEHOLDER)

        # Performance metrics
        for label, key, is_pct in _PERF_METRICS:
            raw = data.get(key)
            txt = (f"{raw:.1f}%" if is_pct else f"{raw:.1f}") if raw is not None else _PLACEHOLDER
            self._perf_values[label].setText(txt)

        # Badge styling
        self._style_mode_badge(mode)
        self._style_engine_badge(engine)
        self._style_opt_state_badge(opt_state)
        self._style_exec_badge(exec_mode)

    @staticmethod
    def _fmt_duration(seconds: float) -> str:
        """Format seconds into a human-readable duration string."""
        if seconds < 60:
            return f"{seconds:.0f} s"
        if seconds < 3600:
            m = seconds / 60
            return f"{m:.1f} min"
        h = seconds / 3600
        return f"{h:.1f} h"

    @staticmethod
    def _badge_style(bg: str, fg: str) -> str:
        return f"background-color: {bg}; color: {fg}; {_BADGE_BASE_STYLE}"

    def _style_mode_badge(self, mode: str) -> None:
        bg, fg = _MODE_COLORS.get(mode, _MODE_DEFAULT)
        self._mode_badge.setStyleSheet(self._badge_style(bg, fg))

    def _style_engine_badge(self, engine: str) -> None:
        bg, fg = _AI_ENGINE_COLORS.get(engine, _AI_ENGINE_DEFAULT)
        self._engine_badge.setStyleSheet(self._badge_style(bg, fg))

    def _style_opt_state_badge(self, state: str) -> None:
        bg, fg = _OPT_STATE_COLORS.get(state, _OPT_STATE_DEFAULT)
        self._opt_state_badge.setStyleSheet(self._badge_style(bg, fg))

    def _style_exec_badge(self, exec_mode: str) -> None:
        bg, fg = _EXEC_MODE_COLORS.get(exec_mode, _EXEC_MODE_DEFAULT)
        self._exec_badge.setStyleSheet(self._badge_style(bg, fg))

    def _apply_styles(self, theme: ThemeBase) -> None:
        """Apply theme colors to the card."""
        self.setStyleSheet(
            f"_ControllerCard {{ background-color: {theme.bg_card};"
            f" border: 1px solid {theme.border};"
            f" border-radius: {theme.border_radius}; }}"
        )
        self._name_label.setStyleSheet(
            f"font-weight: bold; font-size: 14px;"
            f" color: {theme.fg_primary}; background: transparent;"
        )

    def apply_theme(self, theme: ThemeBase) -> None:
        """Re-apply theme to card."""
        self._theme = theme
        self._apply_styles(theme)


class ExecutiveDashboardPage(QWidget):
    """Executive dashboard with KPI cards row and performance table."""

    def __init__(
        self,
        theme: ThemeBase | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._theme = theme

        layout = QVBoxLayout(self)

        # Title
        title = QLabel("Executive Dashboard")
        title.setObjectName("title_label")
        fg = theme.fg_primary if theme else ""
        title.setStyleSheet(
            f"font-size: 20px; font-weight: bold; color: {fg};"
            " background: transparent;"
            if fg else "font-size: 20px; font-weight: bold;"
        )
        layout.addWidget(title)

        # KPI cards row
        kpi_row = QHBoxLayout()
        self._card_total = _KPICard("Total Loops", theme=theme)
        self._card_auto = _KPICard("In AUTO", theme=theme)
        self._card_alarms = _KPICard("Active Alarms", theme=theme)
        self._card_ai = _KPICard("AI Tuning Active", theme=theme)

        self._kpi_total = self._card_total.value_label
        self._kpi_auto = self._card_auto.value_label
        self._kpi_alarms = self._card_alarms.value_label
        self._kpi_ai = self._card_ai.value_label

        for card in (
            self._card_total, self._card_auto,
            self._card_alarms, self._card_ai,
        ):
            kpi_row.addWidget(card)
        layout.addLayout(kpi_row)

        # Controller cards in scroll area
        self._scroll_area = QScrollArea()
        self._scroll_area.setObjectName("cards_scroll_area")
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setFrameShape(QFrame.Shape.NoFrame)

        self._cards_container = QWidget()
        self._cards_layout = _FlowLayout(
            self._cards_container, h_spacing=12, v_spacing=12,
        )
        self._scroll_area.setWidget(self._cards_container)
        layout.addWidget(self._scroll_area, stretch=1)

        self._controller_cards: dict[str, _ControllerCard] = {}

    def update_kpis(
        self,
        total: int,
        in_auto: int,
        active_alarms: int,
        ai_active: int,
    ) -> None:
        """Update KPI card values."""
        self._kpi_total.setText(str(total))
        self._kpi_auto.setText(str(in_auto))
        self._kpi_alarms.setText(str(active_alarms))
        self._kpi_ai.setText(str(ai_active))

    def update_controller_cards(self, controllers: list[dict]) -> None:
        """Create/update controller cards from a list of controller dicts."""
        incoming_names = set()
        for ctrl in controllers:
            name = ctrl.get("name", f"Loop-{ctrl.get('id', '?')}")
            incoming_names.add(name)
            if name in self._controller_cards:
                # Reuse existing card — just update data
                self._controller_cards[name].update_data(ctrl)
            else:
                # Create new card
                card = _ControllerCard(theme=self._theme)
                card.update_data(ctrl)
                self._cards_layout.addWidget(card)
                self._controller_cards[name] = card

        # Remove cards that no longer exist
        for name in list(self._controller_cards):
            if name not in incoming_names:
                card = self._controller_cards.pop(name)
                self._cards_layout.removeWidget(card)
                card.deleteLater()

    def apply_theme(self, theme: ThemeBase) -> None:
        """Re-apply theme colors to KPI cards and controller cards."""
        self._theme = theme
        for card in (
            self._card_total, self._card_auto,
            self._card_alarms, self._card_ai,
        ):
            card.apply_theme(theme)
        for ctrl_card in self._controller_cards.values():
            ctrl_card.apply_theme(theme)
