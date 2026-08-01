# IMPROVE — Testes E2E das alterações

Sessão `/improve deep` de 2026-07-31.
Branch `chore/improve-deep-audit`, worktree `.worktrees/improve-deep-audit`.

Auditoria feita sobre `55b46f2`; a branch foi depois **rebaseada sobre a main
atual `54118e8`** (a sessão paralela commitou 3 mudanças durante o trabalho),
sem nenhum conflito. Commit: `2d46ea1`.

Ferramentas de consulta usadas: **tokensave** (índice reconstruído para
`55b46f2`, 585 arquivos) como fonte primária; **graphify** (`graphify-out/`)
como fallback. Nenhuma alteração foi feita fora desta worktree — o daemon do
usuário (portas 8000/5555/4849) nunca foi tocado; todos os testes de daemon
vivo usaram portas 18010/18011/18049 e caminhos em `/tmp`.

Todos os testes abaixo assumem:

```bash
cd .worktrees/improve-deep-audit
export PATH="$HOME/.local/bin:$PATH"
uv sync --all-packages
```

E, para os testes de daemon vivo, portas descartáveis para não colidir com uma
instância já em execução:

```bash
export SPID_JWT_SECRET='smoke-test-secret-key-minimum-32-bytes!!'
export SPID_API_PORT=18010 SPID_ZMQ_PUBLISH_PORT=18011 SPID_SIMULATOR_PORT=18049
export SPID_SIMULATOR_ENABLED=true SPID_EXECUTION_MODE=execute
export SPID_DB_PATH=/tmp/spid_e2e/project.spid
export SPID_USERS_DB_PATH=/tmp/spid_e2e/users.db
export SPID_PROJECTS_DIR=/tmp/spid_e2e/projects
```

---

## Resumo das alterações

| # | Alteração | Arquivos | Severidade |
|---|-----------|----------|------------|
| 1 | Controlador criado em runtime passa a ter loop, telemetria e OPC-UA | `routers/controllers.py`, `dependencies.py`, `workers/io_worker.py`, `simulator_adapter.py` | Crítica |
| 2 | Projeto aberto/importado registra controladores no `IOWorker` | `application/project_service.py`, `main.py` | Crítica |
| 3 | `PIDWorker._run` deixa de morrer silenciosamente | `workers/pid_worker.py` | Crítica (segurança de controle) |
| 4 | `logging` stdlib passa a ser configurado | `main.py` | Alta |
| 5 | Sockets ZMQ fechados pela thread dona; proxy do `EventBus` com shutdown determinístico | `event_bus.py`, `workers/*.py` | Alta |
| 6 | `/controllers/{id}/stats` enxerga workers vivos | `dependencies.py` | Média |

Verificação global **sobre a main atual (`54118e8`)**: `1538 passed, 1 failed`.
A única falha é `test_api_simulator.py::TestOPCUAEndpoints::test_opcua_start_stop`
— ambiental: a porta 4849 está ocupada pelo daemon do usuário. Comprovada
idêntica no commit base sem nenhuma alteração minha (checkout de `54118e8`,
mesma falha, `1 failed, 12 passed`). **Zero regressões.**

Antes do rebase, sobre `55b46f2`, o resultado era `1503 passed` com um conjunto
de 14 falhas byte-idêntico ao baseline (13 × `AutoSPRequest.period_s`, desde
então corrigidas pela sessão paralela em `d57ac1a`). `ruff` limpo nos arquivos
alterados.

---

## 1. Controlador criado em runtime fica realmente operante

**Bug.** `POST /controllers` gravava a linha no banco e registrava apenas o
simulador. O `LoopManager` (PIDWorker/StatsWorker/AIWorker), a lista de scan do
`IOWorker` e o adaptador cliente OPC-UA só eram populados no boot do daemon
(`main.py: run_daemon`) — `IOWorker.add_controller` existia com **zero
chamadores**. Resultado: a malha criada não computava nada até reiniciar o
daemon, e `/commands/*` respondia 404.

**Correção.** `create_controller` passa a chamar `lm.start_loop`,
`io_worker.add_controller` e `_sync_opcua_registration`;
`delete_controller` faz o espelho (`lm.stop_loop`,
`io_worker.remove_controller`). `SimulatorAdapter.opcua_node_ids()` foi
adicionado para o roteador não acessar `_opcua_server` privado.

### E2E-IMP-01 — criar malha e comandar sem reiniciar o daemon

