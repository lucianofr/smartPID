# Design System — Web HMI (React/Vite) · Smart PID Edge Platform v2

**Documento:** Frontend Design System / Spec (additive — não altera as 8 specs de fatia)
**Data:** 2026-06-18
**Autor:** UI Designer (frontend-design) — para LFR Automação
**Status:** Implementado (refactor Tailwind+shadcn — branch `refactor/web-tailwind-shadcn-isa101`, Fase 9 concluída)
**Pré-requisitos lidos:** umbrella `web-hmi-react-migration-design.md`, fatias 01–08, `identidade_visual_Dark.md`, `identidade_visual_ISA101.md`, `identidade_visual_MD3.md`.

> Este documento é a **camada visual** que falta às 8 specs de fatia. As fatias dizem *o que*
> construir (endpoints REST, contrato WS, aceitação). Aqui está *como deve parecer* — tokens,
> tipografia, layout, inventário de componentes com specs visuais, estados de interação,
> data-viz, acessibilidade, breakpoints e guia por fatia. Stack já travada (não re-derivar):
> React + Vite + TS · TanStack Query (REST) · uPlot (trends) · WebSocket envelope
> `{type, loop_id, ts, data}` · temas Dark Room / ISA-101 / MD3 dark / MD3 light / Ocean ·
> substitui a HMI PySide6 · browser-only, localhost, admin único.

---

## Estado de implementação (engine real — refactor Fase 9)

> Esta seção registra **como** o design system foi implementado. Os tokens (§2), a tipografia
> (§3) e os estados (§6) abaixo permanecem a autoridade visual; o que mudou é o motor de UI.

- **Engine de UI:** **Tailwind v4 (CSS-first, `@theme inline`)** + **shadcn** (primitivas **Radix**,
  React 18) **re-estilizadas flat**. Não há mais `.css` por componente: as 13 folhas de estilo
  periféricas foram removidas e dobradas em utilitários de token. Os tokens semânticos do §2 são
  declarados em `src/index.css` como CSS custom properties por tema (`[data-theme=…]`) e
  **ponte-de-token** (`token-bridge`) para o Tailwind via `@theme inline` — ou seja, as cores do
  Tailwind resolvem para `var(--bg)`, `var(--surface)`, `var(--alarm-critical)`, etc. Trocar de
  tema continua sendo trocar `data-theme` no `<html>`; nenhum componente carrega cor literal.
- **Magic UI: rejeitado.** Avaliado e descartado — seus efeitos (gradientes, shimmer, brilho,
  motion decorativo) violam a ISA-101. Ausência verificada no gate (`grep magicui|magic-ui` vazio).
- **Latitude em dois níveis (§6b):** telas de **operador** (dashboard, faceplate, cards, alarmes)
  são **estritas** — monocromático em normal, cor só para anormalidade. **Login** e **Executive
  Dashboard** têm latitude controlada (hero de número grande, composição) sem violar flat/cor.
- **Enforcement — guard ISA-101 em Vitest.** A regra foi especificada como duas regras
  `no-restricted-syntax` em `eslint.config.js`, mas esse arquivo é **protegido por hook de
  config** e não pode ser editado. A mesma intenção é aplicada como source-guard auto-contido em
  `src/__tests__/isa101-guard.test.ts` (`ENFORCED_FILES` / `ENFORCED_DIRS`), que lê o fonte e
  falha se as superfícies migradas contiverem cores cruas / utilitários de cor não-token / box-shadow
  / gradiente. **Deferimento:** portar para ESLint se/quando a config-protection for liberada.
- **Gate de contraste endurecido (§8.4):** `src/theme/themeContrast.test.ts` +
  `src/theme/tokenResolve.test.ts` cobrem os 5 temas; focus ring ≥3:1 e ≥2px; alvos ≥44×44
  (`e2e/target-size.spec.ts`). Estados obrigatórios **§6a** (loading/empty/error-WS-disconnect,
  flat e token-only, sem shimmer) implementados.
- **Exceções de elemento nativo (contratos de teste congelados):** `CardControls`,
  `DynamicsSliders` (`<input type="range">`) e o `ThemeSwitcher` permanecem com elementos nativos
  re-estilizados flat para preservar testes congelados (`toHaveValue` / `fireEvent.change`). O
  `WelcomeDialog` segue overlay não-portal (não-Radix) com o **scrim** `bg-black/70` sancionado —
  a única sobreposição translúcida permitida (a par do scrim do `dialog.tsx` shadcn).
- **Baselines visuais:** 21 snapshots Playwright (5 temas × {320,768,1024,1440} + faceplate)
  re-abençoados contra o build flat/responsivo desta branch. Gate completo (§12) verde: lint 0
  erros · build · Vitest 410/410 · perf budget · Playwright 39/39.

---

## 0. Princípio reitor — "Instrumento, não dashboard"

A interface é um **painel de instrumentação**, não um dashboard de marketing. A leitura premium
não vem de cor, gradiente ou sombra (proibidos pela ISA-101) — vem de **precisão**: alinhamento
de grade rígido, números tabulares que nunca "pulam", barras analógicas com escala de ticks reais,
ritmo de espaçamento derivado de uma unidade base de 4px, e hierarquia construída só por
**escala tipográfica + peso + cinza**. É o equivalente digital de um bom multímetro de bancada:
silencioso quando tudo está normal, inequívoco quando algo sai do normal.

Esse princípio reconcilia "bonito e moderno" com "ISA-101 seguro":
- **Moderno** = execução impecável de espaço, tipo e estado (não enfeite).
- **ISA-101 seguro** = monocromático em estado normal; **cor = exclusivamente anormalidade**;
  o alarme é sempre o único ponto luminoso da tela. Decoração nunca compete com o alarme.

### Elemento-assinatura (onde gastamos toda a ousadia)
**O `AnalogBar` instrumentado** — uma barra de processo com (a) escala de ticks reais, (b)
marcadores de SP e de limites de alarme desenhados *na própria escala*, e (c) leitura numérica
em monospace tabular alinhada à direita, com o ponto decimal sempre na mesma coluna. Esse é o
componente que o produto é lembrado por. Todo o resto fica disciplinado e quieto ao redor dele.
Decisão deliberada de evitar o "número grande + label pequeno + acento gradiente" (resposta-template).

---

## 1. Direção de design / personalidade

**Direção escolhida:** *Industrial-precision / control-room instrumentation.* Swiss/International
aplicado a SCADA — grade rígida, hairlines, zero raio por padrão (exceto MD3), densidade
informacional alta mas respirável. Não é "dark luxury" nem "neo-brutalism"; é **disciplina de
instrumento**.

