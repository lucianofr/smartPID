# User Management HMI — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a user management page to the HMI so admins can create, edit, deactivate, and reactivate users.

**Architecture:** Extend the existing `/users` backend router with `POST` (create) and `active` toggle on `PUT`. Add matching HMI API client methods, a new `UserManagementPage` with table + dialogs, and wire it into `MainWindow` with admin-only visibility.

**Tech Stack:** FastAPI, PySide6, httpx, pydantic v2, pytest + pytest-asyncio

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `packages/smart_pid_domain/src/smart_pid_domain/dtos/users.py` | Edit | Add `active` to `UserUpdate` |
| `packages/smart_pid_core/src/smart_pid_core/adapters/outbound/user_repo.py` | Edit | Handle `active` in `update()`, add `reactivate()` |
| `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/users.py` | Edit | Add `POST /users` endpoint |
| `packages/smart_pid_hmi/src/smart_pid_hmi/services/ports.py` | Edit | Add user CRUD to `APIClientPort` |
| `packages/smart_pid_hmi/src/smart_pid_hmi/services/api_client.py` | Edit | Add user CRUD methods |
| `packages/smart_pid_hmi/src/smart_pid_hmi/services/mock_service.py` | Edit | Add mock user CRUD methods |
| `packages/smart_pid_hmi/src/smart_pid_hmi/pages/user_management_page.py` | Create | Table + dialogs for user management |
| `packages/smart_pid_hmi/src/smart_pid_hmi/main.py` | Edit | Toolbar button + page wiring |
| `tests/core/integration/test_user_api.py` | Edit | Add tests for POST and reactivation |
| `tests/hmi/services/test_api_client_users.py` | Create | Test user CRUD methods on APIClient |
| `tests/hmi/pages/test_user_management_page.py` | Create | Test page + dialogs |

---

## Task 1: Extend Backend — `UserUpdate` DTO + Repository

**Files:**
- Modify: `packages/smart_pid_domain/src/smart_pid_domain/dtos/users.py`
- Modify: `packages/smart_pid_core/src/smart_pid_core/adapters/outbound/user_repo.py`
- Modify: `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/users.py`
- Modify: `tests/core/integration/test_user_api.py`

### Step 1: Write failing tests for create user and reactivation

- [ ] **Step 1a: Add tests to `tests/core/integration/test_user_api.py`**

Add these test classes at the end of the file:

```python
class TestCreateUser:
    @pytest.mark.asyncio
    async def test_create_user_as_admin(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        resp = await client.post(
            "/users",
            json={"username": "newop", "password": "pass123", "role": "OPERATOR"},
            headers=admin_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["username"] == "newop"
        assert data["role"] == "OPERATOR"
        assert data["active"] is True

    @pytest.mark.asyncio
    async def test_create_user_duplicate_username(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        resp = await client.post(
            "/users",
            json={"username": "admin", "password": "x", "role": "OPERATOR"},
            headers=admin_headers,
        )
        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_create_user_as_operator_forbidden(
        self, client: AsyncClient, user_headers: dict[str, str]
    ) -> None:
        resp = await client.post(
            "/users",
            json={"username": "hacker", "password": "x", "role": "ADMIN"},
            headers=user_headers,
        )
        assert resp.status_code == 403


class TestReactivateUser:
    @pytest.mark.asyncio
    async def test_reactivate_user_via_put(
        self,
        client: AsyncClient,
        admin_headers: dict[str, str],
        user_repo: UserRepository,
    ) -> None:
        await user_repo.create("deactivated", hash_password("pass"), "OPERATOR")
        await user_repo.deactivate(2)
        resp = await client.put(
            "/users/2", json={"active": True}, headers=admin_headers
        )
        assert resp.status_code == 200
        assert resp.json()["active"] is True

    @pytest.mark.asyncio
    async def test_deactivate_via_put(
        self,
        client: AsyncClient,
        admin_headers: dict[str, str],
        user_repo: UserRepository,
    ) -> None:
        await user_repo.create("toban", hash_password("pass"), "OPERATOR")
        resp = await client.put(
            "/users/2", json={"active": False}, headers=admin_headers
        )
        assert resp.status_code == 200
        assert resp.json()["active"] is False
```

- [ ] **Step 1b: Run tests to verify they fail**

Run: `uv run pytest tests/core/integration/test_user_api.py -v -k "TestCreateUser or TestReactivateUser"`
Expected: FAIL — `POST /users` returns 405 (method not allowed), `active` field not recognized

### Step 2: Extend `UserUpdate` DTO with `active` field

