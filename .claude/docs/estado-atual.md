# Estado Atual — User Management HMI (COMPLETO)

**Data:** 2026-04-05
**Branch:** feat/user-management-post-active (6 commits acima de fbbc570)

---

## Implementação Completa — 5 Tasks

### Task 1: Backend — POST /users + active toggle
- `POST /users` endpoint admin-only (201, 409 duplicado, 403 não-admin)
- `active: bool | None` no `UserUpdate` DTO
- `UserRepository.update()` aceita `active`
- Audit log usa `json.dumps()` (seguro contra injection)
- 5 novos testes (16 total no test_user_api.py)

### Task 2: HMI API Client — user CRUD
- `list_users`, `create_user`, `update_user`, `deactivate_user` em APIClient, Port e Mock
- 4 testes com httpx MockTransport

### Task 3: User Management Page
- `UserManagementPage` com tabela 5 colunas, botão "+ New User"
- `CreateUserDialog` (username, password, role + validação)
- `EditUserDialog` (role, password opcional)
- Botões Edit/Deactivate/Reactivate por linha
- 8 testes

### Task 4: MainWindow Integration
- Botão "Users" na toolbar (hidden por default, visível só para ADMIN)
- `_users_loaded_signal` para thread-safe reload
- Signals CRUD wired entre page e API client
- 4 testes de visibilidade por role

### Task 5: Lint + Verificação
- Import order fix em main.py (ruff)
- 32/32 testes passando

## Commits
- b15bf35 feat(api): add POST /users endpoint and active toggle on PUT /users/{id}
- 1060e11 fix(api): use json.dumps for audit details, include active field
- c76239b feat(hmi): add user CRUD methods to APIClient and MockAPIClient
- 5dea966 feat(hmi): add UserManagementPage with create/edit dialogs
- 554a4f2 feat(hmi): integrate UserManagementPage into MainWindow with admin-only visibility
- c3611e3 chore: fix import order in main.py (ruff)

## Arquivos criados/modificados
- `packages/smart_pid_domain/src/smart_pid_domain/dtos/users.py` (edit)
- `packages/smart_pid_core/src/smart_pid_core/adapters/outbound/user_repo.py` (edit)
- `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/users.py` (edit)
- `packages/smart_pid_hmi/src/smart_pid_hmi/services/ports.py` (edit)
- `packages/smart_pid_hmi/src/smart_pid_hmi/services/api_client.py` (edit)
- `packages/smart_pid_hmi/src/smart_pid_hmi/services/mock_service.py` (edit)
- `packages/smart_pid_hmi/src/smart_pid_hmi/pages/user_management_page.py` (create)
- `packages/smart_pid_hmi/src/smart_pid_hmi/main.py` (edit)
- `tests/core/integration/test_user_api.py` (edit)
- `tests/hmi/services/test_api_client_users.py` (create)
- `tests/hmi/pages/test_user_management_page.py` (create)
- `tests/hmi/test_main_window_users.py` (create)

## Próximos Passos
- Merge para main (aguardando autorização do usuário)
