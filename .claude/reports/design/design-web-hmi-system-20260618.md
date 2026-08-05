# Design Review — Web HMI Design System (Smart PID v2)

**Data:** 2026-06-18 · **Autor:** UI Designer (frontend-design)
**Entrega:** `docs/superpowers/specs/2026-06-18-web-frontend-design-system-design.md`
**Escopo:** camada visual do web HMI React/Vite que substitui a PySide6. Additive — não altera as
8 specs de fatia.

---

## 1. Resumo do design system

- **Direção:** *Industrial-precision / control-room instrumentation* (Swiss/International aplicado a
  SCADA). Lê como premium por execução de espaço/tipo/estado — não por enfeite — e permanece ISA-101
  safe: monocromático no normal, **cor = exclusivamente anormalidade**.
- **Elemento-assinatura:** a `AnalogBar` instrumentada (escala de ticks reais, marcadores de SP e
  limites de alarme na escala, leitura numérica mono tabular com coluna decimal alinhada). É onde
  toda a ousadia foi gasta; o resto fica quieto.
- **Tipografia:** par deliberado **IBM Plex Sans + IBM Plex Mono** (numerais tabulares), com swap por
  tema (Roboto/Roboto Mono no MD3; mono-dominante no Dark Room). Escala clamp-based; regra de ouro
  `tabular-nums` em todo valor de processo.
- **Tokens:** contrato semântico único (`--bg`, `--surface`, `--alarm-critical`, `--trend-pv`…) com
  **5 paletas** completas: Dark Room, ISA-101, MD3 dark, MD3 light, Ocean — derivadas dos 3 docs de
  identidade; valores reais (não placeholders), inclusive estado de loop e cores PV/SP/CO por tema.
- **Espaço/grade/shell:** base 4px com ritmo intencional; shell = app bar 48px + nav rail 64/224px +
  alarm bar persistente 36px; dashboard de cards 280px com wrap; bento 12-col para exec/multi-trend.
- **Componentes:** AnalogBar, ControllerCard, Faceplate, RealtimeTrend (uPlot), AlarmBar/AlarmPanel,
  LoopConfigDialog + confirmação apply-tuning, Login, indicadores de status, MultiTrend,
  ExecutiveKPICard, controles do Simulator — cada um com anatomia, estado normal, estado de alarme e
  interação.
- **Interação/motion:** estados hover/focus/active/disabled padronizados; `:focus-visible` sempre;
  só `transform/opacity/clip-path`; barra anima por `scaleX`; blink de alarme só opacidade e
  desligado em `prefers-reduced-motion` (cai para peso+sublinhado).
- **Data-viz:** tema do uPlot derivado dos tokens; séries PV sólida / SP tracejada / CO eixo direito
  (distinguível sem cor); zero area-fill; decimação min/max por coluna de pixel; janela deslizante.
- **Acessibilidade:** alvos WCAG (4.5:1 texto, 3:1 não-textual), semântica ISA-101 em 3 canais
  redundantes (cor+forma+texto), `role="meter"`, `aria-live` por severidade, e uma **matriz de
  contraste cross-tema** como gate de build (§8.4 do spec).
- **Breakpoints:** desktop-first 1024/1440/1920; mobile como cortesia.

---

## 2. Top 5 lacunas de UI/design nas 8 specs de fatia (preenchidas pelo design system)

As 8 specs são fortes em *contrato* (endpoints REST, WS, critérios de aceitação, dependências) mas
quase silenciosas em *aparência*. Principais lacunas:

1. **Sem sistema de tokens nem regra de cor concreta.** Só a Fatia 8 cita "temas via CSS custom
   properties" e nomeia os arquivos de identidade — nenhuma fatia define os nomes de token, as
   5 paletas, ou a regra ISA-101 "cor = só alarme". → **Preenchido:** §2 (5 paletas completas +
   contrato de tokens + regra de estado normal monocromático).

2. **Tipografia e tratamento numérico ausentes.** Nenhuma fatia menciona fontes, escala de tipo,
   pesos, ou `tabular-nums` — crítico para um HMI cujo conteúdo primário é número de processo que
   não pode "pular". → **Preenchido:** §3 (par Plex, escala clamp, regra tabular obrigatória).

3. **Anatomia/estados visuais de componente não especificados.** As fatias citam componentes pelo
   nome (card, faceplate, alarm bar, KPI) mas não dizem geometria, estado de alarme, hover/focus,
   marcadores de SP/limite na barra, octógono vs triângulo, etc. → **Preenchido:** §5 (inventário
   com specs visuais) + §6 (estados/motion).

4. **Layout, shell e composição por tela indefinidos.** Não há shell de navegação, grade,
   bento/densidade, posição da alarm bar, side-sheet do faceplate, banner de "modo simulação", nem
   hierarquia executiva. → **Preenchido:** §4 (shell+grade) e §10 (guia por fatia, tela a tela).

5. **Acessibilidade/contraste e estilo de data-viz não tratados.** "Checar contraste por tema"
   aparece só como *risco* na Fatia 8; nenhuma fatia define alvos WCAG, redundância de cor, tema do
   uPlot, decimação, ou look da janela deslizante. → **Preenchido:** §7 (data-viz) e §8 (a11y +
   matriz de contraste cross-tema como gate de aceitação).

### Lacunas secundárias (também cobertas)
- **Apply-tuning** citado como ação, sem desenho da confirmação de escrita física → §5.3/§10-Fatia2.
- **Motion/reduced-motion** nunca mencionado em nenhuma fatia → §6.
- **Distinção simulador vs processo real** está como *risco* na Fatia 5, sem solução visual →
  banner persistente §5.11/§10-Fatia5.
- **Tag browser OPC** (árvore) e **welcome/projetos** descritos por função, sem layout → §10-Fatia7.

---

## 3. Recomendações de processo

- Tratar a **matriz de contraste §8.4** como teste automatizado (Vitest/Playwright na Fatia 8): falha
  o build se CRIT/WARN caírem abaixo do alvo em qualquer tema.
- Implementar os tokens (§2/§3/§4) já na **Fatia 0+1** (tema base), não só na Fatia 8 — assim toda
  fatia subsequente consome o design system desde o início e evita retrabalho de re-tematização.
- Cumprir a convenção do projeto (CLAUDE.md): ao implementar UI, atualizar `docs/smartPIDv2.md` e os
  `docs/identidade_visual_*.md`; este design system é a fonte da camada visual web.
```