**Como lê como premium sem violar ISA-101:**
1. **Tipografia de instrumento** — par IBM Plex Sans + IBM Plex Mono (desenhados juntos, numerais
   tabulares de verdade). Números de processo nunca trepidam porque usam `font-variant-numeric:
   tabular-nums`. Isso, sozinho, separa o produto de 90% das HMIs.
2. **Grade e ritmo** — espaçamento em escala 4px com saltos intencionais (não padding uniforme).
   Cards alinham baseline; barras alinham a coluna decimal entre loops diferentes.
3. **Profundidade por superfície tonal, não por sombra** — hierarquia via degraus de cinza
   (surface → surface-container → surface-container-high), exatamente como ISA-101 e MD3 pedem.
4. **Estados desenhados** — hover/focus/active/disabled têm tratamento explícito e consistente,
   com `:focus-visible` sempre visível (operador pode estar 100% no teclado).
5. **Cor como evento** — quando um alarme acende, é cinematográfico justamente porque tudo ao
   redor é cinza. A contenção é o luxo.

**Personalidade em uma frase:** *séria, exata, calma — fala alto só quando o processo fala alto.*

---

## 2. Tokens de cor (CSS custom properties) — UMA paleta por tema

Arquitetura: **tokens semânticos** (`--bg`, `--surface`, `--text`, `--alarm-critical`, `--trend-pv`…)
mapeados por tema via `[data-theme="…"]` no `<html>`. Componentes **nunca** usam hex direto —
só tokens. Isso é o que permite trocar tema sem tocar componente (Fatia 8).

### 2.0 Contrato de tokens (nomes estáveis em todos os temas)

```
Superfícies:   --bg, --surface, --surface-container, --surface-container-high, --field-bg
Linhas:        --border, --border-strong, --divider
Texto:         --text, --text-secondary, --text-disabled, --text-on-alarm
Foco:          --focus-ring
Alarme/sev:    --alarm-critical, --alarm-critical-bg, --alarm-warning, --alarm-warning-bg,
               --alarm-diag, --alarm-info, --on-alarm
Estado loop:   --state-running, --state-stopped, --state-error, --state-oos   (ver §2.6)
Trends:        --trend-pv, --trend-sp, --trend-co, --trend-grid, --trend-axis, --trend-bg
Barra:         --bar-track, --bar-fill, --bar-marker
```

> Regra ISA-101 (todos os temas exceto onde a identidade MD3 light pede): em **estado normal**
> `--state-running`/`--bar-fill` são **cinza**, nunca verde. Verde nunca significa "ok/ligado".
> As únicas cores saturadas que aparecem em estado normal são as **3 cores de trend** (PV/SP/CO),
> porque trends precisam de discriminação de série — e estas são dessaturadas/escolhidas para não
> colidir com o vocabulário de alarme (ver §2.7 e §8.4).

### 2.1 Dark Room (sala escura — emissão mínima)
Fonte: `identidade_visual_Dark.md`. Preto absoluto, monocromático, alarme "neon muted".

```css
[data-theme="dark-room"] {
  --bg: #000000;
  --surface: #0D0D11;            /* cards/painéis */
  --surface-container: #0D0D11;
  --surface-container-high: #15151A;
  --field-bg: #050508;          /* inputs e fundo de gráfico */
  --border: #222228;
  --border-strong: #2C2C34;
  --divider: #1A1A20;
  --text: #B0B0B8;              /* valores — nunca branco */
  --text-secondary: #666670;    /* rótulos, unidades */
  --text-disabled: #3A3A42;
  --focus-ring: #8A8A94;        /* anel cinza-claro, sem cor */
  /* Alarmes — único ponto luminoso da tela */
  --alarm-critical: #D92525;    --alarm-critical-bg: #2A0A0A;
  --alarm-warning:  #D9A000;    --alarm-warning-bg:  #2A2000;
  --alarm-diag:     #8A6AD9;    --alarm-info:        #4A8AD9;
  --on-alarm: #F2E6E6;          --text-on-alarm: #F2E6E6;
  /* Estado de loop (cinza no normal) */
  --state-running: #4A4A52;     --state-stopped: #666670;
  --state-error: #D92525;       --state-oos: #3A3A42;
  /* Trends (night-vision: cinzas distintos + CO âmbar muito contido) */
  --trend-pv: #C8C8D0;          --trend-sp: #6E6E78;   --trend-co: #B07A2A;
  --trend-grid: #1A1A20;        --trend-axis: #3A3A42; --trend-bg: #000000;
  /* Barra */
  --bar-track: #050508;         --bar-fill: #4A4A52;   --bar-marker: #888890;
}
```

### 2.2 ISA-101 (dark mode industrial — referência normativa)
Fonte: `identidade_visual_ISA101.md`. Cinza neutro, alarme vivo, roxo/azul para diagnóstico.

```css
[data-theme="isa101"] {
  --bg: #1E1E1E;
  --surface: #2D2D30;
  --surface-container: #2D2D30;
  --surface-container-high: #333337;
  --field-bg: #252526;
  --border: #454548;
  --border-strong: #57575B;
  --divider: #3A3A3D;
  --text: #E0E0E0;             /* nunca branco puro */
  --text-secondary: #ABABAB;
  --text-disabled: #666666;
  --focus-ring: #C8C8C8;
  --alarm-critical: #FF3333;   --alarm-critical-bg: #3A0E0E;
  --alarm-warning:  #FF8800;   --alarm-warning-bg:  #3A2200;
  --alarm-diag:     #AA55FF;   --alarm-info:        #33AAFF;
  --on-alarm: #FFFFFF;         --text-on-alarm: #1E1E1E;
  --state-running: #9A9A9A;    --state-stopped: #ABABAB;
  --state-error: #FF3333;      --state-oos: #666666;
  --trend-pv: #E0E0E0;         --trend-sp: #33AAFF;   --trend-co: #FFB000;
  --trend-grid: #3A3A3D;       --trend-axis: #57575B; --trend-bg: #252526;
  --bar-track: #252526;        --bar-fill: #9A9A9A;   --bar-marker: #CCCCCC;
}
```
> Nota ISA-101: o amarelo de aviso é `#FF8800` (laranja-âmbar) e o crítico `#FF3333`; mantidos
> distintos em matiz **e** em luminância (ver §7.3) para não depender só de cor.

