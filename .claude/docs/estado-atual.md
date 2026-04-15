# Estado atual — 2026-04-14

## Tarefa concluída e mergeada: fix/fuzzy-dr-inter-event-overshoot (b873aa9)

### Problema relatado
Ti estabilizou em 8.9, mas cada distúrbio ainda mostrava overshoot no
gráfico. O usuário pediu Ti ~20-25s e perguntou: "crie uma estratégia
para medir o overshoot e corrigir o Ti".

### Causa raiz
O detector de overshoot existente (`_active_zero_crossings >= 1` em
`_finalise_event`) só dispara se o erro cruzar zero DENTRO de um único
evento (durante ACTIVE ou SETTLING). No processo do usuário o overshoot
surge DEPOIS do evento original ter finalizado (state → IDLE): o
recovery parece limpo, então um NOVO evento, de sinal oposto, dispara
como sendo o próprio overshoot.

O log mostrava o padrão alternado: `big pos / small neg / big pos /
small neg / big pos...` — os eventos "small neg" eram na verdade os
overshoots dos "big pos".

### Correção — inter-event overshoot tracker
Nova lógica em `FuzzyEngineV2DisturbanceRejection`:
1. Em cada finalização (normal ou limit-cycle), `_stamp_last_event()`
   registra o sinal inicial (`_last_event_sign`) e a fonte
   (`_last_event_source = "event" | "limit_cycle" | "overshoot"`).
2. Em cada transição IDLE → ACTIVE, compara o sinal do novo evento com
   `_last_event_sign`. Se:
   - `_last_event_source == "event"` (não "limit_cycle")
   - sinais opostos
   - gap `< 5τ`

   então flag `_overshoot_pending = True` e marca o evento atual
   (`_current_event_is_overshoot`) para não propagar seu sinal adiante.
3. `compute_adjustment` consome `_overshoot_pending` PRIMEIRO (antes do
   event-path habitual), emitindo Δ_Ti=+0.275 com tag `[DR/overshoot]`.
4. O guard `_current_event_is_overshoot` impede "overshoot do overshoot"
   em sequências `big + small + big + small + big + small`.

### Replay do cenário do usuário (Ti=8.9041)
```
big pos disturbance:   Δ=0.0000   Ti=8.9041  [DR]
small neg overshoot:   Δ=+0.2750  Ti=11.3527 [DR/overshoot]
big pos disturbance:   Δ=0.0000   Ti=11.3527 [DR]
small neg overshoot:   Δ=+0.2750  Ti=14.4747 [DR/overshoot]
big pos disturbance:   Δ=0.0000   Ti=14.4747 [DR]
(próximos ciclos:      Ti → 18.45 → 23.55 → ~30)
```

Após 3 overshoots detectados, Ti cresce de 8.9 para ~23.5, no alvo
do usuário (20-25).

### Verificação
- 88/88 tests pass. Ruff clean.
- Cooldown já existente é rearmado por overshoot também (previne hunting).

---

## Histórico anterior: fix/fuzzy-dr-overshoot-triggers-damp (99ccfbb)

### Problema relatado
Com Ti estabilizado em ~11.35, cada recuperação de distúrbio mostrava
overshoot no gráfico (PV caía para 30, voltava passando de 50 até 55,
e só depois assentava em 50). Classic "Ti pequeno demais". O log fuzzy:
`E_max=1.50 T_rec=16.10τ OSC=0.04 Δ_Ti=0` — Ti nem subia.

### Causa raiz
`_finalise_event` computava `osc_norm` a partir de σ dos 15 samples
**pós-evento**. Ao chegar a SETTLING, o overshoot já tinha decaído,
então σ ≈ 0 e OSC ≈ 0. A regra R1 (HIGH/SLOW/STABLE → M) segurava Ti.
Mas o sinal estava lá: `_active_zero_crossings = 1` capturado durante
ACTIVE (o error cruzou zero do + para o - no overshoot) — apenas
não era lido antes do `_reset_event_state()` apagar o contador.

### Correção
`_finalise_event` checa `_active_zero_crossings >= 1` PRIMEIRO.
Se houve qualquer cruzamento durante ACTIVE, o controlador overshot
na recuperação → redireciona para `_finalise_oscillation` (Ti up
+0.275). Recuperações limpas (zero cruzamentos de sinal) continuam
pelo caminho do evento normal.

Nova constante: `_EVENT_OVERSHOOT_MIN_CROSSINGS = 1`. Diferente do
`_OSC_LOCK_MIN_CROSSINGS = 2` usado em `update_sample` / eager check
(que exige 2 para disparar durante ACTIVE, sem esperar o finalise).

### Verificação
- Teste `test_event_with_overshoot_damps_not_holds` reproduz um
  overshoot com 1 zero crossing → passa a emitir Δ_Ti = +0.275.
- Teste `test_event_without_overshoot_still_holds` confirma que
  recuperação limpa (zero crossings) ainda segura Ti.
- 86/86 tests pass. Ruff clean.

---

## Histórico anterior: fix/fuzzy-dr-no-reduce-on-stable (c87bd40)

### Problema relatado
Depois do fix de falsos-positivos, o Ti não mais estourava o guardrail,
mas continuava sendo reduzido a cada distúrbio lento com OSC baixíssimo.
Log: Ti 11.7 → 10.5 → 9.5 → 8.5 em três eventos com OSC=0.04 (100 %
STABLE). Usuário queria Ti ~25.

### Causa raiz
Regra R1 (HIGH/SLOW/STABLE → RM=−0.10) disparava em TODO distúrbio
lento, mesmo sem qualquer sinal de oscilação. Interpretação: "controle
muito lento, reduz Ti". Mas uma malha conservadora pode ser lenta **sem
oscilar** — é margem de segurança, não defeito de tuning. R1 puxava o
Ti continuamente para a borda da estabilidade.

