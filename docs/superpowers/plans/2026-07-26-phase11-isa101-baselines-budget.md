# Phase 11 — ISA-101 Retokenisation, Visual Baselines, and Budget Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finalize ISA-101 on the shared token vocabulary without changing its appearance, replace obsolete visual baselines with the 13-theme matrix, and close every quality gate.

**Architecture:** A mechanical old-token→shared-token map replaces phase-2 interim aliases. Computed-style fixtures prove values, then Playwright records the terminal visual baseline set. No feature behavior changes.

**Tech Stack:** Tailwind v4 CSS tokens, Vitest/jsdom, Playwright visual snapshots, Vite bundle gate.

## Global Constraints

- ISA-101 visual output remains unchanged.
- ISA-101 keeps gray-until-abnormal PV and solid blue SP.
- Final baseline set: Recorder/Phosphor/ISA-101 × 320/768/1024/1440 plus one faceplate = 13.

---

### Task 1: Document and Apply 5→3 Surface Mapping

**Files:**
- Create: `packages/smart_pid_web/docs/isa101-token-mapping.md`
- Modify: `packages/smart_pid_web/src/theme/themes.css`
- Create: `packages/smart_pid_web/src/theme/isa101Mapping.test.ts`

**Interfaces:** The authoritative old hex values come from the pre-rewrite ISA-101 theme at the phase-2 parent commit. Do not infer colors.

- [ ] **Step 1: Write the complete mapping artifact**

The document contains these rows, each with the exact old hex read from git and its final shared token:

| Old token | Final token | Rule |
|---|---|---|
| `--surface-base` | `--bg` | page/background |
| `--surface` | `--surface` | cards/panels |
| `--surface-container` | `--surface` | same visual value retained in component mapping |
| `--surface-container-high` | `--surface` | raised panels collapse to surface |
| `--field-bg` | `--surface-sunk` | inputs/chart wells |
| `--divider` | `--rule` | decorative lines |
| `--border` | `--rule` | ordinary boundaries |
| `--border-strong` | `--rule-strong` | control boundaries |
| `--text-primary` | `--text` | primary text |
| `--text-secondary` | `--text-soft` | secondary text |
| `--text-disabled` | `--text-disabled` | disabled text |
| `--accent` | `--accent` | interactive accent |
| `--focus-ring` | `--focus-ring` | focus |
| `--alarm-critical` | `--alarm-crit` | critical |
| `--alarm-warning` | `--alarm-warn` | warning |
| `--alarm-advisory` | `--alarm-adv` | advisory |
| `--alarm-log` | `--alarm-log` | log |
| `--trend-pv` | `--trace-pv` | ISA abnormal-aware PV |
| `--trend-sp` | `--trace-sp` | solid blue ISA SP |
| `--trend-co` | `--trace-co` | CO |
| `--chart-grid` | `--trend-grid` | grid |
| `--chart-axis` | `--trend-axis` | axis |
| `--chart-bg` | `--trend-bg` | chart well |
| `--bar-track` | `--bar-track` | bar track |
| `--bar-fill` | `--bar-fill` | bar fill |
| `--bar-marker` | `--bar-marker` | marker |

- [ ] **Step 2: Write computed-style equivalence test**

```ts
for (const [token, expected] of Object.entries(ISA101_EXPECTED)) {
  expect(getComputedStyle(root).getPropertyValue(token).trim()).toBe(expected);
}
expect(buildUplotTheme(root).spDash).toEqual([]); // solid ISA SP
```

`ISA101_EXPECTED` includes every §6.4 token and exact recorded value; no `/* interim */` remains.

- [ ] **Step 3: Run and commit**

Run: `npm run test -- src/theme/isa101Mapping.test.ts src/theme/tokenResolve.test.ts`
Expected: PASS.

```bash
git add packages/smart_pid_web/docs/isa101-token-mapping.md packages/smart_pid_web/src/theme
git commit -m "feat(web): finalize ISA-101 shared token mapping"
```

### Task 2: Delete the 21 Obsolete Baselines

**Files:** Delete exactly:

- `e2e/themes.spec.ts-snapshots/dashboard-ocean-{320,768,1024,1440}-linux.png`
- `e2e/themes.spec.ts-snapshots/dashboard-md3-dark-{320,768,1024,1440}-linux.png`
- `e2e/themes.spec.ts-snapshots/dashboard-md3-light-{320,768,1024,1440}-linux.png`
- `e2e/themes.spec.ts-snapshots/dashboard-dark-room-{320,768,1024,1440}-linux.png`
- `e2e/themes.spec.ts-snapshots/dashboard-isa101-{320,768,1024,1440}-linux.png`
- `e2e/faceplate.spec.ts-snapshots/faceplate-default-linux.png`

- [ ] **Step 1: Remove all 21 files after the functional suite is green**
- [ ] **Step 2: Assert no orphan theme names remain**

Run: `grep -R -E 'ocean|md3-dark|md3-light|dark-room' e2e --include='*.spec.ts'`
Expected: no matches except an explicit stored-value migration test.

### Task 3: Generate the 13 Final Baselines

**Files:** Create:
- `dashboard-recorder-{320,768,1024,1440}-linux.png`
- `dashboard-phosphor-{320,768,1024,1440}-linux.png`
- `dashboard-isa101-{320,768,1024,1440}-linux.png`
- `faceplate-default-linux.png`

- [ ] **Step 1: Freeze visual nondeterminism**

In the visual tests disable animations/transitions, seed deterministic REST/WS timestamps, use monotonic `seq`, and wait for `document.fonts.ready` plus chart render.

- [ ] **Step 2: Regenerate dashboard matrix**

Run: `npm run test:e2e -- e2e/themes.spec.ts --update-snapshots`
Expected: 12 dashboard PNGs and no obsolete theme PNG.

- [ ] **Step 3: Regenerate faceplate baseline**

Run: `npm run test:e2e -- e2e/faceplate.spec.ts --update-snapshots`
Expected: one `faceplate-default-linux.png`.

- [ ] **Step 4: Commit snapshots separately**

```bash
git add packages/smart_pid_web/e2e
git commit -m "test(web): replace visual baselines for three themes"
```

### Task 4: Budget and Full Acceptance Gate

**Files:**
- Modify only if measured output changed legitimately: `packages/smart_pid_web/bundle-baseline.json`

- [ ] **Step 1: Verify bundle and font budget**

Run: `npm run build:budget`
Expected: entry JS/CSS remain within the existing gate and total `dist/assets/*.woff2` ≤160 KB. Update baseline only to measured current values, never to hide a regression.

- [ ] **Step 2: Run all frontend gates**

Run: `npm run test && npm run typecheck && npm run lint && npm run test:e2e`
Expected: all 14 E2E specs (13 retained + `user-role`) PASS.

- [ ] **Step 3: Verify exact visual inventory**

Run: `find e2e -path '*snapshots/*.png' -type f | sort`
Expected: exactly the 13 names from Task 3.

- [ ] **Step 4: Commit terminal gate**

```bash
git add packages/smart_pid_web/bundle-baseline.json
git commit -m "chore(web): close rewrite quality gates"
```

## Interfaces exported (for later phases)

Terminal phase: no new runtime interface. Durable artifact: `packages/smart_pid_web/docs/isa101-token-mapping.md`; final visual inventory is exactly 13 PNGs.
