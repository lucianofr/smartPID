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

### Achados auditados e **não** implementados (recomendações)

Levantados pelos audits paralelos e verificados, mas deixados fora para manter
o conjunto de mudanças coeso:

| Achado | Local | Severidade |
|---|---|---|
| SQL montado por f-string (seguro hoje, anti-padrão) | `adapters/outbound/user_repo.py:106` | Média |
| `ControllerCreate.name` / `ProjectCreate.name` sem `min_length`/`max_length` | `dtos/controllers.py`, `dtos/project.py` | Média |
| Comandos numéricos sem limites (`SetpointCommand.value`, `controller_id` sem `gt=0`) | `dtos/commands.py` | Média |
| `arw_limits` pode ser configurado mais largo que `out_limits` → windup | `domain/services/pid_engine.py:108-135` | Média (segurança de controle) |
| Multiplicador de reset-recovery fixo em `16.0`, não configurável | `domain/services/pid_engine.py:131` | Baixa |
| `RealtimeProvider` (complexidade cognitiva 39) e `cn()` (fan-in 75) sem testes dedicados | `smart_pid_web/src/realtime/`, `src/lib/utils.ts` | Baixa |

Pontos verificados e **descartados** como falso-positivo: os 2 561 "unused
imports" e 178 "dead code" do tokensave (métodos alvo de `Thread(target=...)`
e helpers de spec Playwright); os pares "duplicados" `ProtectedLayout`/`App` e
`ModeMapField`/`DeleteConfirm` (mesma forma sintática, responsabilidades
distintas). A ordem de shutdown em `main.py` foi checada e está correta
(`loop_manager.stop_all()` antes de `bus.stop()`).
