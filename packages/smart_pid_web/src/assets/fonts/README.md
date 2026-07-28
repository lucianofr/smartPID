# Self-hosted fonts (§6.2)

| File | Family | Axes / weight | License | Source |
|---|---|---|---|---|
| archivo-latin-var.woff2 | Archivo Variable | wght 100–900 · wdth 62.5–125 · Latin | OFL 1.1 | github.com/google/fonts `ofl/archivo/Archivo[wdth,wght].ttf` |
| geist-mono-latin-400.woff2 | Geist Mono | 400 static · Latin | OFL 1.1 | npm `@fontsource/geist-mono` (record version below) |
| geist-mono-latin-500.woff2 | Geist Mono | 500 static · Latin | OFL 1.1 | npm `@fontsource/geist-mono` (record version below) |
| orbitron-latin-var.woff2 | Orbitron Variable | wght 400–900 · Latin | OFL 1.1 (`OFL-Orbitron.txt`) | github.com/google/fonts `ofl/orbitron/Orbitron[wght].ttf` |

Packed @fontsource/geist-mono version: _5.3.0_

Budget: combined ≤ 160 KB raw (woff2 is pre-compressed ≈ transfer size). Enforced
twice: `src/theme/fonts.test.ts` (source tree) and `scripts/check-bundle.mjs`
(dist output, Task 24).

Regeneration commands live in the phase-2 plan (Task 3) and are reproduced here:

    curl -L -o /tmp/Archivo-var.ttf \
      'https://raw.githubusercontent.com/google/fonts/main/ofl/archivo/Archivo%5Bwdth%2Cwght%5D.ttf'
    uvx --from 'fonttools[woff]' pyftsubset /tmp/Archivo-var.ttf \
      --unicodes='U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+2000-206F,U+2074,U+20AC,U+2122,U+2212' \
      --layout-features='*' --flavor=woff2 --output-file=archivo-latin-var.woff2

    npm pack @fontsource/geist-mono
    tar -xzf fontsource-geist-mono-*.tgz package/files/geist-mono-latin-{400,500}-normal.woff2

pt-BR coverage: U+0000-00FF includes á â ã à ç é ê í ó ô õ ú ü.
Slashed zero: applied via `font-feature-settings: 'zero' 1` (.numeric); Geist Mono
carries the `zero` feature.

Orbitron regeneration (§10.6 — the `neon` display face; same subset range as Archivo):

    node -e "const fs=require('fs');fetch('https://raw.githubusercontent.com/google/fonts/main/ofl/orbitron/Orbitron%5Bwght%5D.ttf').then(r=>r.arrayBuffer()).then(b=>fs.writeFileSync('/tmp/Orbitron-var.ttf',Buffer.from(b)))"
    uvx --from 'fonttools[woff]' pyftsubset /tmp/Orbitron-var.ttf \
      --unicodes='U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+2000-206F,U+2074,U+20AC,U+2122,U+2212' \
      --layout-features='*' --flavor=woff2 --output-file=orbitron-latin-var.woff2

The SIL OFL 1.1 text is committed as `OFL-Orbitron.txt`: redistributing the face
in a commercial product requires shipping the licence beside it.