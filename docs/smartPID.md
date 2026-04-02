# **Especificação Técnica: Smart PID Edge Optimizer (V2.4 Definitiva)**

## **MÓDULO 1: Visão Geral e Escopo**
O **Smart PID Edge Optimizer** é um aplicativo desktop industrial focado em otimização de malhas de controle PID. Ele utiliza Inteligência Artificial (Fuzzy ou Aprendizado por Reforço - RL) para ajustar dinamicamente o parâmetro Integral ($K_i$ ou $T_i$), visando estabilidade e eliminação de erro de regime em processos de diferentes dinâmicas.

A ferramenta funciona tanto como um Otimizador de Borda (Edge Optimizer) acoplado a CLPs existentes, quanto como um Historiador e Ferramenta Analítica de Desempenho de Malhas.

### **1.1. Stack Tecnológico Recomendado**
* **Linguagem:** Python 3.10+.
* **UI/Interface Gráfica:** PySide6 (Qt for Python). O padrão industrial que oferece widgets nativos e alta performance.
* **Gráficos em Tempo Real:** `pyqtgraph`. Muito mais rápido que o Matplotlib (essencial para renderizar a 30~60 FPS sem travar a UI).
* **Comunicação:** `asyncua`. A biblioteca Python mais moderna para OPC UA, suportando operações assíncronas vitais para não travar a interface.
* **Barramento de Mensageria:** `pyzmq` (ZeroMQ).
* **IA e Matemática:** `stable-baselines3` (RL), `scikit-fuzzy`, `numpy`, `scipy.signal` e `control`.
* **Banco de Dados:** `sqlite3`.

---

## **MÓDULO 2: Arquitetura de Software e Multitarefa**

No ambiente industrial, a lógica de controle **nunca** deve rodar na mesma thread da interface gráfica. O sistema adota um padrão de arquitetura desacoplada utilizando um **Barramento de Dados Interno (Internal Message Bus)** baseado em **ZeroMQ**.

### **2.1. O Barramento ZeroMQ (PUB/SUB)**
Roteado via protocolo `inproc://` (In-Process) na memória RAM. Garante latência sub-milissegundos. Nenhuma thread se comunica diretamente com hardware ou com outras threads; tudo flui pelo barramento.
* **Tópico `TELEMETRY.{ID}`:** Publicado pela Thread OPC-UA (ex: `{"pv": 100.5, "sp": 100.0, "co": 45.2, "int_val": 1.2}`). Assinado pela UI, DB e Lógica.
* **Tópico `ACTION.CTRL.{ID}`:** Publicado pela Thread de Lógica. Assinado pela Thread OPC-UA para escrita no CLP.
* **Tópico `EVENT.ALARM.{ID}` e `ALARM.RECENT`:** Publicado pelo Motor de Alarmes. Assinado pela UI e DB.
* **Tópico `LOG.AI.{ID}`:** Explicação passo a passo ("Justificativa") das decisões da IA.
* **Tópico `SYS.STATE`:** Status do sistema (ex: Reconectando).

### **2.2. O Modelo de Threads (Atores)**
Para garantir o determinismo absoluto da malha regulatória, o sistema adota o padrão **Dual-Thread por Malha** somado às threads de infraestrutura:

1. **Thread de I/O (Comunicação Assíncrona):** Única responsável pela rede. Conecta ao OPC-UA, publica `TELEMETRY` e assina `ACTION.CTRL` para escrever no CLP. Se a rede falhar, apenas ela congela.
2. **Thread de Controle Regulatório (The PID Worker):** Altíssima prioridade. Executa estritamente a matemática do PID no *Scan Rate* definido (ex: 100ms). Sobrevive mesmo se a IA falhar.
3. **Thread de Otimização (The AI Worker):** Prioridade baixa/média. Executa a inferência Fuzzy ou RL. Avalia a telemetria, calcula o novo ganho integral ($T_i$) e publica no barramento.
4. **Thread de Banco de Dados (Logger):** Acumula dados em RAM e faz *Batch Inserts* (inserções em lote) no SQLite.
5. **Thread GUI (Main):** Consome dados do barramento (`TELEMETRY.*`) e desenha os gráficos. Interface 100% livre de travamentos.