### 2.3 MD3 dark (Material 3 restrito a neutros + error tokens)
Fonte: `identidade_visual_MD3.md`. Cantos arredondados, sobreposição tonal, cor só no alarme.

```css
[data-theme="md3-dark"] {
  --bg: #141218;                          /* Surface */
  --surface: #211F26;                     /* Surface Container (cards) */
  --surface-container: #1D1B20;           /* Surface Container Low */
  --surface-container-high: #2B2930;      /* Surface Container High */
  --field-bg: #1D1B20;
  --border: #49454F;                      /* Outline Variant */
  --border-strong: #938F99;               /* Outline */
  --divider: #36343B;
  --text: #E6E0E9;                        /* On-Surface */
  --text-secondary: #CAC4D0;              /* On-Surface Variant */
  --text-disabled: #605D66;
  --focus-ring: #CAC4D0;
  --alarm-critical: #F2B8B5;  --alarm-critical-bg: #8C1D18;  /* Error / Error Container */
  --alarm-warning:  #FFDC99;  --alarm-warning-bg:  #4D3300;
  --alarm-diag:     #D0BCFF;  --alarm-info:        #99CBFF;
  --on-alarm: #F9DEDC;        --text-on-alarm: #601410;
  --state-running: #938F99;   --state-stopped: #CAC4D0;
  --state-error: #F2B8B5;     --state-oos: #605D66;
  --trend-pv: #E6E0E9;        --trend-sp: #99CBFF;  --trend-co: #FFD8A8;
  --trend-grid: #36343B;      --trend-axis: #49454F; --trend-bg: #141218;
  --bar-track: #2B2930;       --bar-fill: #938F99;  --bar-marker: #CAC4D0;
  /* shape tokens MD3 (só este tema usa raio) */
  --radius-card: 12px; --radius-control: 8px; --radius-pill: 999px;
}
```

### 2.4 MD3 light (Material 3 light, restrito)
Derivado do M3 light neutral. Único tema claro — usa cinza-quente, **sem branco puro de fundo**
para não ofuscar (campo industrial). Verde ainda proibido como "ok".

```css
[data-theme="md3-light"] {
  --bg: #FDF8FD;                  /* Surface (off-white quente) */
  --surface: #F7F2FA;            /* Surface Container */
  --surface-container: #F2ECF4;  /* Surface Container Low */
  --surface-container-high: #ECE6F0;
  --field-bg: #FFFFFF;
  --border: #CAC4D0;             /* Outline Variant */
  --border-strong: #79747E;      /* Outline */
  --divider: #E0DAE4;
  --text: #1D1B20;               /* On-Surface */
  --text-secondary: #49454F;     /* On-Surface Variant */
  --text-disabled: #9A949F;
  --focus-ring: #49454F;
  --alarm-critical: #B3261E;  --alarm-critical-bg: #F9DEDC;   /* Error / Error Container */
  --alarm-warning:  #8A5000;  --alarm-warning-bg:  #FFE2BC;
  --alarm-diag:     #6750A4;  --alarm-info:        #1E5D9E;
  --on-alarm: #FFFFFF;        --text-on-alarm: #FFFFFF;
  --state-running: #79747E;   --state-stopped: #49454F;
  --state-error: #B3261E;     --state-oos: #9A949F;
  --trend-pv: #1D1B20;        --trend-sp: #1E5D9E;  --trend-co: #9A5B00;
  --trend-grid: #E0DAE4;      --trend-axis: #CAC4D0; --trend-bg: #FFFFFF;
  --bar-track: #ECE6F0;       --bar-fill: #79747E;  --bar-marker: #49454F;
  --radius-card: 12px; --radius-control: 8px; --radius-pill: 999px;
}
```

### 2.5 Ocean (variante de marca — azul-petróleo dessaturado, ainda HMI-seguro)
Tema de identidade extra (citado na umbrella §4 fatia 8). Mantém a regra "cor = alarme":
o azul-petróleo aparece **apenas em superfícies e cromo neutro**, não em estado de processo.
É a forma de dar caráter de marca sem quebrar ISA-101 — a saturação fica nos *fundos*, nunca no
*significado de estado*.

```css
[data-theme="ocean"] {
  --bg: #0A1620;                  /* deep teal-navy */
  --surface: #0F2030;
  --surface-container: #0F2030;
  --surface-container-high: #16304A;
  --field-bg: #081019;
  --border: #1E3A52;
  --border-strong: #2A4E6E;
  --divider: #16283A;
  --text: #D6E2EC;
  --text-secondary: #7E97AC;
  --text-disabled: #44586A;
  --focus-ring: #8FB6D6;
  --alarm-critical: #FF4D4D;  --alarm-critical-bg: #3A0E0E;
  --alarm-warning:  #FFB020;  --alarm-warning-bg:  #3A2A00;
  --alarm-diag:     #9B6BFF;  --alarm-info:        #45B0FF;
  --on-alarm: #FFFFFF;        --text-on-alarm: #081019;
  --state-running: #5E7E96;   --state-stopped: #7E97AC;
  --state-error: #FF4D4D;     --state-oos: #44586A;
  --trend-pv: #CFE0EC;        --trend-sp: #45B0FF;  --trend-co: #FFB020;
  --trend-grid: #16283A;      --trend-axis: #1E3A52; --trend-bg: #081019;
  --bar-track: #081019;       --bar-fill: #5E7E96;  --bar-marker: #8FB6D6;
}
```

### 2.6 Estados de loop — mapa semântico (todos os temas)
| Estado | Token | Tratamento visual |
|---|---|---|
| RUNNING (normal) | `--state-running` (cinza) | ponto/anel cinza; **sem verde** |
| STOPPED / paused | `--state-stopped` (cinza claro) | ponto cinza vazado |
| ERROR / OPC down | `--state-error` (vermelho) | ponto preenchido + ícone diag |
| OOS / desabilitado | `--state-oos` (cinza fraco) | esmaecido, texto-disabled |

### 2.7 Cores de trend — por que existem em estado normal
PV/SP/CO precisam ser distinguíveis num gráfico — discriminação de série é função, não
decoração. Regra: **CO sempre âmbar/laranja** (eixo direito 0–100%), **SP sempre o azul/info
do tema** (referência), **PV sempre o cinza-claro/texto do tema** (variável medida). Nenhuma
delas usa o vermelho de crítico. Verificação cross-tema em §8.4.

---

## 3. Tipografia

### 3.1 Estratégia de pareamento (deliberada, não default)
- **UI / display:** **IBM Plex Sans** — pedigree industrial (desenhada para contexto de máquina),
  larguras estáveis, ótima em corpo pequeno e alto contraste. Evita Inter-em-tudo (default de IA).
