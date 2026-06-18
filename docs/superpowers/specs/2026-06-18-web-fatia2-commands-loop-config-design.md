# Design — Fatia 2: Comandos + Configuração por Loop (Web HMI Smart PID v2)

**Data:** 2026-06-18 · **Status:** Proposto
**Parte de:** [guarda-chuva](2026-06-18-web-hmi-react-migration-design.md). Arquitetura, ponte WS, contrato JSON e stack: ver §2–3 do guarda-chuva.
**Autoridade de UI/design:** [design-system](2026-06-18-web-frontend-design-system-design.md).

## Escopo
Ações de operação e configuração por loop: diálogo de config (PID/fuzzy/RL), comandos SP/modo/CO, enable PID, apply-tuning, controle do worker de IA.

## Backend
Nenhuma mudança — reusa routers existentes. (apply-tuning escreve no controlador via OPC, fluxo já implementado no backend.)

## Frontend
- Diálogo de configuração do loop: params PID (Kp, Ti, Td, estruturas, ARW, filtros), seleção NONE/FUZZY/RL e params correspondentes.
- Controles inline no card/faceplate: SP, modo (8 modos), CO (manual), enable PID.
- Botão apply-tuning com **confirmação explícita** antes de escrever no controlador.
- Painel de IA: start/stop/pause + status atual.

## REST/WS usados
- REST `routers/commands` (comandos reais — `controller_id` no **BODY**):
  - `POST /commands/mode`, `POST /commands/setpoint`, `POST /commands/output`.
  - apply-tuning: `POST /commands/apply-tuning/{controller_id}` (clampa params + exige supervisor).
  - **Params PID:** NÃO existe `/commands/pid/params` → usar `POST /commands/tuning`.
    ⚠️ **DEPENDÊNCIA (tech-debt):** `/commands/tuning` hoje **fura guardrails** (sem
    `clamp_tuning_params`, só `require_operator`, body dict não-tipado). Corrigir o backend
    **antes** de expor tuning cru no web (ver `_tech-debt.md`).
  - tuning-recommendations: `GET /commands/tuning-recommendations/{controller_id}`.
  - **Enable PID:** NÃO existe em `commands` (só no simulador) → **GAP**: confirmar o
    mecanismo real de enable antes de implementar.
- REST `routers/ai`: `/controllers/{controller_id}/ai/start|stop|pause|status|history`.
- REST `routers/controllers` (CRUD: register/put/delete).
- WS: `status` (reflexo das ações), `ai` (`ACTION.AI.{id}`, estado de sintonia).

## Aceitação
- Alterar SP/modo/params reflete no backend e no quadro `status` ao vivo.
- apply-tuning só escreve após confirmação; resultado visível.
- IA start/stop/pause altera estado reportado.

## Páginas PySide6 (paridade)
`controller_dialog`, parte de `dashboard_page` (controles do card).

## Testes
- Vitest: validação de formulários de params, guarda de confirmação do apply-tuning.
- Playwright: mudar SP/modo → telemetria muda; apply-tuning com confirmação.

## Riscos
- Escrita indevida no controlador → confirmação obrigatória + RBAC no backend.
- Validação de params divergente do backend → validar client-side + tratar erro REST.

## Dependências
Fatia 0+1 (shell, auth, WS, cards).