**Pré-condição:** daemon iniciado com banco vazio, simulador ligado.

1. `POST /auth/login` → obter token de admin.
2. `POST /controllers` com `{"name":"E2E-TIC-001"}` → **201**, guardar `id`.
3. Aguardar 3 s.
4. `GET /system/status` → `active_controllers` **≥ 1**.
5. `GET /controllers/{id}/stats` → **200** (antes: 404).
6. `POST /commands/setpoint` `{"controller_id":id,"value":42.0}` → **200**
   (antes: 404 sem loop; 500 `KeyError: Controller N not registered` com loop
   mas sem registro OPC-UA).
7. `grep 'not registered\|telemetry_skipped'` no log do daemon → **0 ocorrências**.

**Condição de parada:** passos 4-6 nos códigos indicados e passo 7 zerado.

**Resultado medido** (script `/tmp/spid_smoke/smoke.sh`, mesmo script nos dois lados):

| | baseline `55b46f2` | com a correção |
|---|---|---|
| `active_controllers` após criar | **0** | **1** |
| `GET /stats` | **404** | **200** |
| `POST /commands/setpoint` | **404** | **200** |
| erros `not registered` no log | — | **0** |

### E2E-IMP-02 — apagar malha encerra o loop

1. Com a malha do E2E-IMP-01 ativa, `DELETE /controllers/{id}` → **204**.
2. Aguardar 1 s.
3. `POST /commands/setpoint` para o mesmo id → **404**.
4. Log do daemon não acumula `io_worker_read_error` para o id apagado.

**Condição de parada:** 204 seguido de 404, sem erros recorrentes no log.
**Resultado medido:** `delete_http=204`, `setpoint_after_delete_http=404`.

---

## 2. Abrir/importar projeto registra os controladores no IOWorker

**Bug.** `ProjectService._start_control_loops` iniciava os loops do projeto
recém-aberto, mas o `IOWorker` continuava com a lista de controladores
congelada no boot. Os loops rodavam sem nunca receber `TELEMETRY.{cid}`.

**Correção.** `ProjectService` recebe `io_worker` e chama `add_controller`
para cada controlador ao abrir/importar; `main.py` injeta a instância e a
expõe em `app.state.io_worker`.

### E2E-IMP-03 — abrir projeto com malhas passa a receber telemetria

1. Daemon rodando com projeto A (vazio).
2. `POST /project/new` `{"name":"projB"}`; criar 2 controladores nele; anotar ids.
3. `POST /project/new` `{"name":"projA2"}` (troca de projeto).
4. `POST /project/open` `{"name":"projB"}` → **200**.
5. Aguardar 5 s (sem reiniciar o daemon).
6. Para cada id: `GET /controllers/{id}/stats` → **200** e `sample_count` > 0.
7. `GET /system/status` → `active_controllers` == 2.

**Condição de parada:** passo 6 com `sample_count` crescente em duas leituras
separadas por 3 s — prova que `TELEMETRY.{cid}` está fluindo, não apenas que a
thread existe.

**Status:** coberto indiretamente pela suíte (`test_project_roundtrip.py`,
`test_api_project.py` — suíte verde). O E2E vivo acima **não foi executado**
nesta sessão; ver "Pendências".

---

## 3. `PIDWorker._run` não morre mais em silêncio

**Bug (achado pelo audit de domínio, confirmado no código).** O laço de
controle capturava apenas `zmq.ZMQError`. Qualquer outra exceção (PV `NaN`,
config inválida, frame msgpack corrompido) encerrava a thread do PID
**sem log e sem alarme**, com a saída congelada no último valor, enquanto
`/system/status` continuava reportando o daemon saudável. `ai_worker.py`,
`db_worker.py` e `io_worker.py` já tinham o guard — `pid_worker.py` era o
único outlier, justamente o mais crítico.

**Correção.** `except Exception` com `logger.exception` (mesmo padrão dos
irmãos) **mais** um `self._stop_event.wait(timeout=scan_s)` no handler: o sleep
normal fica no fim do `try`, então uma falha lançada antes dele faria a thread
girar a 100 % de CPU.

### E2E-IMP-04 — falha transitória não mata a malha

1. Iniciar daemon com uma malha em AUTO recebendo telemetria.
2. Injetar um frame inválido no barramento — via simulador, forçar `pv = NaN`
   (`PUT /simulator/{id}/pv` com `NaN`, ou publicar `TELEMETRY.{cid}` com
   `pv.value = null`).
