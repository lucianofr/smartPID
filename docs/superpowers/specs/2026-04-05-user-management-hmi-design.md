# User Management HMI — Design Spec

**Date:** 2026-04-05
**Status:** Approved
**Scope:** Add user management page to HMI, extend backend with create-user endpoint

---

## 1. Problem

The backend exposes a full user CRUD API at `/users` (admin-only), but the HMI has no page, no API client methods, and no toolbar entry to manage users. Admins cannot create, edit, or deactivate users without direct API calls.

## 2. Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Visibility | Button visible only for ADMIN role | ISA-101: show only what the operator can use |
| Create user | New `POST /users` endpoint (admin-only) | Clean separation from `/auth/register` |
| Reactivation | Extend `UserUpdate` with `active` field | No new endpoint needed |
| Layout | Table + inline action buttons + modals | Familiar admin pattern, consistent with HMI style |

## 3. Backend Changes

### 3.1 New Endpoint: `POST /users`

- **Router:** `routers/users.py`
- **Auth:** `require_admin` dependency
- **Body:** `UserCreate(username: str, password: str, role: UserRole)`
- **Logic:** validate username uniqueness, hash password, insert via `UserRepository`, record audit log
- **Response:** `UserResponse`
- **Error:** 409 Conflict if username already exists

### 3.2 Extend `PUT /users/{id}`

- Add `active: bool | None = None` to `UserUpdate` DTO
- When `active=True`, reactivate the user
- When `active=False`, deactivate (same as DELETE but via PUT)
- Audit log records the change

### 3.3 New DTO

```python
class UserCreate(BaseModel):
    username: str
    password: str
    role: UserRole
```

Added to `smart_pid_domain/dtos/users.py`.

### 3.4 UserRepository Extension

- `create(username: str, password_hash: str, role: UserRole) -> UserRow` — INSERT with uniqueness check
- `reactivate(user_id: int) -> UserRow | None` — SET `active=1`

## 4. HMI API Client

### 4.1 New Methods on `APIClient`

```python
def list_users(self) -> list[UserResponse]          # GET /users
def create_user(username, password, role) -> UserResponse  # POST /users
def update_user(user_id, role?, password?, active?) -> UserResponse  # PUT /users/{id}
def deactivate_user(user_id) -> UserResponse         # DELETE /users/{id}
```

### 4.2 Port Protocol

Add matching methods to `APIClientPort` protocol in `services/ports.py`.

### 4.3 MockAPIClient

Add matching mock implementations with in-memory user list for testing.

## 5. HMI Page: `UserManagementPage`

### 5.1 File

`packages/smart_pid_hmi/src/smart_pid_hmi/pages/user_management_page.py`

### 5.2 Layout

```
┌──────────────────────────────────────────────┐
│  User Management                [+ New User] │
├──────────────────────────────────────────────┤
│ Username │ Role       │ Active │ Created  │ ⚙ │
│──────────┼────────────┼────────┼──────────┼───│
│ admin    │ ADMIN      │  ✓     │ 2026-04… │ ✎ │
│ john     │ OPERATOR   │  ✓     │ 2026-04… │ ✎⊘│
│ jane     │ SUPERVISOR │  ✗     │ 2026-04… │ ✎↻│
└──────────────────────────────────────────────┘
│ Status: Ready                                 │
└──────────────────────────────────────────────┘
```

- **⚙ column:** Edit (✎) always present; Deactivate (⊘) for active users, Reactivate (↻) for inactive
- **Status bar:** feedback messages after operations

### 5.3 Signals

```python
class UserManagementPage(QWidget):
    user_create_requested = Signal(str, str, str)     # username, password, role
    user_update_requested = Signal(int, str, str, object)  # id, role, password, active
    user_deactivate_requested = Signal(int)           # user_id
    user_reactivate_requested = Signal(int)           # user_id
    refresh_requested = Signal()
```

### 5.4 Dialogs

**CreateUserDialog** (`QDialog`):
- Fields: username (`QLineEdit`), password (`QLineEdit`, echo mode password), role (`QComboBox` with ADMIN/SUPERVISOR/OPERATOR)
- Buttons: Cancel, Create
- Validation: username and password non-empty

**EditUserDialog** (`QDialog`):
- Fields: role (`QComboBox`), password (`QLineEdit`, optional — empty means no change)
- Buttons: Cancel, Save
- Pre-populated with current role

**Deactivation Confirmation:**
- `QMessageBox.question` — "Deactivate user '{username}'? They will no longer be able to log in."

### 5.5 Data Flow

1. Page emits signal → MainWindow handler → `_safe_api_call` → APIClient method
2. On success: page calls `load_users()` to refresh table
3. On error: status bar shows error message

## 6. MainWindow Integration

### 6.1 Toolbar Button

- Action "Users" added after "Settings" in toolbar
- Created with `setVisible(False)` by default
- In `_login_success`: check `self._session.role == "ADMIN"`, if true call `self._users_btn.setVisible(True)`

### 6.2 Wiring

```python
# Page creation
self._user_mgmt_page = UserManagementPage(theme=theme)
self._stack.addWidget(self._user_mgmt_page)

# Toolbar
self._users_btn = toolbar.addAction("Users")
self._users_btn.triggered.connect(lambda: self._show_users_page())
self._users_btn.setVisible(False)

# Signal connections
self._user_mgmt_page.user_create_requested.connect(self._create_user)
self._user_mgmt_page.user_deactivate_requested.connect(self._deactivate_user)
# etc.
```

### 6.3 `_show_users_page`

Switches stack to user management page and triggers a refresh (load users from API).

## 7. Testing

### 7.1 Backend Integration Tests

**File:** `tests/core/integration/test_api_user_management.py`

- `test_create_user_as_admin` — POST /users returns 201 with UserResponse
- `test_create_user_duplicate_username` — POST /users returns 409
- `test_create_user_as_operator_forbidden` — POST /users returns 403
- `test_reactivate_user` — PUT /users/{id} with `active: true`
- `test_update_user_active_field` — verify active toggle works

### 7.2 HMI Unit Tests

**File:** `tests/hmi/unit/test_user_management_page.py`

- `test_create_dialog_validation` — empty fields rejected
- `test_edit_dialog_prepopulated` — role combo set correctly
- `test_users_button_hidden_for_operator` — toolbar visibility
- `test_users_button_visible_for_admin` — toolbar visibility
- `test_table_populated` — mock data renders correctly

## 8. Files Changed/Created

| File | Action | Layer |
|------|--------|-------|
| `domain/dtos/users.py` | Edit — add `UserCreate`, extend `UserUpdate` | Domain |
| `core/adapters/inbound/api/routers/users.py` | Edit — add `POST /users`, extend `PUT` | Backend |
| `core/adapters/outbound/user_repo.py` | Edit — add `create`, `reactivate` | Backend |
| `hmi/services/api_client.py` | Edit — add user CRUD methods | HMI |
| `hmi/services/ports.py` | Edit — extend `APIClientPort` | HMI |
| `hmi/services/mock_service.py` | Edit — add mock user methods | HMI |
| `hmi/pages/user_management_page.py` | **Create** | HMI |
| `hmi/main.py` | Edit — toolbar button, page wiring | HMI |
| `tests/core/integration/test_api_user_management.py` | **Create** | Test |
| `tests/hmi/unit/test_user_management_page.py` | **Create** | Test |
