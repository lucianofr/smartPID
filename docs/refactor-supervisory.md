# Design — Malha SUPERVISORY somente-leitura e entrada manual de sintonia no faceplate

**Documento:** Design / Spec (saída de sessão de grilling)
**Data:** 2026-08-07
**Autor:** Luciano França Rocha — LFR Automação
**Status:** Proposto (aguardando revisão)
**Baseline:** commit `c7b6216` (`Merge branch 'fix/opcua-write-limits': bound values that reach an actuator`)
**Glossário:** [`CONTEXT.md`](../CONTEXT.md) — os termos deste documento são os de lá
**ADR:** [`docs/adr/0001-escrita-manual-de-sintonia-sem-limites.md`](./adr/0001-escrita-manual-de-sintonia-sem-limites.md)

> Escrito em pt-BR. Identificadores de código, nomes de rota e textos de interface aparecem
> verbatim, sem tradução — vários testes fazem *binding* neles.
>
> **Chave de caminhos.** Três nomes curtos são ambíguos no repositório; neste documento eles
> significam sempre o *router*, nunca o DTO homônimo:
>
> | Citado como | Caminho |
> |---|---|
> | `commands.py` | `packages/smart_pid_core/.../api/routers/commands.py` |
> | `controllers.py` | `packages/smart_pid_core/.../api/routers/controllers.py` |
> | `config.py` | `packages/smart_pid_core/src/smart_pid_core/config.py` |
>
> Os DTOs aparecem sempre com prefixo: `dtos/commands.py`, `dtos/controllers.py`.

---

## 1. Contexto

`ExecutionMode` (`enums.py:19-21`) já é um conceito de primeira classe e já governa posse de
PV/SP/CO/MODE em tempo de execução. O que **não** existe é qualquer reflexo disso na tela LOOPS:
`Faceplate.tsx` não recebe `execution_mode` e oferece escrita de SP, CO e MODE em qualquer malha,
independentemente de quem roda o PID.

Pior: o backend hoje faz o **oposto** do que o modo promete. `_dcs_owns_loop` (`commands.py:58-81`)
devolve `True` para uma malha SUPERVISORY, e é justamente esse ramo que **roteia** SP/CO/MODE para o
DCS via OPC-UA. Uma malha "só monitorada" é hoje a única em que a escrita do operador sai do
SmartPID e chega ao bloco do DCS.

Do lado da sintonia o quadro é inverso. Kp/Ti/Td de uma malha SUPERVISORY já são lidos do OPC-UA a
1 Hz e reportados no `STATUS` (`pid_worker.py:537-548`), e já chegam ao faceplate como texto
somente-leitura (`Faceplate.tsx:253-263`). Existe até o endpoint de escrita —
`POST /commands/tuning` (`commands.py:312`) — e o *hook* que o consome,
`useWriteTuningMutation` (`useCommands.ts:79`), que **nenhum componente chama**. A peça que falta é
a caixa de entrada.

Este documento fecha as duas pontas: torna SUPERVISORY honestamente somente-leitura para o processo,
e abre a sintonia para o operador nos dois modos de execução.

## 2. Objetivos

- Uma malha SUPERVISORY recusa `POST /commands/setpoint`, `/mode` e `/output` no backend, com 409.
- O faceplate de uma malha SUPERVISORY não oferece entrada de SP, entrada de CO nem botões AUTO/MAN.
- MODE vira um badge somente-leitura, cobrindo os 9 valores de `ControllerMode` e o `UNKNOWN`.
- Três caixas Kp/Ti/Td no faceplate, logo abaixo das indicações existentes, aplicando com ENTER.
- A escrita manual de sintonia chega ao que de fato roda o PID: bloco do DCS em SUPERVISORY,
  `pid_params` em DDC.
- A escrita manual de sintonia não é limitada pelos trilhos do otimizador.
- Um badge SUPERVISORY/DDC no faceplate e no card de malha.

## 3. Não-objetivos