3. Verificar no log: `pid_worker_iteration_error controller_id=N` presente.
4. Aguardar 10 s e restaurar PV válido.
5. `GET /controllers/{id}/stats` volta a evoluir; `POST /commands/setpoint` → 200.
6. `top`/`ps` durante o passo 3-4: CPU da thread **não** vai a 100 %.

**Condição de parada:** a malha volta a controlar sozinha após o frame ruim,
com o erro registrado e sem *spin* de CPU. Antes da correção o passo 5 falharia
permanentemente (thread morta) e nada apareceria no log.

**Status:** o guard e o backoff estão exercidos indiretamente por toda a suíte
de `pid_worker` (verde). A injeção de `NaN` **não foi executada** ao vivo.

---

## 4. `logging` da stdlib passa a ser configurado

**Bug.** `main()` chamava `structlog.configure()` mas nunca configurava o
módulo `logging` da stdlib. Como a maioria dos módulos usa
`logging.getLogger(__name__)` (`io_worker`, `pid_worker`, `loop_manager`,
`rl_engine`, `ai_worker`, adaptadores…), **todo** `.info()`/`.debug()` desses
módulos era descartado, independentemente de `SPID_LOG_LEVEL`. Isso já havia
causado uma investigação inteira em falso numa sessão anterior
(`plans/README.md`, "1 major unfixed finding").

**Correção.** `logging.basicConfig(level=..., format=...)` em `main()`, antes
de `structlog.configure()`.

### E2E-IMP-05 — logs dos workers aparecem

1. Iniciar o daemon com `SPID_LOG_LEVEL=INFO`.
2. `grep -E 'INFO +smart_pid_core' daemon.log | wc -l`.

**Condição de parada:** contagem > 1 e presença de linhas como
`INFO smart_pid_core.adapters.outbound.opcua_adapter opcua_adapter_started`.

**Resultado medido:**

| | baseline | com a correção |
|---|---|---|
| linhas de log stdlib | **1** | **8** |

---

## 5. Ciclo de vida dos sockets ZMQ e shutdown do EventBus

**Bug (duas partes, encontradas ao verificar as correções acima).**

1. **Nenhum worker fechava seus sockets.** `BusPublisher.close()` e
   `BusSubscriber.close()` existiam com zero chamadores em
   `pid_worker`, `stats_worker`, `ai_worker`, `io_worker`, `db_worker` e
   `alarm_worker` (`monitor_worker`, `telemetry_publisher` e o bridge WS já
   faziam certo — eram o padrão pretendido). Sockets ZMQ não são thread-safe;
   deixá-los para `ctx.destroy()` faz o fechamento acontecer na thread errada.
2. **O `EventBus` fechava os sockets do proxy pela thread errada.**
   `stop()` fechava `_xsub`/`_xpub` a partir da thread chamadora enquanto a
   thread do proxy estava dentro de `zmq.proxy()` usando exatamente esses
   sockets — comportamento indefinido.

Sintoma reproduzido: `zmq_ctx_term()` travando indefinidamente em
`EventBus.stop()`, e ocasionalmente `Fatal Python error: Aborted` com o
*stack* dentro de `zmq_proxy`.

**Correção.** Cada worker fecha seus próprios sockets num `finally` (laço
extraído para `_loop()` para manter o `_run()` responsável só pelo tempo de
vida). O proxy do `EventBus` passa a criar, fazer *bind*, servir e fechar os
sockets inteiramente dentro da sua thread, com um laço de `Poller` que observa
um `stop_event` (50 ms) — `stop()` sinaliza, faz `join` e só então destrói o
contexto. `start()` espera o *bind* via `threading.Event`.

### E2E-IMP-06 — suíte não trava nem aborta

Este é o teste que efetivamente detecta a regressão:

```bash
for i in $(seq 1 10); do
  timeout -s ABRT 60 uv run pytest \
    tests/core/integration/test_api_controllers.py -q -p no:cacheprovider \
    >/tmp/run_$i.log 2>&1
  echo "run $i EXIT=$? fatal=$(grep -c 'Fatal Python error' /tmp/run_$i.log)"
done
```

**Condição de parada:** 10/10 com `EXIT=0` e `fatal=0`.

**Resultado medido:**

| | com o wiring do item 1, sem a correção do bus | com a correção |
|---|---|---|
| execuções travadas (`EXIT=124`) | **6 de 8** | **0 de 10** |
| `Fatal Python error` | sim | **0** |