- [ ] **Step 2a: Edit `packages/smart_pid_domain/src/smart_pid_domain/dtos/users.py`**

```python
"""User management DTOs."""
from __future__ import annotations

from pydantic import BaseModel

from smart_pid_domain.enums import UserRole  # noqa: TC001


class UserResponse(BaseModel):
    id: int
    username: str
    role: UserRole
    active: bool = True
    created_at: str = ""


class UserUpdate(BaseModel):
    role: UserRole | None = None
    password: str | None = None
    active: bool | None = None
```

### Step 3: Extend `UserRepository.update()` to handle `active`

- [ ] **Step 3a: Edit the `update` method in `packages/smart_pid_core/src/smart_pid_core/adapters/outbound/user_repo.py`**

Replace the `update` method signature and body to accept `active`:

```python
    async def update(
        self,
        user_id: int,
        role: str | None = None,
        password_hash: str | None = None,
        active: bool | None = None,
    ) -> User | None:
        """Update user fields. Returns updated user or None if not found."""
        updates: list[str] = []
        params: list[str | int] = []
        if role is not None:
            updates.append("perfil = ?")
            params.append(role)
        if password_hash is not None:
            updates.append("senha_hash = ?")
            params.append(password_hash)
        if active is not None:
            updates.append("ativo = ?")
            params.append(1 if active else 0)
        if not updates:
            return await self.get_by_id(user_id)
        params.append(user_id)
        await self._db.execute(
            f"UPDATE Usuarios SET {', '.join(updates)} WHERE id = ?",
            params,
        )
        await self._db.commit()
        return await self.get_by_id(user_id)
```

### Step 4: Add `POST /users` endpoint and extend `PUT` handler

- [ ] **Step 4a: Edit `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/users.py`**

Add import for `UserCreate` and the new endpoint. Full file:

```python
"""User management router — admin only."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from smart_pid_core.adapters.inbound.api.auth import hash_password
from smart_pid_core.adapters.inbound.api.dependencies import (
    get_audit_repo,
    get_user_repo,
    require_admin,
)
from smart_pid_core.adapters.outbound.audit_repo import AuditRepository  # noqa: TC001
from smart_pid_core.adapters.outbound.user_repo import UserRepository  # noqa: TC001
from smart_pid_domain.dtos.auth import UserClaims, UserCreate  # noqa: TC001
from smart_pid_domain.dtos.users import UserResponse, UserUpdate
from smart_pid_domain.enums import AuditAction

router = APIRouter()


@router.get("")
async def list_users(
    _admin: Annotated[UserClaims, Depends(require_admin)],
    user_repo: Annotated[UserRepository, Depends(get_user_repo)],
) -> list[UserResponse]:
    users = await user_repo.list_all()
    return [
        UserResponse(
            id=u.id, username=u.username, role=u.role,
            active=u.active, created_at=u.created_at,
        )
        for u in users
    ]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_user(
    body: UserCreate,
    admin: Annotated[UserClaims, Depends(require_admin)],
    user_repo: Annotated[UserRepository, Depends(get_user_repo)],
    audit_repo: Annotated[AuditRepository, Depends(get_audit_repo)],
) -> UserResponse:
    existing = await user_repo.get_by_username(body.username)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Username '{body.username}' already exists",
        )
    pw_hash = hash_password(body.password)
    user = await user_repo.create(body.username, pw_hash, body.role)
    await audit_repo.record(
        admin.user_id, admin.username, AuditAction.CREATE_USER,
        f"user:{user.id}", f'{{"username": "{user.username}", "role": "{user.role}"}}',
    )
    return UserResponse(
        id=user.id, username=user.username, role=user.role,
        active=user.active, created_at=user.created_at,
    )


@router.get("/{user_id}")
async def get_user(
    user_id: int,
    _admin: Annotated[UserClaims, Depends(require_admin)],
    user_repo: Annotated[UserRepository, Depends(get_user_repo)],
) -> UserResponse:
    user = await user_repo.get_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return UserResponse(
        id=user.id, username=user.username, role=user.role,
        active=user.active, created_at=user.created_at,
    )


@router.put("/{user_id}")
async def update_user(
    user_id: int,
    body: UserUpdate,
    admin: Annotated[UserClaims, Depends(require_admin)],
    user_repo: Annotated[UserRepository, Depends(get_user_repo)],
    audit_repo: Annotated[AuditRepository, Depends(get_audit_repo)],
) -> UserResponse:
    pw_hash = hash_password(body.password) if body.password else None
    user = await user_repo.update(
        user_id, role=body.role, password_hash=pw_hash, active=body.active,
    )
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    await audit_repo.record(
        admin.user_id, admin.username, AuditAction.UPDATE_USER,
        f"user:{user_id}", f'{{"role": "{user.role}", "active": {str(user.active).lower()}}}',
    )
    return UserResponse(
        id=user.id, username=user.username, role=user.role,
        active=user.active, created_at=user.created_at,
    )


@router.delete("/{user_id}")
async def deactivate_user(
    user_id: int,
    admin: Annotated[UserClaims, Depends(require_admin)],
    user_repo: Annotated[UserRepository, Depends(get_user_repo)],
    audit_repo: Annotated[AuditRepository, Depends(get_audit_repo)],
) -> UserResponse:
    user = await user_repo.deactivate(user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    await audit_repo.record(
        admin.user_id, admin.username, AuditAction.DEACTIVATE_USER,
        f"user:{user_id}", None,
    )
    return UserResponse(
        id=user.id, username=user.username, role=user.role,
        active=user.active, created_at=user.created_at,
    )
```

