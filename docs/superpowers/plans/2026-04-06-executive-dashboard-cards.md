# Executive Dashboard Cards Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Executive Dashboard performance table with controller cards using dashboard-tiles style, showing process values, AI optimization info, and performance indices.

**Architecture:** New `_ControllerCard(QFrame)` widget and `_FlowLayout(QLayout)` in `executive_dashboard.py`. Cards replace `QTableWidget`. `main.py` sends raw controller dicts instead of building `perf_rows`. KPI summary cards at top remain unchanged.

**Tech Stack:** PySide6, Python 3.13, pytest + pytest-qt

**Spec:** `docs/superpowers/specs/2026-04-06-executive-dashboard-cards-design.md`

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `packages/smart_pid_hmi/src/smart_pid_hmi/pages/executive_dashboard.py` | Modify | Replace table with `_FlowLayout`, `_ControllerCard`, `QScrollArea` |
| `packages/smart_pid_hmi/src/smart_pid_hmi/main.py` | Modify | Wire `update_controller_cards` instead of `update_performance_table` |
| `tests/hmi/pages/test_executive_dashboard.py` | Modify | Remove table tests, add card tests |
| `tests/hmi/test_main_window_audit_gaps.py` | Modify | Update executive wiring test |

---

### Task 1: Add `_FlowLayout` custom layout

**Files:**
- Modify: `packages/smart_pid_hmi/src/smart_pid_hmi/pages/executive_dashboard.py`
- Test: `tests/hmi/pages/test_executive_dashboard.py`

- [ ] **Step 1: Write the failing test for FlowLayout**

Add to `tests/hmi/pages/test_executive_dashboard.py`:

```python
from PySide6.QtWidgets import QLabel, QPushButton, QWidget

from smart_pid_hmi.pages.executive_dashboard import _FlowLayout


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/hmi/pages/test_executive_dashboard.py::test_flow_layout_add_and_count tests/hmi/pages/test_executive_dashboard.py::test_flow_layout_item_at -v`
Expected: FAIL with `ImportError: cannot import name '_FlowLayout'`

- [ ] **Step 3: Implement `_FlowLayout`**

Add to `packages/smart_pid_hmi/src/smart_pid_hmi/pages/executive_dashboard.py`, after the existing imports and before `_KPICard`:

```python
from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtWidgets import QLayout, QLayoutItem, QSizePolicy, QStyle


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
```

Note: update the imports at the top of the file. The full import block should now be:

```python
from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QLayoutItem,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
```

