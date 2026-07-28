# Self-hosted fonts (§6.2)

The type system of the smartPID Optimizer design system. Three families, one job
each — and the rule of the house is that every number a process produces is set
in the mono face, never in the UI face.

| File | Family | Role | Weight | License | Source |
|---|---|---|---|---|---|
| poppins-latin-600.woff2 | Poppins | display | 600 static · Latin | OFL 1.1 (`OFL-Poppins.txt`) | Google Fonts `css2?family=Poppins:wght@600` |
| poppins-latin-700.woff2 | Poppins | display | 700 static · Latin | OFL 1.1 (`OFL-Poppins.txt`) | Google Fonts `css2?family=Poppins:wght@700` |
| inter-latin-var.woff2 | Inter Variable | UI | wght 400–700 · Latin | OFL 1.1 (`OFL-Inter.txt`) | Google Fonts `css2?family=Inter:wght@400..700` |
| plex-mono-latin-400.woff2 | IBM Plex Mono | data | 400 static · Latin | OFL 1.1 (`OFL-IBMPlexMono.txt`) | Google Fonts `css2?family=IBM+Plex+Mono:wght@400` |
| plex-mono-latin-600.woff2 | IBM Plex Mono | data | 600 static · Latin | OFL 1.1 (`OFL-IBMPlexMono.txt`) | Google Fonts `css2?family=IBM+Plex+Mono:wght@600` |
| plex-mono-latin-700.woff2 | IBM Plex Mono | data | 700 static · Latin | OFL 1.1 (`OFL-IBMPlexMono.txt`) | Google Fonts `css2?family=IBM+Plex+Mono:wght@700` |
| orbitron-latin-var.woff2 | Orbitron Variable | display (neon only) | wght 400–900 · Latin | OFL 1.1 (`OFL-Orbitron.txt`) | github.com/google/fonts `ofl/orbitron/Orbitron[wght].ttf` |

Combined: **120.7 KB** raw. Budget ≤ 160 KB, enforced twice — `src/theme/fonts.test.ts`
(source tree) and `scripts/check-bundle.mjs` (dist output).

## What was retired, and why

Archivo Variable (90 KB) and the two Geist Mono statics were the pre-rewrite type
system. The imported design system specifies Poppins / Inter / IBM Plex Mono, and
carrying both systems would have cost 230 KB against a 160 KB budget. Archivo and
Geist were removed rather than the new families being trimmed, because the type
system is what the design document actually specifies — the four legacy palettes
are colour skins, not typefaces.

Orbitron survives because neon's identity is carried by its lettering rather than
by its chrome (§10.6); every other theme takes the Poppins display stack.

## Weight assignments

- Poppins **700** — brand wordmark, KPI band figures. **600** — panel and section headings.
- Inter **400/500/600/700** via the variable file — all labels, buttons, prose.
- IBM Plex Mono **400** — tuning-log lines. **600** — readouts and metric values. **700** — loop tags (`FIC-001`).

Only four files are preloaded (`inter-latin-var`, `plex-mono-400`, `plex-mono-600`,
`poppins-700`): those are the faces above the fold on the dashboard. The rest arrive
under `font-display: swap`.

## Regeneration

Google Fonts serves the smallest subset it has for a given UA, so the latin block
of its `css2` response is the artifact to pull. This is the recorded command:

```bash
UA='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
# 1. read the stylesheet, 2. take the `/* latin */` @font-face block, 3. fetch its src url
curl -sS -A "$UA" 'https://fonts.googleapis.com/css2?family=Inter:wght@400..700&display=swap'
```

The latin subset covers `U+0000-00FF` plus the typographic extras, which includes
the pt-BR set: á â ã à ç é ê í ó ô õ ú ü.

Slashed zero: applied via `font-feature-settings: 'zero' 1` on `.numeric`. IBM Plex
Mono carries the `zero` feature.

Orbitron regeneration (§10.6 — the neon display face):

```bash
node -e "const fs=require('fs');fetch('https://raw.githubusercontent.com/google/fonts/main/ofl/orbitron/Orbitron%5Bwght%5D.ttf').then(r=>r.arrayBuffer()).then(b=>fs.writeFileSync('/tmp/Orbitron-var.ttf',Buffer.from(b)))"
uvx --from 'fonttools[woff]' pyftsubset /tmp/Orbitron-var.ttf \
  --unicodes='U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+2000-206F,U+2074,U+20AC,U+2122,U+2212' \
  --layout-features='*' --flavor=woff2 --output-file=orbitron-latin-var.woff2
```

All four SIL OFL 1.1 texts are committed beside the faces: redistributing them in
a commercial product requires shipping the licence. `fonts.test.ts` asserts each
file exists and names its family.