- [ ] **Step 4b: Check if `AuditAction.CREATE_USER` exists, add if missing**

Check `packages/smart_pid_domain/src/smart_pid_domain/enums.py` for `CREATE_USER` in `AuditAction`. If missing, add it:

```python
class AuditAction(StrEnum):
    LOGIN = "LOGIN"
    CREATE_USER = "CREATE_USER"  # add this line if missing
    UPDATE_USER = "UPDATE_USER"
    DEACTIVATE_USER = "DEACTIVATE_USER"
    # ... rest of existing entries
```

### Step 5: Run tests and verify they pass

- [ ] **Step 5a: Run the full test file**

Run: `uv run pytest tests/core/integration/test_user_api.py -v`
Expected: ALL PASS

- [ ] **Step 5b: Commit**

```bash
git add packages/smart_pid_domain/src/smart_pid_domain/dtos/users.py \
       packages/smart_pid_domain/src/smart_pid_domain/enums.py \
       packages/smart_pid_core/src/smart_pid_core/adapters/outbound/user_repo.py \
       packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/users.py \
       tests/core/integration/test_user_api.py
git commit -m "feat(api): add POST /users endpoint and active toggle on PUT /users/{id}"
```

---

## Task 2: HMI API Client — User CRUD Methods

**Files:**
- Modify: `packages/smart_pid_hmi/src/smart_pid_hmi/services/ports.py`
- Modify: `packages/smart_pid_hmi/src/smart_pid_hmi/services/api_client.py`
- Modify: `packages/smart_pid_hmi/src/smart_pid_hmi/services/mock_service.py`
- Create: `tests/hmi/services/test_api_client_users.py`

### Step 1: Write failing tests for APIClient user methods

- [ ] **Step 1a: Create `tests/hmi/services/test_api_client_users.py`**

```python
"""Tests for APIClient user management methods."""
from __future__ import annotations

import httpx

from smart_pid_hmi.services.api_client import APIClient
from smart_pid_hmi.services.session import Session


def _mock_transport(status: int, json_body: dict | list) -> httpx.MockTransport:
    """Create a mock transport that always returns the given response."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json=json_body)
    return httpx.MockTransport(handler)


def _make_client(status: int = 200, json_body: dict | list | None = None) -> APIClient:
    transport = _mock_transport(status, json_body or {})
    session = Session()
    return APIClient(base_url="http://test:8000", session=session, transport=transport)


def test_list_users():
    data = [
        {"id": 1, "username": "admin", "role": "ADMIN", "active": True, "created_at": "2026-01-01"},
        {"id": 2, "username": "op1", "role": "OPERATOR", "active": True, "created_at": "2026-01-02"},
    ]
    client = _make_client(200, data)
    users = client.list_users()
    assert len(users) == 2
    assert users[0].username == "admin"
    assert users[1].role == "OPERATOR"


def test_create_user():
    data = {"id": 3, "username": "newuser", "role": "OPERATOR", "active": True, "created_at": ""}
    client = _make_client(201, data)
    user = client.create_user("newuser", "pass123", "OPERATOR")
    assert user.username == "newuser"
    assert user.role == "OPERATOR"


def test_update_user():
    data = {"id": 2, "username": "op1", "role": "SUPERVISOR", "active": True, "created_at": ""}
    client = _make_client(200, data)
    user = client.update_user(2, role="SUPERVISOR")
    assert user.role == "SUPERVISOR"


def test_deactivate_user():
    data = {"id": 2, "username": "op1", "role": "OPERATOR", "active": False, "created_at": ""}
    client = _make_client(200, data)
    user = client.deactivate_user(2)
    assert user.active is False
```