- **Dados / numérico / tags:** **IBM Plex Mono** — desenhada como par do Plex Sans, **numerais
  tabulares** nativos. Toda leitura de processo (PV/SP/CO, Kp/Ti/Td, métricas) é mono tabular.
- **Por tema:** MD3 (dark/light) troca a face de UI para **Roboto** + dados em **Roboto Mono**
  (exigência da identidade MD3); Dark Room pode usar mono em quase tudo (JetBrains Mono / Plex
  Mono) por exigência do doc Dark. ISA-101 e Ocean usam o par Plex.
- Fontes auto-hospedadas (browser-only/localhost; sem CDN externo), `font-display: swap`,
  subset latino, pré-carregar só o peso crítico (500).

```css
:root {
  --font-ui:   "IBM Plex Sans", system-ui, sans-serif;
  --font-data: "IBM Plex Mono", ui-monospace, "Cascadia Code", monospace;
}
[data-theme="md3-dark"], [data-theme="md3-light"] {
  --font-ui: "Roboto", system-ui, sans-serif;
  --font-data: "Roboto Mono", ui-monospace, monospace;
}
[data-theme="dark-room"] {
  --font-ui: "IBM Plex Mono", ui-monospace, monospace;   /* leitura mono-dominante */
  --font-data: "IBM Plex Mono", ui-monospace, monospace;
}
```

### 3.2 Escala de tipo (clamp-based, fluida entre 1024 e 1920)
```css
:root {
  --text-2xs:  0.6875rem;                                  /* 11px — unidades, ticks */
  --text-xs:   0.75rem;                                    /* 12px — labels, meta */
  --text-sm:   0.8125rem;                                  /* 13px — corpo denso, tabelas */
  --text-base: 0.9375rem;                                  /* 15px — corpo */
  --text-lg:   clamp(1rem, 0.95rem + 0.25vw, 1.125rem);    /* títulos de card */
  --text-xl:   clamp(1.25rem, 1.1rem + 0.6vw, 1.5rem);     /* PV no faceplate */
  --text-2xl:  clamp(1.75rem, 1.4rem + 1.2vw, 2.5rem);     /* PV grande / KPI executivo */
  --text-3xl:  clamp(2.5rem, 1.8rem + 2.4vw, 3.75rem);     /* leitura primária de faceplate */
  /* pesos */
  --fw-regular: 400; --fw-medium: 500; --fw-semibold: 600; --fw-bold: 700;
  /* line-heights */
  --lh-tight: 1.1;   /* números */   --lh-snug: 1.3;   --lh-normal: 1.5;  /* texto corrido */
}
```

### 3.3 Uso numérico / tabular (regra de ouro)
Todo número de processo **DEVE** ter:
```css
.numeric {
  font-family: var(--font-data);
  font-variant-numeric: tabular-nums;
  font-feature-settings: "tnum" 1, "zero" 1;   /* zero cortado opcional */
  letter-spacing: 0;
}
```
- PV/SP/CO em cards alinham **à direita**, ponto decimal na mesma coluna; unidade (`°C`, `%`,
  `bar`) em `--text-2xs`/`--text-secondary` ao lado, baseline-alinhada.
- Casas decimais fixas por tag (do backend); nunca arredondar visualmente "pulando" dígitos.

### 3.4 Hierarquia (papéis)
| Papel | Tamanho | Peso | Família |
|---|---|---|---|
| Page title / app bar | `--text-lg` | 600 | UI |
| Card tag (ex. `PIC-005`) | `--text-base` | 700 | data (mono) |
| Card descrição | `--text-xs` | 400 | UI / secondary |
| Valor PV em card | `--text-base` | 500 | data tabular |
| Valor PV em faceplate | `--text-3xl` | 500 | data tabular |
| KPI executivo | `--text-2xl` | 600 | data tabular |
| Label de campo / unidade | `--text-2xs`–`xs` | 400 | UI / secondary |

---

## 4. Espaçamento, grade e shell de navegação

### 4.1 Escala de espaço (base 4px, saltos intencionais)
```css
:root {
  --sp-1: 0.25rem; --sp-2: 0.5rem; --sp-3: 0.75rem; --sp-4: 1rem;
  --sp-5: 1.25rem; --sp-6: 1.5rem; --sp-8: 2rem; --sp-10: 2.5rem; --sp-12: 3rem;
  /* cromo fixo */
  --appbar-h: 48px; --alarmbar-h: 36px; --nav-rail-w: 64px; --nav-rail-w-expanded: 224px;
  --card-w: 280px;            /* largura fixa do ControllerCard (paridade PySide6) */
  --radius-card: 0px; --radius-control: 0px; --radius-pill: 0px;  /* zero por padrão; MD3 sobrescreve */
  --border-w: 1px; --alarmstrip-h: 5px;
}
```
> Ritmo, não padding uniforme: cards têm padding interno `--sp-4`; o *gap* entre seções é
> `--sp-8`; o gap entre cards é `--sp-3`. A diferença é proposital (agrupa visualmente).

### 4.2 Shell / app frame
```
┌──────────────────────────────────────────────────────────────────────┐
│ App bar (48px): logo · projeto atual · status OPC ● · tema · usuário   │  --surface-container
├────┬─────────────────────────────────────────────────────────────────┤
│ N  │                                                                    │
│ a  │   Conteúdo da rota (dashboard / multi-trend / exec / settings…)    │  --bg
│ v  │                                                                    │
│    │                                                                    │
│ ▢  │                                                                    │
├────┴─────────────────────────────────────────────────────────────────┤
│ Alarm bar (36px): ● 2 CRIT  ▲ 5 WARN  · último evento ·  [ ACK ALL ]   │  --surface-container-high
└──────────────────────────────────────────────────────────────────────┘
```
- **Nav rail** vertical à esquerda (ícones; expande a 224px no hover/pin com rótulos). Ícones de
  contorno fino (lucide/Material Symbols outline), 20px, cor `--text-secondary`, ativo `--text`
  com barra-indicadora de 2px na borda interna.
- **App bar** fina: status OPC é um ponto + label (`OPC ●` verde-cinza? **não** — cinza no normal,
  vermelho se down). Seletor de tema e menu de usuário à direita.
- **Alarm bar** persistente no rodapé (Fatia 3), sempre visível em todas as rotas — é cromo de
  segurança, não conteúdo de página.

