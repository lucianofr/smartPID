# Design — Fatia 7: Settings + Users (RBAC) + Conexão + Projetos .spid (Web HMI Smart PID v2)

**Data:** 2026-06-18 · **Status:** Proposto
**Parte de:** [guarda-chuva](2026-06-18-web-hmi-react-migration-design.md). Arquitetura, ponte WS, contrato JSON e stack: ver §2–3 do guarda-chuva.

## Escopo
Administração: configurações, gestão de usuários (RBAC fino existente), conexão OPC-UA e gestão de projetos `.spid`.

## Backend
Nenhuma mudança — reusa `routers/users`, `routers/auth`, `routers/opcua`, `routers/project`, `routers/system`.

## Frontend
- Página de settings (preferências de app/operação).
- Gestão de usuários: CRUD respeitando RBAC; criação via register.
- Página de conexão OPC: endpoint, connect/disconnect, start/stop, browse/search de tags.
- Gestão de projetos `.spid`: list/new/open/import (upload multipart)/download/delete; welcome pós-login listando projetos do backend.

## REST/WS usados
- REST: `routers/users` (CRUD: `GET /{user_id}`, list, `PUT /{user_id}`, `DELETE /{user_id}`); `routers/auth` (`POST /register`); `routers/opcua` (`POST /connect`/`/disconnect`, `PUT /endpoint`, `/opcua/start`·`/stop`, `GET /browse/{node_id:path}`, `GET /search`); `routers/project` (`POST /new`/`/open`/`/import`, `GET /list`/`/current`/`/download`, `DELETE /{name}`); `routers/system` (`GET /status`).
- WS: não essencial (config/admin).

## Aceitação
- CRUD de usuários respeita RBAC (permissões do backend).
- Conexão OPC configurável; tag browse/search funcional.
- Projetos `.spid` gerenciáveis (incl. upload/download); welcome lista projetos.
- Auth/usuários fora dos metadados do projeto (regra do projeto preservada).

## Páginas PySide6 (paridade)
`settings_page`, `user_management_page`, `connection_page`, welcome/project dialog.

## Testes
- Vitest: forms de user/conexão/projeto, gating por RBAC na UI.
- Playwright: criar/editar user; conectar OPC; importar/abrir projeto.

## Riscos
- Vazamento de credencial em projeto `.spid` → manter users em `users.db`, nunca no `.spid` (regra do projeto).
- Upload de arquivo malicioso → validação multipart no backend (já existente).

## Dependências
Fatia 0+1 (shell, auth).
