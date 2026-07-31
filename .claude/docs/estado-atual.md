# Estado atual — 2026-07-31

## Onde estamos

Checkout: raiz do repo (não é worktree dedicada)
Branch: **`fix/loops-faceplate-setpoint-write`**
Commit: `9f1f2d1` — `docs(tests): validate Loops faceplate setpoint write via live E2E run`
**Ainda NÃO mergeado na main. Aguardando aprovação explícita do usuário.**

## Tarefa

"corrija a escrita de um setpoint via faceplate principal na pagina LOOPS.
Use teste E2E para validar." Condição de parada: escrever 70 na caixa de
diálogo do faceplate + clicar "Set setpoint" → SP vai para 70, o
controlador persegue o novo alvo, e a PV chega a 70 dentro de 5 minutos.

## O que foi concluído

**Root cause encontrado (não era bug de código):** `FIC-101`
(`controller_id=1`, projeto ativo `autotest_project_created_by_agent_2026-07-30_1`)
estava persistido com `execution_mode=SUPERVISORY` (default do model —
`packages/smart_pid_domain/.../models/controller.py:141`). Em SUPERVISORY,
`PIDWorker._drain_telemetry` (pid_worker.py:505-509) relê `sp` de TODO frame
de telemetria — correto e testado para uma malha genuinamente supervisionada
por um DCS externo. Mas a fonte de telemetria da `FIC-101` é o Simulador
interno (`ns=2;i=6`), e nada escreve SP nele quando o operador chama
`POST /commands/setpoint` (isso só vai para OPC-UA se o `execution_mode`
**do daemon** — configuração global, `SPID_EXECUTION_MODE`, diferente do
campo por-controlador — for `monitor`, o que não é o caso aqui). Resultado:
o comando retorna `200 OK` e aplica o SP momentaneamente, e o próximo ciclo
de scan (1s) reverte silenciosamente pro valor antigo do registro OPC-UA do
simulador. Zero erro exposto ao operador. Confirmado com
`tests/core/integration/test_pid_worker_supervisory_readthrough.py`
(`test_ddc_keeps_seed_only_ownership`) que o mesmo mecanismo em modo `DDC`
NÃO reverte — `set_output`/`set_sp` valem e ficam.

`FIC-101` é operada como DDC de fato (AUTO, Kp/Ti/Td ao vivo, otimizador
FUZZY ativo computando CO) — só estava com o campo de config errado.

**Gap secundário encontrado (não corrigido — fora de escopo):** editar
`execution_mode` via `PUT /controllers/{id}` NÃO propaga para um
`PIDWorker` já rodando (ele guarda seu próprio snapshot de `Controller` de
quando `start_loop()` rodou, nunca reatribuído — só `ai_config` /
`process_speed` / `tss_s` / `scan_rate_s` fazem hot-reload, e só do AI
worker). É preciso reiniciar o daemon (ou reabrir o projeto, mas
`start_loop` é no-op se o id já está rodando) pra um edit de config pegar
efeito. Não há rota HTTP pra reiniciar uma malha isolada hoje.

**Fix aplicado:**
1. `PUT /api/controllers/1 {"execution_mode": "DDC"}`.
2. `hub restart smart-pid-core-backend` pra aplicar (o daemon já estava
   rodando persistente, 10h+ de uptime, de uma sessão anterior).
3. Validado ao vivo via `xd://browser` (CDP real, backend real, sem mock —
   segue o contrato de `TEST_E2E.md`, não o suite Playwright mockado em
   `packages/smart_pid_web/e2e/`): escreveu SP=70 no faceplate principal da
   página Loops, cliquei "Set setpoint". SP ficou em 70 em 49 polls ao
   longo de 245s (nunca reverteu). PV convergiu de 79.9 pra oscilar
   apertado (±3) em torno de 70 bem dentro do budget de 5 min, com o FUZZY
   amortecendo o overshoot inicial (`Ti: 10.00 → 12.75`).

