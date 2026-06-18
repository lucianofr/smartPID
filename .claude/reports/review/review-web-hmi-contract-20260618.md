# Contract-Accuracy Audit — Web HMI Slice Specs vs Backend

**Data:** 2026-06-18 · **Tipo:** Auditoria de contrato (REST + WS) · **Status:** Concluído
**Escopo:** Verificar que toda rota REST e todo evento/tópico WS citado nas specs das fatias web
(`docs/superpowers/specs/2026-06-18-web-fatia0[1-8]*.md` + guarda-chuva) existe de fato no backend,
com método e caminho (incluindo prefixo do router) corretos.

Os specs NÃO foram editados. Nenhum commit foi feito.

---

## Prefixos de router reais (de `adapters/inbound/api/app.py`)

| Router | Prefixo registrado |
|---|---|
| `stats` | `/controllers` |
| `ai` | `/controllers` |
| `project` | `/project` |
| `system` | `/system` |
| `auth` | `/auth` |
| `controllers` | `/controllers` |
| `commands` | `/commands` |
| `history` | `/history` |
| `simulator` | `/simulator` |
| `opcua` | `/opcua` |
| `alarms` | `/alarms` |
| `users` | `/users` |
| `audit` | `/audit` |
| `system_events` | `/system-events` |
| `export` | `/export` |

> Observação-chave: os routers `stats`, `ai` e `controllers` **compartilham o prefixo `/controllers`**.
> Por isso as rotas de AI são `/controllers/{controller_id}/ai/...` e as de stats são
> `/controllers/stats` e `/controllers/{controller_id}/stats`. Não existem prefixos `/ai` nem `/stats`.

---

## Tabela de mapeamento — REST

