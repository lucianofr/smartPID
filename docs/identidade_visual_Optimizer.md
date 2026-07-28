# Identidade Visual — smartPID Optimizer

Sistema de design importado do Claude Design (projeto `smartpid-optimizer-design-system`)
e implementado como os temas `optimizer` (padrão) e `optimizer-dark` do frontend web.

Documento-fonte, commitado no repositório:
`docs/design/claude-design/smartPID-Optimizer-Dashboard.dc.html`

Ele contém três direções para a tela principal:

| id | Nome | Tratamento |
|---|---|---|
| 1a | Painel Executivo | claro, cards brancos sobre chrome frio — implementado como `optimizer` |
| 1b | Comando IA | escuro, alto contraste, âmbar em destaque — implementado como `optimizer-dark` |
| 1c | Sala de Controle Inteligente | compacto, IA em primeiro plano, KPIs como pílulas no header |

A composição implementada segue **1a**; `optimizer-dark` reaproveita a mesma
geometria com a paleta de **1b**. De 1c foram absorvidos apenas elementos que não
conflitam com a composição de 1a (as métricas laterais do painel de tendência).

---

## 1. Paleta

### Primitivas herdadas do documento de design

**Chrome ramp** — o azul-cinza industrial que carrega ~95% da superfície:

| Token | Hex | Uso |
|---|---|---|
| `--chrome-0` | `#F0F4F7` | inset: input, trilho de barra, poço do gráfico, workspace |
| `--chrome-1` | `#D6DEE6` | superfície elevada |
| `--chrome-6` | `#9BAAB8` | borda padrão |
| `--chrome-7` | `#7A8B99` | borda forte, anel de foco sobre cinza |
| `--chrome-8` | `#5A6B7A` | rótulo apagado, legenda de seção |

**Tinta** — `--ink #3F3F3F` (texto primário e traço CO), `--ink-soft #5C5C5C`,
`--ink-dim #8B9AA7`.

**Azul de seleção** — o único acento interativo: `--select #2B6BAE`,
hover `#357BC4`, press `#21578F`.

**Marca LFR Automação** — navy e âmbar. Usados em superfícies de marca (wordmark,
banda de KPI, call-to-action de IA), **nunca** para indicação de processo:
`--navy-darker #060D1A`, `--navy-deep #0D1F38`, `--navy #1E3A5F`,
`--amber #FF8C42`, `--amber-hover #E67E3A`, `--amber-soft #FFB380`.

**Status ISA-101** — `--status-ok #2F7D4F`, `--status-warn #D8A72E`,
`--status-alarm #C53030`, `--state-ai #4A148C` (FUZZY/RL), `--live #00C853`.

### Três desvios deliberados do documento

O mock usa três cores decorativamente; o produto usa as mesmas cores para carregar
significado, e significado precisa sobreviver a uma auditoria WCAG
(`src/theme/themeContrast.test.ts`, piso 4.5:1 texto / 3.0:1 nao-texto).
Em todos os casos o matiz foi preservado; só a luminosidade se moveu.

| Token | Documento | Implementado | Motivo |
|---|---|---|---|
| `--alarm-warn` | `#D8A72E` | `#8A691A` | 1.94:1 sobre branco; piso é 4.5 |
| `--trace-sp` | `#A0A4A9` | `#7C8189` | 2.27:1 sobre o poço do gráfico; piso é 3.0 |
| `--live` | `#00C853` | `#0E9F53` (só tema claro) | idem; o tema escuro mantém `#00C853` |

Os dois temas passam integralmente o gate de contraste — 65 asserções por tema.

---

## 2. Tipografia

Regra da casa: **todo número que o processo produz é monoespaçado.** Rótulos são
UI sans; títulos de marca são display sans.

| Papel | Família | Pesos | Token |
|---|---|---|---|
| display | Poppins | 600, 700 | `--font-display` |
| UI | Inter Variable | 400–700 | `--font-ui` |
| dados | IBM Plex Mono | 400, 600, 700 | `--font-data` |

Neon mantém Orbitron como face display (§10.6) — é a única paleta cuja identidade
está na letra, não no chrome.

### Escala HMI

Densa de propósito: uma sala de controle lê isto a um metro. A escada é fixa, não
fluida — reflowar numerais entre breakpoints é como um readout começa a parecer
não confiável.

| Token | px | Uso |
|---|---|---|
| `--text-2xs` | 10 | legendas de seção, unidades, meta |
| `--text-xs` | 11 | chips de estado, pílulas de prioridade |
| `--text-sm` | 12 | rótulos de campo, legenda do gráfico |
| `--text-base` | 13 | rótulos de controle, células de tabela, botões |
| `--text-md` | 15 | tag da malha (`FIC-001`) |
| `--text-lg` | 17 | readouts de barra, valores do card |
| `--text-xl` | 19.2 | título do app, títulos de painel |
| `--text-2xl` | 24 | figuras da banda de KPI |
| `--text-3xl` | 30 | PV primário do faceplate |

Tracking: `--tracking-tight -0.02em` (wordmark), `--tracking-wide 0.06em` (chips),
`--tracking-caps 0.1em` (legendas em caixa alta).

---

## 3. Geometria

O chrome de instrumento anterior era quadrado em cada canto. O sistema Optimizer
arredonda:

| Token | Valor | Uso |
|---|---|---|
| `--radius-card` | 10px | cards, painéis, diálogos |
| `--radius-control` | 6px | botões, campos, segmentos |
| `--radius-well` | 8px | poço do gráfico |
| `--radius-pill` | 999px | chips, dots, trilhos de barra |