- O eixo `monitor`/`execute` do daemon (`config.py:116`). Fica como está — ver §11.1.
- As barreiras de `POST /commands/apply-tuning/{id}`. O caminho da IA mantém os três clamps.
- A aba Sintonia do `LoopConfigDialog`, hoje escondida em SUPERVISORY. Ver §11.2.
- Traduzir `SUPERVISORY`/`DDC` na interface.
- O default divergente entre o dataclass (`controller.py:168` → `SUPERVISORY`) e a DDL
  (`sqlite_repo.py:46` → `'DDC'`). Pré-existente, ver §11.3.

## 4. A regra de posse

Tudo neste documento sai de uma frase: **quem executa o PID é dono das variáveis de processo dessa
malha, e nunca é dono da sintonia.**

| | PV | SP | CO | MODE | Kp/Ti/Td |
|---|---|---|---|---|---|
| **SUPERVISORY** | DCS | DCS | DCS | DCS | operador → bloco do DCS |
| **DDC** | DCS | SmartPID | SmartPID | SmartPID | operador → `pid_params` |

As quatro primeiras colunas já estão implementadas no `pid_worker` e no `io_worker`; o que muda é o
`commands.py` parar de contradizê-las. A quinta coluna é a feature nova, e o detalhe que a torna
correta é o destino mudar com o modo: em DDC o PID lê `pid_params` do banco, então escrever no node
OPC-UA não teria efeito nenhum sobre o PID que está rodando.

## 5. Backend — PV/SP/CO/MODE somente-leitura

### 5.1 A recusa

Nas três rotas `set_setpoint` (`commands.py:110`), `set_mode` (`:149`) e `set_output` (`:186`), antes
de qualquer outra verificação de negócio:

```
409  _SUPERVISORY_DETAIL = (
    "Malha em SUPERVISORY: PV/SP/CO/MODE são somente leitura. "
    "O DCS é o dono desta malha."
)
```

409 e não 403: 403 diria ao operador que é permissão, que ele "resolveria" pedindo acesso admin. A
causa é posse da malha, não papel do usuário — e 409 já é o vocabulário do router para isso
(`_MONITOR_DETAIL`).

### 5.2 O que sobra de `_dcs_owns_loop`

A função **não** é removida. Ela serve dois eixos homônimos, e só o eixo da malha muda:

```python
if execution_mode == "monitor":   # eixo do daemon — permanece
    return True
...
return ctrl.execution_mode is ExecutionMode.SUPERVISORY   # eixo da malha — sai
```

Depois da mudança ela responde apenas pelo modo do daemon. Consequências:

- `_write_to_dcs` (`commands.py:84-107`) **continua vivo** — é o caminho de uma malha DDC num daemon
  em `monitor`.
- A guarda "o bloco externo precisa estar em MAN" do `set_output` (`commands.py:215-221`) fica
  inalcançável para SUPERVISORY, mas continua alcançável nesse mesmo cenário. Não é código morto.
- **A ordem importa.** A checagem do daemon precede a da malha, senão
  `test_output_above_limit_rejected_in_monitor_mode` (§10.1, item 17) muda de 400 para 409 sem que
  ninguém tenha pedido.

### 5.3 O que continua permitido em SUPERVISORY

A recusa é de PV/SP/CO/MODE, não de tudo. Seguem inalterados:

- `POST /commands/tuning` — é o objeto da §6.
- `POST /commands/apply-tuning/{id}` — o caminho da IA, com seus clamps.
- `io_worker._drain_and_write_ai_tuning` — a escrita contínua de Ti pelo otimizador quando
  `tuning_write_mode == 'auto_apply'`.
- `PUT /controllers/{id}` — configuração, não comando de processo.

## 6. Backend — escrita manual de sintonia

### 6.1 Os limites saem do caminho manual

`write_tuning` empilha hoje três barreiras de naturezas diferentes:

| # | Barreira | Origem | Destino |
|---|---|---|---|
| 1 | `clamp_tuning_change` — máx. `max_tuning_change_pct` por escrita (default 10) | trilho do otimizador | **removida** |
| 2 | `clamp_tuning_absolute` → Ti em `ai_config.limit_min..limit_max` (default 1,0–10,0) | trilho do otimizador | **removida** |
| 3 | `clamp_tuning_absolute` → `Kp >= KP_MIN` (0,1, `controller.py:50`) | piso físico | **vira 422** |

