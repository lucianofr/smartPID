# Plano 002 — Motor Fuzzy de Otimização do Parâmetro Integral

Gerado em 2026-08-01 a partir de auditoria da implementação existente
(`fuzzy_engine_v2.py`) contra a especificação de regras fornecida pelo
usuário. Decisão de escopo aprovada: SP_TRACKING e DISTURBANCE_REJECTION
maduros — manter, mudanças cirúrgicas apenas; SURGE_LEVEL — revisão completa.

## 1. Visão Geral

O SmartPID já possui um motor fuzzy dedicado exclusivamente ao parâmetro
integral (`FuzzyEngineV2Dispatcher` + três estratégias por
`ControlObjective`), integrado ao `AIWorker` com cadência 3×TSS, clamps
`limit_min`/`limit_max` e conversão Ti↔Ki. Este plano: (a) formaliza a
revisão das três bases de regras contra a especificação, com tabela de
mapeamento regra-especificada → regra-implementada; (b) mantém SP_TRACKING
e DISTURBANCE_REJECTION intactos (zero mudanças de regra; 1 teste
cirúrgico novo no worker); (c) reescreve a estratégia SURGE_LEVEL ("nível
pulmão") com faixa segura de PV configurável (default 20–80% da faixa),
regra incondicional de violação de faixa, empurrão do integral ao mínimo
quando dentro da faixa com erro pequeno, e validação crisp de rampa do CO;
(d) responde à avaliação skfuzzy/pyFuzzy: **manter o núcleo próprio** (ver
§7). O plano é independente de linguagem nas seções 2–6 (MFs, regras,
pseudocódigo); a §8 aterrissa em Python/arquivos do repositório.

## 2. Arquitetura

Componentes clássicos do motor (todos já existentes em
`fuzzy_engine_v2.py`):

- **Fuzzificação**: `_fuzzify()` sobre `triangular_mf`/`trapezoidal_mf`.
- **Inferência**: `_run_rules()` — Mamdani min (AND) / max (agregação).
- **Defuzzificação**: Centro-de-Gravidade com singletons (mesma função).
- **Despacho por objetivo**: `FuzzyEngineV2Dispatcher(objective, …)`.

Fluxo de dados (nomes reais dos componentes):

```
OPC-UA / Simulador
      │ telemetria (PV, SP, CO, Ti, mode)
      ▼
  io_worker ──ZMQ TELEMETRY──► AIWorker._drain_telemetry()
                                  │  error_frac=(SP−PV)/span
                                  │  pv_frac=(PV−eu_min)/span
                                  │  co_frac=CO/100
                                  ▼
  stats_worker ─ZMQ STATS──► AIWorker._drain_stats()   (SP_TRACKING/DR)
                                  │
              timer 3×TSS (AIWorker._ai_period_s)
                                  ▼
        FuzzyEngineV2Dispatcher.compute_adjustment[_from_stats](
            ti_current, limit_min, limit_max)
                                  │ AIDecisionV2(delta_ti, new_ti,
                                  │   inputs, reasoning, membership_values)
                                  ▼
        integral_type == GAIN_KI ?  new_ki = ki/(1+Δ_Ti)  (inverso)
                          TIME_TI ?  new_ti = Ti×(1+Δ_Ti)  (clamped)
                                  ▼
        ACTION.AI (ZMQ) ──► io_worker → write-back OPC-UA node_id_ti
                        └─► TuningRecommendation → AiPanel (aprovação /
                            auto-apply) → POST /commands → clamp_tuning_change
                            (max_tuning_change_pct, default 10%/aplicação)
```

**Onde o integral vive**: configuração em `Controller.pid_params.reset`
(Ti, s) com `Controller.integral_type ∈ {TIME_TI, GAIN_KI}`; runtime em
`AIWorker._ki_current` (sincronizado de OPC-UA quando o DCS muda o valor);
persistência na tabela `Controladores` (`pid_ti` + colunas `ai_*`);
tag OPC-UA `TagBindings.node_id_ti`.

**Cadência × velocidade da malha**: `AIWorker._ai_period_s = 3.0 ×
controller.tss_s`; TSS é definido pelo usuário junto com `ProcessSpeed`
(ULTRA_FAST/FAST/MEDIUM/SLOW). A janela de amostras fuzzy cobre `5×TSS/
scan_rate` (`AIWorker._create_engine`). Requisito de período compatível
com a velocidade da malha: **já atendido**.

## 3. Variáveis fuzzy e tabelas de regras por objetivo

Convenção de saída (todas as estratégias): ajuste multiplicativo
`Ti_new = Ti_old × (1 + Δ_Ti)`, com Δ_Ti defuzzificado sobre singletons
{RM, R, M, A, AM} (+ RD no Surge Level). Sinal: **Δ_Ti < 0 = reduzir Ti =
aumentar ação integral**; **Δ_Ti > 0 = aumentar Ti = reduzir ação
integral**. Para malhas GAIN_KI o worker inverte (ver §4). Sempre
clampado em `[limit_min, limit_max]` do `AIConfig`.

### 3.1 Objetivo A — SP_TRACKING (mantido; mapeamento)

Entradas (janela rolante de stats, não erro instantâneo — deliberado:
robustez a ruído e a transientes de degrau de SP):

| Entrada | Definição | Conjuntos (MF) |
|---|---|---|
| IAE | `mean_abs_error/span ÷ 0.20` | LOW trap(0,0,0.2,0.4) · MED tri(0.3,0.5,0.7) · HIGH trap(0.6,0.8,1,1) |
| OSC | `pk_pk_recente/span ÷ 0.15`, gate `zero_crossings≥2 ∧ reversals≥2` | STABLE trap(0,0,0.2,0.35) · OSC tri(0.3,0.5,0.7) · UNSTABLE trap(0.6,0.8,1,1) |
| EFF | `TV(CO) por amostra ÷ 0.10` | SMOOTH trap(0,0,0.2,0.4) · MODERATE tri(0.3,0.6,0.8) · EXCESS trap(0.7,0.9,1,1) |

Saída: RM −0.35 · R −0.15 · M 0 · A +0.15 · AM +0.35; clamp Δ∈[−0.5,+0.5].
Base de regras: as 15 regras atuais (`RULES` em `fuzzy_engine_v2.py`)
permanecem **inalteradas**.

Mapeamento especificação → implementação:

| Regra especificada | Implementação equivalente | Veredito |
|---|---|---|
| Erro grande ∧ derivada afastando → aumentar integral (Ti↓) | IAE=HIGH ∧ OSC=STABLE → R/RM (offset persistente com malha calma) | Coberta. Versão em janela é superconjunto robusto da instantânea: erro "afastando" sustenta IAE alto. |
| Erro pequeno ∧ estável → manter | R5: IAE=LOW ∧ OSC=STABLE → M | Coberta (idêntica). |
| Inversão de sinal do erro → reset do integral (anti-windup) | Duas camadas: (1) bloco PID já tem anti-windup real — gate ARW local + BKCAL direcional (`pid_engine.py`, `arw_hi_lim/arw_lo_lim`, `LimitBits`); reset do integrador é responsabilidade do bloco, não do tuner. (2) No tuner, inversões repetidas ⇒ `zero_crossings≥2` ⇒ OSC ativa ⇒ A/AM (Ti↑, desarma o windup na origem). | Coberta em camada correta. Nenhuma regra nova. |
| Saída esperada: integral moderado, rápido sem oscilação excessiva | R2/R3/R3' punem oscilação com Ti↑; R1/R6 aceleram com Ti↓ apenas com malha estável | Coberta. |

Mudanças cirúrgicas em A: **nenhuma regra**. Única adição: teste unitário
do caminho GAIN_KI no worker (§6, T-A4) — a inversão `new_ki=ki/(1+Δ)`
(`ai_worker.py` ~linhas 705-712) hoje não tem teste no caminho fuzzy
(verificado: nenhuma ocorrência de GAIN_KI em testes do fuzzy path).

### 3.2 Objetivo B — DISTURBANCE_REJECTION (mantido; mapeamento + 1 divergência documentada)

Entradas (máquina de estados por evento IDLE→ACTIVE→SETTLING, com escape
de limit-cycle, detecção de overshoot inter-eventos e cooldown de 5
ciclos IA pós-damping):

| Entrada | Definição | Conjuntos (MF) |
|---|---|---|
| E_MAX | pico de \|erro\|/span ÷ 0.05 | LOW trap(0,0,0.3,0.5) · MED tri(0.3,0.6,0.9) · HIGH trap(0.7,1,∞,∞) |
| T_REC | duração do evento em múltiplos de τ | FAST trap(0,0,1.5,3) · MED tri(2,4,6) · SLOW trap(5,7,∞,∞) |
| OSC | 2σ residual pós-evento ÷ 0.50 (+ sobreposição por stats rolantes) | STABLE trap(0,0,0.15,0.3) · MED tri(0.2,0.4,0.6) · HIGH trap(0.5,0.75,∞,∞) |

Saída assimétrica (reduzir Ti é alto risco): RM −0.10 · R −0.05 · M 0 ·
A +0.15 · AM +0.40. Base: as 10 regras atuais (`RULES_DR`) **inalteradas**.

Mapeamento:

| Regra especificada | Implementação equivalente | Veredito |
|---|---|---|
| Salto súbito no erro → aumentar integral agressivamente | Evento dispara em \|e\|>2% do span; decisão só na FINALIZAÇÃO do evento; pernas de redução capadas em −0.10/−0.05 | **Divergência deliberada, mantida.** Resposta agressiva imediata durante o transiente mede o distúrbio, não a sintonia; e reduções fortes causam "hunting" (racional documentado em comentário no código: duas reduções seguidas não podem superar uma correção A/AM). A agressividade do prompt fica a cargo do próprio PID; o tuner corrige a sintonia entre eventos. |
| PV aproximando do SP → reduzir taxa de aumento do integral | Dwell de SETTLING (3 amostras em banda) + cooldown pós-limit-cycle suprime reduções por 5 ciclos | Coberta. |
| Erro muda de sinal repetidamente → integral mais conservador | `zero_crossings ≥ 2` ⇒ `_finalise_oscillation()` ⇒ entradas (0,0,1.0) ⇒ AM+A (Ti↑ ~+0.275/ciclo) + cooldown | Coberta (mais forte que o especificado). |
| Saída esperada: agressiva no início, suavização progressiva | Assimetria dos centros + cooldown produz exatamente o envelope "corrige rápido p/ cima, relaxa devagar p/ baixo" | Coberta. |

Mudanças cirúrgicas em B: **nenhuma**.

### 3.3 Objetivo C — SURGE_LEVEL / Nível Pulmão (reescrita)

Prioridade: minimizar variação do CO mantendo PV dentro da faixa segura.
Violação da faixa é proibida.

**Novos parâmetros de configuração** (em `AIConfig`; ver §5): faixa segura
`sl_band_lo_pct`/`sl_band_hi_pct` (default None → 20%/80% da faixa de PV),
`sl_error_small_pct` (default 5.0), `sl_co_ramp_max_pct_min` (default
10.0; 0 desliga o gate).

**Entradas** (janela rolante por amostra; dt = scan_rate):

| Entrada | Definição | Conjuntos (MF) |
|---|---|---|
| POS | `m = |pv_pct − c| / h`, com `c=(lo+hi)/2`, `h=(hi−lo)/2`; m<1 dentro da faixa, m≥1 fora | SAFE trap(0,0,0.55,0.75) · NEAR tri(0.65,0.85,1.0) · OUT trap(0.95,1.10,1e9,1e9) |
| DPOS | `dm/dt` em unidades de m por minuto (janela: extremos), clampado [−10,+10]; >0 = indo para a parede | ESCAPING trap(−10,−10,−0.5,0) · STILL tri(−1,0,1) · TOWARD trap(0.5,2,10,10) |
| ERR | `e_n = (|erro|/span × 100) / sl_error_small_pct` | SMALL trap(0,0,0.8,1.2) · LARGE trap(0.8,1.5,1e9,1e9) |
| TV | TV(CO) por amostra ÷ 0.05 (inalterada da versão atual) | LOW trap(0,0,0.05,0.15) · MEDIUM tri(0.1,0.25,0.4) · HIGH trap(0.3,0.5,1,1) |

Saída: RD −0.65 · R −0.25 · M 0 · A +0.30 · AM +1.00; clamp Δ∈[−1.0,+1.5]
(inalterados).

**Tabela de regras (nova base, substitui `RULES_SL`):**

| # | Premissas | Conclusão | Justificativa |
|---|---|---|---|
| S1 | POS=OUT ∧ (DPOS=TOWARD ∨ DPOS=STILL) | RD | PV fora da faixa e não retornando → correção agressiva máxima (violação proibida). |
| S2 | POS=OUT ∧ DPOS=ESCAPING | M | Fora mas já retornando: manter a correção em curso; continuar RD aqui sobre-aperta e atravessa a faixa até a outra parede. (Desvio documentado do literal "fora→sempre agressivo"; herda o insight da regra atual CRITICAL∧ESCAPING→A, endurecido para M por ainda estar fora.) |
| S3 | POS=NEAR ∧ DPOS=TOWARD | R | Convergindo perigosamente para o limite → aumentar integral moderadamente. |
| S4 | POS=NEAR ∧ DPOS=STILL | M | À beira, mas parado — segurar. |
| S5 | POS=NEAR ∧ DPOS=ESCAPING | A | Voltando ao centro — começar a relaxar. |
| S6 | POS=SAFE ∧ TV=HIGH | AM | CO oscilando → reduzir integral (windup/ganho integral excessivo). |
| S7 | POS=SAFE ∧ ERR=SMALL ∧ TV=LOW | AM | Dentro da faixa + erro < threshold → integral ao MÍNIMO (Ti→limit_max): saída máxima suavidade. |
| S8 | POS=SAFE ∧ ERR=SMALL ∧ TV=MEDIUM | AM | Idem, válvula ainda se mexendo → mais razão para suavizar. |
| S9 | POS=SAFE ∧ ERR=LARGE ∧ TV=LOW | M | Nível seguro e válvula quieta: averaging control tolera offset; não apertar. |
| S10 | POS=SAFE ∧ ERR=LARGE ∧ TV=MEDIUM | A | Relaxamento gentil (herda R2' atual). |

Cobertura: combinações sem regra caem em denominador ≈ 0 no CoG →
Δ_Ti = 0 (hold) — comportamento já garantido por `_run_rules`.

**Gate de rampa do CO (crisp, pós-inferência — validação, não regra):**
se `max(|ΔCO|)/Δt` na janela, em %/min, exceder `sl_co_ramp_max_pct_min`
(e o gate estiver ativo, i.e. > 0): forçar `Δ_Ti := max(Δ_Ti, +0.15)` e
proibir Δ_Ti < 0 neste ciclo. Anexar `co_ramp_violation=True` a
`AIDecisionV2.inputs` e a marca `[CO-RAMP]` ao `reasoning`. Crisp porque a
especificação o define como validação de limite de segurança, não como
inferência.

**Casos de borda**: banda ausente → 20/80. Banda inválida vinda de
persistência antiga/corrompida (lo ≥ hi) → engine cai para 20/80 e
registra warning (a validação de API/UI impede criar esse estado; ver
§8.2/§8.4). `span ≤ 0` → pv_frac=0.5 (comportamento atual do worker,
mantido). Janela com < 2 amostras → DPOS=0, TV=0, gate inativo
(comportamento atual, mantido).

## 4. Pseudocódigo da inferência

```
# núcleo compartilhado (existente, inalterado)
fuzzify(x, MFs)          -> {conjunto: grau}
run_rules(inputs, rules) -> Δ = Σ(centro·força) / Σ(força)   # min-AND, max-OR

# ciclo do AIWorker (a cada 3×TSS, malha em AUTO/CAS/RCAS):
decision = dispatcher.compute_adjustment[_from_stats](ti_current,
                                                      limit_min, limit_max)
if integral_type == GAIN_KI:
    new_ki = clamp(ki_current / (1 + decision.delta_ti),
                   limit_min, limit_max)          # Ki = 1/Ti → sentido inverso
else:  # TIME_TI
    new_ti = clamp(ti_current * (1 + decision.delta_ti),
                   limit_min, limit_max)          # já feito dentro do engine

# SURGE_LEVEL v3 (novo compute_adjustment):
m      = |pv_pct − c| / h                      # posição relativa à faixa
dpos   = (m_fim − m_início) / janela_min       # clamp ±10
e_n    = (|erro|/span·100) / sl_error_small_pct
tv     = TV(CO)/amostra ÷ 0.05
Δ, mfs = run_rules({POS:m, DPOS:dpos, ERR:e_n, TV:tv}, RULES_SL_V3)
Δ      = clamp(Δ, −1.0, +1.5)
if sl_co_ramp_max_pct_min > 0 and max_co_ramp_pct_min(janela) > threshold:
    Δ = max(Δ, +0.15)                          # gate crisp: nunca apertar
new_ti = clamp(ti_current · (1+Δ), limit_min, limit_max)
```

## 5. Parâmetros configuráveis pelo usuário

Existentes (inalterados — listados para completude do contrato):

| Nome | Tipo | Default | Papel |
|---|---|---|---|
| `ai_config.engine` | enum NONE/FUZZY/RL | NONE | liga o motor |
| `ai_config.objective` | enum SP_TRACKING/DISTURBANCE_REJECTION/SURGE_LEVEL | DISTURBANCE_REJECTION | seleciona estratégia |
| `ai_config.limit_min` / `limit_max` | float | 0.1 / 100.0 | clamp absoluto de Ti (ou Ki) |
| `integral_type` | enum TIME_TI/GAIN_KI | TIME_TI | formato do parâmetro na malha |
| `process_speed` + `tss_s` | enum + float | MEDIUM / 60 | cadência IA = 3×TSS; janela = 5×TSS/scan |
| `stability_band_pct` | float\|None | None (→2%) | banda morta de steady-state do otimizador |
| `max_tuning_change_pct` | float | 10.0 | clamp por aplicação no write-back (camada de taxa ΔKi/dt junto com a cadência 3×TSS) |
| `tuning_write_mode` | enum auto_apply/approval_required/disabled | approval_required | via de aplicação |

Novos (todos em `AIConfig`, exibidos na UI apenas quando
`objective == SURGE_LEVEL`):

| Nome | Tipo | Default | Papel |
|---|---|---|---|
| `sl_band_lo_pct` | float\|None | None (→20.0) | limite inferior da faixa segura de PV, % da faixa |
| `sl_band_hi_pct` | float\|None | None (→80.0) | limite superior, % da faixa |
| `sl_error_small_pct` | float | 5.0 | threshold de "erro pequeno", % da faixa |
| `sl_co_ramp_max_pct_min` | float | 10.0 | rampa máxima do CO em %/min; 0 desliga o gate |

Camadas de limitação de taxa (resposta ao requisito ΔKi/dt máximo):
(1) clamp de Δ_Ti por decisão dentro do engine; (2) período mínimo entre
decisões = 3×TSS; (3) `max_tuning_change_pct` no write-back
(`clamp_tuning_change`, `commands.py`); (4) `limit_min`/`limit_max`
absolutos. Nenhum knob novo necessário.

## 6. Plano de testes e validação

Unit (estender `tests/core/unit/test_fuzzy_engine_v2.py`; padrão das
classes existentes `TestSurgeLevel*`):

| ID | Caso | Esperado |
|---|---|---|
| T-C1 | banda 40–60, PV=70% (OUT), DPOS≥0 | Δ_Ti ≤ −0.4 (RD domina) |
| T-C2 | banda 40–60, PV=61%→57% (OUT, ESCAPING) | Δ_Ti ≈ 0 (S2 segura, sem RD) |
| T-C3 | banda default (None→20/80), PV=50%, erro 1% (<5%), CO parado | Δ_Ti ≥ +0.6 (S7: rumo ao Ti máximo) |
| T-C4 | PV=50%, erro 10%, CO parado | Δ_Ti ≈ 0 (S9: averaging tolera offset) |
| T-C5 | PV=50%, CO com TV alto | Δ_Ti ≥ +0.5 (S6) |
| T-C6 | rampa CO 15%/min > threshold 10, regras pedindo R | Δ_Ti = +0.15 e flag `co_ramp_violation` (gate vence) |
| T-C7 | `sl_co_ramp_max_pct_min=0`, mesma rampa | gate inerte |
| T-C8 | banda inválida lo≥hi injetada direto no engine | fallback 20/80 + warning |
| T-C9 | dispatcher SURGE_LEVEL repassa `error_frac` na nova assinatura | sem TypeError; ERR alimentado |
| T-A4 | AIWorker fuzzy + GAIN_KI: Δ_Ti=+0.5 | `new_ki = ki/(1.5)`, clampado (cobre inversão hoje sem teste) |
| T-REG | suíte existente completa | 100% verde — prova de "A/B intactos" |

E2E (simulador `/simulator`, preset LEVEL; formato dos TEST_E2E*.md do
repositório):

| Objetivo | Cenário | Métricas | Condição de parada |
|---|---|---|---|
| A (referência de regressão) | degrau de SP ±10% | overshoot, t_acomodação, IAE por ciclo IA decrescente | \|Δ_Ti\| < 0.02 por 3 ciclos consecutivos |
| B (referência de regressão) | distúrbio automático (auto-disturbance) | e_max, t_rec, ausência de limit cycle | idem |
| C | banda 40–60 configurada; distúrbios de carga periódicos | tempo fora da banda (→0 após convergência), variância/TV do CO decrescente, max dCO/dt ≤ `sl_co_ramp_max_pct_min` | TV(CO) abaixo do patamar inicial E PV na banda por 3 ciclos IA |
| C-default | sem banda configurada | engine opera com 20–80 | log do reasoning mostra m calculado sobre 20–80 |

Exemplo de malha real (requisito do checklist): tanque pulmão de nível
(preset LEVEL do simulador; análogo industrial: LIC de tanque de
alimentação entre unidades, faixa 40–60%, CO = válvula de descarga) para
o objetivo C; malha de temperatura (preset TEMPERATURE) para A/B.

## 7. Avaliação skfuzzy / pyFuzzy — veredito: manter núcleo próprio

- `pyfuzzy`: abandonado (era Python 2). Descartado.
- `scikit-fuzzy`: exigiria dependência nova (+networkx; numpy/scipy já
  existem no core), API de universo discretizado (arrays) incompatível
  com o desenho singleton-CoG atual, manutenção esporádica.
- O núcleo próprio tem ~60 linhas (`triangular_mf`, `trapezoidal_mf`,
  `_fuzzify`, `_run_rules`), é puro-Python sem dependências, e está
  coberto por 1300 linhas de testes que codificam correções de campo
  (hunting, limit-cycle, overshoot). Reescrever = risco de regressão com
  ganho funcional zero. **Decisão: não migrar.**

## 8. Notas de implementação (arquivo a arquivo, para a sessão executora)

Ordem: 8.1 → 8.2 → 8.3 (backend compila e testa após cada um) → 8.4
(frontend) → 8.5 (testes E2E).

### 8.1 Domínio
- `packages/smart_pid_domain/src/smart_pid_domain/models/controller.py`,
  `AIConfig`: adicionar os 4 campos da §5 com os defaults dados.
- `packages/smart_pid_domain/src/smart_pid_domain/dtos/controllers.py`,
  `AIConfigDTO`: espelhar os 4 campos. Validações Pydantic: `0 ≤ lo < hi
  ≤ 100` quando ambos presentes; `sl_error_small_pct > 0`;
  `sl_co_ramp_max_pct_min ≥ 0`.

### 8.2 Persistência
- `packages/smart_pid_core/src/smart_pid_core/adapters/outbound/sqlite_repo.py`:
  colunas novas em `_DDL` (bloco `Controladores`, junto de `ai_limit_min`,
  ~linha 129) E em `_apply_migrations()`/`_add_missing_columns` (contrato
  do arquivo: toda coluna nova em `_DDL` repete na migração, defaults
  idênticos): `sl_band_lo_pct REAL`, `sl_band_hi_pct REAL` (NULL),
  `sl_error_small_pct REAL NOT NULL DEFAULT 5.0`,
  `sl_co_ramp_max_pct_min REAL NOT NULL DEFAULT 10.0`.
  Mapear no dict de escrita (~linha 590) e na leitura row→`AIConfig`
  (~linha 712).
- `db_models.py` (`ControladorRow`): 4 colunas `Mapped` novas —
  `tests/core/unit/test_db_models.py` exige paridade de colunas.

### 8.3 Motor e worker
- `fuzzy_engine_v2.py`, seção Strategy 3 (linhas ~898-1039):
  - Substituir `MF_L_MARGIN_SL`/`MF_DL_DT_SL` pelos MFs POS/DPOS da §3.3;
    adicionar `MF_ERR_SL`; manter `MF_TV_MV_SL` e `OUTPUT_CENTERS_SL`.
  - Substituir `RULES_SL` pela tabela S1–S10.
  - `FuzzyEngineV2SurgeLevel.__init__(dt_sec, window_samples,
    band_lo_pct: float | None = None, band_hi_pct: float | None = None,
    error_small_pct: float = 5.0, co_ramp_max_pct_min: float = 10.0)` —
    resolve None→20/80 e lo≥hi→20/80+warning aqui.
  - `update_sample(error_frac: float, pv_frac: float, co_frac: float)`
    (assinatura NOVA — buffer de erros para ERR). Callsites: apenas
    `FuzzyEngineV2Dispatcher.update_sample` (ramo SURGE_LEVEL) + testes.
  - `compute_adjustment`: POS/DPOS/ERR/TV + gate de rampa (§3.3/§4);
    `reasoning` no formato atual `FuzzyV2[SL]: …` + `[CO-RAMP]` quando o
    gate disparar.
  - `FuzzyEngineV2Dispatcher.__init__`: aceitar e repassar os 4 params SL
    (kwargs com os mesmos defaults).
- `ai_worker.py`, `_create_engine` (~linhas 186-194): repassar
  `sl_band_lo_pct=self._ai_config.sl_band_lo_pct, …` (4 campos) ao
  dispatcher.
- SP_TRACKING/DR: **zero mudanças de código**.

### 8.4 Frontend (`packages/smart_pid_web`)
- `src/features/loop-config/types.ts`: 4 campos em `AiConfigForm`.
- `AiConfigSection.tsx`: renderizar os 4 campos apenas quando
  `value.objective === 'SURGE_LEVEL'` (padrão de Field/Input existente;
  tooltips em pt-BR).
- `LoopConfigDialog.tsx`: incluir nos pontos de draft (~367-373),
  validação (~400-403) e payload (~476-481).
- `validation.ts` (`validateAiConfig`): número finito; `lo < hi`; `0 ≤ %
  ≤ 100`; `error_small > 0`; `co_ramp ≥ 0` — só valida quando
  objective==='SURGE_LEVEL' e engine≠NONE (padrão atual).
- Regenerar tipos: `npm run gen:api` (dump OpenAPI + openapi-typescript),
  conferir com `npm run gen:api:check`.

### 8.5 Riscos e dependências
- **Risco 1 — regressão A/B**: mitigado por zero-diff nas estratégias 1/2
  e T-REG (suíte inteira verde é critério de aceite).
- **Risco 2 — assinatura do dispatcher**: mudança confinada; grep
  `update_sample(` em `fuzzy_engine_v2.py`/`ai_worker.py`/testes cobre
  todos os callsites.
- **Risco 3 — arquivos .spid antigos**: colunas novas via migração
  aditiva idempotente (mecanismo existente `_add_missing_columns`).
- Dependências: nenhuma nova (decisão §7).
- Conflito entre objetivos (requisito da especificação): não há
  priorização dinâmica — cada malha tem exatamente UM objetivo
  (`AIConfig.objective`); trocar de objetivo recria o engine. Dentro do
  SURGE_LEVEL, a prioridade é estática e explícita: segurança (S1/S2 +
  gate) > suavidade (S6–S8) > erro (S9/S10).

## Checklist de completude

- [x] Três objetivos com regras definidas — §3.1/§3.2 (mantidas, mapeadas) e §3.3 (S1–S10).
- [x] Nível pulmão diferencia PV fora vs dentro dos limites — POS OUT/NEAR/SAFE (§3.3).
- [x] Regra explícita de windup — bloco: ARW local + BKCAL (`pid_engine.py`); tuner: S6 (TV=HIGH→AM) e OSC/zero-crossings em A/B.
- [x] Conversão Ti↔Ki documentada — §4 (`GAIN_KI: new_ki = ki/(1+Δ_Ti)`, `ai_worker.py`).
- [x] Limites de segurança min/max — `limit_min`/`limit_max` por malha + 4 camadas de taxa (§5).
- [x] Exemplo de malha real — §6 (tanque pulmão LEVEL 40–60%; temperatura p/ A/B).
- [x] Independência de linguagem — §§2-6 agnósticas; aterrissagem Python isolada na §8.