### E2E-IMP-07 — shutdown do daemon com malhas ativas

1. Subir o daemon, criar uma malha, encerrar (`SIGTERM`).
2. Subir de novo sobre o **mesmo** banco — agora o boot inicia loops reais.
3. `GET /system/status` → `active_controllers` ≥ 1.
4. `kill -TERM` e cronometrar.

**Condição de parada:** processo sai com código 0 em < 10 s.

**Resultado medido:** `CLEAN elapsed_s≈0.5`, exit 0 — **em ambos os lados**.
Ou seja: o travamento é reproduzível no harness de teste, **não** foi
reproduzido no daemon (2 tentativas). A correção continua justificada — é
comportamento indefinido segundo a documentação do ZMQ e mediu-se o defeito
real no pytest — mas **não se afirma** que havia trava de shutdown em produção.

---

## 6. `/controllers/{id}/stats` enxerga workers vivos

**Bug.** `get_stats_workers` lia `app.state.stats_workers`, um *snapshot*
tirado uma única vez em `run_daemon`. `get_ai_workers` já havia sido corrigido
para ler do `LoopManager`; o de stats ficou para trás. Malha criada depois do
boot → 404 eterno.

**Correção.** Mescla `{**snapshot, **loop_manager.get_stats_workers()}` — os
workers vivos vencem, e o snapshot ainda cobre ids que o loop manager não
possui (é também o ponto de injeção usado pelos testes).

> Nota de processo: a primeira versão simplesmente substituía o snapshot e
> quebrou `test_api_stats.py::test_get_stats` (404 ≠ 200), porque o teste
> injeta um `stats_worker` sem loop rodando. A mescla corrige em produção sem
> quebrar o ponto de injeção.

### E2E-IMP-08 — stats de malha criada em runtime

Coberto pelo passo 5 do E2E-IMP-01 (404 → 200) e por
`tests/core/integration/test_api_stats.py` (2 passed).

---

## Pendências e limites desta sessão

- **Não executados ao vivo:** E2E-IMP-03 (abrir projeto) e E2E-IMP-04
  (injeção de `NaN`). Ambos cobertos indiretamente pela suíte; a validação
  interativa em navegador ficou fora.
- **Sem alterações no frontend** — nenhum arquivo de `packages/smart_pid_web`
  foi tocado, logo `npm run test`/`typecheck` não foram executados e nenhuma
  spec de UI em `docs/` precisou de atualização.
- **`OPCUAAdapter` não tem `unregister_controller`.** Ao apagar um
  controlador, o loop e o scan do `IOWorker` param, então a entrada órfã no
  adaptador é inerte — mas fica registrada como dívida.
- **`SystemEventWorker._pub`** é criado no construtor (thread principal) e
  nunca fechado. Como é criado e destruído na mesma thread, `ctx.destroy()`
  lida com ele em segurança; não foi alterado.
- **1 falha ambiental** permanece (`test_opcua_start_stop`, porta 4849 tomada
  pelo daemon do usuário) — idêntica no commit base, não tocada.

### Achados auditados — **todos implementados** (branch `fix/audit-findings`)

Os 6 achados que esta sessão havia deixado como recomendação foram corrigidos
em seguida, numa branch dedicada. Ver a seção "Parte 2" abaixo.

Pontos verificados e **descartados** como falso-positivo: os 2 561 "unused
imports" e 178 "dead code" do tokensave (métodos alvo de `Thread(target=...)`
e helpers de spec Playwright); os pares "duplicados" `ProtectedLayout`/`App` e
`ModeMapField`/`DeleteConfirm` (mesma forma sintática, responsabilidades
distintas). A ordem de shutdown em `main.py` foi checada e está correta
(`loop_manager.stop_all()` antes de `bus.stop()`).

---

# Parte 2 — correção dos 6 achados auditados

Branch `fix/audit-findings`, a partir de `6d9b552`.
Verificação: **1624 backend passed** (+86 testes novos) e **895 frontend
passed / 94 arquivos**; `ruff` limpo; `tsc -b` limpo. A única falha continua
sendo a ambiental de porta 4849. O erro de `eslint` em `AiPanel.tsx:322`
(`label-has-associated-control`) é **pré-existente na main**, em arquivo não
tocado — confirmado rodando o mesmo lint na main.