(1) e (2) são a faixa do **otimizador** — o campo se chama `ai_config`. Aplicá-la a um valor digitado
por um humano é erro de categoria, e (1) tinha um defeito concreto: clampava contra
`ctrl.pid_params`, a config do **banco**, enquanto o faceplate exibe o valor **vivo** lido do DCS.
Com Kp vivo em 2,0, banco em 1,0 e default de 10%, digitar 2,2 gravava 1,1 — o operador pedia $+10\%$
e levava $-45\%$, no atuador. Remover (1) elimina o bug por construção: sem clamp de taxa, não existe
base para estar obsoleta.

(3) é piso físico, não trilho de IA: $K_p = 0$ mata a ação proporcional em silêncio. Mas cortar
calado é o defeito, não o limite existir. Passa a ser **HTTP 422** com mensagem, em vez de um 200 que
grava outro número. As três funções em `tuning_guardrails.py` permanecem intactas — só o
`write_tuning` deixa de chamá-las; `apply_tuning` (`commands.py:441`) segue chamando as três.

Isto reverte deliberadamente parte do commit `a19bd31`. O motivo está no
[ADR 0001](./adr/0001-escrita-manual-de-sintonia-sem-limites.md), sem o qual alguém lê o docstring de
`clamp_tuning_absolute` (`tuning_guardrails.py:50-53`) e "conserta" de volta.

### 6.2 O ramo DDC

`write_tuning` passa a despachar pelo modo de execução:

```
SUPERVISORY → opcua.write_pid_params(...)          # como hoje
DDC         → repo.save(controller com pid_params novo)
              loop_manager.update_controller(controller)
```

O segundo ramo é o que `PUT /controllers/{id}` já faz (`controllers.py:561-564`), e
`loop_manager.update_controller` (`loop_manager.py:169-185`) propaga para o `PIDWorker` vivo — a
malha DDC pega a sintonia nova sem reiniciar.

Só os campos presentes no `TuningCommand` são alterados; os ausentes (`None`) ficam como estão. O DTO
já aceita os três como opcionais, então não há mudança de esquema.

**Por que não reusar `PUT /controllers/{id}`, que já despacha nos dois modos:** ele engole falha de
OPC-UA (`except Exception: logger.exception`, `controllers.py:574-579`) e devolve 200 numa escrita que
o DCS nunca recebeu — inaceitável numa caixa de atuador. E ele grava o valor digitado em `pid_params`
mesmo em SUPERVISORY, fazendo o banco **liderar** a sintonia de uma malha cujo dono é o DCS, o
contrário do que `_mirror_sim_pid_params` (`main.py:171-197`) e o `pid_worker` assumem. Com
`/commands/tuning`, SUPERVISORY não toca o banco: a verdade continua sendo o read-back.

### 6.3 Permissão e auditoria

Sem mudança. `require_admin` nos dois ramos — a mesma barreira que `PUT /controllers/{id}`
(`controllers.py:500`) já exige para editar a mesma grandeza. Auditoria `AuditAction.TUNE_PID` nos
dois ramos.

`CommandResponse` (`dtos/commands.py:62-67`) fica como está: sem clamps não há valor aplicado que
divirja do pedido, então os campos `applied_kp/ti/td` que chegamos a considerar nasceriam mortos.

## 7. Frontend — Faceplate

### 7.1 A prop e seu default

`FaceplateProps` (`Faceplate.tsx:20-30`) ganha `executionMode`. `DashboardPage.tsx:172-179` já tem o
`ControllerResponse` completo em `selected`, então é uma linha.

**Ausente ou desconhecido conta como SUPERVISORY** — ou seja, travado. É o precedente do próprio
repositório (`LoopConfigDialog.tsx:339` usa `?? 'SUPERVISORY'`; `test/fixtures.ts:38` idem) e é o
default seguro: a falha vira "não consigo escrever", não "escrevi onde não devia". Em produção a
situação não ocorre — o campo é garantido pelo backend; o caso existe só em fixture de teste.

### 7.2 O que some em SUPERVISORY

| Elemento | Local | Ação |
|---|---|---|
| `<CardControls controls={['setpoint']}>` | `Faceplate.tsx:214-219` | não monta |
| `<CardControls controls={['output']}>` | `:220-229` | não monta |
| Botões AUTO/MAN + `role="group"` | `:232-249` | substituídos pelo badge de modo |

