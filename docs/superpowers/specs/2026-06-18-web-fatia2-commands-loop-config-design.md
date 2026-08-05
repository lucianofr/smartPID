# Design — Fatia 2: Comandos + Configuração por Loop (Web HMI Smart PID v2)

**Data:** 2026-06-18 · **Status:** Proposto
**Parte de:** [guarda-chuva](2026-06-18-web-hmi-react-migration-design.md). Arquitetura, ponte WS, contrato JSON e stack: ver §2–3 do guarda-chuva.
**Autoridade de UI/design:** [design-system](2026-06-18-web-frontend-design-system-design.md).

## Escopo
Ações de operação e configuração por loop: diálogo de config (PID/fuzzy/RL), comandos SP/modo/CO, toggle de otimização (enable/disable do optimizer), apply-tuning, controle do worker de IA.

## Auth (single-admin / no-RBAC)
O sistema é **single-user (um administrador), sem RBAC (mono-usuário)** — ver decisão de
produto no [guarda-chuva §1](2026-06-18-web-hmi-react-migration-design.md). Todas as ações
desta fatia exigem o **administrador autenticado** (rota pública só o login). **Não há tiers
de papel** (operator/supervisor/admin) nem 403 por papel: o gate é binário — 401 sem auth vs
200 admin. As ações de **write-back** (apply-tuning, tuning cru, toggle de otimização)
continuam exigindo **confirmação explícita no cliente + auditoria** no backend.

## Backend
- apply-tuning e os comandos de SP/modo/CO escrevem no controlador via OPC — fluxo já implementado.
- **Toggle de otimização — endpoint implementado** (branch `feat/pid-optimization-enable-toggle`):
  `POST /commands/optimization {controller_id, enabled}` persiste o master switch por loop
  `Controller.optimization_enabled` (conceito `ENABLE_OPTIMIZER` de `docs/bloco_pid.md`).
  Quando **desabilitado**, o SmartPID continua monitorando/publicando telemetria/stats mas o
  AI worker **não** computa sintonia nem publica `ACTION.AI` (nada é escrito de volta no
  controlador). Quando **habilitado**, o optimizer roda normalmente (ainda gated por
  mode = AUTO/CAS/RCAS e `ai_config.engine != NONE`). Persistido em `Controladores`
  (`optimization_enabled INTEGER NOT NULL DEFAULT 1`, com migração); o `AIWorker._enabled` é
  seedado a partir do flag na construção.

## Frontend
- Diálogo de configuração do loop: params PID (Kp, Ti, Td, estruturas, ARW, filtros), seleção NONE/FUZZY/RL e params correspondentes.
- Controles inline no card/faceplate: SP, modo (8 modos), CO (manual), toggle de otimização (enable/disable do optimizer).
- Botão apply-tuning com **confirmação explícita** antes de escrever no controlador.
- Painel de IA: start/stop/pause + status atual.

## REST/WS usados
- REST `routers/commands` (comandos reais — `controller_id` no **BODY**):
  - `POST /commands/mode`, `POST /commands/setpoint`, `POST /commands/output`.
  - apply-tuning: `POST /commands/apply-tuning/{controller_id}` (clampa params).
  - **Params PID:** NÃO existe `/commands/pid/params` → usar `POST /commands/tuning`.
    `POST /commands/tuning` agora aplica guardrails (`TuningCommand` tipado + clamp por
    `max_tuning_change_pct`) — corrigido no backend (TD-003, branch
    `fix/backend-security-hardening`, ver `_tech-debt.md`).
  - tuning-recommendations: `GET /commands/tuning-recommendations/{controller_id}`.
  - **Toggle de otimização (enable/disable do optimizer):** `POST /commands/optimization`
    Body `{ "controller_id": int, "enabled": bool }` → resposta `CommandResponse`
    (`{ ok, controller_id, enabled, detail }`). Persiste `Controller.optimization_enabled`.
    Erros: `401` sem JWT, `404` controlador desconhecido.
- REST `routers/ai`: `/controllers/{controller_id}/ai/start|stop|pause|status|history`.
- REST `routers/controllers` (CRUD: register/put/delete).
- WS: `status` (reflexo das ações), `ai` (`ACTION.AI.{id}`, estado de sintonia).

## Aceitação
- Alterar SP/modo/params reflete no backend e no quadro `status` ao vivo.
- apply-tuning só escreve após confirmação; resultado visível.
- Toggle de otimização persiste (`Controller.optimization_enabled`) e reflete no AI worker
  (desabilitado → sem `ACTION.AI`/write-back).
- IA start/stop/pause altera estado reportado.

## Páginas PySide6 (paridade)
`controller_dialog`, parte de `dashboard_page` (controles do card).

## Testes
- Vitest: validação de formulários de params, guarda de confirmação do apply-tuning, toggle de otimização.
- Playwright: mudar SP/modo → telemetria muda; apply-tuning com confirmação; toggle de otimização persiste.
- Auth: rota restrita retorna `401` sem JWT vs `200` com o admin autenticado (sem 403 por papel).

## Riscos
- Escrita indevida no controlador → confirmação obrigatória + auditoria; gate do admin autenticado no backend.
- Validação de params divergente do backend → validar client-side + tratar erro REST.

## Dependências
Fatia 0+1 (shell, auth, WS, cards).