| # | Achado | Correção | Arquivo |
|---|---|---|---|
| 1 | SQL por f-string | SET montado a partir de tupla literal de colunas | `user_repo.py` |
| 2 | Nomes sem limite | `min_length`/`max_length` em controller; validador único para projeto | `dtos/controllers.py`, `dtos/project.py` |
| 3 | Comandos sem limites | `controller_id > 0`; rejeita NaN/inf; `ti`/`td` ≥ 0 | `dtos/commands.py` |
| 4 | ARW mais largo que out_limits → windup | banda ARW é limitada a `[lo, hi]` no `compute()` | `pid_engine.py` |
| 5 | Multiplicador 16.0 fixo | `PIDEngine(reset_recovery_gain=…)`, default documentado | `pid_engine.py` |
| 6 | `cn()` e resync-buffer sem teste | 2 arquivos de teste novos | `utils.test.ts`, `resyncBuffer.test.tsx` |

## A-1 — ARW não pode mais desligar o anti-windup (segurança de controle)

**Bug.** O portão de anti-windup testa `cv >= arw_hi`, mas o CV é grampeado
pelos limites de **saída**. Com `arw_hi` configurado acima de `out_hi_lim`
(ex.: ARW 150 com saída 0–100), a condição nunca é verdadeira: o integral
acumula indefinidamente enquanto a saída está saturada — windup clássico.

**Correção.** Duas linhas em `compute()`: `arw_lo = max(arw_lo, lo)` e
`arw_hi = min(arw_hi, hi)`. Vale para qualquer projeto já gravado, sem
migração e sem rejeitar configurações existentes. O caso útil — banda ARW
**mais estreita** que a saída, que para de integrar antes da saturação —
continua exatamente como configurado.

### E2E-FIX-01 — malha com ARW mal configurado não enrola o integral

1. Criar malha com `out_hi_lim=100`, `arw_hi_lim=150`, `AUTO`, Ti curto.
2. Forçar saturação: SP bem acima do alcance da PV (ex.: SP 95 num processo
   que satura em 80), deixar rodar 2×TSS até CO travar em 100.
3. Baixar o SP para dentro do alcance (ex.: 40).
4. Cronometrar quanto tempo o CO leva para sair de 100.

**Condição de parada:** o CO começa a cair em ≤ 1×TSS após o passo 3. Antes da
correção o integral acumulado durante o passo 2 mantém o CO grampeado em 100
por muito mais tempo (proporcional ao tempo saturado), com overshoot na volta.

**Cobertura automatizada:** `tests/core/unit/test_pid_engine_arw_bounds.py`
(9 testes). Verificado que **falham sem a correção**: removendo só as duas
linhas do clamp, 3 testes quebram mostrando o integral acumulando ±1.0 por
scan enquanto saturado.

## A-2 — ganho de recuperação configurável por malha

`16.0` virou `DEFAULT_RESET_RECOVERY_GAIN`, documentado, e
`PIDEngine(reset_recovery_gain=…)`. Como o `LoopManager` cria um `PIDEngine`
por controlador, dá para ajustar por malha sem migração de schema.

### E2E-FIX-02 — recuperação da saturação

1. Saturar a malha (passo 2 do E2E-FIX-01) e registrar o tempo de saída da
   saturação com o default.
2. Repetir com um engine construído com `reset_recovery_gain=2.0`.

**Condição de parada:** a saída da saturação é visivelmente mais lenta com
ganho 2 do que com 16, e nenhuma das duas apresenta oscilação sustentada.
**Cobertura:** 4 testes no mesmo arquivo (default aplicado, constante = 16,
override, e ganho 1 desliga a aceleração).

## A-3 — nome de projeto: uma regra só

O charset era validado apenas em `ProjectService._safe_project_path`; o DTO
aceitava qualquer string. Ao adicionar a validação no DTO, **o próprio teste
pegou uma divergência real**: `.` e `..` passam no charset (o ponto é um
caractere legal) e só eram barrados por uma checagem separada no serviço.

A regra completa virou `validate_project_name()` no pacote de domínio, chamada
**pelos dois lados**. O serviço deixou de ter cópia própria.

### E2E-FIX-03 — nome inseguro rejeitado na borda

1. `POST /project/new` com `{"name": "../../etc/evil"}` → **422** (antes 400).
2. Idem com `"."`, `".."`, `"a/b"`, `"   "`, 129 caracteres → **422**.
3. `POST /project/new` com `"planta 1_v2.0-final"` → **200**.
4. Confirmar que nenhum arquivo foi criado fora de `SPID_PROJECTS_DIR`.

