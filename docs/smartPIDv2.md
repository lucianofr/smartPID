# **Especificação Técnica: Smart PID Edge Platform **

## **MÓDULO 1: Visão Geral e Escopo**
O **Smart PID Edge Platform** é um sistema industrial focado em otimização de malhas de controle PID. Ele utiliza Inteligência Artificial (Fuzzy ou Aprendizado por Reforço - RL) para ajustar dinamicamente o parâmetro Integral ($K_i$ ou $T_i$), visando estabilidade e eliminação de erro de regime em processos de diferentes dinâmicas.

A ferramenta funciona tanto como um Otimizador de Borda (Edge Optimizer) acoplado a CLPs existentes, quanto como um Historiador e Ferramenta Analítica de Desempenho de Malhas.

### **1.1. Arquitetura de Plataforma (Divisão de Módulos)**
Para garantir resiliência extrema e escalabilidade, o sistema abandona a topologia monolítica e divide-se em dois módulos independentes que se comunicam via rede:
1. **Módulo A: Core Engine (O Backend / Edge Daemon):**
   * Sem interface gráfica (*Headless mode*). Projetado para rodar como Serviço do Windows ou Daemon Linux (`systemd`) em um PC Industrial colado ao CLP.
   * Único responsável por interagir com o CLP (OPC-UA), rodar a IA, calcular o PID, gerenciar alarmes e escrever no banco de dados SQLite.
2. **Módulo B: HMI Desktop (O Frontend / UI):**
   * Aplicativo visual desenhado para o operador/engenheiro na sala de controle.
   * Funciona estritamente como um "Cliente" de rede. Não possui acesso direto ao hardware (OPC-UA) nem ao arquivo do banco de dados, consumindo dados do Backend.

### **1.2. Stack Tecnológico Atualizado**
* **Frontend (HMI):** 
  * Python 3.10+, PySide6 (Qt for Python). 
  * `pyqtgraph` (Gráficos ultra-rápidos para renderizar a 30~60 FPS).
  * `httpx` ou `requests` (Cliente para API HTTP).
* **Backend (Core Engine):** 
  * `asyncua` (Comunicação OPC-UA assíncrona).
  * `stable-baselines3` (RL), `scikit-fuzzy`, `numpy`.
  * `control`, `scipy.signal` (Simulador de Processos).
  * `sqlite3` (Banco de Dados em modo WAL).
* **Middleware (Ponte de Comunicação):** 
  * `pyzmq` (ZeroMQ via TCP) para telemetria em milissegundos.
  * `FastAPI` (API REST) para consultas de histórico e envio de comandos.

---

## **MÓDULO 2: Arquitetura Distribuída, Middleware e Multitarefa**

A lógica de controle e a interface gráfica não apenas rodam em threads separadas, mas podem rodar em máquinas físicas diferentes. A comunicação é orquestrada por dois canais:

### **2.1. O Canal de Tempo Real (ZeroMQ PUB/SUB via TCP)**
O Backend expõe um socket ZeroMQ via rede (ex: `tcp://0.0.0.0:5555`). O Frontend atua como Assinante (SUB) para atualizar a tela sem travamentos.
* **Tópico `TELEMETRY.{ID}`:** Publicado pela Thread OPC-UA do Backend (ex: `{"pv": 100.5, "sp": 100.0, "co": 45.2, "int_val": 1.2}`).
* **Tópico `EVENT.ALARM.{ID}` e `ALARM.RECENT`:** Publicado pelo Motor de Alarmes do Backend instantaneamente quando um limite é rompido.
* **Tópico `LOG.AI.{ID}`:** Explicação passo a passo ("Justificativa") das decisões da IA.
* **Tópico `SYS.STATE`:** Status do sistema e uso de CPU/RAM do PC Edge.

### **2.2. O Canal de Comando e Histórico (FastAPI REST)**
O Backend expõe um servidor HTTP (ex: porta 8000). O Frontend usa requisições web para ações que exigem validação:
* **`GET /history/{tag_id}?hours=24`:** O Frontend pede os dados passados para desenhar gráficos; o Backend lê o SQLite e devolve em JSON.
* **`POST /command/setpoint`:** O Frontend manda um novo SP; a API valida a permissão e escreve no OPC-UA.
* **`PUT /config/pid`:** O engenheiro salva novos ganhos ou muda o método da IA.

