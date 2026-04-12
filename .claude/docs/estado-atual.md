# Estado atual — 2026-04-12

## Última tarefa
Detecção mais rápida de oscilação + damping mais agressivo do Ti.

## Branch (aguardando merge)
`feat/fuzzy-faster-detection-stronger-damping`

## Mudanças em `fuzzy_engine.py`
- `_OSC_WINDOW`: 12 → **10** (janela enche mais rápido)
- `_OSC_THRESHOLD`: 3 → **2** (detecta na 3ª amostra com mudanças de sinal)
- `_OSC_DAMPING_GAIN`: 1.5 → **3.0** (damping 2× mais forte por unidade de amplitude)
- `_OSC_GAMMA_CAP`: 0.8 → **1.0** (permite damping magnitude total)
- **Ganho adaptativo**: `effective_gain = _OSC_DAMPING_GAIN * max(1.0, trend)`. Quando a oscilação está crescendo (trend > 1), o gain é escalado pelo ratio → reação ainda mais rápida a divergência.

Rejeição de ruído preservada via `_OSC_MIN_AMPLITUDE = 0.025` (2.5% RMS) e `_TREND_DAMPING_RATIO = 0.9` (oscilação amortecendo sozinha → gamma=0).

## Exemplos de comportamento
| amp | trend | gamma (antes) | gamma (agora) |
|-----|-------|---------------|---------------|
| 5%  | 1.0   | -0.075        | -0.15         |
| 10% | 1.0   | -0.15         | -0.30         |
| 10% | 1.3   | -0.15         | -0.39         |
| 20% | 1.0   | -0.30         | -0.60         |
| 30% | 1.2   | -0.45         | -1.00 (cap)   |

## Testes
- `test_growing_oscillation_raises_ti_rapidly` (novo): oscilação crescente 5%→15% em 20 iter deve elevar Ti >30%.
- 27/27 testes passam. Ruff limpo.

## Próximo passo
Testar no simulador com processo oscilante — verificar se Ti sobe rapidamente e estabiliza próximo do ótimo sem overshooting.

## Histórico recente
1. `fix/fuzzy-no-ti-reversal-on-convergence` (MERGED, d5ee0fe) — suavizou regras.
2. `fix/fuzzy-reject-noise-detect-damping-trend` (MERGED, c35d0bf) — rejeita ruído, detecta damping próprio.
3. `feat/fuzzy-faster-detection-stronger-damping` (atual) — detecção rápida + damping agressivo.
