# Estado atual — 2026-04-14

## Tarefa concluída e mergeada: fix/fuzzy-dr-post-damp-cooldown (e9aca60)

### Problema relatado
Mesmo com os centros assimétricos, o log real mostrava:
- 14:07 LC #1: Ti 2.64 → 3.37
- 14:09 LC #2: Ti 3.37 → 4.30
- 14:13 evento lento (E_max=1.50 T_rec=18τ OSC=0.11): Ti 4.30 → 3.87
  → reduziu 10% logo após amortecimento → malha voltou a oscilar.

### Causa raiz
Após uma correção de ciclo limite a malha está na BORDA da estabilidade
— Ti acabou de ser subido porque foi detectada oscilação. Uma redução
pelo event-path imediatamente depois desfaz a proteção que o próprio
motor acabou de prescrever. Mesmo redução pequena (−10%) é suficiente
para reinstalar oscilação.

### Correção
Adicionado **cooldown pós-damping** em `FuzzyEngineV2DisturbanceRejection`:
- Nova constante `_LIMIT_CYCLE_COOLDOWN_CYCLES = 5`.
- Novo estado `_cooldown_remaining: int` (contador por ciclo de AI).
- Em `compute_adjustment`:
  - Firing `limit_cycle` → rearma `_cooldown_remaining = 5`.
  - Qualquer outra chamada → decrementa `_cooldown_remaining`.
  - Se decisão é redução (`Δ_Ti < 0`) E `_cooldown_remaining > 0` →
    força `Δ_Ti = 0` (reduction suppressed).
- Reasoning reporta `DR/cooldown=k` enquanto ativo (operador vê no log).

Replay do log:
- 14:07 LC: Ti 2.64 → 3.37 (cooldown=5 armado)
- 14:09 LC: Ti 3.37 → 4.30 (cooldown=5 re-armado)
- 14:13 evento lento: Δ=0 `[DR/cooldown=4]` (retreat suprimido)
- 14:15, 14:17, 14:19, 14:21: Ti mantém 4.30 (cooldown escorre até 0)
- 14:23: cooldown expirado, event-path pode reduzir cautelosamente.
  Se oscilação volta, LC fire rearma cooldown.

### Verificação
- `pytest tests/core/unit/test_fuzzy_engine_v2.py + AI worker tests`:
  **79/79 passaram**.
- Ruff: clean.

---

## Histórico anterior: fix/fuzzy-dr-asymmetric-retreat (6732123)

### Problema relatado
Log real mostrava Ti convergindo para 4.58 (malha estabilizada) e então
retrocedendo em 3 eventos consecutivos (Δ=−0.30, −0.30, −0.19)
colapsando Ti para 1.82 — voltando a instabilizar. Hunting clássico.

### Causa raiz
Centros de saída simétricos em `OUTPUT_CENTERS_DR`: `RM=-0.30, R=-0.10`
vs `A=+0.15, AM=+0.40`. Como a regra R1 (HIGH/SLOW/STABLE → RM) dispara
em qualquer recuperação lenta (inclusive pós-estabilização), três
eventos `HIGH/SLOW/STABLE` derrubam Ti 60% antes da primeira correção
de ciclo limite conseguir reagir.

### Correção
`OUTPUT_CENTERS_DR` ficou assimétrico: `RM=-0.10, R=-0.05, M=0.0,
A=+0.15, AM=+0.40`. Direção de redução preservada; magnitude capada a
1/3 da original. Duas reduções consecutivas não conseguem mais superar
uma correção de ciclo limite (+0.275).

Replay do log do usuário com o fix:
- 12:43: Ti 4.58 → 4.12 (antes: 3.21)
- 12:45: Ti 4.12 → 3.71 (antes: 2.25)
- 12:47: Ti 3.71 → 3.44 (antes: 1.82)
- Drop total: 25% (antes: 60%) — limite cycle subsequente restaura.

### Verificação
- `pytest tests/core/unit/test_fuzzy_engine_v2.py + AI worker tests`:
  **78/78 passaram**.
- Ruff: clean.

---

## Histórico anterior no main

### fix/fuzzy-dr-mf-saturation (cecc9b3)

### Problema relatado
Mesmo após os 3 fixes anteriores de DR, uma entrada real do AI log
mostrava: `FuzzyV2[DR]: E_max=1.50 T_rec=13.20τ OSC=0.42 Δ_Ti=+0.000`.
Os indicadores claramente capturavam oscilação, mas o motor fuzzy
devolvia Δ_Ti=0 e Ti ficava estagnado.

### Causas raízes (duas, acopladas)

**1. Trapezóides de borda direita não saturavam.**
`MF_T_REC_DR.SLOW = trap(5, 7, 10, 10)` — para qualquer `x > 10` o
`trapezoidal_mf` retorna 0. Com `T_rec=13.20τ` **todas as três**
memberships de t_rec viraram 0, nenhuma regra que cita t_rec disparou,
`denominator=0` → `Δ_Ti=0`. Mesmo bug potencial em `MF_E_MAX_DR.HIGH`
e `MF_OSC_DR.HIGH`. Corrigido estendendo o platô `(c=d=1e9)`.

**2. Regras com osc:MED reduzem Ti mesmo num ciclo limite.**
Mesmo com a MF corrigida, regra R1' (`HIGH/SLOW/MED → R=−0.10`) faz
reduzir Ti — alimentando a oscilação quando o evento era, na verdade,
meia-onda de um ciclo limite mal classificado. Corrigido: em
`_finalise_event`, se `osc_norm ≥ 0.3` (onset de MED), redireciona para
`_finalise_oscillation` (sempre amortece).

### Verificação
- `pytest tests/core/unit/test_fuzzy_engine_v2.py + AI worker tests`:
  **76/76 passaram**.
- Ruff: clean.
- End-to-end (AIWorker + bus, oscilação ±20% por 400 amostras):
  **13 decisões positivas, 0 negativas, Ti = 1.0 → 23.5**.

### Arquivos modificados
- `packages/smart_pid_core/src/smart_pid_core/domain/services/fuzzy_engine_v2.py`
- `tests/core/unit/test_fuzzy_engine_v2.py`

---

## Histórico recente no main

- `fix/fuzzy-dr-mf-saturation` (**61899ae** / merge cecc9b3) — este fix.
- `fix/fuzzy-dr-eager-limit-cycle` (c379441 / merge 5be1837) — dispara
  decisão de ciclo limite em cada ciclo de AI.
- `fix/fuzzy-dr-limit-cycle-decision-strength` (4ef2e6e / 7391773) —
  alimenta inputs `(LOW,FAST,HIGH)` ao finalisar ciclo limite.
- `fix/fuzzy-dr-stuck-in-active` (71cae7c / ce50b83) — primeira detecção
  de ciclo limite (ACTIVE ≥ 5τ + crossings).
- `fix/sim-param-change-preserves-pv` (8d8af4d / 70b0fd7) — preserva
  PV ao trocar parâmetros do processo.
- `fix/simulator-pid-params-race` (5e722c4 / f8e9cfb) — simulator
  parou de sobrescrever kp/ti/td via OPC-UA em cada tick.
