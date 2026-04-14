# Estado atual — 2026-04-14

## Tarefa concluída: fix/fuzzy-dr-eager-limit-cycle

### Problema relatado
Após o 2º fix de DR (`fix/fuzzy-dr-limit-cycle-decision-strength`, já no
main), o sistema continuava oscilando indefinidamente e o motor fuzzy
ainda não estava aumentando o Ti o suficiente para amortecer.

### Causa raiz (investigação end-to-end, não apenas unit test)
Um teste e2e realista (AIWorker + EventBus + telemetria ±20% oscilando)
revelou o quadro verdadeiro:
- **29 decisões** de AI em 400 amostras (~8 s wall clock)
- **Apenas 1 decisão** com Δ_Ti positivo; as outras 28 reportavam
  `holding (state=ACTIVE)` com Δ_Ti = 0
- Ti subia 1.0 → 1.275 uma única vez e estacionava

O bug: o gatilho `_is_limit_cycle()` só disparava em `update_sample`
após ≥ 3τ de ACTIVE (300 amostras com τ=10 s default, dt=0.1 s = ~30 s
de parede). Entre disparos, o AIWorker chamava `compute_adjustment` em
seu próprio período (3·TSS) e recebia "holding" com Δ_Ti = 0. O log
ficava cheio de entradas `Ti: 1.0000 → 1.0000`, como no screenshot do
usuário.

### Correção
1. **Eager check em `compute_adjustment`**: se o engine está em ACTIVE
   e já acumulou ≥ `_OSC_LOCK_MIN_CROSSINGS` zero crossings, chama
   `_finalise_oscillation()` **agora**, sem esperar o threshold temporal.
   Isso garante que cada chamada do AIWorker sob oscilação sustentada
   resulta em uma decisão de amortecimento.
2. **`_OSC_LOCK_MIN_CROSSINGS` reduzido de 3 → 2**. Um evento transiente
   clássico tem 0 zero crossings (erro sobe e desce do mesmo lado do SP);
   meio ciclo de oscilação já cruza zero duas vezes. ≥ 2 é o threshold
   mais apertado que ainda descarta transientes isolados.
3. Novo teste de regressão
   `test_compute_adjustment_fires_per_ai_cycle_under_oscillation`
   reproduzindo exatamente o padrão de produção.

Resultado end-to-end (mesma simulação anterior):
- 28 decisões, **13 com Δ_Ti positivo**
- Ti cresce **1.0 → 23.5 em 400 amostras** (~8 s wall clock)
- Antes do fix: Ti = 1.275 no mesmo teste

### Verificação
- `pytest tests/core/unit/test_fuzzy_engine_v2.py` + AI worker
  integration: **74/74 passaram**.
- Ruff clean para `fuzzy_engine_v2.py`.
- Teste manual end-to-end (AIWorker + bus) confirma crescimento
  exponencial de Ti.

### Arquivos modificados
- `packages/smart_pid_core/src/smart_pid_core/domain/services/fuzzy_engine_v2.py`
- `tests/core/unit/test_fuzzy_engine_v2.py`

### Branch
`fix/fuzzy-dr-eager-limit-cycle` criada a partir de `main`.
**Não commitada, não mergeada.** Aguardando aprovação.

---

## Histórico recente (já no main)

- `fix/fuzzy-dr-limit-cycle-decision-strength` (4ef2e6e) — trocou inputs
  alimentados à base de regras para (LOW,FAST,HIGH) evitando R1' negativo.
- `fix/fuzzy-dr-stuck-in-active` (71cae7c) — detecção inicial de limit
  cycle (ACTIVE ≥ 5τ + crossings). **Faltava disparar por AI cycle, não
  só por amostra** — corrigido agora.
- `fix/sim-param-change-preserves-pv` (8d8af4d) — preserva PV ao trocar
  parâmetros do processo no simulador.
- `fix/simulator-pid-params-race` (5e722c4) — simulator parou de
  sobrescrever kp/ti/td via OPC-UA em cada tick.