---

## **MÓDULO 3: O Núcleo de Controle PID e Topologias**

### **3.1. Modos de Execução da Malha**
* **Modo Supervisório (Externo):** O controle PID reside no PLC. O App monitora PV, SP e CO via OPC-UA e escreve *apenas* o ajuste do parâmetro integral no PLC.
* **Modo DDC (Direct Digital Control / Interno):** O App executa a equação PID completa. Lê PV, calcula CO e escreve o valor no atuador via OPC-UA.
* **Scan Rate**: deverá ser possível escolher um SCAN RATE para cada controlador adicionado e configurado no sistema.

Os detalhes de implantação do algoritmo PID no modo DDC estão no arquivo `./bloco_wpid.md`

---

## **MÓDULO 4: Inteligência Artificial e Self-Tuning Autônomo**

O sistema opera de forma autônoma (*Zero-Touch*), não exigindo que o usuário programe regras lógicas. Cada malha pode escolher entre 3 estratégias de otimização: **NONE, FUZZY ou RL (Reinforcement Learning)**. 

### **4.1. Objetivos de Controle (O Comportamento Desejado)**
A sintonia do motor de IA muda radicalmente de acordo com o "Objetivo de Controle" selecionado pelo usuário na configuração da malha:
1. **Seguimento de Setpoint (SP Tracking):** Foco em alcançar o alvo rápido, mas freando agressivamente para não ultrapassar (Overshoot nulo). A IA penaliza velocidade excessiva de aproximação.
2. **Rejeição de Distúrbios (Regulatory):** O SP é fixo. Foco em "matar" o erro de regime (Offset) o mais rápido possível quando uma força externa afasta a PV do alvo. A IA é mais agressiva perto do erro zero.
3. **Controle de Nível Pulmão (Surge Level):** A PV (Nível) deve flutuar livremente para não perturbar a válvula. A IA cria uma "banda morta virtual" e só atua quando a PV atinge os extremos perigosos, ignorando pequenos erros ao redor do SP.

---

### **4.2. Estrutura do Motor de Inferência Fuzzy**
Se a malha operar no modo **FUZZY**, o aplicativo instancia um motor pré-configurado via `scikit-fuzzy`. A inferência segue os seguintes passos estritos:

**A. Fuzzificação (Entradas e Conjuntos):**
As duas variáveis de entrada são o **Erro** ($E = SP - PV$) e a **Variação do Erro** ($\Delta E$).
* Para universalizar a IA (não importando se a malha mede 0-100°C ou 0-5000 PSI), as entradas são **Normalizadas** para a faixa de **-100% a +100%** do Fundo de Escala (Span/Range) do instrumento.
* Os Conjuntos Fuzzy (Membership Functions) adotam 7 níveis, utilizando funções Triangulares no centro e Trapezoidais nos extremos, com **50% de sobreposição (overlap)** garantindo transições suaves:
  * **NB** (Negative Big / Negativo Grande)
  * **NM** (Negative Medium / Negativo Médio)
  * **NS** (Negative Small / Negativo Pequeno)
  * **ZO** (Zero)
  * **PS** (Positive Small / Positivo Pequeno)
  * **PM** (Positive Medium / Positivo Médio)
  * **PB** (Positive Big / Positivo Grande)

