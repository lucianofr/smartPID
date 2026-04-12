# Estado atual — 2026-04-12

## Tarefa concluída
Fix: Fuzzy engine reduzia Ti novamente durante convergência, reexcitando oscilação da malha.

## Branch
`fix/fuzzy-no-ti-reversal-on-convergence` (criada a partir de main, **NÃO mergeada** — aguardando aprovação).

## Causa raiz
1. Regras `(ME,ZO)` e `(LA,ZO)` disparavam `PL=+1.0`, interpretando picos de oscilação (|e| moderado-grande com |Δe|≈0) como offset estável → reduzia Ti exatamente no pico.
2. Detector de oscilação só disparava com amplitude RMS ≥ 5% do span. Assim que a malha convergia para < 5%, o override desligava e as regras voltavam a reduzir Ti, reexcitando oscilação.

## Correções aplicadas em `packages/smart_pid_core/src/smart_pid_core/domain/services/fuzzy_engine.py`
1. **Output centers assimétricos** (curvas de defuzzificação):
   - `PL`: +1.0 → **+0.6**
   - `PM`: +0.5 → **+0.3**
   - Negativos (`NL=-1.0`, `NM=-0.5`) mantidos — errar aumentando Ti é barato; errar reduzindo é caro.
2. **Regras menos agressivas nas células ambíguas** (|e|=ME/LA, |Δe|=ZO/SM) para `SP_TRACKING`, `DISTURBANCE_REJECTION`, `SURGE_LEVEL` — `PL` substituído por `PM` onde pico e offset são indistinguíveis.
3. **Detector de oscilação mais sensível**:
   - `_OSC_THRESHOLD`: 3 → **2** sign flips
   - `_OSC_MIN_AMPLITUDE`: 0.05 → **0.015** (1.5% do span)
   - `_OSC_DAMPING_GAIN`: 1.5 → **2.0**

## Teste de regressão adicionado
`tests/core/unit/test_fuzzy_engine.py::TestOscillationDetection::test_damped_oscillation_does_not_reduce_ti` — simula senoide amortecida (10% decaindo a ~2%) e verifica que Ti não cai abaixo do valor inicial.

## Validação
- 25/25 testes fuzzy PASSAM (24 antigos + 1 novo).
- Ruff lint: OK no fuzzy_engine.py e test_fuzzy_engine.py.

## Próximos passos (aguardando usuário)
1. Aprovação explícita para merge da branch em main.
2. Teste em processo real / simulador para confirmar que a malha sustenta a convergência sem reversão de Ti.

## Arquivos modificados
- `packages/smart_pid_core/src/smart_pid_core/domain/services/fuzzy_engine.py`
- `tests/core/unit/test_fuzzy_engine.py`