O gating fica no `Faceplate`, **não** no `CardControls`: esse componente não tem — e não deve ganhar
— noção de `execution_mode` (a prop `mode` dele é o modo do bloco, outro eixo), e é montado
isoladamente em outros lugares.

Com os dois `CardControls` fora, `coDraft`/`coTouched` (`Faceplate.tsx:111-124`) só têm uso em DDC.

### 7.3 O badge de modo

Onde estavam os botões, um `Badge` somente-leitura com `data.mode`. O valor **já vem decodificado do
servidor** via `mode_int_map` — o front não mapeia inteiro nenhum.

`MODE_CHIP`/`MODE_CHIP_FALLBACK` (`LoopCard.tsx:92-97`, hoje `const` privada) migram para um módulo
compartilhado e passam a servir as duas superfícies. Uma entrada nova: `UNKNOWN` → tom `warn`, com
`title="Mapeamento de modos não configurado"`. `UNKNOWN` é o que `io_worker.py:183` emite quando
`mode_int_map` está vazio, que é o default de fábrica — hoje isso é invisível porque os botões
AUTO/MAN aparecem de qualquer jeito, e também quebra o AI worker (`ai_worker.py:1169`). Os outros 7
valores de `ControllerMode` seguem no fallback existente; pintar os 9 distintamente é invenção.

### 7.4 As caixas Kp/Ti/Td

Uma caixa sob cada coluna da linha de ganhos (`Faceplate.tsx:253-263`), preservando o alinhamento.
O rail tem 320 px (`lg:w-80`) com `p-3`, e `flex gap-2` em 3 colunas dá ~93 px cada — cabe no
`max-w-[110px]` do `ENTRY_INPUT` do `CardControls`. Três linhas rótulo+campo custariam altura que o
rail não tem a 768 px (ver o comentário de `SHORT_VIEWPORT`, `Faceplate.tsx:155-159`).

Comportamento:

- **Repouso:** campo vazio, valor vivo como `placeholder`. Preencher com o valor vivo faria o
  read-back de 1 Hz brigar com o que o operador está digitando.
- **ENTER:** dispara `useWriteTuningMutation` só com o campo editado (`{kp: 2.2, ti: null, td: null}`).
  Mandar os três faria cada ENTER em Kp reescrever Ti e Td — três escritas no DCS para uma intenção.
- **Depois:** limpa o campo. O placeholder acompanha o read-back em ~1 s, e essa mudança **é** a
  confirmação visual de que a escrita chegou.
- **Erro (409 sem link, 422 `Kp < KP_MIN`, 502):** toast via `onCommandError`
  (`Faceplate.tsx:129-131`), campo preservado para correção.
- **Permissão:** as caixas só aparecem com `useCan('tuning.edit')`, espelhando o `require_admin` do
  endpoint. Sem isso, todo ENTER de um `user` voltaria 403. Um `user` numa malha SUPERVISORY vê um
  faceplate integralmente somente-leitura, o que é coerente.

`writeTuning` (`commandApi.ts:44`) muda de `(id, kp, ti, td)` para os três opcionais.

**As caixas aparecem nos dois modos.** A diferença é de durabilidade, não de aparência: em DDC a
escrita persiste em `pid_params` e sobrevive a restart; em SUPERVISORY é uma escrita transiente num
bloco do DCS. Nenhum tratamento visual distinto — quem informa isso é o badge da §7.5, que já está
ali dizendo quem é o dono da malha.

### 7.5 O badge SUPERVISORY/DDC

`Badge` tom `neutral`, texto cru `SUPERVISORY` ou `DDC`, no `<header>` (`Faceplate.tsx:164-181`) ao
lado do ponto de link. Texto cru porque é vocabulário de instrumentação e é o que o select da
configuração já mostra. `title` reaproveitando a prosa que já existe em `LoopConfigDialog.tsx:595`.

## 8. Frontend — Card de malha

Só o badge. `LoopCard` **não tem nenhum controle de escrita** hoje (`LoopCard.tsx:207-241`: chip de
modo, chip de estratégia de IA, botão de configuração), então "omitir as opções de escrita" já está
satisfeito.

Terceiro badge na linha existente, mesmo `CHIP`. Cabe: os dois atuais somam ~110 px dos 206 px do
card.

