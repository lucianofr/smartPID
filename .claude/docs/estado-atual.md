# Estado atual — 2026-04-12

## Última tarefa
Fix: Fuzzy engine empurrava Ti para cima indefinidamente após convergência (ruído de medição disparava o override de oscilação).

## Branch (não mergeada — aguardando aprovação)
`fix/fuzzy-reject-noise-detect-damping-trend` a partir de main.

## Causa raiz
Correção anterior (`fix/fuzzy-no-ti-reversal-on-convergence`) baixou demais os thresholds do override (amp 5%→1.5%, flips 3→2). Para o processo FOPDT K=1, τ1=10, τ2=5, θ=3 (optimum Ti≈13 IAE/ITAE), o override passou a disparar em ruído de ±2% após convergência → gamma negativo sustentado → Ti > 33 e ainda subindo.

## Correções aplicadas em `fuzzy_engine.py`
1. Thresholds do override recalibrados:
   - `_OSC_MIN_AMPLITUDE`: 0.015 → **0.025** (rejeita ruído típico)
   - `_OSC_THRESHOLD`: 2 → **3** (restaurado)
   - `_OSC_DAMPING_GAIN`: 2.0 → **1.5** (restaurado)
2. **Novo: detecção de tendência de amplitude** (`_amplitude_trend()`).
   - Compara RMS da metade recente vs metade antiga da janela.
   - Se razão < 0.9 → oscilação está convergindo espontaneamente → gamma=0 (não sobe Ti).
   - Se razão ≥ 0.9 → oscilação estável/crescendo → aplica damping negativo.

## Testes de regressão adicionados
- `test_measurement_noise_does_not_increase_ti` — 100 amostras de ruído ±2%; Ti não pode subir acima de 15 a partir de 13.
- `test_self_damping_oscillation_does_not_overshoot_ti` — senoide amortecida 15%→2%; Ti não pode estourar para > 40.
- (removido `test_damped_oscillation_does_not_reduce_ti` — premissa inválida em teste sintético sem feedback físico.)

## Validação
- 26/26 testes fuzzy passam.
- Ruff lint: OK.

## Arquivos modificados
- `packages/smart_pid_core/src/smart_pid_core/domain/services/fuzzy_engine.py`
- `tests/core/unit/test_fuzzy_engine.py`

## Histórico das correções do fuzzy engine
1. `fix/fuzzy-no-ti-reversal-on-convergence` (MERGED, commit d5ee0fe) — suavizou regras PL→PM nas células ambíguas, abaixou amplitude de osc.
2. `fix/fuzzy-reject-noise-detect-damping-trend` (ATUAL, não mergeada) — corrige o overshoot de Ti causado pelo (1).

## Próximo passo
Teste em simulador com K=1, τ1=10, τ2=5, θ=3 para confirmar que Ti estabiliza próximo de 13 e não continua subindo.