- [ ] **Step 1b: Run tests to verify they fail**

Run: `uv run pytest tests/hmi/services/test_api_client_users.py -v`
Expected: FAIL — `APIClient` has no attribute `list_users`

### Step 2: Add user CRUD to `APIClientPort`

- [ ] **Step 2a: Edit `packages/smart_pid_hmi/src/smart_pid_hmi/services/ports.py`**

Add at the end of the `APIClientPort` class, before `# Lifecycle`:

```python
    # User management
    def list_users(self) -> list[UserResponse]: ...
    def create_user(
        self, username: str, password: str, role: str,
    ) -> UserResponse: ...
    def update_user(
        self, user_id: int, role: str | None = ...,
        password: str | None = ..., active: bool | None = ...,
    ) -> UserResponse: ...
    def deactivate_user(self, user_id: int) -> UserResponse: ...
```

And add `UserResponse` to the `TYPE_CHECKING` imports:

```python
if TYPE_CHECKING:
    from datetime import datetime
    from pathlib import Path
    from queue import SimpleQueue

    from smart_pid_domain.dtos import (
        CommandResponse,
        ControllerResponse,
        HistoryResponse,
        SimulatorStatusResponse,
        TokenResponse,
    )
    from smart_pid_domain.dtos.users import UserResponse
```

### Step 3: Add user CRUD methods to `APIClient`

- [ ] **Step 3a: Edit `packages/smart_pid_hmi/src/smart_pid_hmi/services/api_client.py`**

Add import at the top (inside the existing `from smart_pid_domain.dtos import` block or as a new import):

```python
from smart_pid_domain.dtos.users import UserResponse
```

Add these methods to the `APIClient` class, before `close()`:

```python
    def list_users(self) -> list[UserResponse]:
        resp = self._http.get("/users", headers=self._headers())
        resp.raise_for_status()
        return [UserResponse.model_validate(u) for u in resp.json()]

    def create_user(self, username: str, password: str, role: str) -> UserResponse:
        resp = self._http.post(
            "/users",
            json={"username": username, "password": password, "role": role},
            headers=self._headers(),
        )
        resp.raise_for_status()
        return UserResponse.model_validate(resp.json())

    def update_user(
        self, user_id: int, role: str | None = None,
        password: str | None = None, active: bool | None = None,
    ) -> UserResponse:
        body: dict = {}
        if role is not None:
            body["role"] = role
        if password is not None:
            body["password"] = password
        if active is not None:
            body["active"] = active
        resp = self._http.put(
            f"/users/{user_id}", json=body, headers=self._headers(),
        )
        resp.raise_for_status()
        return UserResponse.model_validate(resp.json())

    def deactivate_user(self, user_id: int) -> UserResponse:
        resp = self._http.delete(f"/users/{user_id}", headers=self._headers())
        resp.raise_for_status()
        return UserResponse.model_validate(resp.json())
```

### Step 4: Add mock user methods to `MockAPIClient`

- [ ] **Step 4a: Edit `packages/smart_pid_hmi/src/smart_pid_hmi/services/mock_service.py`**

Add import at the top:

```python
from smart_pid_domain.dtos.users import UserResponse
```

Add these methods to the `MockAPIClient` class at the end:

```python
    def list_users(self) -> list[UserResponse]:
        return [
            UserResponse(id=1, username="admin", role="ADMIN", active=True, created_at="2026-01-01"),
            UserResponse(id=2, username="operator", role="OPERATOR", active=True, created_at="2026-01-02"),
            UserResponse(id=3, username="inactive", role="OPERATOR", active=False, created_at="2026-01-03"),
        ]

    def create_user(self, username: str, password: str, role: str) -> UserResponse:
        return UserResponse(id=99, username=username, role=role, active=True, created_at="")

    def update_user(
        self, user_id: int, role: str | None = None,
        password: str | None = None, active: bool | None = None,
    ) -> UserResponse:
        return UserResponse(
            id=user_id, username="user", role=role or "OPERATOR",
            active=active if active is not None else True, created_at="",
        )

    def deactivate_user(self, user_id: int) -> UserResponse:
        return UserResponse(id=user_id, username="user", role="OPERATOR", active=False, created_at="")
```

### Step 5: Run tests and verify they pass

- [ ] **Step 5a: Run the new test file**

Run: `uv run pytest tests/hmi/services/test_api_client_users.py -v`
Expected: ALL PASS

- [ ] **Step 5b: Commit**

