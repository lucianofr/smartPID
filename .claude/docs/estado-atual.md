# Estado atual — 2026-04-13

## Tarefa concluída: fix/sim-param-change-preserves-pv

### Problema relatado
Usuário reportou que alterações nos parâmetros do processo na tela
Simulator Control (Gain K, Tau1, Tau2, Dead Time) "aparentemente não
estão sendo aplicadas". Screenshot mostrava CUSTOM/K=5/τ1=120/τ2=40/L=30.

### Causa raiz
`SimulatorAdapter.set_parameters()` (e `set_preset()`) substituíam o
`ctrl.model` por uma **nova** instância de `ProcessModel`, descartando o
estado interno (`_state`, `_pv`). No próximo tick o novo modelo partia
de estado zero, então a PV saltava de seu valor corrente (ex: 60) para
~0 e, com τ1 grande (120s), demorava minutos para responder. Para o
usuário dava a impressão de que os parâmetros não tinham efeito.

Reprodução (confirmada via script):
- Antes da troca: PV=60.00 (K=1.2, CO=50, regime permanente)
- 1 tick após `set_parameters(K=5, τ1=120, τ2=40, L=30)`: PV=0.00

### Correção
1. Novo método `ProcessModel.update_parameters(gain, tau1, tau2, dead_time)`
   em `packages/smart_pid_core/src/smart_pid_core/domain/services/process_models.py`:
   re-discretiza preservando `_state` quando a dimensão não muda. Quando
   muda (FOPTD↔SOPTD ou dead_time cruzando 0) inicializa novo estado via
   mínimos quadrados para que `Cd @ x ≈ pv_prévio`.
2. `SimulatorAdapter.set_parameters()` e `set_preset()` passam a chamar
   `ctrl.model.update_parameters(...)` em vez de criar nova instância
   (`packages/smart_pid_core/src/smart_pid_core/adapters/inbound/simulator_adapter.py`).
3. Teste de regressão `test_set_parameters_preserves_pv_continuity`
   adicionado em `tests/core/unit/test_simulator_adapter.py`.

### Verificação
- `pytest tests/core/unit/test_simulator_adapter.py tests/core/unit/test_process_models.py`: **57/57 passaram**.
- Script manual: PV=60 antes → PV=60 imediatamente após
  `set_parameters` → evolui com a nova dinâmica (aos 5min chega a 96
  rumo ao novo regime K*CO=250).
- Falhas pré-existentes não relacionadas: `test_ai_e2e.py` flaky,
  `test_config_users_db.py` e `test_opcua_server.py` (port/config).

### Arquivos modificados
- `packages/smart_pid_core/src/smart_pid_core/domain/services/process_models.py`
- `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/simulator_adapter.py`
- `tests/core/unit/test_simulator_adapter.py`

### Branch
`fix/sim-param-change-preserves-pv` criada a partir de `main`.
**Não commitado, não mergeado.** Aguardando aprovação do usuário.

### Próximos passos
1. Usuário revisa as mudanças na branch.
2. Após aprovação: commit + merge para `main`.