**Condição de parada:** todos os nomes hostis rejeitados e o legítimo aceito.
Os testes existentes já aceitavam `(400, 422)`, então a mudança de código de
status não quebra contrato. **Cobertura:** `tests/domain/test_dtos_validation.py`
inclui um teste de equivalência que roda o `_safe_project_path` real e exige
que DTO e serviço rejeitem exatamente o mesmo conjunto.

## A-4 — comandos: id positivo e valor finito

`controller_id` agora exige `> 0`. Para `value` **não** foi imposta faixa
numérica: setpoint é grandeza de engenharia e depende da malha (1500 °C e
−0.9 bar são legítimos) — a faixa continua sendo checada no `LoopManager`
contra os limites daquela malha. O que foi barrado é o que nunca é válido em
unidade nenhuma: **NaN e ±inf**, que envenenam o integral da forma velocidade
e passam ileso por qualquer comparação de limite.

### E2E-FIX-04 — comando com valor não-finito é recusado

1. `POST /commands/setpoint` `{"controller_id": 1, "value": NaN}` → **422**.
2. Idem `Infinity` → **422**.
3. `{"controller_id": 0, "value": 50}` → **422**.
4. `{"controller_id": 1, "value": 1500}` numa malha com `sp_hi_lim=2000` → **200**.
5. Após o passo 1, a PV/CO da malha continuam normais (nada foi escrito).

**Condição de parada:** 422 nos três primeiros, 200 no quarto, malha intacta.
**Cobertura:** `tests/domain/test_dtos_validation.py` (67 testes).

## A-5 — SET clause a partir de whitelist literal

`UserRepository.update` continua montando o SET dinamicamente (são 3 campos
opcionais), mas os nomes de coluna saem de uma tupla literal e nada mais, de
modo que nenhum texto vindo do chamador pode alcançar o SQL nem se a assinatura
crescer. Os valores seguem parametrizados.

### E2E-FIX-05 — alterar perfil/senha/estado de um usuário

1. Login como admin, `PUT /users/{id}` mudando só o perfil → 200, senha intacta.
2. `PUT` mudando só a senha → login antigo falha, novo funciona.
3. `PUT` desativando → login do usuário passa a falhar (401/403).
4. Reativar → login volta a funcionar.

**Condição de parada:** cada campo muda isoladamente sem afetar os outros nem
outras linhas. **Cobertura:** `tests/core/integration/test_user_repo_update.py`
(10 testes), incluindo um que captura a instrução emitida e exige exatamente
`UPDATE Usuarios SET perfil = ?, senha_hash = ?, ativo = ? WHERE id = ?`, e
outro que grava `'; DROP TABLE Usuarios; --` como senha e confirma que a tabela
sobrevive.

## A-6 — testes de frontend

- `src/lib/utils.test.ts` (9 testes) — `cn()`, com 75 call sites e nenhum teste:
  condicionais descartados e conflito de utilitário Tailwind resolvido pelo
  último. Uma regressão aqui não quebra nada ruidosamente, só desestiliza a UI.
- `src/realtime/resyncBuffer.test.tsx` (3 testes) — o buffer de resync do
  `RealtimeProvider`. Antes de escrever, foi verificado o que já era coberto:
  watchdog (`liveness.test.tsx`), backoff, `auth-failed`, `4401` e `resyncing`
  já tinham teste; **`RESYNC_BUFFER_MAX` não tinha nenhum** em todo o
  repositório. Cobre as três políticas: status retido durante o resync,
  coalescência (rajada de 50 vira 1) e o teto lossless de 256 alarmes com
  descarte do 257º.

### E2E-FIX-06 — reconexão com tráfego durante o resync

1. Abrir o dashboard com uma malha em AUTO e telemetria fluindo.
2. Derrubar o backend por ~10 s e subir de novo (força gap de sequência).
3. Durante a rejanela, disparar vários alarmes e deixar a PV variando.

**Condição de parada:** ao voltar, a trend **não** replica uma rajada de
valores antigos (só o mais recente), a lista de alarmes contém todos os
disparados durante a queda, e o banner sai de "resincronizando" para "ao vivo".

---

# Parte 3 — execução da suíte E2E (2026-07-31)

