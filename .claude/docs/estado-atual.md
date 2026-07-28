# Estado atual — 2026-07-28

## Onde estamos

Worktree: `.claude/worktrees/new-hmi-design`
Branch: **`feat/web-design-system-dashboard`**
Commit: `f835d88` — `feat(web): rebuild the frontend on the smartPID Optimizer design system`
**Ainda NÃO mergeado na main. Aguardando aprovação explícita do usuário.**

(O estado anterior deste arquivo — Task 9.4, refactor Tailwind+shadcn ISA-101,
já mergeado — está no histórico do git.)

## O que foi concluído

Importação do projeto Claude Design `smartpid-optimizer-design-system` (id
`2c37233f-a81f-4964-8914-50a2d0ca9e4c`) e reimplementação do frontend web
(`packages/smart_pid_web`) sobre ele.

O documento de design tem 3 direções para a tela principal. Implementadas:
- **1a "Painel Executivo"** (claro) para o tema `optimizer`, **novo padrão**
- **1b "Comando IA"** (escuro) para o tema `optimizer-dark`
- **1c "Sala de Controle"** (compacto) absorvido como tratamento responsivo
  da banda de KPI em viewports baixos

### Camada de tokens
- Contrato §6.4 vai de 48 para **60 tokens**: camada de marca (`--brand-ink`,
  `--brand-accent`, `--kpi-band`, ...), chip de estratégia IA (`--state-ai`),
  dot de link (`--live`) e elevação (`--shadow-card`, `--shadow-lifted`).
- Os 6 temas declaram todos (58 por bloco `[data-theme]`; `--font-ui` e
  `--font-data` ficam em `:root`).
- Geometria: quadrado para arredondado (card 10px, controle 6px, poço 8px).
- Escala tipográfica: escada HMI fixa (10/11/12/13/15/17/19.2/24/30px).

### Tipografia
- Poppins (display) + Inter (UI) + IBM Plex Mono (dados), self-hosted, subset
  latin, com as 4 licenças OFL commitadas.
- **Archivo e Geist Mono foram removidos** — os dois sistemas juntos custariam
  230 KB contra orçamento de 160 KB. Orbitron sobrevive só como face display do
  tema neon.
- Total: 120,7 KB (era 123,5).

### Componentes
Novos: `src/app/BrandMark.tsx` (StepMark + Wordmark), `src/features/dashboard/KpiBand.tsx`.
Reescritos: `AppShell`, `LoopCard`, `DashboardPage`, `Faceplate`, `TrendPanel`,
`Trend`, `AnalogBar`, `Readout`, `AiPanel`, `CardControls` e as 12 primitivas
em `src/components/`.

## Decisões tomadas (e por quê)

1. **Três cores desviam do mock**, todas na mesma direção — o mock as usa
   decorativamente, o produto as usa para carregar significado, e significado
   precisa passar em auditoria WCAG:
   `--alarm-warn` `#D8A72E` para `#8A691A`, `--trace-sp` `#A0A4A9` para
   `#7C8189`, `--live` `#00C853` para `#0E9F53` (só tema claro). Matiz preservado.
2. **Faceplate 320px, não 372px** do mock — `e2e/responsive.spec.ts` fixa
   320+-8 desde a fase 9.
3. **Botão "Exportar CSV" usa `--accent`, não `--brand-ink`** — sob
   `optimizer-dark`, `--brand-ink`, `--surface` e `--on-accent` são todos navy;
   o pareamento do mock ficava invisível.
4. **Botões `Start`/`Pause`/`Stop` mantêm os nomes** em vez de virar RUN/STOP —
   E2E vincula esses nomes exatos e o otimizador tem mesmo três estados. O
   tratamento visual de segmento foi aplicado por cima.
5. **Alvos de toque continuam >=44px** mesmo onde o mock desenha 30/34px.
6. **`Badge` tone `warn` continua contorno, não preenchido** — severidade
   ISA-101 é texto+borda+forma. Os chips de estado preenchidos entraram como
   tones novos (`ai`, `running`).
7. Adicionadas env vars `SPID_WEB_PORT` / `PLAYWRIGHT_BASE_URL` +
   `--strictPort` ao `playwright.config.ts` — torna permanente o workaround que
   a Task 9.4 fez com um config temporário.

## Bug de infraestrutura encontrado (importante)

O `node_modules` deste worktree era um **symlink** para o do checkout principal,
fazendo as duas árvores dividirem o cache de otimização de deps do Vite —
re-otimização constante e reloads no meio dos testes (E2E flaky: 5 falhas / 3
falhas / 0 falhas em três execuções seguidas). Resolvido com `npm ci` real no
worktree: 3/3 execuções estáveis, 6,4s em vez de 36s.

Relacionado: um dev server do **checkout principal** estava na porta 5173 e o
`reuseExistingServer` do Playwright o reusava, rodando a suíte inteira contra o
código errado. Sempre usar `SPID_WEB_PORT=<porta livre>` neste worktree.

## Verificação (toda verde)

| Gate | Resultado |
|---|---|
| `tsc -b` | OK |
| `eslint .` | OK |
| `vitest run` | **847/847** testes, 90/90 arquivos |
| `playwright test` | **100/100** — rodado 2x, snapshots estáveis |
| baselines visuais | 25 regeneradas (6 temas x 4 viewports + faceplate) |
| bundle | JS +3,9 KB, CSS +1,9 KB, fontes -2,8 KB — dentro do orçamento e da tolerância |

Comando E2E: `SPID_WEB_PORT=5199 ./node_modules/.bin/playwright test`

## Pendências conhecidas

1. **Cosmético**: a 900px de altura o rótulo do eixo X ("-30 min ate agora")
   fica cortado ~2px na base do card de tendência. Não quebra nenhuma asserção.
2. **KPIs "variabilidade média" e "economia estimada" mostram travessão.** As
   fontes são `GET /controllers/stats` e o log de sintonia da IA — ambos polls
   novos nessa página. Ligar exige decisão de produto sobre custo de rede.
3. **O gate de no-scroll do trilho a 1024x768 depende da banda de KPI ficar
   <=46px de altura.** Se ela crescer, o faceplate é o primeiro a quebrar.
4. `docs/design/claude-design/` só tem o `.dc.html`. Os tokens
   `spacing/elevation/patterns/styles.css` do projeto de design não foram
   baixados — o dashboard não referencia nenhum token deles (verificado por
   grep de `var(--...)`), e o MCP devolvia placeholder de compressão.

## Próximos passos sugeridos

1. Usuário revisa as 25 baselines em `e2e/*-snapshots/`.
2. Aprovar, então merge de `feat/web-design-system-dashboard` para `main`.
3. Opcional: ligar os dois KPIs vazios; polir o clip de 2px do eixo.