### **2.3. O Modelo de Threads (Atores no Backend)**
O Backend adota o padrão **Dual-Thread por Malha** somado às threads de infraestrutura:
1. **Thread de I/O (Comunicação Assíncrona):** Única responsável pela rede. Conecta ao OPC-UA e escreve no CLP.
2. **Thread de Controle Regulatório (The PID Worker):** Altíssima prioridade. Executa estritamente a matemática do PID no *Scan Rate* definido. Sobrevive mesmo se a IA falhar.
3. **Thread de Otimização (The AI Worker):** Prioridade baixa/média. Executa a inferência Fuzzy ou RL. Avalia a telemetria, calcula o novo ganho integral ($T_i$) e publica internamente.
4. **Thread de Banco de Dados e API:** O motor SQLite (em modo WAL e efetuando *Batch Inserts*) e o servidor FastAPI.

---

## **MÓDULO 3: O Núcleo de Controle PID e Topologias**

Toda a matemática e execução do PID ocorre internamente no Backend.

### **3.1. Modos de Execução da Malha**
* **Modo Supervisório (Externo) [DEFAULT]:** O controle PID reside no PLC. O Backend monitora PV, SP e CO via OPC-UA e escreve *apenas* o ajuste do parâmetro integral no PLC. Na interface de configuração, os campos exclusivos do DDC (PID Tuning, Scaling & Limits, Filters & IO, Shed & Safety, PID Structure, Integral Type) ficam ocultos.
* **Modo DDC (Direct Digital Control / Interno):** O Backend executa a equação PID completa. Lê PV, calcula CO e escreve o valor no atuador via OPC-UA. Todos os campos de configuração ficam visíveis.
* **Scan Rate**: Deverá ser possível escolher um SCAN RATE para cada controlador adicionado e configurado no sistema. Isso garante determinismo para malhas lentas vs rápidas.

*Os detalhes de implantação do algoritmo PID no modo DDC estão no arquivo `./bloco_wpid.md`.*

---

## **MÓDULO 4: Inteligência Artificial e Self-Tuning Autônomo**

O sistema opera de forma autônoma (*Zero-Touch*), não exigindo que o usuário programe regras lógicas. Cada malha pode escolher entre 3 estratégias de otimização, que executam de forma isolada na *Thread de Otimização* do Backend: **NONE, FUZZY ou RL (Reinforcement Learning)**. 

### **4.1. Objetivos de Controle (O Comportamento Desejado)**
A sintonia do motor de IA muda radicalmente de acordo com o "Objetivo de Controle" selecionado pelo usuário na configuração da malha:
1. **Seguimento de Setpoint (SP Tracking):** Foco em alcançar o alvo rápido, mas freando agressivamente para não ultrapassar (Overshoot nulo). A IA penaliza velocidade excessiva de aproximação.
2. **Rejeição de Distúrbios (Regulatory):** O SP é fixo. Foco em "matar" o erro de regime (Offset) o mais rápido possível quando uma força externa afasta a PV do alvo. A IA é mais agressiva perto do erro zero.
3. **Controle de Nível Pulmão (Surge Level):** A PV (Nível) deve flutuar livremente para não perturbar a válvula. A IA cria uma "banda morta virtual" e só atua quando a PV atinge os extremos perigosos, ignorando pequenos erros ao redor do SP.

---

### **4.2. Estrutura do Motor de Inferência Fuzzy**
Se a malha operar no modo **FUZZY**, o Backend instancia um motor pré-configurado via `scikit-fuzzy`. A inferência segue os seguintes passos estritos:

**A. Fuzzificação (Entradas e Conjuntos):**
As duas variáveis de entrada são o **Erro** ($E = SP - PV$) e a **Variação do Erro** ($\Delta E$).
* Para universalizar a IA, as entradas são **Normalizadas** para a faixa de **-100% a +100%** do Fundo de Escala (Span/Range) do instrumento.
* Os Conjuntos Fuzzy adotam 7 níveis, utilizando funções Triangulares no centro e Trapezoidais nos extremos, com **50% de sobreposição (overlap)**:
  * **NB** (Negative Big), **NM** (Negative Medium), **NS** (Negative Small), **ZO** (Zero), **PS** (Positive Small), **PM** (Positive Medium), **PB** (Positive Big).

**B. Matrizes de Regras Lógicas (Base de Conhecimento):**
O motor carrega dinamicamente uma das 3 matrizes baseadas no Objetivo de Controle. A saída determina a alteração do ajuste integral:

* **Matriz 1: Seguimento de Setpoint (SP Tracking)**
  *(Lógica: Se o erro é grande, mas a PV já está voando em direção ao SP, a matriz manda reduzir a ação integral (NM/NB) para evitar Overshoot).*
  | E \ ΔE | NB | NM | NS | ZO | PS | PM | PB |
  | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
  | **PB** | ZO | PS | PM | PB | PB | PB | PB |
  | **PM** | NS | ZO | PS | PM | PM | PB | PB |
  | **PS** | NM | NS | ZO | PS | PM | PM | PB |
  | **ZO** | NB | NM | NS | ZO | PS | PM | PB |
  | **NS** | NB | NM | NM | NS | ZO | PS | PM |
  | **NM** | NB | NB | NM | NM | NS | ZO | PS |
  | **NB** | NB | NB | NB | NB | NM | NS | ZO |