### 4.3 Grade de conteúdo
- Container fluido com `padding-inline: clamp(--sp-4, 2vw, --sp-8)`.
- Dashboard: faixa horizontal de cards de largura fixa (280px) com wrap (`flex-wrap`), justificada
  à esquerda — paridade com PySide6 (cards lado a lado). Em telas largas vira grade implícita de
  N colunas conforme cabe.
- Páginas analíticas (exec, multi-trend): **bento** de 12 colunas (ver §8.6).

---

## 5. Inventário de componentes (specs visuais)

Cada componente lista: anatomia · normal · alarme/estado · interação. Todos consomem tokens.

### 5.1 `AnalogBar` (elemento-assinatura)
Anatomia: `[ rótulo ][ trilho com escala de ticks + preenchimento + marcadores ][ valor + unidade ]`
- **Geometria:** trilho de 8px de altura (card) / 14px (faceplate); largura flexível. Raio 0
  (pílula só no MD3). Fundo `--bar-track`.
- **Preenchimento (valor):** `--bar-fill` (cinza no normal). Transição de largura em 120ms linear
  (ver §6 — compositor-friendly via `transform: scaleX` quando possível, com `transform-origin:left`).
- **Escala de ticks:** micro-traços de 1px em `--bar-marker` a 0/25/50/75/100% (faceplate) ou só
  0/100 (card). Densidade adaptativa por largura.
- **Marcadores na escala (a assinatura):**
  - **SP:** triângulo fino apontando para baixo, posicionado no valor de SP (apenas em PV-bar).
  - **Limites de alarme (HI/LO/HIHI/LOLO):** traços verticais finos `--alarm-warning`/`--alarm-critical`
    *dessaturados* (50% opacidade) na posição da escala — visíveis mas não "acesos" até disparar.
- **Valor:** mono tabular, `--text`, alinhado à direita; unidade em `--text-2xs`/`--text-secondary`.
- **Alarme:** o **preenchimento** muda para `--alarm-critical`/`--alarm-warning` (mudança abrupta,
  sem fade — é evento, não animação). O valor numérico ganha peso 600. O resto do card permanece
  cinza (não "ilumina" o card — regra Dark Room).
- **Acessibilidade:** `role="meter"`, `aria-valuemin/max/now`, `aria-label="PV PIC-005 150.2 °C"`.

```
PV  ├──────────────●──────┤ 150.2 °C        (▽ = SP marker, │ = limite alarme dessat.)
        │      ▽         │
SP  ├──────────────────────┤ 152.0 °C
CO  ├────────────┤            64.0 %
```

### 5.2 `ControllerCard` (Nível 1 — visão geral)
Largura fixa **280px**, fundo `--surface`, borda `--border` 1px (MD3: sem borda + raio 12px).
- **Strip de alarme (topo):** faixa de 5px (`--alarmstrip-h`), transparente no normal, colorida
  pela severidade ativa (vermelho=CRIT, âmbar=WARN). É o primeiro sinal periférico.
- **Header:** `[ TAG (mono 700) descrição (xs secondary) ]  ⚠?  ⚙`. Ícone de alarme só aparece
  em alarme — **octógono** preenchido para CRIT, **triângulo** para WARN (forma + cor, redundância).
  Botão ⚙ (config, Fatia 2) à direita, `--text-secondary`, hover `--text`.
- **Corpo:** três `AnalogBar` empilhados (PV, SP, CO), padding `--sp-4`, gap `--sp-2`.
- **Rodapé:** `Mode: AUTO` (mono) + ponto de estado de loop (§2.6) + chip de estratégia IA
  (`NONE`/`FUZZY`/`RL`) quando aplicável.
- **Sem sparklines** (regra absoluta dos 3 docs de identidade).
- **Estado em alarme:** borda do card assume cor de severidade (2px); strip do topo acende; ícone
  no header. Borda piscante só se não-reconhecido (ver §6.4 — respeita reduced-motion).
- **Hover:** elevação tonal (`--surface-container-high`), não sombra. **Focus:** anel `--focus-ring`
  2px offset 2px. **Click:** abre faceplate (Fatia 8) / seleciona.

### 5.3 `Faceplate` (Nível 3 — painel de controle)
Side-sheet à direita (paridade) ou modal lateral; largura 360–420px.
- **Cabeçalho:** TAG grande (mono 700) + descrição + estado de loop + status OPC.
- **Leitura primária:** PV em `--text-3xl` mono tabular, com unidade; SP e CO em `--text-xl`.
- **Barras analógicas maiores** (14px) com escala completa de ticks e marcadores SP/limites.
- **Controles de modo PID:** toggle/segmented `[ AUTO | MAN | CAS … ]` — interruptores planos
  táteis: inativo `--surface-container-high` + `--text-secondary`; ativo `--field-bg` + `--text`
  com borda `--border-strong` (Dark Room) / segmented MD3 no tema MD3. Os 8 modos cabem num menu
  segmentado em 2 linhas ou dropdown para os menos usados (RCas/ROut).
- **Controles de IA:** `[ RUN | PAUSE | STOP ]` (mesma linguagem de toggle), + leitura gamma/Ki ao
  vivo (chip `ai`), + estratégia.
- **Entrada de SP local:** campo numérico mono com stepper; CO manual (slider + campo) só habilitado
  em modo MAN.
- **`apply-tuning`:** botão destacado (borda forte, **não** cor de alarme) que abre confirmação
  modal explícita (Fatia 2): "Escrever Kp=… Ti=… no controlador PIC-005?" → `[ Cancelar ] [ Escrever ]`.

### 5.4 `RealtimeTrend` (uPlot) — ver também §7 (data-viz)
- Fundo `--trend-bg`; grade `--trend-grid` (hairline, quase invisível); eixos `--trend-axis`.
- Eixo Y esquerdo PV/SP (mesma escala); eixo Y direito CO (0–100%).
- Linhas: PV `--trend-pv` 1.5px, SP `--trend-sp` 1.5px tracejada fina (para distinguir de PV sem
  depender só de cor), CO `--trend-co` 1.5px no eixo direito. **Sem area-fill** (zero fill — regra).
- Janela deslizante de N pontos/segundos; cursor com crosshair fino e legenda flutuante mono.

### 5.5 `AlarmBar` + `AlarmPanel` (Fatia 3)
- **AlarmBar (rodapé, 36px):** contadores por severidade (`● n CRIT` `▲ n WARN` `◆ n DIAG`) +
  texto do último evento (cinza, só ícone/contador coloridos) + `[ ACK ALL ]` à direita.
  Não-reconhecidos: contador pisca (1s, reduced-motion → sem blink, usa peso/sublinhado).
