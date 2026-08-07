# SmartPID

Supervisão e otimização contínua de malhas de controle PID industriais. O SmartPID
lê uma malha por OPC-UA, avalia seu desempenho e devolve parâmetros de sintonia
otimizados — executando ou não o próprio algoritmo PID, conforme o modo de execução
da malha.

## Language

### Malha

**Malha**:
Uma malha de controle PID monitorada pelo SmartPID, identificada por um TAG.
No código o tipo é `Controller`; a tabela é `Controladores`.
_Avoid_: Loop, controlador, instrumento

**Modo de execução**:
Quem executa o algoritmo PID de uma malha — o SmartPID ou o sistema externo.
Campo `Controller.execution_mode` (`ExecutionMode`), coluna `modo_execucao`.
_Avoid_: Modo de monitoramento, modo de operação, modo da malha

**SUPERVISORY**:
Modo de execução em que o PID roda no CLP/DCS e o SmartPID apenas observa a malha
e devolve sintonia. Não é traduzido na interface.
_Avoid_: Supervisório, modo supervisão, monitoramento

**DDC**:
Modo de execução em que o próprio SmartPID executa a equação PID e escreve a saída.
Sigla de _Direct Digital Control_. Não é traduzida na interface.
_Avoid_: Controle direto, modo direto, execução local

**DCS**:
O sistema de controle externo que roda o PID de uma malha SUPERVISORY — um CLP,
um DCS real ou o simulador embutido. É a autoridade sobre PV/SP/CO/MODE dessa malha.
_Avoid_: CLP, PLC, planta, servidor (quando se quer dizer o sistema de controle)

**Modo do bloco**:
O estado operacional do bloco PID — `MAN`, `AUTO`, `CAS`, `RCAS`, `ROUT`, `OOS`,
`IMAN`, `LO`, `BYPASS` (`ControllerMode`). Distinto do modo de execução: uma malha
SUPERVISORY em AUTO tem modo de execução SUPERVISORY e modo de bloco AUTO.
_Avoid_: Modo, modo PID, estado da malha

**Modo do daemon**:
Configuração de implantação de todo o processo — `monitor` (nunca escreve nada que
atue) ou `execute`. É `Settings.execution_mode`, **homônimo mas não relacionado** ao
modo de execução da malha; os dois convivem em `_dcs_owns_loop`.
_Avoid_: Modo de execução (reservado para a malha)

### Sintonia

**Sintonia**:
O trio Kp/Ti/Td de uma malha. Em SUPERVISORY quem a possui é o DCS e o SmartPID a
lê por OPC-UA; em DDC o SmartPID a possui e a guarda em `pid_params`.
_Avoid_: Ganhos, parâmetros PID, tuning

**Recomendação de sintonia**:
Uma proposta Kp/Ti/Td produzida pelo otimizador, pendente de confirmação do
operador. Distinta de uma escrita manual de sintonia, que não passa por proposta.
_Avoid_: Sugestão, ajuste da IA

**Mapa de modos**:
A tradução, por malha, entre o inteiro que o DCS publica e o modo do bloco —
`MAN=0`, `AUTO=1`, `CAS=2`… Campo `TagBindings.mode_int_map`, cadastrado pelo
usuário. Sem ele o modo lido é `UNKNOWN`.
_Avoid_: Mapeamento de modo, enum de modo

**Vínculo de tag**:
O endereço OPC-UA (node id) de uma variável de uma malha. `TagBindings`.
_Avoid_: Endereço, tag, node

### Interface

**Faceplate**:
O painel grande e único à esquerda da tela LOOPS, que mostra a malha selecionada.
Componente `Faceplate`.
_Avoid_: Faceplate principal, painel, rail

**Card de malha**:
Um dos painéis compactos da faixa superior da tela LOOPS, um por malha.
Componente `LoopCard`.
_Avoid_: Faceplate pequeno, mini faceplate, card