| Fatia | Spec claim (método + path) | Rota real (método + path completo c/ prefixo) | Status |
|---|---|---|---|
| 0+1 | `POST login` (routers/auth) | `POST /auth/login` | MATCH |
| 0+1 | `GET controllers` list | `GET /controllers` | MATCH |
| 0+1 | `GET controllers` get | `GET /controllers/{controller_id}` | MATCH |
| 0+1 | `GET /opcua/status` | `GET /opcua/status` | MATCH |
| 2 | `POST /{id}/pid/mode` (commands) | `POST /commands/mode` (controller_id no **body**, não no path) | MISMATCH |
| 2 | `POST /pid/sp` (commands) | `POST /commands/setpoint` (controller_id no body) | MISMATCH |
| 2 | `POST /pid/params` (commands) | *(não existe rota de params no router commands)* | MISSING |
| 2 | `POST /co` (commands) | `POST /commands/output` (controller_id no body) | MISMATCH |
| 2 | `POST /pid/enable` (commands) | *(não existe em commands; só em simulator: `POST /simulator/{controller_id}/pid/enable`)* | MISSING |
| 2 | `apply-tuning/{id}` | `POST /commands/apply-tuning/{controller_id}` | MISMATCH (prefixo `/commands` omitido) |
| 2 | `ai start` (routers/ai) | `POST /controllers/{controller_id}/ai/start` | MISMATCH (path real é `/controllers/{id}/ai/start`) |
| 2 | `ai stop` (routers/ai) | `POST /controllers/{controller_id}/ai/stop` | MISMATCH |
| 2 | `ai pause` (routers/ai) | `POST /controllers/{controller_id}/ai/pause` | MISMATCH |
| 2 | `ai status` (routers/ai) | `GET /controllers/{controller_id}/ai/status` | MISMATCH |
| 2 | `ai history` (routers/ai) | `GET /controllers/{controller_id}/ai/history` | MISMATCH |
| 2 | `controllers` CRUD register/put/delete | `POST /controllers`, `PUT /controllers/{id}`, `DELETE /controllers/{id}` | MATCH |
| 3 | `GET /active` (alarms) | `GET /alarms/active` | MATCH |
| 3 | `GET /{controller_id}/alarm-config` (alarms) | `GET /controllers/{controller_id}/alarm-config` (router **controllers**, não alarms) | MISMATCH |
| 3 | `POST /{alarm_id}/ack` (alarms) | `POST /alarms/{alarm_id}/ack` | MATCH |
| 3 | `POST /ack-all` (alarms) | `POST /alarms/ack-all` | MATCH |
| 3 | `PUT /{controller_id}/alarm-config` (alarms) | `PUT /controllers/{controller_id}/alarm-config` (router **controllers**, não alarms) | MISMATCH |
| 4 | `GET /{controller_id}/stats` (stats) | `GET /controllers/{controller_id}/stats` | MISMATCH (prefixo real `/controllers`) |
| 4 | `GET /stats` (stats) | `GET /controllers/stats` | MISMATCH (prefixo real `/controllers`) |
| 4 | `GET /history` (history) | `GET /history/{controller_id}` (path param obrigatório, não `/history`) | MISMATCH |
| 4 | `GET /list` (export) | *(não existe; export não tem endpoint de listagem)* | MISSING |
| 4 | `GET /{export_id}` (export) | `GET /export/{export_id}` | MATCH |
| 4 | `GET /{export_id}/download` (export) | `GET /export/{export_id}/download` | MATCH |
| 4 | criação de export (export) | `POST /export` | MATCH (era implícito; método/path confirmados) |
| 5 | `POST /preset` (simulator) | `POST /simulator/preset` | MATCH |
| 5 | `POST /disturbance` (simulator) | `POST /simulator/disturbance` | MATCH |
| 5 | `DELETE /disturbance/{controller_id}` (simulator) | `DELETE /simulator/disturbance/{controller_id}` | MATCH |
| 5 | `POST /output` (simulator) | `POST /simulator/{controller_id}/co` (não existe `POST /simulator/output`) | MISMATCH |
| 5 | `POST /mode` (simulator) | `POST /simulator/{controller_id}/pid/mode` (não existe `POST /simulator/mode`) | MISMATCH |
| 5 | `PUT /{controller_id}/auto-disturbance` (simulator) | `PUT /simulator/{controller_id}/auto-disturbance` | MATCH |
| 5 | `PUT /{controller_id}/auto-sp` (simulator) | `PUT /simulator/{controller_id}/auto-sp` | MATCH |
| 5 | `start/stop` (simulator) | `POST /simulator/start`, `POST /simulator/stop` | MATCH |
| 6 | `GET /stats` (stats) | `GET /controllers/stats` | MISMATCH (prefixo real `/controllers`) |
| 6 | `GET /{controller_id}/stats` (stats) | `GET /controllers/{controller_id}/stats` | MISMATCH |
| 6 | `GET /active` (controllers) | *(não existe rota `/controllers/active`)* | MISSING |
| 6 | `GET /ai-history` (routers/ai) | `GET /alarms/ai-history` (router **alarms**, não ai) | MISMATCH |
| 6 | `GET /tuning-recommendations/{controller_id}` (routers/ai) | `GET /commands/tuning-recommendations/{controller_id}` (router **commands**, não ai) | MISMATCH |
| 7 | `GET /{user_id}` (users) | `GET /users/{user_id}` | MATCH |
| 7 | list (users) | `GET /users` | MATCH |
| 7 | `PUT /{user_id}` (users) | `PUT /users/{user_id}` | MATCH |
| 7 | `DELETE /{user_id}` (users) | `DELETE /users/{user_id}` | MATCH |
| 7 | `POST /register` (auth) | `POST /auth/register` | MATCH |
| 7 | `POST /connect` (opcua) | `POST /opcua/connect` | MATCH |
| 7 | `POST /disconnect` (opcua) | `POST /opcua/disconnect` | MATCH |
| 7 | `PUT /endpoint` (opcua) | `PUT /opcua/endpoint` | MATCH |
| 7 | `/opcua/start` (opcua) | *(no router `opcua` não existe `/start`; só em `simulator`: `POST /simulator/opcua/start`)* | MISSING |
| 7 | `/opcua/stop` (opcua) | *(no router `opcua` não existe `/stop`; só em `simulator`: `POST /simulator/opcua/stop`)* | MISSING |
| 7 | `GET /browse/{node_id:path}` (opcua) | `GET /opcua/browse/{node_id:path}` | MATCH |
| 7 | `GET /search` (opcua) | `GET /opcua/search` (param `q`, não `query`) | MATCH |
| 7 | `POST /new` (project) | `POST /project/new` | MATCH |
| 7 | `POST /open` (project) | `POST /project/open` | MATCH |
| 7 | `POST /import` (project) | `POST /project/import` | MATCH |
| 7 | `GET /list` (project) | `GET /project/list` | MATCH |
| 7 | `GET /current` (project) | `GET /project/current` | MATCH |
| 7 | `GET /download` (project) | `GET /project/download` | MATCH |
| 7 | `DELETE /{name}` (project) | `DELETE /project/{name}` | MATCH |
| 7 | `GET /status` (system) | `GET /system/status` | MATCH |
| 8 | comandos via routers existentes (faceplate reusa Fatia 2) | herdam os mesmos MISMATCH/MISSING da Fatia 2 | MISMATCH (herdado) |

---

## Tabela de mapeamento — WebSocket / Tópicos

| Fatia | Spec claim | Realidade no backend | Status |
|---|---|---|---|
| 0+1 / guarda-chuva | Endpoint `GET /ws/realtime` (RealtimeWS) | **Não existe.** Não há diretório `ws/`, nem `@app.websocket`, nem `/ws/realtime` em `packages/smart_pid_core/src/`. | MISSING (planejado — adição da Fatia 0+1, ainda não implementado) |
| guarda-chuva | envelope `type`: `telemetry`/`status`/`action`/`alarm`/`ai` | São tipos lógicos a derivar dos eventos do domínio; não existem como "tópicos WS" hoje porque o WS não existe. Os eventos de domínio correspondentes existem: `TelemetryReceived`, `SystemStateChanged`/`STATUS.*`, `ControlActionComputed`, `AlarmTriggered`/`AlarmCleared`, `AIActionComputed`/`TuningRecommended`. | MISSING (depende do WS) |
| guarda-chuva §2.3 | tópicos do bus: `TELEMETRY.{id}`, `STATUS.{id}`, `ACTION.CTRL.{id}`, `ACTION.AI.{id}`, `ALARM`, AI/stats | Tópicos reais publicados/bridgeados: `TELEMETRY.{id}`, `STATUS.{id}`, `ACTION.CTRL.{id}`, `ACTION.AI.{id}`, **`EVENT.ALARM.*`** (não `ALARM`), `EVENT.SYSTEM`, `PARAMS.{id}`. | MISMATCH (tópico de alarme real é `EVENT.ALARM.*`, não `ALARM`) |
| 2 | WS `telemetry`, `ai` | dependem do WS inexistente | MISSING (depende do WS) |
| 3 | WS `alarm` (já encaminhado pela ponte da Fatia 0+1) | bus `EVENT.ALARM.*`; ponte WS inexistente | MISSING (depende do WS) |
| 4/5/6/8 | WS `telemetry` | depende do WS inexistente | MISSING (depende do WS) |