Remove `QHeaderView`, `QTableWidget`, `QTableWidgetItem` from imports (no longer needed). Remove `QStyle` from the implementation above — it's not used. Add `QScrollArea` for later tasks.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/hmi/pages/test_executive_dashboard.py::test_flow_layout_add_and_count tests/hmi/pages/test_executive_dashboard.py::test_flow_layout_item_at -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_hmi/src/smart_pid_hmi/pages/executive_dashboard.py tests/hmi/pages/test_executive_dashboard.py
git commit -m "feat(hmi): add _FlowLayout custom layout for executive dashboard"
```

---

### Task 2: Add `_ControllerCard` widget

**Files:**
- Modify: `packages/smart_pid_hmi/src/smart_pid_hmi/pages/executive_dashboard.py`
- Test: `tests/hmi/pages/test_executive_dashboard.py`

- [ ] **Step 1: Write failing tests for `_ControllerCard`**

Add to `tests/hmi/pages/test_executive_dashboard.py`:

```python
from smart_pid_hmi.pages.executive_dashboard import _ControllerCard


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/hmi/pages/test_executive_dashboard.py -k "controller_card" -v`
Expected: FAIL with `ImportError: cannot import name '_ControllerCard'`

- [ ] **Step 3: Implement `_ControllerCard`**

Add to `packages/smart_pid_hmi/src/smart_pid_hmi/pages/executive_dashboard.py`, after `_KPICard` class:

```python
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

        self._led = QLabel("\u25CF")  # filled circle
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
            badge.setStyleSheet(
                "padding: 2px 8px; border-radius: 4px; font-size: 10px;"
            )
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
        self._gamma_value = self._make_tile("\u03B3", ai_row)  # gamma symbol
        root.addLayout(ai_row)

        # --- Performance grid (4x2) ---
        from PySide6.QtWidgets import QGridLayout

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
                "background-color: #2d5a27; color: #7fff7f;"
                " padding: 2px 8px; border-radius: 4px; font-size: 10px;"
            )
        else:
            self._mode_badge.setStyleSheet(
                "background-color: #444; color: #ccc;"
                " padding: 2px 8px; border-radius: 4px; font-size: 10px;"
            )

    def _style_engine_badge(self, engine: str) -> None:
        if engine in {"FUZZY", "RL"}:
            self._engine_badge.setStyleSheet(
                "background-color: #3a2d10; color: #f0a030;"
                " padding: 2px 8px; border-radius: 4px; font-size: 10px;"
            )
        else:
            self._engine_badge.setStyleSheet(
                "background-color: #333; color: #888;"
                " padding: 2px 8px; border-radius: 4px; font-size: 10px;"
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/hmi/pages/test_executive_dashboard.py -k "controller_card" -v`
Expected: All 9 `test_controller_card_*` tests PASS

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_hmi/src/smart_pid_hmi/pages/executive_dashboard.py tests/hmi/pages/test_executive_dashboard.py
git commit -m "feat(hmi): add _ControllerCard widget with dashboard-tile layout"
```

---

### Task 3: Replace table with scroll area and cards in `ExecutiveDashboardPage`

**Files:**
- Modify: `packages/smart_pid_hmi/src/smart_pid_hmi/pages/executive_dashboard.py`
- Test: `tests/hmi/pages/test_executive_dashboard.py`

- [ ] **Step 1: Write failing tests**

Replace the old table tests and add new card tests in `tests/hmi/pages/test_executive_dashboard.py`.

Remove these two tests entirely:

```python
def test_has_performance_table(qtbot):
    ...

def test_update_performance_table(qtbot):
    ...
```

Add these new tests:

```python
from PySide6.QtWidgets import QScrollArea


def test_has_scroll_area(qtbot):
    page = ExecutiveDashboardPage()
    qtbot.addWidget(page)
    scroll = page.findChild(QScrollArea, "cards_scroll_area")
    assert scroll is not None


def test_update_controller_cards_creates_cards(qtbot):
    page = ExecutiveDashboardPage()
    qtbot.addWidget(page)
    controllers = [
        _make_controller_data(name="FIC-101"),
        _make_controller_data(name="LIC-201"),
        _make_controller_data(name="TIC-301"),
    ]
    page.update_controller_cards(controllers)
    assert len(page._controller_cards) == 3


def test_cards_update_on_second_call(qtbot):
    page = ExecutiveDashboardPage()
    qtbot.addWidget(page)
    page.update_controller_cards([_make_controller_data(name="A")])
    assert len(page._controller_cards) == 1
    page.update_controller_cards([
        _make_controller_data(name="X"),
        _make_controller_data(name="Y"),
    ])
    assert len(page._controller_cards) == 2


def test_flow_layout_in_scroll_area(qtbot):
    page = ExecutiveDashboardPage()
    qtbot.addWidget(page)
    assert isinstance(page._cards_container.layout(), _FlowLayout)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/hmi/pages/test_executive_dashboard.py -k "scroll_area or controller_cards_creates or cards_update_on_second or flow_layout_in" -v`
Expected: FAIL (methods/attributes not yet present)

- [ ] **Step 3: Modify `ExecutiveDashboardPage`**

In `packages/smart_pid_hmi/src/smart_pid_hmi/pages/executive_dashboard.py`, replace the performance table section in `ExecutiveDashboardPage.__init__` and related methods.

Remove the `_PERF_COLUMNS` constant at the top of the file:
```python
_PERF_COLUMNS = ["Loop", "Mode", "PV", "SP", "Error%", "IAE", "Status"]
```

In `ExecutiveDashboardPage.__init__`, replace the performance table block (lines ~142-155):

```python
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
```

with:

```python
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
```

Remove the `update_performance_table` method entirely and add:

```python
    def update_controller_cards(self, controllers: list[dict]) -> None:
        """Create/update controller cards from a list of controller dicts."""
        # Clear existing cards
        for card in self._controller_cards.values():
            card.setParent(None)
            card.deleteLater()
        self._controller_cards.clear()

        # Create new cards
        for ctrl in controllers:
            name = ctrl.get("name", f"Loop-{ctrl.get('id', '?')}")
            card = _ControllerCard(theme=self._theme)
            card.update_data(ctrl)
            self._cards_layout.addWidget(card)
            self._controller_cards[name] = card
```

Update `apply_theme` to cascade to controller cards:

```python
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
```

- [ ] **Step 4: Run all executive dashboard tests**

Run: `uv run pytest tests/hmi/pages/test_executive_dashboard.py -v`
Expected: All tests PASS (old table tests removed, new card tests pass)

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_hmi/src/smart_pid_hmi/pages/executive_dashboard.py tests/hmi/pages/test_executive_dashboard.py
git commit -m "feat(hmi): replace executive dashboard table with controller cards"
```

---

### Task 4: Wire `main.py` to use `update_controller_cards`

**Files:**
- Modify: `packages/smart_pid_hmi/src/smart_pid_hmi/main.py:404-420`
- Modify: `tests/hmi/test_main_window_audit_gaps.py:97-114`

- [ ] **Step 1: Update the wiring test**

In `tests/hmi/test_main_window_audit_gaps.py`, replace the test at line ~97:

```python
    def test_controllers_loaded_populates_performance_table(self, main_window):
        """After controllers load, exec dashboard table should have rows."""
        controllers = [
            {
                "id": 1, "name": "FIC-101", "mode": "AUTO",
                "pv": 50.0, "sp": 50.0,
                "sp_hi_lim": 100.0, "sp_lo_lim": 0.0,
            },
            {
                "id": 2, "name": "LIC-201", "mode": "OOS",
                "pv": 65.0, "sp": 65.0,
                "sp_hi_lim": 100.0, "sp_lo_lim": 0.0,
            },
        ]
        main_window._on_controllers_received(controllers)
        table = main_window._executive_page._table
        assert table.rowCount() == 2
        assert table.item(0, 0).text() == "FIC-101"
```

with:

```python
    def test_controllers_loaded_populates_controller_cards(self, main_window):
        """After controllers load, exec dashboard should have cards."""
        controllers = [
            {
                "id": 1, "name": "FIC-101", "mode": "AUTO",
                "execution_mode": "DDC",
                "pv": 50.0, "sp": 50.0,
                "sp_hi_lim": 100.0, "sp_lo_lim": 0.0,
            },
            {
                "id": 2, "name": "LIC-201", "mode": "OOS",
                "execution_mode": "DDC",
                "pv": 65.0, "sp": 65.0,
                "sp_hi_lim": 100.0, "sp_lo_lim": 0.0,
            },
        ]
        main_window._on_controllers_received(controllers)
        cards = main_window._executive_page._controller_cards
        assert len(cards) == 2
        assert "FIC-101" in cards
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/hmi/test_main_window_audit_gaps.py::TestExecutiveDashboardWiring::test_controllers_loaded_populates_controller_cards -v`
Expected: FAIL (main.py still calls `update_performance_table`)

- [ ] **Step 3: Update `main.py`**

In `packages/smart_pid_hmi/src/smart_pid_hmi/main.py`, replace lines ~404-420:

```python
        # Feed executive dashboard performance table
        perf_rows = []
        for c in controllers:
            sp = c.get("sp", 0.0)
            pv = c.get("pv", 0.0)
            sp_range = c.get("sp_hi_lim", 100.0) - c.get("sp_lo_lim", 0.0)
            error_pct = (abs(pv - sp) / sp_range * 100.0) if sp_range else 0.0
            perf_rows.append({
                "loop": c.get("name", ""),
                "mode": c.get("mode", ""),
                "pv": pv,
                "sp": sp,
                "error_pct": round(error_pct, 1),
                "iae": 0.0,
                "status": "OK" if c.get("mode") != "OOS" else "OOS",
            })
        self._executive_page.update_performance_table(perf_rows)
```

with:

```python
        # Feed executive dashboard controller cards
        self._executive_page.update_controller_cards(controllers)
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/hmi/test_main_window_audit_gaps.py::TestExecutiveDashboardWiring -v && uv run pytest tests/hmi/pages/test_executive_dashboard.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_hmi/src/smart_pid_hmi/main.py tests/hmi/test_main_window_audit_gaps.py
git commit -m "feat(hmi): wire main.py to use controller cards in executive dashboard"
```

---

### Task 5: Run full test suite and lint

**Files:** None (verification only)

- [ ] **Step 1: Run full HMI test suite**

Run: `uv run pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 2: Run lint**

Run: `uv run --with ruff ruff check packages/smart_pid_hmi/src/smart_pid_hmi/pages/executive_dashboard.py`
Expected: No errors (or fix any that appear)

- [ ] **Step 3: Fix any issues found**

If lint or tests fail, fix the issues and re-run.

- [ ] **Step 4: Commit fixes if needed**

```bash
git add -u
git commit -m "fix(hmi): lint and test fixes for executive dashboard cards"
```

---

### Task 6: Update spec docs

Per project convention, UI changes must update relevant spec docs.

**Files:**
- Modify: `docs/smartPIDv2.md` — Executive Dashboard section
- Modify: `docs/superpowers/specs/2026-04-02-smart-pid-v2-architecture-design.md` — if Executive Dashboard is mentioned

- [ ] **Step 1: Search for Executive Dashboard references in spec docs**

Search `docs/` for mentions of "Executive Dashboard", "performance table", or "executive" to find all sections that need updating.

- [ ] **Step 2: Update descriptions**

Change any references to "performance table" or "grid" to describe the new controller cards layout. Mention: dashboard-tile cards, per-controller process values, AI optimization section, performance indices grid, responsive flow layout.

- [ ] **Step 3: Commit doc updates**

```bash
git add docs/
git commit -m "docs: update specs to reflect executive dashboard cards redesign"
```