- **AlarmPanel (lista):** tabela densa virtualizada — colunas `Sev · Tag · Mensagem · Estado ·
  Hora · Ack`. Linha de alarme não-ack: faixa lateral de 3px na cor da severidade + fundo
  `--alarm-*-bg` muito sutil. Ordenável por severidade/hora; filtro por estado/loop. Ack por linha
  + ack-all. Estado de severidade sempre redundante (ícone geométrico + cor + texto).

### 5.6 Diálogos (`LoopConfigDialog`, confirmações) — Fatia 2
- Modal centrado, largura 520–680px, fundo `--surface-container-high`, header com TAG, body em
  seções colapsáveis: **PID** (Kp, Ti, Td, estrutura, ARW min/max, filtro derivativo, deadband),
  **Otimização IA** (radio NONE/FUZZY/RL → revela params do escolhido), **Limites**.
- Campos: label `--text-xs` acima, input mono (`--field-bg`, borda `--border`, focus `--focus-ring`
  + borda `--border-strong`). Validação inline (mensagem `--alarm-warning` abaixo do campo; nunca
  só cor — texto explícito). Footer fixo: `[ Cancelar ] [ Salvar ]`.

### 5.7 `Login` (Fatia 0+1)
- Tela cheia, fundo `--bg`, **card central** estreito (360px) `--surface` com borda hairline.
  Marca + nome do produto no topo (sem hero de marketing — é uma estação industrial).
- Campos usuário/senha (mono), botão primário `[ Entrar ]` (borda forte, sem gradiente).
  Erro de auth: linha `--alarm-critical` com texto explícito ("Usuário ou senha inválidos").
- Sem ilustração decorativa; a personalidade vem do par tipográfico e do alinhamento.

### 5.8 Indicadores de status
- **Ponto de estado** 8px: preenchido/vazado por estado (§2.6). Sempre com label textual ao lado
  (acessibilidade). **Status OPC** na app bar: `OPC` + ponto (cinza normal / vermelho down) +
  tooltip com endpoint.
- **Chip de modo/estratégia:** retângulo fino mono, `--surface-container-high`, `--text-secondary`.

### 5.9 `MultiTrend` (Fatia 4)
- uPlot multi-série (vários loops × PV/SP/CO). Painel lateral de **seleção de séries** (checkboxes
  com swatch da cor da série + tag). Cada série herda PV/SP/CO do tema mas é tonalmente variada por
  loop (claro→escuro dentro da mesma matiz) para distinguir loops sem inventar cores novas.
- Controles: escala/auto-escala por eixo, janela deslizante, pause/resume do live.

### 5.10 `ExecutiveKPICard` (Fatia 6)
- Card maior que o ControllerCard, bento. Número KPI grande (`--text-2xl` mono tabular) + label +
  micro-delta (seta ▲/▼ + valor, cor **só** se for variabilidade fora de meta → usa âmbar/vermelho;
  caso contrário cinza). Mini-distribuição opcional (barra de faixa), **não** sparkline em cards de
  loop — aqui é agregado executivo, permitido como barra de faixa discreta.
- KPIs: variabilidade `2σ/RANGE`, TV (valve travel), IAE, estado de IA, % loops em AUTO.

### 5.11 Controles do `Simulator` (Fatia 5)
- **Banner de modo simulação** persistente no topo da página (faixa `--alarm-diag` dessaturada +
  texto "MODO SIMULAÇÃO — digital twin"), para nunca confundir com processo real.
- Seletor de preset (dropdown/segmented), sliders de dinâmica (ganho, tempo morto L, τ) com leitura
  mono ao lado de cada slider, botões `[ Injetar distúrbio ] [ Remover ]`, controle de output/modo
  do twin, toggles auto-disturbance / auto-sp, `[ Start | Stop ]`.

---

## 6. Estados de interação e motion

### 6.1 Estados (todos os controles interativos)
| Estado | Tratamento |
|---|---|
| Default | token base |
| Hover | superfície sobe um degrau tonal (`--surface-container-high`); cursor pointer |
| Focus-visible | `outline: 2px solid var(--focus-ring); outline-offset: 2px;` (sempre visível) |
| Active/pressed | superfície desce um degrau + `transform: translateY(0)` (sem deslocamento falso) |
| Disabled | `--text-disabled`, `opacity: .6`, `cursor: not-allowed`, sem hover |
| Selected | borda interna 2px `--border-strong` ou `--text` |

### 6.2 Tokens de transição
```css
:root {
  --dur-fast: 120ms; --dur-normal: 200ms; --dur-slow: 320ms;
  --ease-out: cubic-bezier(0.16, 1, 0.3, 1);
  --ease-standard: cubic-bezier(0.2, 0, 0, 1);
}
```

### 6.3 Apenas propriedades compositor-friendly
Animar somente `transform`, `opacity`, `clip-path`. **Nunca** animar `width/height/top/left/margin`.
- Preenchimento de barra: `transform: scaleX()` com `transform-origin: left` (não animar `width`).
- Telemetria ao vivo: atualização de valor sem fade (legibilidade); a barra interpola via transform.
- uPlot redesenha por dados, não por CSS — sem transição CSS no canvas.

### 6.4 Movimento de alarme (deliberado, contido)
- Alarme novo não-reconhecido: pisca **opacidade** do ícone/contador (1.0↔0.4, 1s, `step` suave).
  Após ACK: para de piscar, fica estável. Nunca pisca o card inteiro (regra Dark Room).