## 9. Ordem de implementação

Quatro fatias, cada uma com o suite verde no fim:

1. **Harness e fixtures** (§10.3) — `execution_mode` explícito em todo fixture de e2e e de unidade.
   Sozinha, não muda comportamento; é o que torna as fatias seguintes verificáveis.
2. **Backend, recusa** (§5) — `_dcs_owns_loop`, as três rotas, `_SUPERVISORY_DETAIL`.
3. **Backend, sintonia** (§6) — remoção dos clamps, 422 do `KP_MIN`, ramo DDC.
4. **Frontend** (§7, §8) — prop, gating, badges, caixas.

A fatia 1 antes de tudo é o que evita depurar dois problemas ao mesmo tempo: o refactor e o fato de o
harness nunca ter mandado o campo.

## 10. Impacto em testes

### 10.1 Backend — 16 quebram, 1 revisar

Todos em `tests/core/integration/test_api_commands.py`. O helper local
`_create_and_start_controller(api_deps)` cria malha **SUPERVISORY** por omissão
(`controller.py:168`), o que explica a concentração.

*Recusa de SP/CO/MODE (§5):*

| Linha | Teste | Hoje | Depois |
|---|---|---|---|
| 386 | `test_setpoint_above_limit_rejected_on_dcs_branch` | 400 | 409 |
| 413 | `test_setpoint_below_limit_rejected_on_dcs_branch` | 400 | 409 |
| 441 | `test_setpoint_inside_limits_still_reaches_dcs` | 200 + escrita | 409, sem escrita |
| 508 | `test_output_reaches_dcs_on_supervisory_loop` | 200 + escrita | 409, sem escrita |
| 535 | `test_output_above_limit_rejected_on_supervisory_loop` | 400 | 409 |
| 651 | `test_mode_written_over_opcua` | 200 + `write_target_mode` | 409, sem escrita |
| 811 | `test_unmapped_co_node_is_not_a_500` | 409 com `"co"` no detail | 409, outro detail |
| 831 | `test_refused_when_the_external_block_is_not_in_man` | 409 com `"AUTO"` no detail | 409, outro detail |
| 847 | `test_written_when_the_external_block_is_in_man` | 200 + escrita | 409 |
| 865 | `test_unknown_external_mode_stays_permissive` | 200 + escrita | 409 |

Os dois casos de *detail* (811, 831) mantêm o 409 por coincidência e falham no texto — reescrever
apontando para uma malha DDC num daemon `monitor`, que é onde esses caminhos continuam vivos (§5.2).

*Sintonia (§6):*

| Linha | Teste | Hoje | Depois |
|---|---|---|---|
| 264 | `test_out_of_range_params_clamped` | `kp=100` → ≤1,1 | grava 100 |
| 313 | `test_kp_floored_at_absolute_minimum` | `kp=0` → 200, `KP_MIN` | 422 |
| 347 | `test_supervisory_ti_raised_into_configured_band` | `ti=0,5` → 1,0 | grava 0,5 |
| 727 | `test_absolute_clamp_still_fires_after_the_rate_clamp` | `kp=0` → 200, `KP_MIN` | 422 |
| 764 | `test_clamped_write_is_logged` | 200 + WARNING | 422, sem o log |
| 691 | `test_ddc_loop_keeps_zero_ti_instead_of_the_ai_band` | `fake.written` preenchido | `None` (ramo DDC persiste) |

**Revisar (1):** `test_output_above_limit_rejected_in_monitor_mode` (:473). A malha é SUPERVISORY
*e* o daemon está em `monitor`. Deve continuar 400 pelo ramo do daemon — mas só se a ordem da §5.2
for respeitada. É o teste que prova essa ordem; vale torná-lo explícito trocando a malha por DDC.

**Sobrevivem, confirmados:** `tests/core/unit/test_guardrails.py` inteiro (chama as funções
diretamente, e elas não mudam); `tests/domain/test_dtos_validation.py` (`kp/ti/td` já são opcionais
hoje — `test_all_fields_remain_optional`, :180); os 5 testes de `TestApplyTuning`;
`TestSupervisoryWithoutLinkRefuses` (:564-622, já esperam 409 puro); `test_role_contract.py`.

