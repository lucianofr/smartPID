# Estado Atual — Loop Config Dialog

**Data:** 2026-04-05
**Branch:** feat/loop-config-dialog (8 commits, NÃO merged)
**Base:** main em 9730d9c

---

## O que foi feito

### 1. DTOs expandidos (Task 1)
- 6 sub-models pydantic: PIDParamsDTO, ScaleConfigDTO, AIConfigDTO, TagBindingsDTO, ControlOptsDTO, IOOptsDTO
- ControllerCreate/Update/Response com 30+ campos
- `packages/smart_pid_domain/src/smart_pid_domain/dtos/controllers.py`

### 2. Backend API expandida (Task 2)
- `_to_response()` mapeia todos os campos do Controller
- `_body_to_controller()` constrói Controller completo a partir do DTO
- `update_controller` lida com todos os sub-models nested
- `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/controllers.py`

### 3. ControllerDialog com modo edição (Task 3)
- Renomeado AddControllerDialog → ControllerDialog
- `edit_data: dict | None` para preencher todos os campos
- Modo edit: título "Edit Controller — TAG", nome read-only
- `packages/smart_pid_hmi/src/smart_pid_hmi/widgets/controller_dialog.py`

### 4. Botão de engrenagem nos cards (Task 4)
- QPushButton("⚙") no header de cada ControllerCardWidget
- Signal `settings_requested(int)` emitido no clique
- Não propaga controller_selected
- `packages/smart_pid_hmi/src/smart_pid_hmi/widgets/controller_card.py`

### 5. API client update_controller (Task 5)
- `update_controller(id, data)` em APIClientPort, APIClient, MockAPIClient
- PUT /controllers/{id}
- `packages/smart_pid_hmi/src/smart_pid_hmi/services/`

### 6. Wiring no MainWindow (Task 6)
- DashboardPage.settings_requested → MainWindow._on_edit_controller
- Background fetch → _edit_dialog_signal → _open_edit_dialog (thread-safe)
- P&ID tab escondida (sem nav button, widget mantido dormant)
- `packages/smart_pid_hmi/src/smart_pid_hmi/main.py`

### 7. __main__.py adicionado
- `python -m smart_pid_hmi` agora funciona

### 8. Cleanup (Task 7)
- Lint limpo, __all__ sorted, refs flat corrigidas em testes

---

## Pendências

- **NÃO fazer merge** até avaliar conflitos com a outra conversa (audit V2 em feat/hmi-theme-redesign)
- Main foi resetada para 9730d9c (commits espúrios de subagentes removidos)
- Conflitos esperados em: main.py, dashboard_page.py, controller_card.py, enums.py

## Testes

- Domain: 138 passed
- Core API: 13 passed
- HMI (widgets + services + main): 201 passed
