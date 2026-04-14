# Estado atual — 2026-04-14

## Tarefa concluída: fix/fuzzy-dr-limit-cycle-decision-strength

### Problema relatado
Após o fix anterior (`fix/fuzzy-dr-stuck-in-active`, já no main), o
sistema continuava oscilando e o motor fuzzy não estava aumentando Ti
o suficiente para amortecer.

### Causa raiz
O `_finalise_oscillation` anterior alimentava a base de regras com
`e_max_norm=1.5` (saturado) + `t_rec_norm=10` (saturado) + osc real,
o que disparava simultaneamente:
- Regra **R1'** (HIGH/SLOW/MED → R = −0.10) — REDUZIR Ti (mais agressivo!)
- Regra **R5** (osc:HIGH → A = +0.15) — AUMENTAR Ti

Ambas com força similar (~0.2), produzindo Δ_Ti ≈ +0.028 (quase
cancelamento). Em algumas amplitudes a R1' chegava a vencer, deixando
Δ_Ti negativo e PIORANDO a oscilação.

A causa semântica: um ciclo limite NÃO é um evento de disturbance, então
passar `e_max` e `t_rec` da excursão observada confunde a base de regras.

### Correção
1. `_finalise_oscillation` agora alimenta inputs que descrevem
   fisicamente um limit cycle: `(e_max=0.0, t_rec=0.0, osc=1.0)` =
   "sem excursão transiente, mas oscilação alta". Isso casa **rule R2**
   (LOW/FAST/HIGH → AM = +0.4) sem ambiguidade, mais R5 (osc:HIGH → A).
   Δ_Ti resultante ≈ **+0.275 por ciclo** (vs ~+0.028 antes).
2. Threshold abaixado de 5τ → **3τ** (`_OSC_LOCK_TAU_THRESHOLD`) para
   engajar mais cedo.
3. Adicionado `_decision_source` ("event" | "limit_cycle") usado no
   `reasoning` para o operador ver no log de IA por que a decisão foi
   tomada: `FuzzyV2[DR/limit-cycle]: …`.
4. Novo teste `test_simulated_loop_actually_damps_under_decisions`:
   simulando 12 ciclos de IA, Ti deve crescer ≥ 2×.

Resultado: simulando 8 ciclos com oscilação ±20%, Ti vai de 1.0 → 6.98
(7× em 8 ciclos), quebrando o ciclo limite rapidamente.

### Verificação
- `pytest tests/core/unit/test_fuzzy_engine_v2.py`: **58/58 passaram**
  (incluindo dois novos testes de limit-cycle).
- `pytest tests/core/integration/test_ai_worker*.py`: **15/15 passaram**.
- Ruff: clean para `fuzzy_engine_v2.py`.

### Arquivos modificados
- `packages/smart_pid_core/src/smart_pid_core/domain/services/fuzzy_engine_v2.py`
- `tests/core/unit/test_fuzzy_engine_v2.py`

### Branch
`fix/fuzzy-dr-limit-cycle-decision-strength` criada a partir de `main`.
**Não commitada, não mergeada.** Aguardando aprovação do usuário.

### Próximos passos
1. Usuário revisa.
2. Após aprovação: commit + merge para `main`.

---

## Histórico recente (já merged em main)

### fix/fuzzy-dr-stuck-in-active (commit 71cae7c, merge ce50b83)
DR ficava preso em ACTIVE em oscilação sustentada (zero crossings
brevíssimos, nunca 3 amostras seguidas dentro da banda). Adicionada
detecção de ciclo limite (ACTIVE ≥ 5τ + ≥ 3 zero crossings) que força
finalize. **PORÉM** a decisão era fraca demais — corrigido na tarefa
acima.

### fix/sim-param-change-preserves-pv (commit 8d8af4d, merge 70b0fd7)
`SimulatorAdapter.set_parameters/set_preset` substituía `ctrl.model`
por nova instância, zerando estado interno e fazendo PV saltar para 0.
Adicionado `ProcessModel.update_parameters()` que re-discretiza
preservando estado.

### fix/simulator-pid-params-race (commit 5e722c4, merge f8e9cfb)
Simulator escrevia kp/ti/td em OPC-UA a cada tick e sobrescrevia
escritas do AI optimizer. Fix: tick só ecoa estado; config via
`_sync_pid_config_to_opcua`.