### 10.2 Frontend — 8 unitários, 13 e2e

`Faceplate.test.tsx`: 8 dos 11 `renderFaceplate()` tocam SP/CO/AUTO/MAN e passam a precisar de
`executionMode="DDC"` explícito (ou de uma versão SUPERVISORY que afirme a ausência dos controles).
Os 3 restantes (`:50`, `:55`, `:70`) só olham as barras e o wrapper — sobrevivem.

E2E, 13 corpos de teste em 6 arquivos: `faceplate.spec.ts` (:26, :41, :53), `responsive.spec.ts`
(:219, :231), `target-size.spec.ts` (:32), `user-role.spec.ts` (:8, :58, :123), `themes.spec.ts`
(parcial), `fatia2-commands.spec.ts` (:30).

**Quebras incondicionais, independentes do modo:** as baselines de screenshot. `faceplate.spec.ts:61`
e as 24 do `themes.spec.ts` (6 temas × 4 viewports) contêm o rail em quadro; esconder duas linhas de
entrada, somar três caixas e somar um badge invalida todas. Precisam ser regravadas na fatia 4.

**Não afetados, verificados:** `CardControls.test.tsx` (17 testes — o componente não muda),
`LoopCard.test.tsx` (13 — o terceiro badge é aditivo, nenhuma asserção conta elementos nem usa
snapshot), `useCommands.test.tsx` (6 — mockam transporte; o 409 já é exercitado genericamente),
`tuning-confirm.spec.ts` (5 — só `apply-tuning`).

### 10.3 O harness nunca mandou `execution_mode`

`e2e/helpers/harness.ts` — nem a interface `HarnessLoop` (:18) nem `controllerPayload()` (:57)
incluem o campo. **Nenhuma malha de e2e tem modo de execução no payload.** O comentário em
`integral-type.spec.ts:9-12` afirmando que FIC-101 é SUPERVISORY descreve uma intenção que o
harness nunca implementou.

Como FIC-101 é a malha default de `gotoDashboard`, é ela que decide o raio real. Na fatia 1:

| Malha | Onde | Modo a fixar |
|---|---|---|
| FIC-101 | `harness.ts:31` | `SUPERVISORY` — honra o comentário e dá cobertura à regra nova |
| TIC-202 | `harness.ts:44` | `DDC` — preserva cobertura de escrita de SP/CO/MODE |
| PIC-005 | `fatia2-commands.spec.ts:13` | `DDC` — o spec existe para exercitar comandos; sem modo declarado e sem comentário de intenção, DDC é o que o mantém significando o que se propõe |

Os specs que hoje dirigem SP/MODE/CO em FIC-101 migram para TIC-202, e ganham um caso novo afirmando
que em FIC-101 esses controles **não existem**.

## 11. Consequências conhecidas, fora de escopo

### 11.1 Malha DDC em daemon `monitor` continua escrevendo no DCS

O default de fábrica do daemon é `monitor` (`config.py:116`). Depois desta mudança, uma malha
SUPERVISORY recusa sempre (regra da malha), mas uma malha DDC num daemon `monitor` segue roteando
para o DCS. É discutível — `monitor` deveria significar "não escreve" — mas mexer nisso dobra o raio
de impacto sem mudar nada na tela LOOPS.

### 11.2 A aba Sintonia continua escondida em SUPERVISORY

`DDC_TABS` (`LoopConfigDialog.tsx:64`) esconde Sintonia e Avançado em SUPERVISORY, enquanto
`controllers.py:570` escreve `pid_params` no OPC-UA justamente para SUPERVISORY — caminho que a UI
não alcança. Depois desta mudança fica mais estranho: dá para editar Kp no faceplate e não na
configuração. Correção recomendada, em PR separado: remover `'Sintonia'` de `DDC_TABS`.

### 11.3 Defaults divergentes de `execution_mode`

Dataclass diz `SUPERVISORY` (`controller.py:168`), DDL diz `'DDC'` (`sqlite_repo.py:46`). Uma malha
criada pela API e uma criada por `INSERT` direto nascem em modos diferentes. Pré-existente; agora
passa a ter consequência visível (uma trava a escrita, a outra não).

### 11.4 `PIDParamsDTO` não valida nada

