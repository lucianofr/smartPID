# Design — Fatia 7: Settings + Conexão + Projetos .spid (Web HMI Smart PID v2)

**Data:** 2026-06-18 · **Status:** Proposto
**Parte de:** [guarda-chuva](2026-06-18-web-hmi-react-migration-design.md). Arquitetura, ponte WS, contrato JSON e stack: ver §2–3 do guarda-chuva.
**Autoridade de UI/design:** [design-system](2026-06-18-web-frontend-design-system-design.md).

> ✅ **Desbloqueado (2026-06-18).** Os CRITICALs de backend foram corrigidos na branch
> `fix/backend-security-hardening`: `routers/project.py` agora exige auth em todas as rotas
> (TD-001), `project_service` sanitiza o `name` contra path traversal (TD-002),
> `/commands/tuning` aplica guardrails (TD-003) e o import `.spid` tem limite de tamanho com
> 413 (TD-005). A auth é **imposta no servidor**. Ver `_tech-debt.md` (Resolved). Pendentes
> não-bloqueantes: TD-004 (CORS/bind) e TD-006 (token WS), tratados na Fatia 0+1.

## Auth (single-admin / no-RBAC)
O sistema é **single-user (um administrador), sem RBAC (mono-usuário)** — ver decisão de
produto no [guarda-chuva §1](2026-06-18-web-hmi-react-migration-design.md). **Não há gestão de
usuários nem tiers de papel** (operator/supervisor/admin): existe um único administrador. O
controle de auth de cada rota é binário — **pública** (login) **ou** exige o **administrador
autenticado** (401 sem auth vs 200 admin). Sem 403 por papel.
> ⚠️ **Backend pendente (TD-007):** o backend ainda expõe `routers/users` e gates por tier de
> papel; esta fatia assume o modelo single-admin. A migração do backend (remover RBAC/users
> router, colapsar gates para "exige admin autenticado") está rastreada em `_tech-debt.md` (TD-007).

## Escopo
Administração: configurações, login do administrador único (+ troca de senha opcional),
conexão OPC-UA e gestão de projetos `.spid`.

## Backend
Reusa `routers/auth`, `routers/opcua`, `routers/project`, `routers/system`.
Auth e sanitização de path em `routers/project.py` / `project_service` já implementados
(`fix/backend-security-hardening`, ver `_tech-debt.md`). Todas as rotas restritas exigem o
**administrador autenticado** (sem tiers de papel). A gestão de usuários / RBAC do backend
é descontinuada nesta direção de produto (ver TD-007).

## Frontend
- Página de settings (preferências de app/operação).
- Login do administrador único + troca de senha opcional (sem CRUD de usuários / RBAC).
- Página de conexão OPC: endpoint, connect/disconnect, browse/search de tags. (A aquisição é **contínua** — não há start/stop de aquisição.)
- Gestão de projetos `.spid`: list/new/open/import (upload multipart)/download/delete; welcome pós-login listando projetos do backend.

## REST/WS usados
- REST: `routers/auth` (login + troca de senha do admin); `routers/opcua` (`POST /connect`/`/disconnect`, `PUT /endpoint`, `GET /browse/{node_id:path}`, `GET /search`); `routers/project` (`POST /new`/`/open`/`/import`, `GET /list`/`/current`/`/download`, `DELETE /{name}`); `routers/system` (`GET /status`).
  - **Aquisição contínua:** no sistema real a aquisição OPC roda continuamente; não há (nem se expõe) start/stop de aquisição. A página de conexão cobre apenas connect/disconnect e configuração de endpoint.
  - **Sem `routers/users`:** modelo single-admin — sem CRUD de usuários (ver TD-007 para a remoção no backend).
- WS: não essencial (config/admin).

## Aceitação
- Todas as rotas restritas exigem o administrador autenticado (401 sem auth vs 200 admin).
- Conexão OPC configurável; tag browse/search funcional.
- Projetos `.spid` gerenciáveis (incl. upload/download); welcome lista projetos.
- Auth/credenciais fora dos metadados do projeto (regra do projeto preservada).

## Páginas PySide6 (paridade)
`settings_page`, `connection_page`, welcome/project dialog.

## Testes
- Vitest: forms de settings/conexão/projeto.
- Playwright: conectar OPC; importar/abrir projeto; trocar senha do admin.
- **Testes negativos de auth:** rota restrita retorna `401` sem JWT vs `200` com o admin autenticado (sem 403 por papel).

## Riscos
- Vazamento de credencial em projeto `.spid` → manter credenciais em `users.db`, nunca no `.spid` (regra do projeto).
- Upload de arquivo malicioso / `.spid` → limite de tamanho (413) e sanitização de path já implementados no backend (`fix/backend-security-hardening`, TD-002/TD-005). Validação de conteúdo do `.spid` (magic header SQLite + tabelas esperadas) permanece como melhoria futura de baixa prioridade.

## Dependências
Fatia 0+1 (shell, auth).
