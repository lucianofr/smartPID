# Estado atual — `fix/audit-findings`

Correção dos 6 achados auditados na sessão `/improve deep` — 2026-07-31.
Worktree: `.worktrees/audit-findings` · Branch: `fix/audit-findings` ·
Commit: `acf1dab`, a partir de `6d9b552` (main).

> Branch dedicada criada para esta tarefa, conforme a regra inviolável de
> branching. `git branch --show-current` verificado antes de qualquer edição.
> **Não foi feito merge nem push** — aguardando aprovação explícita.

## O que foi concluído

Os 6 achados que a sessão anterior deixou documentados como recomendação foram
implementados, cada um com teste. **12 arquivos, +1022/−60.**

### Segurança de controle
1. **ARW não pode mais desligar o anti-windup** — o portão testa
   `cv >= arw_hi`, mas o CV é grampeado pelos limites de *saída*; com
   `arw_hi > out_hi_lim` a condição nunca era verdadeira e o integral acumulava
   saturado. `compute()` agora limita a banda a `[lo, hi]`. Sem migração, vale
   para projetos já gravados, e a banda mais estreita (caso útil) fica intacta.
2. **Ganho de recuperação configurável** — `16.0` virou
   `DEFAULT_RESET_RECOVERY_GAIN` + `PIDEngine(reset_recovery_gain=…)`. O
   `LoopManager` cria um engine por malha, então é ajustável por loop sem mexer
   no schema.

### Limites de entrada
3. **Comandos** — `controller_id > 0`, rejeita NaN/inf, `ti`/`td` ≥ 0.
   **Deliberadamente sem faixa numérica** em setpoint/output: são grandezas de
   engenharia por malha (1500 °C, −0.9 bar) e a faixa já é checada no
   `LoopManager`. O que se barra é o que nunca é válido: não-finito.
4. **Nomes** — `min_length`/`max_length` em controller;
   `validate_project_name()` no domínio, chamado pelo DTO **e** pelo
   `_safe_project_path`.

### Robustez e cobertura
5. **`UserRepository.update`** monta o SET a partir de tupla literal de colunas.
6. **Testes de frontend** — `cn()` (75 call sites, zero testes) e o buffer de
   resync do `RealtimeProvider` (`RESYNC_BUFFER_MAX` não tinha cobertura
   nenhuma no repositório).

## Decisões tomadas

- **Nenhuma faixa numérica em setpoint/output** — a sugestão original do audit
  (`ge=0, le=100`) rejeitaria setpoints industriais legítimos.
- **Clamp em runtime, não validação de config** para o ARW — rejeitar no DTO
  quebraria linhas já gravadas e não pegaria mudança de parâmetro em runtime.
- **Uma função de validação de nome**, não duplicação — o próprio teste pegou
  que `.` e `..` passavam no charset e só eram barrados por checagem separada
  no serviço.
- **`Annotated[...]`** para as restrições compartilhadas dos comandos, em vez de
  reusar instâncias de `FieldInfo` (testado como funcional, mas é a forma
  documentada e estável).
- Não foi adicionado knob de config nem UI para o ganho de recuperação — seria
  feature com migração de schema, não correção de achado.

## Verificação

- **Backend: 1624 passed** (+86 testes novos), 1 falha ambiental
  (`test_opcua_start_stop`, porta 4849 ocupada pelo daemon do usuário — PID
  3705672, externo a esta sessão).
- **Frontend: 895 passed / 94 arquivos** (+12 testes novos). `tsc -b` limpo.
- `ruff` limpo em todos os arquivos alterados.
- **Testes de ARW comprovadamente não-vacuosos**: removendo apenas as duas
  linhas do clamp, 3 testes falham mostrando o integral acumulando ±1.0 por
  scan enquanto saturado.
- `eslint` acusa 1 erro em `AiPanel.tsx:322`
  (`label-has-associated-control`) — **pré-existente na main**, arquivo não
  tocado, confirmado rodando o mesmo lint na main.

## Arquivos

```
modificados:
  packages/smart_pid_core/.../adapters/outbound/user_repo.py
  packages/smart_pid_core/.../application/project_service.py
  packages/smart_pid_core/.../domain/services/pid_engine.py
  packages/smart_pid_domain/.../dtos/{commands,controllers,project}.py
novos:
  tests/core/unit/test_pid_engine_arw_bounds.py          (9)
  tests/core/integration/test_user_repo_update.py        (10)
  tests/domain/test_dtos_validation.py                   (67)
  packages/smart_pid_web/src/lib/utils.test.ts           (9)
  packages/smart_pid_web/src/realtime/resyncBuffer.test.tsx (3)
atualizado:
  IMPROVE-TESTS-E2E.md  — "Parte 2" com 6 testes E2E (E2E-FIX-01..06)
```

## Próximos passos

1. Revisar o diff e aprovar o merge para `main`.
2. Rodar ao vivo os E2E descritos, em especial **E2E-FIX-01** (malha com ARW
   mal configurado saindo da saturação) — é o de maior valor prático.
3. Dívida ainda aberta, herdada da sessão anterior: `OPCUAAdapter` não tem
   `unregister_controller`.
