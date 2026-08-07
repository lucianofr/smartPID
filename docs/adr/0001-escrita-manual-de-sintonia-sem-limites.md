# Escrita manual de sintonia não é limitada pelos trilhos do otimizador

**Status:** aceito — 2026-08-07
**Reverte parcialmente:** `a19bd31` (`fix(control): bound values that reach an actuator`)

`POST /commands/tuning` aplicava a uma escrita digitada pelo operador as mesmas barreiras que
existem para conter o AIWorker: `max_tuning_change_pct` por escrita e a faixa `ai_config.limit_min..limit_max`
para Ti. Essas barreiras deixam de valer nesse caminho; `POST /commands/apply-tuning/{id}` e a
escrita automática do `io_worker` mantêm todas. `Kp < KP_MIN` deixa de ser corte silencioso e passa
a ser HTTP 422.

O motivo é que os dois caminhos têm autores diferentes. O otimizador escreve sozinho, repetidamente
e sem ninguém olhando — é exatamente onde um limite de passo serve. Um administrador digitando um
número numa caixa é a autoridade final sobre a malha, e o campo que o limitava chama-se `ai_config`:
é a faixa que *ele mesmo* declarou para o otimizador, não para si. Havia ainda um defeito concreto: o
clamp de taxa media contra `ctrl.pid_params`, a config do banco, enquanto o faceplate de uma malha
SUPERVISORY exibe o valor vivo lido do DCS — com Kp vivo em 2,0, banco em 1,0 e o default de 10%,
pedir 2,2 gravava 1,1.

## Consequências

O caminho de configuração DDC (`PUT /controllers/{id}` → `PIDParamsDTO`) nunca teve validação
alguma, então esta decisão iguala os dois caminhos manuais em vez de abrir um caso novo. A proteção
que resta é a que não pode ser silenciosa: `Kp < KP_MIN` é recusado com mensagem, porque `Kp = 0`
mata a ação proporcional sem nenhum sinal na tela.

`clamp_tuning_change`, `clamp_tuning_absolute` e `clamp_tuning_params` continuam existindo e
testadas — o docstring de `clamp_tuning_absolute` fala em impedir que o caminho manual contorne os
limites do operador, e essa frase agora descreve apenas o caminho da IA.