* **Matriz 2: Rejeição de Distúrbios (Regulatory Control)**
  *(Lógica: Muito mais agressiva no centro. Se há qualquer erro residual e a PV não está se movendo ($\Delta E = ZO$), a IA empurra forte a ação integral).*
  | E \ ΔE | NB | NM | NS | ZO | PS | PM | PB |
  | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
  | **PB** | PM | PM | PB | PB | PB | PB | PB |
  | **PM** | PS | PM | PM | PB | PB | PB | PB |
  | **PS** | ZO | PS | PM | PM | PB | PB | PB |
  | **ZO** | NM | NS | ZO | ZO | ZO | PS | PM |
  | **NS** | NB | NB | NB | NM | NM | NS | ZO |
  | **NM** | NB | NB | NB | NB | NM | NM | NS |
  | **NB** | NB | NB | NB | NB | NB | NM | NM |

* **Matriz 3: Controle de Nível Pulmão (Surge Level)**
  *(Lógica: O centro inteiro é ZO (Zero Action). O controlador permite oscilação e só reage violentamente (PB/NB) se ameaçar secar ou transbordar).*
  | E \ ΔE | NB | NM | NS | ZO | PS | PM | PB |
  | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
  | **PB** | PM | PB | PB | PB | PB | PB | PB |
  | **PM** | ZO | PS | PM | PM | PM | PB | PB |
  | **PS** | ZO | ZO | ZO | ZO | ZO | ZO | PS |
  | **ZO** | ZO | ZO | ZO | **ZO** | ZO | ZO | ZO |
  | **NS** | NS | ZO | ZO | ZO | ZO | ZO | ZO |
  | **NM** | NB | NB | NM | NM | NM | NS | ZO |
  | **NB** | NB | NB | NB | NB | NB | NB | NM |

**C. Defuzzificação:**
Utiliza o método de **Centro de Gravidade (Centroid - CoG)** para converter o polígono resultante no valor escalar contínuo **$\gamma$** (variando estritamente de **-1.0** a **+1.0**).

---

### **4.3. Cadência, Tempo Morto ($L$) e Adaptação de Velocidade ($S_v$)**
A saída matemática ($\gamma$) passa pelo "Filtro de Física do Processo":

**1. Fator de Velocidade (Scaling Factor - $S_v$):**
* Rápidos (Vazão): $S_v = 0.05$ (Paciência. Ajustes microscópicos de 5%).
* Médios (Pressão): $S_v = 0.15$ (Ajustes de 15%).
* Lentos (Temperatura): $S_v = 0.30$ (Correções agressivas de 30% para vencer inércia).

**2. Equação de Atualização do Ganho Integral ($K_i$):**
$$K_{i(novo)} = K_{i(atual)} \cdot (1 + (\gamma \cdot S_v))$$
*(Inversamente tratada se a topologia exigir $T_i$ em Segundos/Repetição).*

**3. Cadência de Execução baseada em Tempo Morto ($T_{ciclo}$):**
Para evitar correções encavaladas, a IA aguarda a resposta do processo baseada no Tempo Morto ($L$) informado pelo usuário:
$$T_{ciclo} = L \times 3$$

---

### **4.4. Motor de Aprendizado por Reforço (RL)**
Caso o usuário selecione a IA do tipo RL (`stable-baselines3` - SAC/PPO):
* O agente usa **Online Learning** contínuo.
* **Funções de Recompensa (Reward Functions)** atreladas ao Objetivo:
  * *SP Tracking/Rejection:* Recompensa positiva por minimizar IAE/ITAE, punindo oscilações da válvula (TV).
  * *Surge Level:* Recompensa positiva por manter a Válvula parada. Só pune o IAE se a PV sair da banda morta.
* Sujeito aos mesmos Guardrails (limites de $T_i$) e cadência ($T_{ciclo}$).

### **4.5. Explicabilidade da IA (Log de Raciocínio)**
A cada ciclo da IA, a Thread no Backend publica uma mensagem no ZeroMQ justificando a matemática.
* *Exemplo:* "Aumentando Ti em 5% - Erro estável (ZO), mas Derivada aponta distúrbio rápido (NB)."
Essas mensagens são exibidas na HMI em uma caixa terminal e gravadas na tabela `Log_Sintonia_IA`.

---

## **MÓDULO 5: Comunicação OPC-UA e Mapeamento**

### **5.1. Máquina de Estados da Conexão (Resiliência no Backend)**
* **OFFLINE:** Desconectado intencionalmente. IA pausa.
* **ONLINE:** Transmitindo dados.
* **RECONNECTING:** Queda de rede. O Backend tenta reconectar de forma invisível para o operador. Ao voltar, executa o *Bumpless Transfer*.