```bash
git add packages/smart_pid_hmi/src/smart_pid_hmi/services/ports.py \
       packages/smart_pid_hmi/src/smart_pid_hmi/services/api_client.py \
       packages/smart_pid_hmi/src/smart_pid_hmi/services/mock_service.py \
       tests/hmi/services/test_api_client_users.py
git commit -m "feat(hmi): add user CRUD methods to APIClient and MockAPIClient"
```

---

## Task 3: User Management Page — Table + Dialogs

**Files:**
- Create: `packages/smart_pid_hmi/src/smart_pid_hmi/pages/user_management_page.py`
- Create: `tests/hmi/pages/test_user_management_page.py`

### Step 1: Write failing tests for the page

- [ ] **Step 1a: Create `tests/hmi/pages/test_user_management_page.py`**

```python
"""Tests for UserManagementPage."""
from __future__ import annotations

from PySide6.QtWidgets import QApplication

from smart_pid_hmi.pages.user_management_page import (
    CreateUserDialog,
    EditUserDialog,
    UserManagementPage,
)
from smart_pid_hmi.themes.isa101 import ISA101Theme

app = QApplication.instance() or QApplication([])


def test_page_creation():
    theme = ISA101Theme()
    page = UserManagementPage(theme=theme)
    assert page is not None
    assert page.user_table.columnCount() == 5


def test_populate_users():
    theme = ISA101Theme()
    page = UserManagementPage(theme=theme)
    users = [
        {"id": 1, "username": "admin", "role": "ADMIN", "active": True, "created_at": "2026-01-01"},
        {"id": 2, "username": "op1", "role": "OPERATOR", "active": False, "created_at": "2026-01-02"},
    ]
    page.populate_users(users)
    assert page.user_table.rowCount() == 2


def test_create_dialog_fields():
    dialog = CreateUserDialog()
    assert dialog._username_edit.text() == ""
    assert dialog._password_edit.text() == ""
    assert dialog._role_combo.currentText() == "OPERATOR"


def test_create_dialog_validation():
    dialog = CreateUserDialog()
    # Empty fields — get_data returns None
    assert dialog.get_data() is None


def test_create_dialog_valid_data():
    dialog = CreateUserDialog()
    dialog._username_edit.setText("newuser")
    dialog._password_edit.setText("secret")
    dialog._role_combo.setCurrentText("SUPERVISOR")
    data = dialog.get_data()
    assert data == ("newuser", "secret", "SUPERVISOR")


def test_edit_dialog_prepopulated():
    dialog = EditUserDialog(current_role="SUPERVISOR")
    assert dialog._role_combo.currentText() == "SUPERVISOR"
    assert dialog._password_edit.text() == ""


def test_edit_dialog_returns_data():
    dialog = EditUserDialog(current_role="OPERATOR")
    dialog._role_combo.setCurrentText("ADMIN")
    dialog._password_edit.setText("newpass")
    data = dialog.get_data()
    assert data == ("ADMIN", "newpass")


def test_edit_dialog_empty_password_returns_none():
    dialog = EditUserDialog(current_role="OPERATOR")
    dialog._role_combo.setCurrentText("SUPERVISOR")
    data = dialog.get_data()
    assert data == ("SUPERVISOR", None)
```

- [ ] **Step 1b: Run tests to verify they fail**

Run: `uv run pytest tests/hmi/pages/test_user_management_page.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'smart_pid_hmi.pages.user_management_page'`

### Step 2: Implement the page and dialogs

- [ ] **Step 2a: Create `packages/smart_pid_hmi/src/smart_pid_hmi/pages/user_management_page.py`**

