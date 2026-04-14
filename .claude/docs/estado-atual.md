# Estado atual — 2026-04-14

## Tarefa concluída: fix/fuzzy-dr-stuck-in-active

### Problema relatado
Motor fuzzy não funciona corretamente quando o loop está configurado para
DISTURBANCE_REJECTION (SP_TRACKING está perfeito). Screenshot mostrava
PV oscilando continuamente em torno de SP, sem ajuste algum de Ti.

### Causa raiz
A máquina de estados de `FuzzyEngineV2DisturbanceRejection` (em
`packages/smart_pid_core/src/smart_pid_core/domain/services/fuzzy_engine_v2.py`)
exige que `|e/span|` permaneça abaixo de 2% por **3 amostras consecutivas**
para sair de ACTIVE → SETTLING. Em uma oscilação sustentada (ciclo limite),
o erro cruza zero brevemente a cada cruzamento mas nunca permanece dentro
da banda por 3 amostras seguidas, então a máquina **fica travada em ACTIVE
para sempre, sem nunca emitir uma decisão** — fuzzy não tuna nada.

Reprodução (script, 400 amostras de erro senoidal ±20% span, período 20s):
- Estado: `{'IDLE': 1, 'ACTIVE': 399}`
- Decisões emitidas: 0

### Correção
Adicionados em `FuzzyEngineV2DisturbanceRejection`:
1. Tracking durante ACTIVE de todos os erros vistos e contagem de
   cruzamentos por zero (`_active_errors`, `_active_zero_crossings`).
2. `_is_limit_cycle()`: retorna True se ACTIVE ≥ 5τ AND ≥ 3 cruzamentos
   por zero — heurística para distinguir oscilação sustentada de uma
   recuperação lenta de disturbance transiente.
3. `_finalise_oscillation()`: força encerramento do evento como
   "oscilação alta", computando σ dos erros observados durante ACTIVE
   e setando `t_rec_norm` saturado em SLOW. Isso aciona a regra
   `({"osc": "HIGH"}, "A")` → AUMENT Ti → amortecimento.
4. `_reset_event_state()` extraído para uso comum.

Após a correção: 7 decisões em 400 amostras, todas Δ_Ti=+0.028 (Ti up).

### Verificação
- `pytest tests/core/unit/test_fuzzy_engine_v2.py`: **57/57 passaram**
  (incluindo o novo teste `test_sustained_oscillation_breaks_active_lock_and_increases_ti`).
- `pytest tests/core/integration/test_ai_worker*.py`: **15/15 passaram**.
- Ruff: clean para `fuzzy_engine_v2.py`.

### Arquivos modificados
- `packages/smart_pid_core/src/smart_pid_core/domain/services/fuzzy_engine_v2.py`
- `tests/core/unit/test_fuzzy_engine_v2.py`

### Branch
`fix/fuzzy-dr-stuck-in-active` criada a partir de `main`.
**Não commitado, não mergeado.** Aguardando aprovação do usuário.

### Próximos passos
1. Usuário revisa as mudanças.
2. Após aprovação: commit + merge para `main`.

---

## Histórico recente (já merged em main)

### fix/sim-param-change-preserves-pv (commit 8d8af4d, merge 70b0fd7)
`SimulatorAdapter.set_parameters/set_preset` substituía `ctrl.model` por
nova instância de `ProcessModel`, zerando estado interno e fazendo PV
saltar para 0. Adicionado `ProcessModel.update_parameters()` que
re-discretiza preservando estado (ou seeda novo estado via mínimos
quadrados quando dimensão muda).

### fix/simulator-pid-params-race (commit 5e722c4, merge f8e9cfb)
Simulator escrevia kp/ti/td em OPC-UA a cada tick (50 ms) e
sobrescrevia escritas do AI optimizer. Fix: `_tick` só ecoa estado;
config de PID vai via `_sync_pid_config_to_opcua`.