**B. Matrizes de Regras Lógicas (Base de Conhecimento):**
O motor carrega dinamicamente uma das 3 matrizes baseadas no Objetivo de Controle (Seção 4.1). As células determinam a Saída Linguística para o ajuste integral:

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
  *(Lógica: O centro inteiro é ZO (Zero Action). O controlador permite que o Nível oscile na zona segura e só reage violentamente (PB/NB) se o tanque ameaçar secar ou transbordar).*
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
O motor processa as regras ativadas e utiliza o método de **Centro de Gravidade (Centroid - CoG)** para converter o polígono resultante em um valor escalar contínuo (*Crisp Value*) chamado **$\gamma$** (Gama). 
O valor $\gamma$ varia estritamente de **-1.0** (Redução Máxima de Ganho) a **+1.0** (Aumento Máximo de Ganho).

---

### **4.3. Cadência, Tempo Morto ($L$) e Adaptação de Velocidade ($S_v$)**
A saída matemática do motor Fuzzy ($\gamma$) não é injetada diretamente no controlador de forma arbitrária. Ela passa pelo "Filtro de Física do Processo" definido pelo usuário:

**1. Fator de Velocidade (Scaling Factor - $S_v$):**
Define a agressividade por ciclo.
* Processos Rápidos (Ex: Vazão): $S_v = 0.05$ (Paciência. Ajustes microscópicos de 5%).
* Processos Médios (Ex: Pressão): $S_v = 0.15$ (Ajustes de 15%).
* Processos Lentos (Ex: Temperatura): $S_v = 0.30$ (Correções agressivas de 30% para vencer a inércia térmica).

**2. Equação de Atualização do Ganho Integral ($K_i$):**
O cálculo realizado pela Thread de Otimização será:
$$K_{i(novo)} = K_{i(atual)} \cdot (1 + (\gamma \cdot S_v))$$
*(Nota: Se a topologia exigir $T_i$ em Segundos/Repetição, a matemática é inversamente tratada, pois aumentar $T_i$ diminui a força integral).*

**3. Cadência de Execução baseada em Tempo Morto ($T_{ciclo}$):**
Para evitar correções encavaladas ("hunting"), a IA não roda a cada milissegundo. Ela aguarda a resposta do processo baseada no Tempo Morto estimado ($L$) informado pelo usuário:
$$T_{ciclo} = L \times 3$$
*(Exemplo: Se o Tempo Morto da caldeira é de 10s, a Thread de IA avalia a Matriz Fuzzy, ajusta o PID, e adormece por exatos 30s antes de atuar novamente).*

---

### **4.4. Motor de Aprendizado por Reforço (RL)**
Caso o usuário selecione a IA do tipo RL (Agente Autônomo com `stable-baselines3` - SAC/PPO):
* O agente usa **Online Learning** contínuo.
* **Funções de Recompensa (Reward Functions)** atreladas ao Objetivo (Seção 4.1):
  * *SP Tracking/Rejection:* Recompensa positiva pela minimização de IAE (Erro) / ITAE, punindo severamente oscilações (Total Variation - TV).
  * *Surge Level:* Recompensa positiva por manter a Válvula (CO) parada. Só pune o Erro (IAE) se a PV sair da banda morta configurada.
* Sujeito aos mesmos Guardrails (limites de $T_i$ Min/Max) e à mesma cadência ($T_{ciclo}$) da lógica Fuzzy.

### **4.5. Explicabilidade da IA (Log de Raciocínio)**
Sistemas industriais exigem confiança ("Caixas-Pretas" não são bem-vindas). 
A cada vez que a IA roda o ciclo e altera um parâmetro, a Thread publica uma mensagem no barramento interno justificando a matemática de forma simplificada:
* *Fuzzy Exemplo:* "Aumentando Ti em 5% - Erro estável (ZO), mas Derivada aponta distúrbio rápido (NB)."
* *RL Exemplo:* "Aumentando Ti em 2% - Offset detectado; Recompensa atual negativa devido ao IAE alto."
Estas mensagens são exibidas em tempo real numa caixa terminal na interface e gravadas na tabela `Log_Sintonia_IA`.

---

## **MÓDULO 5: Comunicação OPC-UA e Mapeamento**