Elevação — dois passos, e só o card selecionado sobe:

| Token | `optimizer` | `optimizer-dark` |
|---|---|---|
| `--shadow-card` | `0 1px 3px rgba(13,31,56,.07)` | `0 1px 3px rgba(0,0,0,.3)` |
| `--shadow-lifted` | `0 10px 24px rgba(43,107,174,.28)` | anel âmbar + `0 10px 26px rgba(255,140,66,.22)` |

As quatro paletas legadas (recorder, phosphor, isa101, neon) respondem ambos os
tokens com `0 0 #0000` e permanecem planas.

---

## 4. Composição da tela principal

```
+- header 64px ----------------------------------------------------+
| [STEP] smartPID Optimizer | nav |    * OPC-UA conectado | LR | eng|
+- banda de KPI (gradiente navy) ----------------------------------+
| [i] 8 malhas | [i] 6 com IA | [i] -34% variab. | [i] R$ 186 mil  |
+------------------------------------------------------------------+
| +- faceplate 320px -+ | Malhas PID                                |
| | FIC-001           | | +206px++206px++206px++206px+  ->scroll    |
| | PV #####...  37.1 | | +-----++-----++-----++-----+             |
| | SP ####....  37.1 | +-------------------------------------------+
| | CO ###.....  30.9 | | Tendencia - FIC-001    PV - SP : CO -     |
| | [AUTO][ MAN ]     | | +---------------------------------------+ |
| | [ RUN][STOP ]     | | |  poco chrome-0, area PV em gradiente  | |
| | Kp    Ti    Td    | | +---------------------------------------+ |
| | ,- IA sugere --.  | |                                           |
| | | Aplicar >    |  | |                                           |
| | '--------------'  | |                                           |
| | IAE Var/SP TV     | |                                           |
| +-------------------+ |                                           |
+------------------------------------------------------------------+
```

### Header
Wordmark `smart` + **`PID` em âmbar** + ` Optimizer`, precedido do ícone STEP —
uma curva de resposta ao degrau assentando, em âmbar. Nav ativa marcada por
sublinhado âmbar de 2px, não por preenchimento. Dot de link + nome do usuário
com avatar de iniciais à direita.

### Banda de KPI
Quatro células iguais sobre `--kpi-band` (gradiente 120° de `--brand-ink-deep`
para `--brand-ink`). Cada uma: tile de ícone 38px com tinta âmbar a 15%, figura
em display 700 e legenda em caixa alta com `--tracking-caps`.

### Card de malha (206px)
Barra de status de 3px no topo colorida pelo modo (AUTO verde / MAN âmbar); dot de
alarme no canto quando a qualidade fieldbus não é normal; tag em mono 700; três
mini-barras PV/SP/CO de 6px; dois chips — modo e estratégia (FUZZY/RL em roxo
`--state-ai`, NONE como travessão). Selecionado: borda `--accent` e
`--shadow-lifted`. Hover: `translateY(-2px)`.

### Faceplate (320px)
PV com trilho de 14px e readout de 30px; SP/CO com trilho de 10px e readout de
17px. Segmentados AUTO/MAN e RUN/STOP com estados preenchidos. Caixa de IA em
tinta âmbar com CTA `--brand-accent` e log de sintonia. Grade de 4 métricas
(IAE, Var/SP, Var/Range, TV).

> **Desvio:** o mock usa 372px de largura; a implementação usa 320px porque
> `e2e/responsive.spec.ts` fixa o trilho em 320+-8 desde a fase 9.

### Painel de tendência
Card branco com legenda inline mostrando o valor vivo de cada série em mono.
Poço `--surface-sunk` com raio 8px. PV sólido 2px com área em gradiente, SP
tracejado `6 4`, CO sólido 1.5px.

---

## 5. Contrato de tokens

60 tokens, declarados por **todos** os seis temas (58 por bloco `[data-theme]`;
`--font-ui` e `--font-data` ficam em `:root`). Definido em
`packages/smart_pid_web/src/theme/contract.ts`, verificado por
`tokenResolve.test.ts` e `isa101Mapping.test.ts`.

Camadas: superfícies, linhas, texto, foco/seleção, acento, **marca**, alarme,
estado, **IA/live**, tendência, barra, glow, **elevação**, tipo.

Componentes consomem **apenas** esses nomes — `src/__tests__/token-guard.test.ts`
falha o build ao encontrar qualquer `#rrggbb`, `rgb()`, `hsl()`, `oklch()`,
utilitário `[#...]` ou classe de paleta nomeada em qualquer `.ts`/`.tsx` sob `src/`.

---

## 6. Temas

| id | Rótulo | Natureza |
|---|---|---|
| `optimizer` | Optimizer | **padrão** — direção 1a, claro, marca LFR |
| `optimizer-dark` | Optimizer Dark | direção 1b, navy, âmbar promovido a acento interativo |
| `recorder` | Recorder | skin de instrumento — registrador de papel (§6.5, normativo) |
| `phosphor` | Phosphor | skin de instrumento — CRT (§6.6, normativo) |
| `isa101` | ISA-101 | skin conforme ISA-101 (fase 11, auditado) |
| `neon` | Neon | skin de alto contraste (§10) |

As quatro paletas legadas são skins de cor, não sistemas de tipo: todas adotaram
a escala e as famílias novas, e respondem a camada de marca com o próprio acento
em vez de navy/âmbar.