`gain: float = 1.0` puro (`dtos/controllers.py:134-141`): sem faixa, sem `FiniteFloat`. O caminho de
configuração DDC já aceita `Kp = 0` hoje. Isso é o que torna a §6.1 uma correção de assimetria e não
um buraco novo — mas o 422 do `KP_MIN` deveria eventualmente valer também para `PUT /controllers/{id}`.

## 12. Decisões

| # | Decisão | Motivo |
|---|---|---|
| D1 | `execution_mode` é o termo canônico; "modo de monitoramento" não entra | Já é o nome do campo, da coluna e do tooltip. Segundo nome = segunda linguagem |
| D2 | SUPERVISORY vira política real no backend, não só UI escondida | Esconder botão não impede `curl`, e a auditoria registraria escritas que o modo promete proibir |
| D3 | 409, não 403 | 403 sugere problema de permissão que o operador tentaria resolver virando admin. A causa é posse da malha |
| D4 | O eixo `monitor`/`execute` do daemon não muda | Postura de implantação, não contrato de malha. Dobraria o raio sem efeito na tela LOOPS |
| D5 | `_dcs_owns_loop`, `_write_to_dcs` e a guarda de MAN permanecem | Continuam vivos para malha DDC em daemon `monitor` |
| D6 | Reusar `POST /commands/tuning`, sem gate de modo no endpoint | Em DDC editar sintonia pela configuração é legítimo. O gate é de superfície, não de rota |
| D7 | Clamps de taxa e de faixa de Ti saem do caminho manual | São trilhos do `ai_config`; aplicá-los a um humano é erro de categoria. Remove de brinde o bug da base obsoleta |
| D8 | `Kp < KP_MIN` vira 422, não corte silencioso | O defeito é alterar o número do operador sem avisar, não o limite existir |
| D9 | `apply-tuning` mantém os três clamps | O otimizador escreve sozinho e repetidamente; é exatamente onde os trilhos servem |
| D10 | `applied_kp/ti/td` em `CommandResponse` descartados | Sem clamps não há divergência a reportar. Nasceriam mortos |
| D11 | Caixas Kp/Ti/Td nos dois modos, destinos diferentes | Em DDC o PID lê `pid_params`; escrever no node OPC-UA não afetaria o PID que roda |
| D12 | `/commands/tuning` e não `PUT /controllers/{id}` | O PUT engole falha de OPC-UA (200 numa escrita perdida) e faria o banco liderar a sintonia de uma malha do DCS |
| D13 | ENTER escreve só o campo editado | Mandar os três = três escritas no DCS para uma intenção do operador |
| D14 | Campo vazio com valor vivo no `placeholder` | Read-back a 1 Hz brigaria com o que está sendo digitado |
| D15 | Caixas só com `useCan('tuning.edit')` | Espelha o `require_admin` do endpoint; senão todo ENTER de um `user` volta 403 |
| D16 | `executionMode` ausente conta como SUPERVISORY | Precedente do repo (`LoopConfigDialog.tsx:339`, `fixtures.ts:38`) e falha segura |
| D17 | Badge com texto cru `SUPERVISORY`/`DDC` | Vocabulário de instrumentação, e é o que o select da configuração já mostra |
| D18 | `MODE_CHIP` compartilhado; só `UNKNOWN` é novo | Uma tabela de pintura para as duas superfícies. Pintar os 9 é invenção |
| D19 | `UNKNOWN` em tom `warn` | Torna visível um `mode_int_map` não configurado, que hoje também quebra o AI worker em silêncio |
| D20 | Caixas sob cada coluna, não em linhas rótulo+campo | O rail não tem altura a 768 px; 93 px cabem no `max-w-[110px]` existente |
| D21 | Gating no `Faceplate`, não no `CardControls` | `CardControls` é montado isoladamente e sua prop `mode` é o modo do bloco, outro eixo |
| D22 | Fixtures de e2e explícitos antes de tudo | O harness nunca mandou o campo; sem isso a fatia 2 depura dois problemas de uma vez |
| D23 | FIC-101 → SUPERVISORY, TIC-202 e PIC-005 → DDC | Honra o comentário existente e preserva cobertura de escrita numa malha que ainda a permite |