### **5.1. Máquina de Estados da Conexão (Resiliência)**
* **OFFLINE:** Desconectado intencionalmente. IA e barramento pausam.
* **ONLINE:** Transmitindo dados.
* **RECONNECTING:** Queda de rede. O app tenta reconectar no background sem travar a interface. Ao voltar, executa o *Bumpless Transfer* lendo os valores atuais do CLP.

### **5.2. Mapeamento de Tags (Tag Binding Table) e Browser**
Este mapeamento deverá ser realizado para cada controlador adicionado ao sistema. Adicionar um icóne de configurações onde irá abrir as configurações do controlador, entre elas deverá estar a tabela de mapeamento de tags. 

* Tabela relacionando variáveis internas (PV, SP, CO, Ti e etc...) aos *NodeIDs* do OPC-UA (ex: `ns=4;s=MAIN.PV`).
* **Navegador Modal OPC-UA:** Ferramenta visual estilo *Tree View* para navegar nas pastas do CLP e selecionar tags via duplo clique, com barra de pesquisa integrada.


---

## **MÓDULO 6: Gerenciamento de Dados, Historiador e SQLite**

Os dados são armazenados em arquivos locais `.spid` (que são bancos SQLite). Operam em modo `PRAGMA journal_mode=WAL;` para suportar leitura e escrita simultâneas entre threads.

### **6.1. Hibridez e Performance**
* **RAM (Curto Prazo):** Buffer da IA usando `collections.deque` (janela móvel rápida).
* **Lotes (Batch Inserts):** Acumula dados em memória e grava no banco a cada 5~10 segundos.
* **Limpeza Automática:** Retenção histórica estrita de **7 dias**. Query: `DELETE FROM Log_Processo WHERE timestamp <= datetime('now', '-7 days');`