**Nenhum código-fonte foi alterado** — o caminho de escrita (`Faceplate.tsx`
→ `CardControls.tsx` → `useSetpointMutation` → `POST /commands/setpoint` →
`LoopManager.set_setpoint` → `PIDWorker.set_sp`) já estava correto; só a
config da malha estava errada. O único diff no branch é documentação +
evidência.

## Decisões tomadas (e por quê)

1. **Não gatear `LoopManager.set_setpoint/set_mode/set_output` contra
   malhas SUPERVISORY.** Cheguei a considerar rejeitar o comando (como já
   se faz pro `execution_mode` do daemon = "monitor"), mas
   `tests/core/unit/test_loop_manager_commands.py` cria o fixture
   `Controller` SEM `execution_mode` (default SUPERVISORY) e espera
   `set_setpoint`/`set_mode`/`set_output` funcionarem sem exceção — um
   guard quebraria esse suite inteiro. O comportamento "aceita mas não
   persiste" pra SUPERVISORY é intencional e testado; a única correção
   válida era a config da malha.
2. **Não mudei o default do model (`SUPERVISORY`) nem o default do diálogo
   "Nova malha".** É uma postura de segurança deliberada (não assumir
   autoridade de controle por padrão) — mudar isso é decisão de produto,
   fora do escopo de "corrigir a escrita de setpoint".
3. **Runbook novo em vez de spec Playwright.** `TEST_E2E.md` já estabelece
   que validação contra backend real usa Chrome/CDP (`xd://browser`), não
   Playwright — o suite `packages/smart_pid_web/e2e/*.spec.ts` é 100%
   mockado por design (comentários no topo de cada spec confirmam). Criei
   `TEST_E2E_loops_faceplate_setpoint.md` seguindo o mesmo formato
   (Steps/Expected/Evidence/Result) em vez de inventar uma segunda
   convenção de teste.
4. **Branch dedicada criada** (`fix/loops-faceplate-setpoint-write`), a
   partir de `main`, conforme regra do CLAUDE.md. Havia mudanças
   não-commitadas de OUTRA tarefa (fix do simulador / inject disturbance,
   sessão anterior) já na árvore de trabalho — não toquei nelas, só
   fiz stage dos 5 arquivos novos desta tarefa.

## Verificação

| Gate | Resultado |
|---|---|
| Escrita de SP=70 via faceplate principal (Loops) | PASS — SP fica em 70, sem reversão, em 49 amostras / 245s |
| Controlador persegue o novo alvo | PASS — CO muda de direção em <1s; PV se move em direção a 70 |
| PV chega a 70 dentro de 5 min | PASS — convergiu (oscilação ±3) por volta de t≈220-245s |
| Testes unit/integration existentes | NÃO rodei a suite completa (nenhum código-fonte mudou nesta tarefa — só docs/evidência) |

## Pendências conhecidas

1. Gap de hot-reload de config (`execution_mode` e outros campos não
   propagam pra um `PIDWorker` já rodando) — real, mas fora do escopo desta
   tarefa. Não há rota pra reiniciar uma malha isolada sem reiniciar o
   daemon inteiro.
2. Havia uma escrita de SP=80 "misteriosa" observada durante a investigação
   (antes da minha escrita de 70), provavelmente de uma sessão/browser
   concorrente no mesmo backend compartilhado — não é um driver contínuo
   (confirmei 15s parado sem nenhuma mudança), tratei como ruído do
   ambiente compartilhado, não interferiu na validação final.
3. As 15 modificações não-commitadas de OUTRA tarefa (simulador / inject
   disturbance) continuam intocadas na árvore de trabalho.

## Próximos passos sugeridos

1. Usuário revisa `TEST_E2E_loops_faceplate_setpoint.md` e as 4 evidências
   em `test-evidence/LOOPS-SP-*.png`.
2. Aprovar, então merge de `fix/loops-faceplate-setpoint-write` pra `main`.
3. Se algum dia for necessário editar config de malha ao vivo sem restart
   completo do daemon, endereçar o gap de hot-reload como tarefa própria.