Os 14 testes descritos acima foram **executados ao vivo** sobre a main
`1c976a7`. Harness em `/tmp/spid_e2e/` (`harness.py`, `t1.py`, `t2.py`,
`t3.py`, `t4.py`, `imp06.sh`); daemons em portas descartáveis (181xx) com
`HOME` redirecionado para `/tmp/spid_e2e/*/home` — sem isso o `DaemonState`
de teste reescreveria `~/.smart-pid/daemon_state.json` do usuário. O daemon do
usuário (8537/5555/4849) não foi tocado em nenhum momento.

## Resultado: 14/14 PASS

| Teste | Evidência medida |
|---|---|
| E2E-IMP-01 | `active_controllers=1`, `/stats`=200, `/commands/setpoint`=200, 0 linhas `not registered\|telemetry_skipped` |
| E2E-IMP-02 | `delete=204`, setpoint depois=404, `io_worker_read_error` 0→0 |
| E2E-IMP-03 | `open=200`, `active=2`, `sample_count` 6→9 nas duas malhas (3 s de intervalo), 0 erros de IO — **falhou na primeira execução**, ver D2 |
| E2E-IMP-04 | 50 frames `pv.value=null`: `pid_worker_iteration_error`=50, `stats_worker_iteration_error`=50, CV 20/20/50 e amostras 20/20/50 (as duas threads voltaram sozinhas), CPU 1,2 % na janela de falha — **falhou na primeira execução**, ver D3 |
| E2E-IMP-05 | 7 linhas `INFO smart_pid_core`, `opcua_adapter_started` presente |
| E2E-IMP-06 | 10/10 `EXIT=0`, `Fatal Python error`=0 |
| E2E-IMP-07 | boot1 `CLEAN`/6,4 s/exit 0; `active_controllers=1` no boot 2; boot2 `CLEAN`/5,8 s/exit 0 |
| E2E-IMP-08 | `/stats`=200 com `sample_count` crescente numa malha criada em runtime |
| E2E-FIX-01 | ARW 150 com saída 0–100: CO sai do limite em 0 s (≤ 1×TSS=120 s), assenta em 124 s, PV final 60,0 — **idêntico** à configuração correta (ARW 100) e diferente do motor pré-correção (`6d9b552`: 124,5 s) |
| E2E-FIX-02 | recuperação: ganho 16 → 124,0 s; ganho 2 → 124,5 s; ganho 1 → 124,5 s; nenhum oscila (PV final 60,0) |
| E2E-FIX-03 | `../../etc/evil`, `.`, `..`, `a/b`, `"   "`, 129 chars → todos **422**; `planta 1_v2.0-final` → 200; nada criado fora de `SPID_PROJECTS_DIR` |
| E2E-FIX-04 | `NaN`→422, `Infinity`→422, `controller_id:0`→422, SP 1500 com `sp_hi_lim=2000`→200, malha intacta — **falhou na primeira execução**, ver D1 |
| E2E-FIX-05 | perfil/senha/ativo mudam isoladamente: role→admin (login mantém), senha nova (antiga 401), desativado 401, reativado 200, admin intacto |
| E2E-FIX-06 | navegador real: banner `null → SEM CONEXÃO → RESSINCRONIZANDO → null(live)`; PV exibida após o resync é a **atual** (0,00) e não a pré-queda (49,56); alarme disparado durante a queda (`HI 63.37 lim 60.00`, 20:34:37) presente na lista após o resync |

## Defeitos encontrados pela execução — todos corrigidos

### D1 — comando com `NaN`/`Infinity` devolvia **500**, não 422

Achado por E2E-FIX-04. O DTO rejeita corretamente (`FiniteFloat`), mas o
*handler padrão* do FastAPI monta `{"detail": jsonable_encoder(exc.errors())}`
— e esse payload ecoa o valor recusado. `JSONResponse` renderiza com
`allow_nan=False`, então a própria resposta 422 explodia com
`ValueError: Out of range float values are not JSON compliant: nan`, virando
500. Vale para qualquer campo `allow_inf_nan=False` do sistema.

**Correção:** handler próprio de `RequestValidationError` que substitui floats
não-finitos pelo seu nome antes de serializar (`error_handlers.py`). Mesma
forma de resposta, agora renderizável.
**Teste:** `test_api_commands.py::test_setpoint_non_finite_literal_is_422`
(NaN/Infinity/-Infinity) — verificado que falha sem a correção.

### D2 — trocar de projeto deixava o simulador e o cliente OPC-UA **parados**