```python
"""UserManagementPage — admin-only page for user CRUD operations."""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from smart_pid_hmi.themes.base import ThemeBase

_COLUMNS = ["Username", "Role", "Active", "Created At", "Actions"]
_ROLES = ["OPERATOR", "SUPERVISOR", "ADMIN"]


class CreateUserDialog(QDialog):
    """Dialog for creating a new user."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Create User")
        self.setMinimumWidth(320)

        layout = QFormLayout(self)

        self._username_edit = QLineEdit()
        self._username_edit.setPlaceholderText("Username")
        layout.addRow("Username:", self._username_edit)

        self._password_edit = QLineEdit()
        self._password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._password_edit.setPlaceholderText("Password")
        layout.addRow("Password:", self._password_edit)

        self._role_combo = QComboBox()
        self._role_combo.addItems(_ROLES)
        self._role_combo.setCurrentText("OPERATOR")
        layout.addRow("Role:", self._role_combo)

        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
        )
        self._buttons.accepted.connect(self.accept)
        self._buttons.rejected.connect(self.reject)
        layout.addRow(self._buttons)

    def get_data(self) -> tuple[str, str, str] | None:
        """Return (username, password, role) or None if validation fails."""
        username = self._username_edit.text().strip()
        password = self._password_edit.text()
        if not username or not password:
            return None
        return (username, password, self._role_combo.currentText())


class EditUserDialog(QDialog):
    """Dialog for editing user role and optionally resetting password."""

    def __init__(
        self, current_role: str, parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Edit User")
        self.setMinimumWidth(300)

        layout = QFormLayout(self)

        self._role_combo = QComboBox()
        self._role_combo.addItems(_ROLES)
        self._role_combo.setCurrentText(current_role)
        layout.addRow("Role:", self._role_combo)

        self._password_edit = QLineEdit()
        self._password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._password_edit.setPlaceholderText("Leave empty to keep current")
        layout.addRow("New Password:", self._password_edit)

        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
        )
        self._buttons.accepted.connect(self.accept)
        self._buttons.rejected.connect(self.reject)
        layout.addRow(self._buttons)

    def get_data(self) -> tuple[str, str | None]:
        """Return (role, password_or_None)."""
        password = self._password_edit.text()
        return (self._role_combo.currentText(), password if password else None)


class UserManagementPage(QWidget):
    """Admin page for managing users: list, create, edit, deactivate/reactivate."""

    user_create_requested = Signal(str, str, str)       # username, password, role
    user_update_requested = Signal(int, str, str, object)  # id, role, password, active
    user_deactivate_requested = Signal(int)             # user_id
    user_reactivate_requested = Signal(int)             # user_id
    refresh_requested = Signal()

    def __init__(self, theme: ThemeBase, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._theme = theme
        self._users: list[dict] = []

        layout = QVBoxLayout(self)

        # Header row
        header = QHBoxLayout()
        title = QLabel("User Management")
        title.setStyleSheet(
            f"font-size: {theme.font_size_title}px; font-weight: bold; "
            f"color: {theme.fg_primary};"
        )
        header.addWidget(title)
        header.addStretch()
        self._create_btn = QPushButton("+ New User")
        self._create_btn.clicked.connect(self._on_create_clicked)
        header.addWidget(self._create_btn)
        layout.addLayout(header)

        # User table
        self.user_table = QTableWidget(0, len(_COLUMNS))
        self.user_table.setHorizontalHeaderLabels(_COLUMNS)
        self.user_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch,
        )
        self.user_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.user_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.user_table)

        # Status bar
        self._status_label = QLabel("Ready")
        self._status_label.setStyleSheet(f"color: {theme.fg_secondary};")
        layout.addWidget(self._status_label)

    def set_status(self, msg: str) -> None:
        """Update the status label text."""
        self._status_label.setText(msg)

    def populate_users(self, users: list[dict]) -> None:
        """Fill the table from a list of user dicts."""
        self._users = users
        self.user_table.setRowCount(0)
        for user in users:
            row = self.user_table.rowCount()
            self.user_table.insertRow(row)

            self.user_table.setItem(row, 0, QTableWidgetItem(user.get("username", "")))
            self.user_table.setItem(row, 1, QTableWidgetItem(user.get("role", "")))

            active = user.get("active", True)
            active_item = QTableWidgetItem("Yes" if active else "No")
            active_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.user_table.setItem(row, 2, active_item)

            self.user_table.setItem(row, 3, QTableWidgetItem(user.get("created_at", "")))

            # Action buttons in a widget
            actions = QWidget()
            actions_layout = QHBoxLayout(actions)
            actions_layout.setContentsMargins(2, 2, 2, 2)

            edit_btn = QPushButton("Edit")
            user_id = user.get("id", 0)
            edit_btn.clicked.connect(lambda checked, uid=user_id, r=row: self._on_edit_clicked(uid, r))
            actions_layout.addWidget(edit_btn)

            if active:
                toggle_btn = QPushButton("Deactivate")
                toggle_btn.clicked.connect(
                    lambda checked, uid=user_id: self._on_deactivate_clicked(uid),
                )
            else:
                toggle_btn = QPushButton("Reactivate")
                toggle_btn.clicked.connect(
                    lambda checked, uid=user_id: self.user_reactivate_requested.emit(uid),
                )
            actions_layout.addWidget(toggle_btn)

            self.user_table.setCellWidget(row, 4, actions)

    def _on_create_clicked(self) -> None:
        dialog = CreateUserDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            if data is not None:
                self.user_create_requested.emit(*data)

    def _on_edit_clicked(self, user_id: int, row: int) -> None:
        role_item = self.user_table.item(row, 1)
        current_role = role_item.text() if role_item else "OPERATOR"
        dialog = EditUserDialog(current_role=current_role, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            role, password = dialog.get_data()
            self.user_update_requested.emit(user_id, role, password or "", None)

    def _on_deactivate_clicked(self, user_id: int) -> None:
        reply = QMessageBox.question(
            self, "Confirm Deactivation",
            "Deactivate this user? They will no longer be able to log in.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.user_deactivate_requested.emit(user_id)

    def apply_theme(self, theme: ThemeBase) -> None:
        """Update theme references when the global theme changes."""
        self._theme = theme
```

