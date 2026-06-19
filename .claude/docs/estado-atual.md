# Estado atual — 2026-06-19

## Fatia 0+1 (Web HMI) — Foundation + Live Dashboard — CONCLUÍDA (branch `feat/web-fatia01-foundation-dashboard`, worktree `.worktrees/main-web-hmi`)

### O que foi entregue (Tasks 1–12)
- **Backend:** ponte `RealtimeBridge` (EventBus→WS, consumidor único não-bloqueante via
  `run_in_executor`, espelhando `TelemetryPublisher`), endpoint `GET /ws/realtime`,
  `ConnectionManager` resiliente, `ConnectionBuffer` (coalescing status/stats + lossless
  alarm/ai/system), mapper topic→envelope `{type,loop_id,seq,ts,data}`. Subscreve
  `STATUS.`, `ACTION.CTRL.`, `ACTION.AI.`, `EVENT.ALARM.`, `EVENT.SYSTEM`, `STATS.`.
  `response_model` travado nos routers (auth login, controllers list/get, opcua status).
  SPA single-origin (`StaticFiles(html=True)` após routers) + config `web_dist_dir`/
  `allowed_ws_origins`.
- **Frontend (`packages/smart_pid_web/`, React/Vite/TS):** scaffold (vitest jsdom + Playwright),
  `tokens.css`/`themes.css` (ISA-101 + Dark Room) + `ThemeProvider`, `AuthContext`
  (POST /auth/login, token em `sessionStorage`) + `RequireAuth` + `LoginPage`,
  `envelope.ts` + `RealtimeProvider` (WS único, backoff, onResync) + `useRealtime`,
  `AnalogBar`/`ControllerCard`/`RealtimeTrend`/app shell, `DashboardPage` ao vivo
  (status via WS; OPC via REST poll `GET /opcua/status`, online quando `ONLINE`).
- **e2e:** Playwright login→dashboard renderiza frame de status ao vivo (verde).

### Decisões-chave
- **Auth do WS:** primeira mensagem `{type:"auth", token}`; header `Origin` validado;
  fecha com `4401` em token/origin ausente/inválido (nunca `?token=`).
- **Correções de contrato:** `StatusData.timestamp` é **string ISO-8601** (envelope `ts`
  permanece número/epoch, carimbado pela ponte). `RealtimeType` inclui `'system'` → **6 tipos**.
- **Task 5 enxuta:** CORS dev allowlist + security headers são propriedade da Phase 4 (P4),
  não reimplementados aqui.
- **`.sdd/` gitignored** (relatórios de processo SDD não versionados).

### Deferrals conhecidos (fecham na Fatia 8)
- Ligação ao vivo do `ConnectionBuffer` ao broadcast + fechar-no-overflow (re-sync via REST).
- Mapeamento real de unidade/range do `ControllerCard` (`pv_scale.unit`/`eu_min`/`eu_max`;
  sem campo de casas decimais).

### Verificação (Task 12)
- `tests/core/api/`: 28 passed, 3 failed (apenas os 3 `TestProjectServiceOPCUA` pré-existentes
  do Py3.14 — não relacionados a esta fatia).
- `tests/core/api/test_ws_realtime.py`: 22 passed.
- ruff nos arquivos da fatia (`adapters/inbound/api/`): clean. (8 E402 + 1 SIM118 residuais
  são pré-existentes na `main`, em arquivos não tocados nesta branch.)
- mypy: binário não instalado neste ambiente (não bloqueia).
- web: lint exit 0 (2 warnings exhaustive-deps); 11 testes unitários pass; build emite `dist/`
  (67 kB gzip JS).

### CONCERNS abertos (defeitos do scaffold — NÃO corrigidos nesta task de docs)
1. **`pyproject.toml`** `[tool.uv.workspace] members=["packages/*"]` inclui `smart_pid_web`
   (sem `pyproject.toml`), o que quebra **todo** `uv run` nesta branch. Workaround usado para
   rodar o gate: `exclude = ["packages/smart_pid_web"]` (revertido, não commitado). Precisa de
   fix permanente (pertence ao scaffold/Task 6).
2. **`npm run test` sai com código 1**: o vitest coleta o spec Playwright `e2e/login-dashboard.spec.ts`
   (sem `test.exclude`/`include` no `vite.config.ts`), que lança na coleção. Os 11 testes
   unitários passam; só o exit code está errado. Precisa de fix no config do vitest (Task 6).

### Próximos passos
- **next: Fatia 2** (comandos + config por loop). Antes: corrigir os 2 CONCERNS do scaffold.

### Arquivos modificados nesta task (Task 12)
- `docs/smartPIDv2.md` (nova subseção 8.6 — Web HMI Fatia 0+1)
- `.claude/docs/estado-atual.md` (este arquivo)

### Range de commits da fatia
`d891a87..8f9a5a4` (11 commits ahead of `main`).

---

# Estado anterior — 2026-04-14

## Tarefa concluída e mergeada: fix/fuzzy-dr-overshoot-in-settling (a611cdb)

### Problema relatado
Gráfico mostrava PV claramente cruzando SP na recuperação (overshoot
abaixo do SP após distúrbio positivo), mas Ti permanecia em 8.9 —
o motor não detectava o overshoot.

### Causa raiz
Três detectores existentes falharam neste padrão específico:
1. `_active_zero_crossings` só conta durante ACTIVE. Se a recuperação
   permanece no lado original do SP durante os 3 samples do dwell de
   saída, SETTLING começa com zc=0.
2. σ de 15 samples pós-evento dilui um pico breve de overshoot — um
   pico de 8% span em 15 samples dá 2σ/0.5 ≈ 0.12, abaixo do MED
   threshold de 0.3.
3. Regra R1 (HIGH/SLOW/STABLE → M) segura Ti neste regime.

### Correção
Novo check em `_finalise_event`: olhar direto para o PICO em
`_post_errors` de sinal OPOSTO ao sinal inicial da excursão. Se
`peak_opposite >= _EVENT_TRIGGER` (2% span), PV cruzou SP na
recuperação → `_finalise_oscillation` (Ti up +0.275, tag
`[DR/limit-cycle]`).

### Matriz de casos
| Cenário                                | Comportamento     |
|----------------------------------------|-------------------|
| Overshoot dentro de ACTIVE             | damp ✓ (existente)|
| **Overshoot dentro de SETTLING**       | **damp ✓ (novo)** |
| Recuperação limpa (sem cruzamento)     | hold ✓            |
| Overshoot inter-evento (novo evento)   | damp ✓ (existente)|

### Verificação
- 89/89 tests pass. Ruff clean.
- Replay dos 3 casos: A, B, C produzem comportamento esperado.

---

## Histórico anterior: fix/fuzzy-dr-inter-event-overshoot (b873aa9)

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