> Nota: o WS é explicitamente a **única adição** prevista pelos specs (guarda-chuva §2.1/§2.3 e
> Fatia 0+1 "Backend"). Portanto sua ausência hoje é esperada e coerente com o faseamento — mas
> os specs descrevem o endpoint/tópicos como contrato a ser cumprido, então foram listados aqui
> para que a implementação da Fatia 0+1 acerte o tópico de alarme (`EVENT.ALARM.*`).

---

## Correções recomendadas (por item MISMATCH/MISSING)

### Fatia 2 — Comandos
- `commands` não usa `controller_id` no path; usa **body**. Caminhos reais:
  `POST /commands/setpoint`, `POST /commands/mode`, `POST /commands/output` (cada um com
  `controller_id` no corpo JSON). Corrigir as referências `/{id}/pid/mode`, `/pid/sp`, `/co`.
- `/pid/params` e `/pid/enable` **não existem** no router `commands`.
  - Params PID em produção são escritos via `POST /commands/tuning` (Kp/Ti/Td no body) ou
    aplicados via `POST /commands/apply-tuning/{controller_id}`.
  - `pid/enable` só existe no **simulador**: `POST /simulator/{controller_id}/pid/enable`.
  - Corrigir a spec para refletir o mecanismo real (tuning/apply-tuning) ou marcar como gap de backend.
- `apply-tuning/{id}` → caminho real `POST /commands/apply-tuning/{controller_id}`.
- Rotas de AI: prefixo correto é `/controllers/{controller_id}/ai/...`
  (`start`/`stop`/`pause` POST; `status`/`history` GET). Não há router/prefixo `/ai`.

### Fatia 3 — Alarmes
- `alarm-config` (GET e PUT) vive no router **controllers**, não em `alarms`:
  `GET|PUT /controllers/{controller_id}/alarm-config`. Corrigir o spec (referência `routers/alarms`
  → `routers/controllers` para esses dois endpoints).

### Fatia 4 — Multi-trend + Stats + Export
- Stats: prefixo real `/controllers`: `GET /controllers/stats` e `GET /controllers/{controller_id}/stats`.
- History: caminho real `GET /history/{controller_id}` (param obrigatório), não `GET /history`.
  Query: `start`, `end`, `limit`.
- Export `GET /list` **não existe** — o router export não tem listagem. Criar no backend ou remover do spec.

### Fatia 5 — Simulador
- `POST /output` → não existe; o real é `POST /simulator/{controller_id}/co`.
- `POST /mode` → não existe; o real é `POST /simulator/{controller_id}/pid/mode` (body `mode` "AUTO"/"MAN").

### Fatia 6 — Executive Dashboard
- `GET /controllers/active` **não existe**. Usar `GET /controllers` (list completa) ou criar a rota no backend.
- `GET /ai-history` está no router **alarms**: `GET /alarms/ai-history` (params `start`,`end`,`controller_id`).
- `GET /tuning-recommendations/{controller_id}` está no router **commands**:
  `GET /commands/tuning-recommendations/{controller_id}`.
- Stats: mesmos prefixos corrigidos da Fatia 4 (`/controllers/...`).

### Fatia 7 — Settings/Users/OPC/Projetos
- `/opcua/start` e `/opcua/stop` **não existem** no router `opcua` (connect/disconnect cobrem o ciclo).
  Endpoints `opcua/start|stop` existem apenas para o **servidor do simulador**:
  `POST /simulator/opcua/start` e `POST /simulator/opcua/stop`. Corrigir o spec (remover de `routers/opcua`).
- `GET /opcua/search` usa o query param `q` (não `query`); ajuste de contrato fino para o frontend.

### Guarda-chuva — Tópico de alarme do bus
- O tópico real de alarme é `EVENT.ALARM.*` (e há também `EVENT.SYSTEM`), não `ALARM`.
  A ponte WS da Fatia 0+1 deve assinar `EVENT.ALARM.` para emitir `type: "alarm"`.

---

## Resumo de contagem

- **MATCH:** 41
- **MISMATCH:** 21
- **MISSING:** 8

(Cada linha das tabelas REST + WS conta como uma asserção; itens "herdado/depende do WS" contados uma vez.)