- **`prefers-reduced-motion: reduce`:** sem blink; o não-reconhecido fica indicado por **peso 700 +
  sublinhado + ícone preenchido** em vez de animação. Todas as transições caem para 0ms/opacity-only.

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { animation-duration: 0.01ms !important; transition-duration: 0.01ms !important; }
}
```

---

## 7. Regras de data-viz (uPlot por paleta)

### 7.1 Tema do uPlot por palette
Gerar a config do uPlot a partir dos tokens lidos via `getComputedStyle` no mount e no theme-change:
- `axes[*].stroke = --trend-axis`, `axes[*].grid.stroke = --trend-grid`, `axes[*].ticks.stroke =
  --trend-grid`, fundo via container `--trend-bg`.
- Séries: PV `{stroke: --trend-pv, width: 1.5}`, SP `{stroke: --trend-sp, width: 1.5, dash: [6,4]}`,
  CO `{stroke: --trend-co, width: 1.5, scale: "co"}`. **`fill` ausente** (zero area-fill).
- Cursor: `cursor.points` discretos; legenda em mono tabular.

### 7.2 Decimação e janela deslizante (look + perf)
- Janela deslizante de N (config; default ~600 pts / ~60 s). Ao exceder, descartar à esquerda
  (FIFO) — coerente com a política de "último valor" do WS (umbrella §2.3).
- Decimação **min/max por pixel-column** (preserva picos/transientes — crítico em controle) quando
  pontos > largura em px. Alvo ~60 fps; redraw em `requestAnimationFrame`, batendo com a taxa WS.
- Visual de "janela viva": eixo X rola; última amostra com ponto-cursor sutil; sem reflow do layout.

### 7.3 Distinguibilidade de série e alarme (não só cor)
- SP tracejada, PV sólida, CO em eixo separado → distinguíveis em mono/daltonismo.
- Cores de alarme escolhidas com **separação de luminância** além de matiz (crítico mais escuro/
  saturado que warning em cada tema) — verificação obrigatória em §8.4.

### 7.4 Barras analógicas como data-viz de primeira classe
A `AnalogBar` é tratada como visualização, não enfeite: escala real, marcadores na escala, leitura
tabular. É a "data viz como parte do design system" exigida pela política anti-template.

---

## 8. Acessibilidade, contraste e verificação cross-tema

### 8.1 Alvos
- **Texto normal ≥ 4.5:1**, texto grande ≥ 3:1, **elementos não-textuais (barras, bordas de
  estado, ícones de alarme) ≥ 3:1** vs fundo (WCAG 1.4.11). Verificar por tema.
- `--text` sobre `--surface` e sobre `--bg` deve passar 4.5:1 em todos os temas (os valores em §2
  foram escolhidos para isso; Dark Room usa `#B0B0B8` sobre `#0D0D11` ≈ 7:1).

### 8.2 Semântica ISA-101 (cor nunca sozinha)
Toda condição de alarme é codificada por **3 canais redundantes**: cor + forma de ícone (octógono
CRIT / triângulo WARN / losango DIAG) + texto. Isso satisfaz WCAG 1.4.1 (uso de cor) e a prática
ISA-101 de não depender de cor.

### 8.3 Teclado e leitor de tela
- Tab order lógico; `:focus-visible` sempre; faceplate/diálogos com focus-trap e `Esc` fecha.
- Alvos de toque/click ≥ 32px no cromo denso, ≥ 44px em controles primários (apply-tuning, ACK).
- `role="meter"` nas barras; `aria-live="assertive"` na AlarmBar para novos CRIT; `aria-live="polite"`
  para WARN. Escala de texto do browser até 200% sem quebra (layout em rem/clamp).

### 8.4 Matriz de verificação de alarme cross-tema (gate de aceitação)
Para cada tema, confirmar que CRIT/WARN/DIAG são legíveis sobre o fundo e que CRIT e WARN são
distinguíveis entre si. **A cor de alarme é um indicador NÃO-TEXTUAL** (faixa lateral de 3px +
ícone geométrico de 10px — octógono/triângulo/losango), logo o alvo correto é **≥ 3:1 (WCAG
1.4.11)**, consistente com §8.1 — não o limiar de texto. A independência de cor vem da **forma**
(§8.2), não da luminância. Valores medidos (contraste CRIT vs `--surface`):

| Tema | CRIT | WARN | DIAG | CRIT vs fundo (alvo ≥ 3:1) | CRIT vs WARN |
|---|---|---|---|---|---|
| Dark Room | `#D92525` | `#D9A000` | `#8A6AD9` | 3.92:1 vs `#0D0D11` ✓ | matiz OU lum distintos + forma |
| ISA-101 | `#FF3333` | `#FF8800` | `#AA55FF` | 3.77:1 vs `#2D2D30` ✓ | matiz OU lum distintos + forma |
| MD3 dark | `#F2B8B5` | `#FFDC99` | `#D0BCFF` | 9.54:1 vs `#211F26` ✓ | matiz OU lum distintos + forma |
| MD3 light | `#B3261E` | `#8A5000` | `#6750A4` | 5.93:1 vs `#F7F2FA` ✓ | matiz OU lum distintos + forma |
| Ocean | `#FF4D4D` | `#FFB020` | `#9B6BFF` | 5.06:1 vs `#0F2030` ✓ | matiz OU lum distintos + forma |

> **Reconciliação (Fatia 8, 2026-06-20):** a tabela original exigia ≥ 4.5/5:1 para CRIT vs fundo,
> conflitando com §8.1 (não-textual = 3:1) e inatingível para os vermelhos de identidade ISA-101
> (`#FF3333`) / Dark Room (`#D92525`) sobre superfícies escuras. Decisão do owner: alinhar o gate a
> **3:1 (WCAG 1.4.11)** sem alterar as cores de identidade. CRIT vs WARN é validado por **matiz OU
> luminância distintos** (MD3-light é distinto por matiz, ΔL≈0; os demais por ambos) + redundância de
> forma (§8.2). `--text` sobre `--surface`/`--bg` permanece estrito em **≥ 4.5:1** (todos passam).
> Implementação: `src/theme/themeContrast.test.ts` (Vitest) com contraste calculado localmente
> (fórmula WCAG, sem dependência externa) — falha o build se um par cair abaixo do alvo.

---

## 9. Breakpoints (desktop-first industrial)

Prioridade 1024 / 1440 / 1920 (estações de controle). Mobile é cortesia, não foco.
```css
:root { /* não há container "centralizado": HMI usa largura total */ }
@media (min-width:1024px){ /* base: nav rail 64px, cards 280px com wrap */ }
@media (min-width:1440px){ /* bento exec/multi-trend ganha colunas; faceplate side-sheet 420px */ }
@media (min-width:1920px){ /* densidade aumenta: mais cards por linha, trend mais alto */ }
@media (max-width:1023px){ /* nav rail vira topo colapsável; cards 100% largura; faceplate full-screen */ }
```
- Sem overflow horizontal em nenhum breakpoint; tabelas densas (alarmes/usuários) com scroll
  interno e cabeçalho fixo.
- Bento exec (§5.10) em 12 colunas: KPIs 3×col em 1920, 2×col em 1440, 1×col em 1024.

---

## 10. Guia de UI por fatia (como deixar cada tela bonita e ISA-segura)