### Step 3: Run tests and verify they pass

- [ ] **Step 3a: Run the page tests**

Run: `uv run pytest tests/hmi/pages/test_user_management_page.py -v`
Expected: ALL PASS

- [ ] **Step 3b: Commit**

```bash
git add packages/smart_pid_hmi/src/smart_pid_hmi/pages/user_management_page.py \
       tests/hmi/pages/test_user_management_page.py
git commit -m "feat(hmi): add UserManagementPage with create/edit dialogs"
```

---

## Task 4: MainWindow Integration — Toolbar + Wiring

**Files:**
- Modify: `packages/smart_pid_hmi/src/smart_pid_hmi/main.py`
- Create: `tests/hmi/test_main_window_users.py`

### Step 1: Write failing tests for admin-only button visibility

- [ ] **Step 1a: Create `tests/hmi/test_main_window_users.py`**

```python
"""Tests for Users button visibility in MainWindow based on role."""
from __future__ import annotations

import base64
import json
import time

from PySide6.QtWidgets import QApplication

from smart_pid_hmi.config import HMISettings
from smart_pid_hmi.main import MainWindow
from smart_pid_hmi.services.mock_service import MockAPIClient, MockTelemetrySource
from smart_pid_hmi.services.session import Session

app = QApplication.instance() or QApplication([])


def _make_token(role: str) -> str:
    header = base64.urlsafe_b64encode(b'{"alg":"HS256"}').rstrip(b"=").decode()
    payload = base64.urlsafe_b64encode(json.dumps({
        "sub": "1", "username": "testuser", "role": role,
        "exp": int(time.time()) + 86400,
    }).encode()).rstrip(b"=").decode()
    return f"{header}.{payload}.mocksig"


def _make_window() -> tuple[MainWindow, Session]:
    from smart_pid_hmi.bus_bridge import BusBridge
    settings = HMISettings(mock_mode=True)
    session = Session()
    api_client = MockAPIClient()
    telemetry_source = MockTelemetrySource()
    bus_bridge = BusBridge(queue=telemetry_source.queue, refresh_ms=100)
    window = MainWindow(
        settings=settings, session=session,
        api_client=api_client, telemetry_source=telemetry_source,
        bus_bridge=bus_bridge,
    )
    return window, session


def test_users_button_hidden_by_default():
    window, _ = _make_window()
    assert not window._users_btn.isVisible()


def test_users_button_visible_for_admin():
    window, session = _make_window()
    session.store_token(_make_token("ADMIN"))
    window._show_admin_controls()
    assert window._users_btn.isVisible()


def test_users_button_hidden_for_operator():
    window, session = _make_window()
    session.store_token(_make_token("OPERATOR"))
    window._show_admin_controls()
    assert not window._users_btn.isVisible()


def test_users_button_hidden_for_supervisor():
    window, session = _make_window()
    session.store_token(_make_token("SUPERVISOR"))
    window._show_admin_controls()
    assert not window._users_btn.isVisible()
```

- [ ] **Step 1b: Run tests to verify they fail**

Run: `uv run pytest tests/hmi/test_main_window_users.py -v`
Expected: FAIL — `MainWindow` has no attribute `_users_btn`

### Step 2: Integrate page into MainWindow

- [ ] **Step 2a: Edit `packages/smart_pid_hmi/src/smart_pid_hmi/main.py`**

**Add import** at the top with the other page imports:

```python
from smart_pid_hmi.pages.user_management_page import UserManagementPage
```

**Add a new signal** to the class, alongside the existing ones:

```python
    _users_loaded_signal = Signal(list)
```

**In `__init__`**, connect the signal (near the other signal connections at the top of `__init__`):

```python
        self._users_loaded_signal.connect(self._on_users_loaded)
```

**In `__init__`**, after the Settings button block (line ~124), add the Users button:

```python
        self._users_btn = toolbar.addAction("Users")
        self._users_btn.triggered.connect(
            lambda: self._show_users_page()
        )
        self._users_btn.setVisible(False)
```