### **5.2. Mapeamento de Tags (Tag Binding Table) e Browser OPC-UA Remoto**
Adicionar um ícone de configurações onde irá abrir as opções do controlador, entre elas a tabela de mapeamento relacionando variáveis internas (PV, SP, CO, Ti) aos *NodeIDs* (ex: `ns=4;s=MAIN.PV`).

* **Navegador Modal OPC-UA Remoto:** Ferramenta visual estilo *Tree View* com barra de pesquisa. 
  * *Mecânica V3.0:* Como a HMI não está conectada ao CLP, o clique no botão da Lupa envia um `GET /opcua/browse` para o Backend. O Backend varre a árvore do CLP e envia para a HMI desenhar a interface de seleção.

---

## **MÓDULO 6: Gerenciamento de Dados, Historiador e SQLite**

O arquivo local `.spid` (banco SQLite) reside **exclusivamente na máquina do Backend**. A HMI não possui acesso direto ao arquivo, consumindo dados históricos via FastAPI.

### **6.1. Hibridez e Performance no Backend**
* **RAM (Curto Prazo):** Buffer da IA usando `collections.deque`.
* **Lotes (Batch Inserts):** Acumula dados em memória e grava no banco a cada 5~10 segundos. O banco usa `PRAGMA journal_mode=WAL;`.
* **Limpeza Automática:** Retenção histórica estrita de **7 dias**. Query diária gerenciada pelo Backend: `DELETE FROM Log_Processo WHERE timestamp <= datetime('now', '-7 days');`

### **6.2. Schema Unificado de Tabelas (DDL Final)**
```sql
-- Usuarios e RBAC (Usados para validar chamadas na API)
CREATE TABLE Usuarios (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password_hash TEXT, role TEXT);

-- Controladores (O Backend é o detentor absoluto das configurações)
CREATE TABLE Controladores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT UNIQUE NOT NULL, descricao TEXT,
    modo_execucao TEXT CHECK(modo_execucao IN ('SUPERVISORY', 'DDC')),
    scan_rate_ms INTEGER DEFAULT 1000,
    node_id_pv TEXT, node_id_sp TEXT, node_id_co TEXT, node_id_integral TEXT,
    is_scaled BOOLEAN DEFAULT 0, pv_min REAL, pv_max REAL, co_min REAL, co_max REAL,
    pid_structure TEXT CHECK(pid_structure IN ('ISA', 'PARALLEL', 'SERIES')),
    integral_type TEXT CHECK(integral_type IN ('GAIN_KI', 'TIME_TI')),
    kp_manual REAL, kd_manual REAL, ki_inicial REAL,
    ai_engine TEXT DEFAULT 'NONE' CHECK(ai_engine IN ('NONE', 'FUZZY', 'RL')),
    ai_thread_status TEXT DEFAULT 'STOPPED',
    objetivo_controle TEXT DEFAULT 'DISTURBANCE_REJECTION',
    process_speed TEXT CHECK(process_speed IN ('SLOW', 'MEDIUM', 'FAST')),
    tempo_morto_l REAL, ai_limit_min REAL, ai_limit_max REAL
);

-- Alarmes Limites
CREATE TABLE Configuracao_Alarmes (
    controlador_id INTEGER, deadband_percent REAL,
    hihi_val REAL, hihi_prioridade TEXT, hi_val REAL, hi_prioridade TEXT,
    lo_val REAL, lo_prioridade TEXT, lolo_val REAL, lolo_prioridade TEXT,
    FOREIGN KEY(controlador_id) REFERENCES Controladores(id) ON DELETE CASCADE
);

-- Historiador de Processo (Otimizado com Índices)
CREATE TABLE Log_Processo (
    id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    controlador_id INTEGER, pv REAL, sp REAL, co REAL, integral_val REAL,
    FOREIGN KEY(controlador_id) REFERENCES Controladores(id)
);
CREATE INDEX idx_log_processo_time ON Log_Processo(timestamp, controlador_id);

-- Log de Eventos de IA (Justificativa)
CREATE TABLE Log_Sintonia_IA (
    id INTEGER PRIMARY KEY, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    controlador_id INTEGER, valor_anterior REAL, valor_novo REAL, justificativa TEXT
);

-- Auditoria e Alarmes Históricos
CREATE TABLE Log_Auditoria (id INTEGER PRIMARY KEY, timestamp DATETIME, usuario_id INTEGER, acao TEXT, valor_antigo TEXT, valor_novo TEXT);
CREATE TABLE Log_Alarmes (id INTEGER PRIMARY KEY, controlador_id INTEGER, tipo TEXT, prioridade TEXT, timestamp_in DATETIME, timestamp_out DATETIME, timestamp_ack DATETIME, usuario_ack_id INTEGER);
```