### Fatia 0+1 — Foundation + Live Dashboard (`dashboard_page`, `connection_page`)
- **Layout:** shell §4.2 (app bar + nav rail + alarm bar). Conteúdo = faixa de `ControllerCard`
  280px com wrap, justificada à esquerda; acima dela, uma faixa fina de contexto (projeto atual,
  contagem de loops, status OPC global).
- **Trend ao vivo:** opcional um `RealtimeTrend` largo abaixo dos cards (o loop selecionado), ou só
  dentro do faceplate. Manter dashboard limpo: cards primeiro, trend secundário.
- **Login:** §5.7 — card central, sem hero. **Status OPC:** §5.8.
- **Beleza:** o alinhamento da coluna decimal dos PV entre cards é o detalhe que vende. Hover tonal,
  focus ring sempre. Estado normal 100% cinza.

### Fatia 2 — Comandos + LoopConfigDialog (`controller_dialog`, controles do card)
- **Layout:** controles inline no card e no faceplate (§5.3). `LoopConfigDialog` §5.6 com seções
  colapsáveis (PID / IA / Limites). Radio NONE/FUZZY/RL revela os params do escolhido (progressive
  disclosure — não despejar tudo).
- **apply-tuning:** botão de borda forte + **modal de confirmação explícita** mostrando os valores a
  escrever. Distinguir claramente "salvar config" (local) de "escrever no controlador" (ação física).
- **Beleza/segurança:** confirmação é UX de segurança, não fricção gratuita — texto específico do que
  será escrito e em qual tag.

### Fatia 3 — Alarmes (`alarm_panel`, `alarm_bar`)
- **AlarmBar** §5.5 sempre no rodapé. **AlarmPanel** = tabela densa virtualizada com faixa lateral
  de severidade + fundo `--alarm-*-bg` sutil; ordenação/filtro; ack por linha e ack-all.
- **Severidade redundante** (ícone+cor+texto). Blink só em não-ack e só opacidade; reduced-motion →
  peso/sublinhado. `aria-live` para novos CRIT.
- **Beleza:** a tabela é o produto aqui — densidade legível, zebra sutil por `--divider`, hora em
  mono tabular alinhada.

### Fatia 4 — Multi-trend + Stats + Export (`multi_trend_page`, stats)
- **Layout bento:** trend grande à esquerda/topo (8 col), painel de seleção de séries + stats à
  direita (4 col). Stats como grade de métricas (IAE/ITAE/ISE/MSE/σ/TV/variabilidade) em cards
  pequenos mono tabular.
- **MultiTrend** §5.9: cores PV/SP/CO do tema, variação tonal por loop; decimação min/max; janela
  deslizante. Export: botão claro → estado de "gerando…" → download (sem bloquear UI).
- **Beleza:** stats tratadas como mostrador de bancada; trend domina a tela.

### Fatia 5 — Simulador (`simulator_page`)
- **Banner de modo simulação** §5.11 (faixa diag dessaturada) — inegociável para não confundir com
  processo real. Painel de controles (preset, sliders, distúrbio, output/modo, auto-toggles) à
  esquerda; `RealtimeTrend` do twin à direita mostrando a resposta em tempo real.
- **Beleza:** sliders com leitura mono ao lado; botão "Injetar distúrbio" produz um degrau visível
  no trend — o feedback é a recompensa.

### Fatia 6 — Executive Dashboard (`executive_dashboard`)
- **Bento de KPIs** §5.10 (grade-quebra editorial permitida aqui: um KPI hero maior + secundários).
  Saúde de loops como grade compacta de pontos de estado (§2.6) + % em AUTO. Janela de período
  (segmented `[ 1h | 8h | 24h | 7d ]`). Recomendações de sintonia por loop em lista com a tag,
  Δ proposto e botão que **leva ao faceplate** (não escreve daqui sem confirmação).
- **Beleza:** este é o único lugar com hierarquia "hero" — um número grande domina; cor só quando KPI
  fora de meta. Continua ISA-safe porque o significado de alarme não muda.

### Fatia 7 — Settings + Conexão + Projetos (`settings_page`, `connection_page`, welcome)
- **Settings:** form em duas colunas, seções com cabeçalho hairline; toggles e selects do design
  system. Inclui login do administrador único + troca de senha opcional (sistema
  **single-user / sem RBAC** — sem gestão de usuários nem tiers de papel; ver Fatia 7 spec).
- **Conexão OPC:** campo de endpoint + `[ Connect | Disconnect ]` + **tag browser** (árvore
  navegável `GET /browse` + busca) — árvore com indentação e ícones de nó; seleção popula o
  controlador. A **aquisição é contínua** — sem controle de start/stop de aquisição.
- **Projetos `.spid`:** **Welcome pós-login** = lista de projetos do backend em cards/linhas (nome,
  data, nº de loops) + `[ Novo ] [ Importar (upload) ] [ Abrir ]`; ações download/delete por item.
  Upload com dropzone + barra de progresso. **Nunca** exibir credenciais (users vivem em `users.db`).
- **Beleza:** admin não precisa ser feio — mesma grade, mesmo par tipográfico, tabelas alinhadas.

### Fatia 8 — Temas + Faceplate (`themes/*`, `faceplate`, `analog_bar`)
- **Seletor de tema:** controle no menu (5 opções: Dark Room, ISA-101, MD3 dark, MD3 light, Ocean) →
  seta `data-theme` no `<html>`, persiste em `localStorage`. Preview ao vivo (a tela inteira troca).
- **Faceplate** §5.3 — paridade visual/funcional; é a vitrine do design system (PV grande tabular,
  barras instrumentadas, toggles de modo/IA, apply-tuning).
- **Aceitação visual:** snapshots por tema nos breakpoints 1024/1440/1920 + a **matriz de contraste
  §8.4** como gate. Drift de identidade evitado porque tudo deriva dos tokens §2 (fonte: os 3 docs).
- **Beleza:** o faceplate no tema ISA-101 deve parecer um instrumento de verdade; no MD3 light,
  limpo e arredondado; no Ocean, marca presente sem quebrar a regra de cor.

---

## 11. Resumo de não-fazer (anti-template + anti-ISA-violação)
- Sem hero de marketing, sem gradiente-blob, sem "número grande + label + acento gradiente" como
  resposta padrão (só KPI hero no exec, justificado).
- Sem sombras/bevels/3D (exceto sobreposição tonal); sem verde para "ok"; sem cor em estado normal
  (salvo as 3 cores de trend, que são função).
- Sem sparklines em cards de loop. Sem branco puro de fundo/texto. Sem padding uniforme em tudo —
  ritmo intencional. Sem animar layout. Sem cor como único canal de significado.
```