**In `__init__`**, after `self._settings_page` is added to the stack (line ~151), add:

```python
        self._user_mgmt_page = UserManagementPage(theme=theme)
        self._stack.addWidget(self._user_mgmt_page)
```

**In `__init__`**, after the `self._settings_page.theme_changed.connect(...)` line (line ~172), add signal wiring:

```python
        self._user_mgmt_page.user_create_requested.connect(self._create_user)
        self._user_mgmt_page.user_update_requested.connect(self._update_user)
        self._user_mgmt_page.user_deactivate_requested.connect(self._deactivate_user)
        self._user_mgmt_page.user_reactivate_requested.connect(self._reactivate_user)
```

**In `_login_success`**, after `self._check_simulator_available()` (line ~200), add:

```python
        self._show_admin_controls()
```

**Add these new methods** to the `MainWindow` class:

```python
    def _show_admin_controls(self) -> None:
        """Show admin-only UI elements based on session role."""
        is_admin = self._session.role and self._session.role.upper() == "ADMIN"
        self._users_btn.setVisible(is_admin)

    def _show_users_page(self) -> None:
        """Switch to user management page and refresh user list."""
        self._stack.setCurrentWidget(self._user_mgmt_page)
        self._load_users()

    def _load_users(self) -> None:
        """Load users from API and populate user management page."""
        def do_load():
            try:
                users = self._api_client.list_users()
                user_dicts = [u.model_dump() for u in users]
                self._users_loaded_signal.emit(user_dicts)
            except Exception as e:
                logger.error("Failed to load users: %s", e)

        threading.Thread(target=do_load, daemon=True).start()

    @Slot(list)
    def _on_users_loaded(self, users: list[dict]) -> None:
        """Populate user management page with loaded data."""
        self._user_mgmt_page.populate_users(users)
        self._user_mgmt_page.set_status(f"Loaded {len(users)} users")

    def _create_user(self, username: str, password: str, role: str) -> None:
        def do_create():
            try:
                self._api_client.create_user(username, password, role)
                self._load_users()
            except Exception as e:
                self._api_error_signal.emit(str(e))
        threading.Thread(target=do_create, daemon=True).start()

    def _update_user(self, user_id: int, role: str, password: str, active: object) -> None:
        def do_update():
            try:
                pw = password if password else None
                active_val = active if isinstance(active, bool) else None
                self._api_client.update_user(user_id, role=role, password=pw, active=active_val)
                self._load_users()
            except Exception as e:
                self._api_error_signal.emit(str(e))
        threading.Thread(target=do_update, daemon=True).start()

    def _deactivate_user(self, user_id: int) -> None:
        def do_deactivate():
            try:
                self._api_client.deactivate_user(user_id)
                self._load_users()
            except Exception as e:
                self._api_error_signal.emit(str(e))
        threading.Thread(target=do_deactivate, daemon=True).start()

    def _reactivate_user(self, user_id: int) -> None:
        def do_reactivate():
            try:
                self._api_client.update_user(user_id, active=True)
                self._load_users()
            except Exception as e:
                self._api_error_signal.emit(str(e))
        threading.Thread(target=do_reactivate, daemon=True).start()
```

### Step 3: Run tests and verify they pass

- [ ] **Step 3a: Run the MainWindow users tests**

Run: `uv run pytest tests/hmi/test_main_window_users.py -v`
Expected: ALL PASS

- [ ] **Step 3b: Run the full test suite to check for regressions**

Run: `uv run pytest tests/ -v --timeout=30`
Expected: ALL PASS (or known unrelated failures only)

- [ ] **Step 3c: Commit**

```bash
git add packages/smart_pid_hmi/src/smart_pid_hmi/main.py \
       packages/smart_pid_hmi/src/smart_pid_hmi/pages/user_management_page.py \
       tests/hmi/test_main_window_users.py
git commit -m "feat(hmi): integrate UserManagementPage into MainWindow with admin-only visibility"
```

---

## Task 5: Lint + Final Verification

**Files:** All modified files

### Step 1: Run linter

- [ ] **Step 1a: Run ruff**

Run: `uv run --with ruff ruff check packages/ tests/ --fix`
Expected: No errors (or fix any auto-fixable issues)

### Step 2: Run full test suite

- [ ] **Step 2a: Run all tests**

Run: `uv run pytest tests/ -v --timeout=30`
Expected: ALL PASS

### Step 3: Final commit if lint fixes were needed

- [ ] **Step 3a: Commit any lint fixes**

```bash
git add -u
git commit -m "chore: fix lint issues from user management implementation"
```