---

## **MÓDULO 7: Estatísticas de Desempenho e Ferramentas Matemáticas**

Para economizar tráfego de rede, o Backend calcula os KPIs localmente em janelas deslizantes (ex: últimos 30min) via NumPy, enviando apenas os resultados consolidados para a HMI:
* **IAE (Integral Absolute Error):** Erro total acumulado. Bom para desempenho geral.
* **MSE (Mean Squared Error) e ISE:** Penalizam grandes desvios/instabilidades.
* **ITAE:** Pune erro de regime (Offset).
* **Desvio Padrão ($\sigma$):** Dispersão da PV.
* **Variabilidade (SP e Range):** $V_{sp} = \frac{2\sigma}{SP}$ e $V_{range} = \frac{2\sigma}{Span}$.
* **TV (Total Variation):** Chattering da válvula.

---

## **MÓDULO 8: Interface de Usuário (Frontend HMI - PySide6)**

O layout é projetado para o cliente visual. O usuário inicia a HMI e se depara com uma tela de **"Conexão ao Edge Server"** (solicitando IP, Porta e credenciais).

### **8.0. Utilização de Temas**
O código da UI deve ser desenvolvido de maneira que permita a aplicação de temas:
* **Tema Dark Mode**: Tema escuro, estilo dark room.
* **Tema Material Design 3 Dark**: Baseado no padrão do Google (variante escura).
* **Tema Material Design 3 Light**: Baseado no padrão do Google (variante clara, azul marinho).
* **Tema HPC Light**: Alta Performance inspirado em Rockwell/Elipse. Cinza claro (#E0E0E0), valores dinâmicos em azul frio (#475CA7), flat 2D, touch-friendly. Ver `docs/tema_rockwell_elipse.md`.
* **Tema ISA-101**: Baseado na norma ISA-101, com tons cinza claro, cores neutras e primárias restritas apenas aos alarmes.

### **8.1. Dashboard Executivo (Landing Page)**
Visão gerencial do ROI do software, consumida via API:
* **KPIs Globais:** % em AUTO, % Cobertura da IA.
* **Bad Actors:** Ranking das piores malhas (maior IAE ou Variabilidade).
* **AI ROI:** Comparativo "Antes/Depois" da IA ligada.
* **Saúde do Backend:** CPU/RAM do servidor Edge e Uptime da rede.

### **8.2. Dashboard Operacional (Master-Detail)**
Tela dividida verticalmente (50% / 50%):
* **Grid de Cards (Topo):** Overview de todas as malhas. Barras analógicas (PV, SP, CO), badge de modo, botão de configurações (⚙) e borda colorida se em alarme. Sem sparklines — os dados de tendência ficam no gráfico Trend abaixo.
* **Gráfico Trend (Baixo-Esquerda):** Ocupa 70% da largura. Eixo Y1 (PV/SP), Y2 (CO). Marcadores visuais onde a IA atuou. 
  * O usuário deve ser capaz de escolher a **janela de tempo** digitando um número e escolhendo a unidade no dropbox (segundo, minuto, hora).
  * Checkbox para Auto-Scale.
  * Campos para definir escala manual de PV (SP usa a mesma) e CO.
  * Botão para exportar os dados atualmente plotados no gráfico em CSV.
* **Faceplate do Controlador (Baixo-Direita):** Bar graphs (PV/SP/CO). Estatísticas ($2\sigma/Range$, IAE).
* **Botões de Estado do Otimizador:** Seletor [ RUN | PAUSE | STOP ] isolado do modo Man/Auto do PID.
* **Widget Inferior Fixo:** Uma barra rodapé global mostrando os 10 últimos alarmes, independente da tela atual.

### **8.3. Painel Multi-Trend**
Grid 2x2 para instanciar até 4 controladores. Funcionalidade **Time-Sync**: Zoom ou Pan em um gráfico move os outros 3 perfeitamente na mesma faixa de tempo.

### **8.4. Painel de Alarmes, Eventos e Logs da IA**
* **Painel de Alarmes:** Aba dedicada com tabela. Filtros por PRIORIDADE, TIPO e Intervalo de tempo.
* **Caixa de Log da IA:** Caixa textual (*Terminal Style*) mostrando o raciocínio da IA (tópico `LOG.AI`) em tempo real.

### **8.5. Painel de Configurações Gerais**
* Configurar IP/Credenciais do servidor OPC-UA no Backend.
* Botões para criar/manipular projetos: Novo, Abrir, Salvar, Salvar Como.

### **8.6. Web HMI (React/Vite) — Fatia 0+1 (Foundation + Live Dashboard)**

> O cliente web React/Vite/TS substitui a HMI PySide6 (a partir de 8.6 a UI corrente é a web;
> as seções 8.0–8.5 descrevem a HMI desktop legada/congelada). A Fatia 0+1 entrega a fundação
> ponta-a-ponta e o dashboard ao vivo.

**Superfície entregue:**
* **Login JWT:** `POST /auth/login`; o token de acesso é guardado em `sessionStorage`. Rotas
  protegidas via `RequireAuth`.
* **Dashboard ao vivo:** grade de `ControllerCard` (PV/SP/CO em `AnalogBar`, badge de modo) com
  `RealtimeTrend`, alimentada pelo WebSocket `/ws/realtime`.
* **Autenticação do WebSocket:** primeira mensagem do cliente `{type:"auth", token}` validada por
  `decode_access_token`; header `Origin` validado contra allowlist; o socket fecha com código
  `4401` em token/origin ausente ou inválido (nunca `?token=` na URL).
* **Buffer por conexão (`ConnectionBuffer`):** coalescing de último-valor para `status`/`stats`;
  entrega lossless (bounded) para `alarm`/`ai`/`system`. **Construído mas a ligação ao broadcast
  ao vivo (e o fechar-no-overflow) está deferida** — ver deferrals abaixo.
* **Status OPC-UA via REST poll:** `GET /opcua/status` consultado periodicamente; conexão
  considerada online quando o estado é `ONLINE` (não trafega pelo WS).
* **Serviço single-origin da SPA:** `StaticFiles(html=True)` montado **após** os routers; security
  headers (herdados de P4); allowlist de CORS de desenvolvimento (`http://127.0.0.1:5173`). Bind em
  `127.0.0.1`.
* **Tema ISA-101** + contrato canônico de tokens (`tokens.css` + `themes.css`).

**Correções de contrato registradas (vs. spec da fatia, confirmadas nos publish sites):**
* `StatusData.timestamp` é **string ISO-8601** (não epoch). O `ts` do envelope WS permanece número
  (epoch, carimbado pela ponte com `time.time()`).
* `RealtimeType` inclui `'system'` (para `EVENT.SYSTEM`, `loop_id: null`): **6 tipos**
  (`status`, `stats`, `action`, `alarm`, `ai`, `system`).

**Deferrals conhecidos (fecham na Fatia 8):**
* Ligação ao vivo do `ConnectionBuffer` ao broadcast + fechar-no-overflow para re-sync via REST.
* Mapeamento real de unidade/range do `ControllerCard` a partir do backend
  (`pv_scale.unit` / `eu_min` / `eu_max`; não há campo de casas decimais) — instrumentado na Fatia 8.

---

## **MÓDULO 9: Sistema de Alarmes e Eventos**

A matemática do alarme roda no Backend. Quando acionado, o Backend dispara o `EVENT.ALARM` via ZeroMQ.
### **9.1. Regras e Níveis**
* **Níveis:** HIHI, HI, LO, LOLO (com configuração de Banda Morta/Histerese).
* **Prioridades Visuais:**
  * CRITICAL (Vermelho, Octógono 🛑) - Ação imediata, pisca forte, emissão de som opcional configurável.
  * WARNING (Amarelo, Triângulo ⚠️) - Pisca lento.
  * ADVISORY (Roxo, Círculo ℹ️) - Diagnóstico.
  * LOG (Cinza/Oculto) - Apenas banco de dados.

### **9.2. Persistência dos Dados de Alarme**
* **Persistência:** Máximo de 30 dias de alarmes armazenados no SQLite pelo Backend.
* **Reconhecimento (ACK):** O operador clica "ACK" na HMI, que envia um `PUT /alarms/ack` para o Backend registrar no banco.

---

## **MÓDULO 10: Segurança, RBAC e Gestão de Arquivos (.spid)**

### **10.1. Autenticação de Rede e Perfis**
As senhas ficam em Hash `bcrypt` no Backend. O Backend emite um **Token de Sessão (JWT)** para a HMI após o login, exigido em toda chamada de API:
1. **Admin:** Acesso total.
2. **Supervisor:** Otimização, limites, sintonia PID, ligar/desligar IA.
3. **Operador:** Apenas monitoramento, ACK de alarmes e operação (SP, Modo Man/Auto). Botões proibidos ficam desabilitados (*Grayed out*).
* **Audit Trail:** Toda alteração enviada gera registro de "Valor Antigo" para "Valor Novo" no Backend.

### **10.2. Ciclo de Vida do Projeto (.spid) Remoto**
Como o banco é remoto, os comandos da HMI disparam ações na API do Backend:
* **Novo:** A API cria tabelas em branco no Backend.
* **Abrir:** A API carrega as configurações na RAM do Backend e ativa o controle.
* **Salvar:** A API consolida as alterações temporárias no `.spid` atual.
* **Salvar Como:** A API clona o arquivo no PC Edge. Pode clonar tudo ou "Apenas Template" (limpando o `Log_Processo` para aplicar em outra máquina).

---

## **MÓDULO 11: Ferramenta de Exportação**
* **Global ou Individual:** Exportação em lote de toda a planta ou por malha.
* **Formatos:** CSV/XLSX ou PDF executivo.
* **Mecânica V3.0:** Executado por um *Background Worker*. A HMI faz o pedido à API, o Backend consulta os 7 dias de dados, processa e gera o PDF/CSV, e transfere o arquivo binário via HTTP para a HMI salvar no PC do usuário.

---

## **MÓDULO 12: Simulador Físico e Gêmeo Digital Integrado**

O simulador emula o comportamento dinâmico de plantas industriais para validação do motor Fuzzy/RL antes do comissionamento real. Todo o processamento matemático do Simulador ocorre no **Backend**.

### **12.1. Arquitetura do Motor de Simulação (Uso de Bibliotecas)**
A arquitetura do motor obedecerá a uma regra estrita de priorização:

**A. Modelos de Primeiros Princípios (First-Principles Models):**
O Backend usará bibliotecas validadas (como **GEKKO** para simulação dinâmica ou **TCLab** para temperatura) para criar *Presets*. Isso garante que um tanque respeite gravidade e cavitação, em vez de ser uma linha reta irreal.

**B. Presets Clássicos (Fallbacks Matemáticos):**
Para casos onde bibliotecas prontas não apliquem, o Backend usará a biblioteca `control` para funções de transferência padrão:
* **Vazão (Flow):** $G(s) = \frac{1}{0.1s + 1}$
* **Nível (Level):** $G(s) = \frac{1}{s}$
* **Pressão (Pressure):** $G(s) = \frac{1}{2s + 1}$
* **Temperatura:** $G(s) = \frac{1 e^{-10s}}{60s + 1}$

**C. Opção de Processo CUSTOM (SOPTD):**
O usuário define explicitamente a Função de Transferência informando $K$, $\tau_1$, $\tau_2$ e o Tempo Morto ($L$) - resolvido internamente via Aproximação de Pade.
$G_{custom}(s) = \frac{K}{(\tau_1 s + 1)(\tau_2 s + 1)} \cdot e^{-Ls}$

**D. Injeção de Distúrbios:**
Permite injetar *Ruído Branco* de medição ($\sigma$) ou *Degrau de Carga* (Load Disturbance) para testar a robustez da IA.

### **12.2. Integração Visual e Assets Técnicos (SVG)**
A HMI não calcula a simulação, mas fornece a imersão visual.
* **Imagens Baseadas no Processo:** A interface carrega um SVG (ex: Trocador de Calor, Tanque).
* **Dynamic Overlay:** Os valores (PV, SP, CO) transmitidos via ZeroMQ pelo Backend são renderizados "flutuando" sobre as partes corretas do desenho SVG em tempo real na HMI.
* **Edição On-The-Fly:** Alterar o Tempo Morto ($L$) na HMI atualiza o Backend em tempo real.
* Botão **"Exportar Dinâmica para a Malha"** transfere os parâmetros $L$ e *Velocidade* validados para a configuração real.

### **12.3. Namespace OPC-UA Local (Servidor do Simulador no Backend)**
O Backend instancia um Servidor OPC-UA embarcado usando `asyncua`. A árvore simula uma planta real:
* `Objects/SmartPID_Simul/Process_Flow/...` (Tags: PV, SP, CO, Mode)
* O Backend conecta-se a si mesmo em `localhost`, enganando o barramento interno. Isso permite simular 100% da cadeia de rede e arquitetura de dados antes de plugar o software no CLP real da fábrica.

---

## 13. Web HMI — Superfície de comandos & config (Fatia 2, verificada 2026-06-19)

Investigação Task 1 contra `main 427b670` (inclui P1/P2/P3/P4). Corpos e rotas reais que o
cliente web consome. **Auth:** toda rota exige `require_authenticated_admin` (modelo single-admin
P3 — NÃO `require_operator/supervisor`). Erros REST devolvem `{detail}` (→ `ApiError`).

### Comandos (`/commands`, todos POST → `CommandResponse {ok, controller_id?, detail?, enabled?}`)
- `POST /setpoint` — `SetpointCommand {controller_id, value}` (chave `value`, não `setpoint`).
- `POST /mode` — `ModeCommand {controller_id, mode: ControllerMode}` (9 modos incl. BYPASS).
- `POST /output` — `OutputCommand {controller_id, value}` (chave `value`, não `output`).
- `POST /tuning` — `TuningCommand {controller_id, kp?, ti?, td?}` (GAP-2a). kp/ti/td opcionais;
  clamp server-side por `max_tuning_change_pct`; **409** se OPC-UA desconectado. NÃO existe
  `/commands/pid/params`.
- `POST /optimization` — `OptimizationCommand {controller_id, enabled}` (GAP-2b) → resposta inclui
  `enabled`. Rótulo de UI: **"Enable AI Optimization"** (otimizador, não bloco PID). 404 se loop
  inexistente. O único `pid/enable` literal é `POST /simulator/{id}/pid/enable` — escopo simulador,
  NUNCA produção.
- `GET /tuning-recommendations/{controller_id}` — dict (sem response_model); **404 = sem
  recomendação**.
- `POST /apply-tuning/{controller_id}` — **sem corpo**; clamp server-side; devolve dict
  `{controller_id, applied_kp, applied_ti, applied_td, clamped}`. **409** se PID externo não está em
  AUTO; **404** se nenhuma recomendação pendente.

### Controles de IA (`/controllers/{id}/ai/*`)
- `POST .../ai/start | stop | pause` — **sem corpo**; fire-and-forget via ZMQ; devolve
  `{ok, controller_id, detail}` (sem response_model). Verbos **POST** (não PATCH).
- `GET .../ai/status` → `AIStatusResponse {controller_id, engine, objective, speed, current_ki,
  last_gamma?, enabled}`. **404** se não há AI worker para o loop.
- `GET .../ai/history` → `AIHistoryResponse {controller_id, entries[]}`.

### Config por loop (LoopConfigDialog)
- **PID params (Kp/Ti/Td) ao vivo:** `POST /commands/tuning` (GAP-2a, escreve no DCS via OPC-UA).
- **Limites & policy persistidos:** `PUT /controllers/{id}` (`ControllerUpdate`, todos os campos
  opcionais) → `ControllerResponse`. Inclui `sp_hi_lim/sp_lo_lim`, `out_hi_lim/out_lo_lim`,
  `arw_hi_lim/arw_lo_lim`, `max_tuning_change_pct`, `mode_normal`, `permitted_modes`.
- **Seletor de engine de IA (NONE/FUZZY/RL) — HABILITADO** (decisão do usuário 2026-06-19):
  `PUT /controllers/{id}` **aceita e persiste** `ai_config {engine, objective, dead_time_l,
  limit_min, limit_max, rl_*}` e **faz hot-reload do AI worker** (controllers.py:330-447).
  Corrige a "AI-engine persistence GAP" do contrato (premissa desatualizada — `ai_config` existe
  em `ControllerCreate` e `ControllerUpdate`). Sem rota dedicada `/ai/config`; usar o PUT.

### UI da superfície de comandos (Fatia 2 — montada no Live Dashboard, 2026-06-19)

Os controles ficam embutidos em cada `ControllerCard` do dashboard (Fatia 0+1). A `DashboardPage`
busca a lista completa de `ControllerResponse` via `GET /api/controllers` (uma única query — sem
refetch por card) e deriva tudo a partir dela.

- **`CardControls`** (slot `controls` do card): linha de Setpoint (input numérico + botão *Set*),
  seletor de **Mode** (9 `ControllerMode`, incl. BYPASS), input de **Output** habilitado só em `MAN`,
  e o toggle **"Enable AI Optimization"** (`POST /commands/optimization`). O `mode` vem **ao vivo** do
  frame `status` do WS (`useRealtime().lastStatus`); `optimizationEnabled` vem de
  `ControllerResponse.optimization_enabled`. Validação client-side (setpoint/output) antes de enviar.
- **`LoopConfigDialog`** (aberto pelo botão ⚙ do card): seções colapsáveis **PID** (Kp/Ti/Td/alpha/
  deadband + `pid_structure`), **Otimização IA** com **seletor de engine HABILITADO** (NONE/FUZZY/RL,
  objective, dead_time_L, limites de Ki e campos RL) e **Limites** (out/arw hi-lo, filtros pv/sp).
  O `initial` carrega o `ai_config` **completo** (9 campos) para round-trip sem clobber; salva via
  `PUT /controllers/{id}`.
- **`AiPanel`** (por loop): mostra engine/objective/enabled/strategy/Ki/gamma (status + frames `ai`
  ao vivo), botões **Start/Pause/Stop** (`POST .../ai/{action}`) e **Apply tuning**.
- **Guarda de apply-tuning:** "Apply tuning" só fica habilitado com recomendação `pending` e **não**
  escreve no PID até o usuário confirmar em `ConfirmApplyTuningDialog` ("Confirm Write") →
  `POST /commands/apply-tuning/{id}`. Coberto por Vitest e por e2e Playwright
  (`e2e/fatia2-commands.spec.ts`, contagem de invocações de rota).