### Correção
Redefinido: reduções só acontecem quando há **sinal de oscilação**.
- R1 HIGH/SLOW/STABLE → **M** (antes RM)
- R1'' MED/SLOW/STABLE → **M** (antes R)
- R1' HIGH/SLOW/MED → R (mantido: tem sinal de OSC mild)
- R4 MED/MED/MED → R (mantido: tem OSC MED)
- R5 (osc:HIGH → A) e AM (limit-cycle) inalteradas.

### Replay do cenário do usuário
Eventos 19:59 / 20:01 / 20:03 (OSC=0.04 STABLE):
- Antes: Δ=−0.10 cada, Ti 11.7 → 10.5 → 9.5 → 8.5
- Depois: **Δ=0 cada, Ti mantém em 11.72**

E ainda:
- Oscilação genuína (HIGH/FAST/HIGH): Δ=+0.15 ✓
- Limit-cycle (LOW/FAST/HIGH): Δ=+0.275 ✓

Ti agora mantém o valor que as correções de limit-cycle alcançaram —
o equilíbrio fica acima da fronteira de oscilação, não em cima dela.

### Verificação
- 84/84 tests pass (fuzzy + AI worker). Ruff clean.

---

## Histórico anterior: fix/fuzzy-dr-osc-false-positives (e8b4903)

### Problema relatado
Depois do fix que fez DR usar stats, Ti cresceu descontroladamente
até bater no guardrail de 100 (quando o ideal era ~15-20). Com Ti tão
alto, PV nunca voltava ao SP (erro em regime).

Log mostrava 3 firings consecutivos de limit-cycle com OSC=0.79, 1.00,
0.97 enquanto o gráfico mostrava apenas um grande distúrbio isolado
recuperando.

### Causa raiz
`_osc_from_stats` com gate frouxo (zc ≥ 2 AND reversals ≥ 2) não
distinguia oscilação sustentada de um distúrbio isolado. O pk_pk de
uma única excursão grande (PV caiu e voltou, overshoot no recovery)
ficava na janela rolante de 200 amostras por ~3 minutos, inflando
OSC enquanto o loop já tinha voltado à calmaria.

### Correção
Gate mais restrito no `_osc_from_stats`:

1. `zero_crossings ≥ 4` (antes 2) — exige ≥ 2 ciclos completos.
2. `reversals ≥ 4` (antes 2) — exige ≥ 2 reversões completas.
3. `mean_abs / pk_pk ≥ 0.20` (novo) — senoide pura ≈ 0.32, spike
   isolado sobre baseline quieto ≪ 0.1. Rejeita excursões isoladas.

### Verificação
- Scenario "real osc" (zc=10, rev=9, ratio=0.33): Ti cresce
  4.44 → 5.67 → 7.23 → 9.22 → 11.75 ✓
- Scenario "isolated disturbance" (zc=2, rev=2, ratio=0.04):
  Ti hold em 48.77 ✓ (antes: runaway para 100)
- 83/83 tests pass. Ruff clean.

---

## Histórico anterior: fix/fuzzy-dr-stats-based-osc (dde58bc)

### Problema relatado
Usuário mostrou: `OSC:1.00 pkpk:46.59 rev:9 zc:10` na barra de status
(StatsWorker detectava oscilação clara) mas o log fuzzy:
```
E_max=1.50 T_rec=17.00τ OSC=0.16 Δ_Ti=-0.100
```
— reduziu Ti apesar da oscilação. Ti nunca subia, loop oscilava sem fim.

### Causa raiz
DR calculava OSC como `2σ` sobre **15 amostras pós-evento**. Essa
janela curta subamostra o ciclo de oscilação → σ subdimensionado →
OSC ≈ 0.2 (interpretado como STABLE) enquanto pk_pk real = 46% span.

SP_TRACKING não tem esse problema: usa `pk_pk_frac / 0.15` filtrado
por `zc ≥ 2 AND reversals ≥ 2` — métricas que o StatsWorker já calcula
sobre janela rolante.

### Correção
DR agora espelha SP_TRACKING:
1. Novo método `FuzzyEngineV2DisturbanceRejection.compute_adjustment_from_stats()`
   — computa `stats_osc` com **exatamente a mesma fórmula** do SP_TRACKING:
   `min(1.0, pk_pk_frac / 0.15)` filtrado por `zc ≥ 2 AND reversals ≥ 2`.
2. Se `stats_osc ≥ 0.3` (onset de MED), sobrescreve `_decision_inputs`
   com `(LOW=0, FAST=0, stats_osc)` — a base de regras dispara R2 (AM)
   e R5 (A) sem ambiguidade.
3. `FuzzyEngineV2Dispatcher.compute_adjustment_from_stats` roteia
   snapshots de stats para DR (antes só SP).
4. `AIWorker` envia stats para DR também (antes só para SP).

### Replay do cenário do usuário
- Ti=4.4474, stats (pkpk=46.59, zc=10, rev=9):
  - Cycle 1: Δ=+0.2750  Ti=5.6704 [DR/limit-cycle]
  - Cycle 2: Δ=+0.2750  Ti=7.2298 [DR/limit-cycle]
  - Cycles 3-10 (stats quiet): Δ=0 Ti=7.2298 [DR] — segura.

### Verificação
- 81/81 tests pass (fuzzy unit + AI worker integration).
- Ruff clean.
- Replay manual reproduz o comportamento desejado.

---

## Histórico anterior: fix/fuzzy-dr-post-damp-cooldown (e9aca60)

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
