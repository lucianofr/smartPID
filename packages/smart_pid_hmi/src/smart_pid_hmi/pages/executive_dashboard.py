"""ExecutiveDashboardPage — KPI cards and performance table."""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLayout,
    QLayoutItem,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
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


_PERF_COLUMNS = ["Loop", "Mode", "PV", "SP", "Error%", "IAE", "Status"]


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
_BADGE_BASE_STYLE = "padding: 2px 8px; border-radius: 4px; font-size: 10px;"


class _ControllerCard(QFrame):
    """Dashboard-tile card for a single controller."""

    # Card sizing
    CARD_MIN_W = 380
    CARD_MAX_W = 450
    CARD_FIXED_H = 320

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
        self._exec_badge = QLabel()
        for badge in (self._mode_badge, self._engine_badge, self._exec_badge):
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            badge.setStyleSheet(_BADGE_BASE_STYLE)
            header.addWidget(badge)

        root.addLayout(header)

        # --- Separator ---
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFixedHeight(1)
        root.addWidget(sep)

        # --- Process values row (PV, SP, Error%) ---
        pv_row = QHBoxLayout()
        pv_row.setSpacing(8)
        self._pv_value = self._make_tile("PV", pv_row)
        self._sp_value = self._make_tile("SP", pv_row)
        self._error_value = self._make_tile("Error", pv_row)
        root.addLayout(pv_row)

        # --- Optimization row (Objective, State, gamma) ---
        ai_row = QHBoxLayout()
        ai_row.setSpacing(8)
        self._objective_value = self._make_tile("Objective", ai_row)
        self._ai_state_value = self._make_tile("State", ai_row)
        self._gamma_value = self._make_tile("\u03b3", ai_row)  # gamma symbol
        root.addLayout(ai_row)

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
            lbl.setStyleSheet("font-size: 9px;")
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
        lbl.setStyleSheet("font-size: 9px;")
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

        self._name_label.setText(name)
        self._mode_badge.setText(mode)
        self._exec_badge.setText(exec_mode)
        self._engine_badge.setText(engine)

        # LED color based on mode
        auto_modes = {"AUTO", "CAS", "RCAS", "ROUT"}
        manual_modes = {"MAN", "IMAN"}
        if mode in auto_modes:
            self._led.setStyleSheet("color: #7fff7f; font-size: 12px;")
        elif mode in manual_modes:
            self._led.setStyleSheet("color: #f0c040; font-size: 12px;")
        else:
            self._led.setStyleSheet("color: #888888; font-size: 12px;")

        # Process values
        pv = data.get("pv")
        sp = data.get("sp")
        self._pv_value.setText(f"{pv:.1f}" if pv is not None else _PLACEHOLDER)
        self._sp_value.setText(f"{sp:.1f}" if sp is not None else _PLACEHOLDER)

        if pv is not None and sp is not None:
            span = data.get("sp_hi_lim", 100.0) - data.get("sp_lo_lim", 0.0)
            error_pct = abs(pv - sp) / span * 100.0 if span else 0.0
            self._error_value.setText(f"{error_pct:.1f}%")
        else:
            self._error_value.setText(_PLACEHOLDER)

        # Optimization section
        ai_state = data.get("ai_state", "")
        ai_gamma = data.get("ai_gamma")

        if engine == "NONE":
            self._objective_value.setText(_PLACEHOLDER)
            self._ai_state_value.setText("Disabled")
            self._gamma_value.setText(_PLACEHOLDER)
        else:
            self._objective_value.setText(objective)
            self._ai_state_value.setText(str(ai_state) if ai_state else _PLACEHOLDER)
            self._gamma_value.setText(
                f"{ai_gamma:.2f}" if ai_gamma is not None else _PLACEHOLDER
            )

        # Performance metrics
        for label, key, is_pct in _PERF_METRICS:
            raw = data.get(key)
            if raw is not None:
                txt = f"{raw:.1f}%" if is_pct else f"{raw:.1f}"
            else:
                txt = _PLACEHOLDER
            self._perf_values[label].setText(txt)

        # Badge styling
        self._style_mode_badge(mode)
        self._style_engine_badge(engine)

    def _style_mode_badge(self, mode: str) -> None:
        auto_modes = {"AUTO", "CAS", "RCAS", "ROUT"}
        if mode in auto_modes:
            self._mode_badge.setStyleSheet(
                f"background-color: #2d5a27; color: #7fff7f; {_BADGE_BASE_STYLE}"
            )
        else:
            self._mode_badge.setStyleSheet(
                f"background-color: #444; color: #ccc; {_BADGE_BASE_STYLE}"
            )

    def _style_engine_badge(self, engine: str) -> None:
        if engine in {"FUZZY", "RL"}:
            self._engine_badge.setStyleSheet(
                f"background-color: #3a2d10; color: #f0a030; {_BADGE_BASE_STYLE}"
            )
        else:
            self._engine_badge.setStyleSheet(
                f"background-color: #333; color: #888; {_BADGE_BASE_STYLE}"
            )

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

        # Performance table
        self._table = QTableWidget(0, len(_PERF_COLUMNS))
        self._table.setObjectName("performance_table")
        self._table.setHorizontalHeaderLabels(_PERF_COLUMNS)
        self._table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self._table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows,
        )
        self._table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers,
        )
        layout.addWidget(self._table, stretch=1)

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

    def update_performance_table(self, rows: list[dict]) -> None:
        """Populate the performance table from a list of row dicts.

        Expected keys: loop, mode, pv, sp, error_pct, iae, status.
        """
        self._table.setRowCount(0)
        for row_data in rows:
            row_idx = self._table.rowCount()
            self._table.insertRow(row_idx)
            values = [
                str(row_data.get("loop", "")),
                str(row_data.get("mode", "")),
                f"{row_data.get('pv', 0.0):.1f}",
                f"{row_data.get('sp', 0.0):.1f}",
                f"{row_data.get('error_pct', 0.0):.1f}",
                f"{row_data.get('iae', 0.0):.1f}",
                str(row_data.get("status", "")),
            ]
            for col, val in enumerate(values):
                item = QTableWidgetItem(val)
                item.setFlags(
                    item.flags() & ~Qt.ItemFlag.ItemIsEditable,
                )
                self._table.setItem(row_idx, col, item)

    def apply_theme(self, theme: ThemeBase) -> None:
        """Re-apply theme colors to KPI cards and labels."""
        self._theme = theme
        for card in (
            self._card_total, self._card_auto,
            self._card_alarms, self._card_ai,
        ):
            card.apply_theme(theme)
