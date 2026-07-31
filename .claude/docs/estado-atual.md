# Estado atual — `chore/improve-deep-audit`

Sessão `/improve deep` — 2026-07-31.
Worktree: `.worktrees/improve-deep-audit` · Branch: `chore/improve-deep-audit` · Commit: `2d46ea1`, rebaseado sobre a main atual `54118e8`.

> Este arquivo fica **na worktree**, não no repositório principal, de propósito:
> há outra sessão trabalhando em paralelo na main (daemon PID 2450091, alterações
> não commitadas em `dtos/simulator.py`, `CLAUDE.md`, web etc.). Nada fora desta
> worktree foi tocado.

## O que foi concluído

Auditoria profunda (tokensave como fonte primária — índice reconstruído para
`55b46f2`, 585 arquivos; graphify como fallback; 3 subagentes read-only em
paralelo para segurança, frontend e domínio backend), seguida de 6 correções
verificadas. **12 arquivos, +373/−29.**

1. **Controlador criado em runtime fica operante** — `POST /controllers` agora
   inicia o loop (`LoopManager`), entra na lista de scan do `IOWorker` e é
   registrado no adaptador OPC-UA; `DELETE` faz o espelho.
   `IOWorker.add_controller` existia com zero chamadores; `remove_controller`
   foi adicionado. Novo acessor público `SimulatorAdapter.opcua_node_ids()`.
2. **Abrir/importar projeto registra no `IOWorker`** — `ProjectService` recebe
   `io_worker`; `main.py` injeta e expõe em `app.state.io_worker`.
3. **`PIDWorker._run` não morre em silêncio** — `except Exception` +
   `logger.exception` (padrão já usado por ai/db/io workers; o PID era o único
   outlier) + backoff de um `scan_s` para não virar spin de CPU a 100 %.
4. **`logging` da stdlib configurado** em `main()` — antes, todo log de módulo
   que usa `logging.getLogger` era descartado (1 → 8 linhas medidas).
5. **Ciclo de vida de sockets ZMQ** — cada worker fecha os próprios sockets num
   `finally`; o proxy do `EventBus` passa a criar/bind/servir/fechar tudo dentro
   da própria thread, com `Poller` + `stop_event` e `join` antes de destruir o
   contexto.
6. **`get_stats_workers` lê workers vivos** (mesclando com o snapshot de boot).

## Decisões tomadas

- **Escopo mantido coeso** num único tema (ciclo de vida de controlador em
  runtime + ciclo de vida de recursos dos workers). Achados de DTO/validação,
  SQL por f-string e limites de anti-windup foram **documentados, não
  implementados** — estão na tabela final de `IMPROVE-TESTS-E2E.md`.
- **`get_stats_workers` mescla** em vez de substituir: a primeira versão
  substituía e quebrou `test_api_stats.py` (o teste injeta um worker sem loop).
- **Não se afirma trava de shutdown em produção**: o travamento foi reproduzido
  e corrigido no harness de pytest (6/8 → 0/10); no daemon não reproduziu.
- Correção do `EventBus` justificada mesmo assim: é UB documentado do ZMQ e o
  defeito foi medido.

## Verificação

- Suíte completa sobre a main atual (`54118e8`): **1538 passed, 1 failed**.
  A única falha (`test_opcua_start_stop`) é ambiental — porta 4849 ocupada pelo
  daemon do usuário — e foi comprovada **idêntica no commit base**, com um
  checkout de `54118e8` sem nenhuma alteração minha. **Zero regressões.**
  (Antes do rebase, sobre `55b46f2`: 1503 passed, conjunto de 14 falhas
  byte-idêntico ao baseline; as 13 de `AutoSPRequest.period_s` foram corrigidas
  pela sessão paralela em `d57ac1a`.)
- Estabilidade: `test_api_controllers.py` 10/10, 6/6 e novamente 6/6 após o
  rebase, sem travar (antes da correção do bus: 6 de 8 travavam com
  `Fatal Python error`).
- `ruff`: limpo nos 12 arquivos alterados; repositório 36 → 33 erros.
- Smoke test em daemon vivo (portas 18010/18011/18049, `/tmp`), baseline vs
  patched com o mesmo script:
  `active_controllers` 0 → 1 · `/stats` 404 → 200 · `/commands/setpoint`
  404 → 200 · logs stdlib 1 → 8 · shutdown limpo nos dois lados.
- `graphify update .` executado (8172 nós, 18070 arestas).

## Arquivos modificados

```
packages/smart_pid_core/src/smart_pid_core/
  adapters/inbound/api/dependencies.py
  adapters/inbound/api/routers/controllers.py
  adapters/inbound/simulator_adapter.py
  application/event_bus.py
  application/project_service.py
  application/workers/{ai,alarm,db,io,pid,stats}_worker.py
  main.py
IMPROVE-TESTS-E2E.md          (novo — 8 testes E2E, um por alteração)
```

## Próximos passos

1. Revisar o diff e decidir o merge (**não foi feito merge nem push** — a regra
   de branching exige aprovação explícita).
2. Executar ao vivo os dois E2E ainda não rodados: **E2E-IMP-03** (abrir projeto
   e confirmar `sample_count` crescendo) e **E2E-IMP-04** (injetar `NaN` e
   confirmar que a malha se recupera sem spin de CPU).
3. Avaliar os achados não implementados (tabela final de `IMPROVE-TESTS-E2E.md`),
   com destaque para `arw_limits` mais largo que `out_limits` (windup) —
   segurança de controle.
4. Dívida registrada: `OPCUAAdapter` não tem `unregister_controller`.