### **6.2. Schema Unificado de Tabelas (DDL Final)**
```sql
-- Usuarios e RBAC
CREATE TABLE Usuarios (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password_hash TEXT, role TEXT);

-- Controladores (Incluindo configurações de IA e Simulador)
CREATE TABLE Controladores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT UNIQUE NOT NULL,
    descricao TEXT,
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
    tempo_morto_l REAL,
    ai_limit_min REAL, ai_limit_max REAL
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

O software calcula KPIs em janelas deslizantes (ex: últimos 30min) via NumPy. Usados pela interface e como Recompensa para o motor RL:
* **IAE (Integral Absolute Error):** Erro total acumulado. Bom para desempenho geral.
* **MSE (Mean Squared Error) e ISE:** Penalizam grandes desvios/instabilidades severas.
* **ITAE:** Pune erro de regime (Offset). Ideal para Fornos/Processos lentos.
* **Desvio Padrão ($\sigma$):** Dispersão da PV em torno da média.
* **Variabilidade (SP e Range):** $V_{sp} = \frac{2\sigma}{SP}$ e $V_{range} = \frac{2\sigma}{Span}$.
* **TV (Total Variation):** Chattering da válvula.
* **Índice de Saturação:** Tempo em que a CO esteve travada em 0% ou 100%.

---

## **MÓDULO 8: Interface de Usuário (UI/UX)**

O layout segue o Padrão Industrial HMI (*Dark Mode*, *Master-Detail*, cores restritas para alarmes).

### 8.0. Utilização de temas
O código da UI deve ser desenvolvido de maneira tal que seja possível a aplicação de temas. Crie três temas principais inicialmente:
* **Tema Dark Mode**X: Tema escuro, estilo dark room.
* **Tema Material Design 3**X: Tema baseado no padrão Material Design do Google.
* **Tema ISA-101**X: Tema baseado na norma ISA-101, com tons cinza escuros, cores suaves para as variáveis de processo e cores primárias apenas para os alarmes.

### **8.1. Dashboard Executivo (Landing Page)**
Visão gerencial do ROI do software.
* **KPIs Globais:** % em Modo Automático, % Cobertura da IA.
* **Bad Actors:** Ranking das 5 piores malhas (maior IAE ou Variabilidade).
* **AI ROI:** Comparativo "Antes e Depois" da IA ligada.
* **Saúde:** CPU/RAM do servidor Edge e Uptime do OPC-UA.

### **8.2. Dashboard Operacional (Master-Detail)**
Tela dividida verticalmente (50% / 50%):
* **Grid de Cards (Topo):** Overview de todas as malhas. Contém Sparklines, Valores e Borda Colorida se em alarme. Clicar altera o contexto inferior.
* **Gráfico Trend (Baixo-Esquerda):** Gráfico de alta resolução (70% da largura). Eixo Y1 (PV/SP), Y2 (CO). Marcadores visuais onde a IA atuou. O usuário deve ser capaz de escolher a janela de tempo que ele quer visualizar, coloque uma caixa de texto pwara o usuário entrar com um número que terá como unidade o que for escolhido no dropbox com as escolhas (segundo, minuto e hora), esta será a janela de tempo. 
- Checkbox para auto scale
- campos para definir escala de PV (SP usa a mesma escala) e CO. 
- Botão para exportar em CSV os dados mostrados no gráfico.
* **Faceplate do Controlador (Baixo-Direita):** Bar graphs (PV/SP/CO). Entradas numéricas. Estatísticas ($2\sigma/Range$, IAE).
* **Botões de Estado do Otimizador:** Seletor [ RUN | PAUSE | STOP ] isolado do modo Man/Auto do PID.
* **Widget Inferior Fixo:** Uma barra/lista rodapé global mostrando os 10 últimos alarmes, idependente da tela atual.

### **8.3. Painel Multi-Trend**
Grid 2x2. Até 4 controladores instanciados simulaneamentes. Funcionalidade **Time-Sync**: Zoom ou Pan em um gráfico move os outros 3 perfeitamente na mesma faixa de tempo.

### **8.3. Painel de Alarmes e Eventos**
* **Painel de Alarmes:** Aba dedicada com tabela completa. Filtros para filtrar a PRIORIDAE, TIPO DE ALARME e intervalo de tempo a ser mostrado.

### **8.4. Caixa de Log da IA**
Caixa textual (*Terminal Style*) na visão de detalhes, rolando as justificativas da IA e do motor de inferência Fuzzy em tempo real.

### **8.5. Painel de configurações gerais**
- Configurar servidor OPC-UA a ser conectado
- Adiconar os botões para criar manipular o projeto: criar novo, abrir, salvar e salvar como. 

---

## **MÓDULO 9: Sistema de Alarmes e Eventos**

### **9.1. Regras e Níveis**
* **Níveis:** HIHI, HI, LO, LOLO. Possuem configuração de Banda Morta (Histerese) para evitar chattering.
* **Prioridades Visuais:**
  * CRITICAL (Vermelho, Octógono 🛑) - Ação imediata, pisca forte, emissão de som opcional. Definido em configurações do sistema. 
  * WARNING (Amarelo, Triângulo ⚠️) - Pisca lento.
  * ADVISORY (Roxo, Círculo ℹ️) - Diagnóstico.
  * LOG (Cinza/Oculto) - Apenas registro de banco.

### **9.2. Persistencia dos dados de alarme**

* **Persistência:** máximo de 30 dias de alarmes. Após isso os dados mais antigos são descartados. 

---

## **MÓDULO 10: Segurança, RBAC e Gestão de Arquivos (.spid)**

### **10.1. Autenticação e Perfis**
As senhas ficam em Hash `bcrypt`. O acesso é bloqueado até login.
1. **Admin:** Acesso total, configs OPC-UA e criação de malhas/usuários.
2. **Supervisor:** Otimização, limites, sintonia PID, ligar/desligar a IA.
3. **Operador:** Apenas monitoramento, ACK de alarmes e operação (SP, Modo Man/Auto). Interface desabilita visualmente botões proibidos (*Grayed out*).
* **Audit Trail (CFR 21 Part 11):** Toda alteração feita por usuários gera registro rastreável de "Valor Antigo" para "Valor Novo".

### **10.2. Ciclo de Vida do Projeto (.spid)**
A extensão `.spid` (banco SQLite) é associada ao App.
* **Novo:** Cria tabelas em branco.
* **Abrir:** Desliga threads atuais, salva dados RAM pendentes, conecta novo banco e reconecta OPC-UA.
* **Salvar:** Salva todas as modificações que foram feitas no projeto. Salva seu estado atual no arquivo corrente. Se não existir o salvar como é chamado.
* **Salvar Como:** Opção de clonar todo o histórico ou "Apenas Template" (limpando o Log_Processo para usar em outra máquina idêntica).

---

## **MÓDULO 11: Ferramenta de Exportação**
* **Global ou Individual:** Exportação em lote de toda a planta ou por malha.
* **Formatos:** CSV/XLSX (para engenharia) ou PDF executivo (Relatório formatado contendo gráficos, estatísticas IAE/MSE e Log da IA cruzado com o gráfico).
* Executado em *Background Worker* para não travar a aplicação durante a consulta aos 7 dias de logs.

---

Você tem toda a razão. A especificação original focou puramente na matemática de Funções de Transferência genéricas (via biblioteca `control`) e omitiu a diretriz arquitetural de usar bibliotecas de simulação de processos orientadas a objetos/física, o que traria muito mais realismo e pouparia tempo de desenvolvimento.

Abaixo está o **MÓDULO 12 reescrito e expandido**, incorporando a regra de priorização de bibliotecas de simulação com modelos pré-construídos, mantendo a opção CUSTOM para controle total do usuário e todos os demais detalhes visuais e de rede.

Pode substituir o Módulo 12 anterior por este:

---

## **MÓDULO 12: Simulador Físico e Gêmeo Digital Integrado**

O sistema integrará um simulador capaz de emular o comportamento dinâmico de plantas industriais. O simulador será utilizado tanto para o modo "Demo/Training" quanto para a validação das estratégias de controle (Fuzzy/RL) e sintonia em malha fechada antes do comissionamento real.

### **12.1. Arquitetura do Motor de Simulação (Uso de Bibliotecas)**
Para garantir a máxima fidelidade física (termodinâmica e fluidodinâmica) e evitar "reinventar a roda", a arquitetura do motor de simulação obedecerá a uma regra estrita de priorização de bibliotecas:

**A. Uso de Bibliotecas de Processos Pré-Construídas (First-Principles Models):**
Se existir no ecossistema Python bibliotecas ativas e validadas que já implementem modelos de processos industriais comuns (ex: pacotes baseados em **GEKKO** para simulação dinâmica, modelos acadêmicos consolidados como o **TCLab** para temperatura, ou bibliotecas de *Digital Twins* baseadas em equações de estado), **estas bibliotecas devem ser usadas nativamente** para criar os *Presets* do simulador. 
Isso garante que um modelo de "Tanque" respeite naturalmente a gravidade, cavitação e área da base, e não seja apenas uma linha reta matemática.

**B. Presets Clássicos (Fallbacks Matemáticos):**
Caso modelos pré-construídos de terceiros não cubram a necessidade, o simulador deve embarcar modelos matemáticos clássicos (usando a biblioteca `control` e `scipy.signal`) emulando comportamentos padrão:
* **Vazão (Flow):** Resposta quase instantânea. $G(s) = \frac{1}{0.1s + 1}$
* **Nível (Level):** Integrador puro, a PV não estabiliza sem controle. $G(s) = \frac{1}{s}$
* **Pressão (Pressure):** Estabilidade rápida com inércia moderada. $G(s) = \frac{1}{2s + 1}$
* **Temperatura (Temperature):** Grande atraso de transporte. $G(s) = \frac{1 e^{-10s}}{60s + 1}$

**C. Opção de Processo CUSTOM (SOPTD - Second Order Plus Time Dead):**
Independente das bibliotecas prontas acima, o sistema **deve obrigatoriamente fornecer uma opção CUSTOM** onde o usuário não depende de físicas embutidas, mas sim da matemática pura. O usuário define explicitamente a Função de Transferência do processo preenchendo os parâmetros:
* **Ganho do Processo ($K$)**
* **Constante de Tempo Principal ($\tau_1$)**
* **Constante de Tempo Secundária ($\tau_2$)**
* **Tempo Morto ($L$)** - Resolvido no código via Aproximação de Pade para garantir o atraso real no gráfico.
* Equação: $G_{custom}(s) = \frac{K}{(\tau_1 s + 1)(\tau_2 s + 1)} \cdot e^{-Ls}$

**D. Injeção de Distúrbios Físicos e de Medição:**
Para testar a robustez do *Smart Tuning*, o simulador deve permitir:
* **Ruído Branco de Medição:** O usuário liga um botão e define um desvio padrão ($\sigma$) que é somado à PV simulada, testando se a IA consegue diferenciar oscilação de ruído.
* **Degrau de Carga (Load Disturbance):** Simulação de uma válvula externa abrindo de repente, forçando a PV a cair para ver a IA e o PID reagirem.

---

### **12.2. Integração Visual e Assets Técnicos (SVG)**
O painel do simulador não será apenas um bloco de números; ele terá um *HMI* próprio para imersão do usuário.

* **Imagens Baseadas no Processo:** Ao selecionar um Preset (ex: Temperatura) ou o CUSTOM, a interface carrega um diagrama vetorial **SVG** correspondente (ex: um Trocador de Calor, ou um Diagrama de Blocos de Controle).
* **Dynamic Overlay (Sobreposição de Dados):** Os valores calculados pela biblioteca de simulação (PV, SP e CO) são renderizados "flutuando" sobre as partes corretas do desenho SVG em tempo real (ex: O valor numérico da CO fica sobre o desenho da válvula, a PV fica sobre o desenho do transmissor).
* **Edição On-The-Fly:** O usuário pode alterar o Tempo Morto ($L$) ou injetar um distúrbio com a simulação rodando. O motor recalculada instantaneamente a dinâmica, refletindo nos gráficos.
* Um botão **"Exportar Dinâmica para a Malha"** permite transferir os parâmetros $L$ e a *Velocidade* validados durante a simulação diretamente para a configuração real da IA no banco de dados.

---

### **12.3. Namespace OPC-UA Local (O Servidor do Simulador)**
Para a Thread de IA e o barramento do sistema não perceberem a diferença entre o simulador local e um CLP Siemens/Rockwell em campo, o Simulador instanciará um Servidor OPC-UA embarcado usando `asyncua`.

A árvore OPC-UA local simulada refletirá a estrutura padrão orientada a objetos:
* `Objects/SmartPID_Simul/Process_Flow/...`
* `Objects/SmartPID_Simul/Process_Level/...`
* `Objects/SmartPID_Simul/Process_Custom/...`

Dentro da pasta do processo selecionado, as tags estarão vivas e operantes:
* 🔹 `PV` (Float - Read Only, escrita gerada pelo Simulador)
* 🔹 `SP` (Float - Read/Write)
* 🔹 `CO` (Float - Read/Write)
* 🔹 `Mode` (Int - Man/Auto)
* 🔹 Pasta oculta `Advanced_Stats` com tags de diagnóstico como `IAE_Current` e `AI_Status`.

Dessa forma, o aplicativo conecta nesse servidor em `localhost`, simulando 100% da cadeia de rede e arquitetura de dados antes do software ser acoplado à rede industrial real.