Achado por E2E-IMP-03, que a Parte 1 nunca chegou a rodar ao vivo. Todos os
caminhos de projeto (`new`/`open`/`import`) param o simulador — e `new` também
o cliente OPC-UA — e nada os reiniciava. Pior: `_load_opcua_endpoint` **parava**
o cliente quando o projeto não tinha `opcua_endpoint` gravado, que é
exatamente o caso do simulador. Como o `IOWorker` pula o scan inteiro em
silêncio enquanto o adaptador está offline, o resultado era: loops vivos,
`/system/status` saudável, `active_controllers=2`, e **zero telemetria** até
reiniciar o daemon. Medido: `sample_count` travado em 0.

**Correção:** `ProjectService._resync_simulator_link()` religa o twin e
reaponta o cliente OPC-UA para os nós da malha recém-aberta ao final dos três
caminhos; `_load_opcua_endpoint` passa a não interferir em modo simulador (o
twin é dono do address space). A regra de binding, que estava duplicada em
três lugares (boot, `POST /controllers`, projeto) e foi justamente onde o caso
de projeto se perdeu, virou `simulator_adapter.bind_opcua_client()` — usada
pelos três.
**Testes:** `test_project_service.py` — `test_open_project_relinks_twin_and_opcua_client`,
`test_new_project_keeps_the_twin_running`,
`test_import_project_relinks_twin_and_opcua_client` — os três falham sem a correção.

### D3 — `StatsWorker` e `MonitorWorker` morriam em silêncio com um frame ruim

Achado por E2E-IMP-04. A Parte 1 corrigiu o `PIDWorker` afirmando que
`ai_worker`/`db_worker`/`io_worker` já tinham o guard e que o PID era o único
fora do padrão — mas `stats_worker` e `monitor_worker` nunca foram olhados.
Ambos só capturavam `zmq.ZMQError`; um `pv.value = null` chega como `TypeError`
(`None` na aritmética), escapa do laço e encerra a thread. Consequência: o
`/controllers/{id}/stats` continua servindo o último snapshot para sempre — um
worker morto é indistinguível de uma malha perfeitamente estável — e, em modo
monitor, `STATUS.{id}` simplesmente para (o `MonitorWorker` é o único produtor).
Medido antes da correção: `sample_count` congelado em 20 enquanto o PIDWorker
registrava 50 erros e seguia rodando.

**Correção:** mesmo guard do `PIDWorker` nos dois (log + `wait(scan_s)` para
não girar a 100 % de CPU).
**Testes:** `test_retention_and_worker_survival.py::TestWorkersSurviveACorruptedFrame`
(2 testes) — ambos falham sem a correção.

### D4 — a "falha ambiental" da porta 4849 era um defeito do fixture

A suíte carregava um vermelho permanente (`test_opcua_start_stop`) sempre que
um daemon estivesse rodando, porque `sim_api_deps` construía `CoreSettings`
sem `simulator_port` — e o `.env` do repositório manda 4849, a porta que o
daemon do desenvolvedor já ocupa. O fixture passa a pedir uma porta livre ao
SO. Prova: `SPID_SIMULATOR_PORT=18999 pytest test_api_simulator.py` já passava
13/13 antes da mudança, com o daemon do usuário no ar.

## Notas de execução

- **E2E-IMP-04 roda in-process.** O barramento é `inproc://`, então um frame
  corrompido só pode ser publicado de dentro do processo. O teste monta os
  mesmos objetos que `run_daemon` monta (EventBus + LoopManager + workers
  reais) e usa `lm.set_setpoint`, que é exatamente o que
  `POST /commands/setpoint` chama. A camada HTTP sobre esses objetos está
  coberta por IMP-01/03.
- **E2E-FIX-01/02 usam o motor pré-correção tirado do git** (`6d9b552`) como
  lado "antes", não um mock — o A/B é a mudança de código real.
- **E2E-FIX-06 no navegador**, SPA servida por `vite preview` (porta 5199)
  com proxy para o daemon de teste. A propriedade "não replica a rajada" só é
  observável no nível de unidade (`resyncBuffer.test.tsx`): a coalescência
  acontece num único tick de React, então o DOM nunca mostra os frames
  intermediários. O que o navegador prova é o efeito visível dela — depois do
  resync a tela mostra o valor **atual**, não o congelado de antes da queda.

## Verificação final

- Backend: `1633 passed, 0 failed` (com o daemon do usuário no ar).
- Frontend: `897 passed / 94 arquivos`, `tsc -b` limpo.
- `ruff` limpo em todos os arquivos alterados.
