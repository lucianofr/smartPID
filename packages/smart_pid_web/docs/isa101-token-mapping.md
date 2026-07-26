# ISA-101 token mapping — 5→3 surface ladder onto the §6.4 shared vocabulary

**Status:** final (phase 11). Superseded the phase-2 interim block in
`src/theme/themes.css`.

Every hex below is the **pre-rewrite** `[data-theme='isa101']` value read verbatim from
`git show ca0a6f6:packages/smart_pid_web/src/theme/themes.css` — `ca0a6f6` is the parent of
`38005e9` ("delete legacy src, scaffold rewrite shell"), i.e. the last commit where the
original ISA-101 palette was live. The three `--trend-*-width` values come from the same
commit's `src/theme/tokens.css` `:root`. **No color is inferred.**

The table is executable: `src/theme/isa101Mapping.test.ts` holds the same old palette, the
same old→new edges and the same final values, and asserts them against
`getComputedStyle()` under `[data-theme="isa101"]`. If this document and the CSS ever
disagree, that test fails.

## Why a mapping was needed

§6.4 is normative: **all three themes share one token vocabulary**, and components consume
only those names. The old ISA-101 palette had a 5-step surface ladder
(`--surface-base`-less: `--bg` → `--surface` → `--surface-container` →
`--surface-container-high` → `--field-bg`) and its own line/text/alarm names. v2 collapses
that to 3 surfaces (`--bg` / `--surface` / `--surface-sunk`). ISA-101's **visual output is
unchanged**; its CSS is not.

Verified invariant (`isa101Mapping.test.ts` → *"all three themes declare the identical token
vocabulary"*): `recorder`, `phosphor` and `isa101` each declare exactly the same 41 custom
properties, and `CONTRACT_TOKENS` covers all of them plus the three `:root` type tokens. A
component styled `var(--surface)` therefore renders correctly under every theme.

## The mapping

| Old token | Old hex | Final token | Rule |
|---|---|---|---|
| `--bg` | `#1E1E1E` | `--bg` | page/background |
| `--surface` | `#2D2D30` | `--surface` | cards/panels |
| `--surface-container` | `#2D2D30` | `--surface` | identical hex — absorbed, no visual change |
| `--surface-container-high` | `#333337` | `--surface` *(panels)* / `--selection` *(the raise)* | see **Collapse 1** |
| `--field-bg` | `#252526` | `--surface-sunk` | inputs/chart wells |
| `--border` | `#454548` | `--rule` | ordinary boundaries |
| `--divider` | `#3A3A3D` | `--rule` | decorative lines — see **Collapse 2** |
| `--border-strong` | `#57575B` | `--rule-strong` | control boundaries |
| `--text` | `#E0E0E0` | `--text` | primary text |
| `--text-secondary` | `#ABABAB` | `--text-soft` | secondary text |
| `--text-disabled` | `#666666` | `--text-disabled` | disabled text |
| `--focus-ring` | `#C8C8C8` | `--focus-ring` | focus |
| `--border-strong` | `#57575B` | `--accent` | see **Accent** |
| `--text-disabled` | `#666666` | `--accent-hover` | see **Accent** |
| `--border` | `#454548` | `--accent-sunk` | see **Accent** |
| `--surface-container-high` | `#333337` | `--accent-soft` | the old primary-button fill |
| `--on-alarm` | `#FFFFFF` | `--on-accent` | the palette's only light foreground |
| `--alarm-critical` | `#FF3333` | `--alarm-crit` | critical |
| `--alarm-critical-bg` | `#3A0E0E` | `--alarm-crit-bg` | critical row tint |
| `--alarm-warning` | `#FF8800` | `--alarm-warn` | warning |
| `--alarm-warning-bg` | `#3A2200` | `--alarm-warn-bg` | warning row tint |
| `--alarm-diag` | `#AA55FF` | `--alarm-adv` | advisory (`.sev-advisory` used `--alarm-diag`) |
| `--alarm-diag-bg` | `#260A3A` | `--alarm-adv-bg` | advisory row tint |
| `--text-secondary` | `#ABABAB` | `--alarm-log` | log — see **Collapse 3** |
| `--on-alarm` | `#FFFFFF` | `--on-alarm` | foreground on severity fills |
| `--state-running` | `#9A9A9A` | `--state-running` | gray, never green |
| `--state-stopped` | `#ABABAB` | `--state-stopped` | |
| `--state-error` | `#FF3333` | `--state-error` | |
| `--state-oos` | `#666666` | `--state-oos` | |
| `--trend-pv` | `#E0E0E0` | `--trace-pv` | ISA gray PV |
| `--trend-sp` | `#33AAFF` | `--trace-sp` | ISA blue SP |
| `--trend-co` | `#FFB000` | `--trace-co` | CO |
| `--trend-grid` | `#3A3A3D` | `--trend-grid` | grid |
| `--trend-axis` | `#57575B` | `--trend-axis` | axis |
| `--trend-bg` | `#252526` | `--trend-bg` | chart well |
| `--trend-pv-width` | `1.5` | `--trend-pv-width` | `1.5px` — gained a CSS unit |
| `--trend-sp-width` | `1.5` | `--trend-sp-width` | `1.5px` |
| `--trend-co-width` | `1.5` | `--trend-co-width` | `1.5px` |
| `--bar-track` | `#252526` | `--bar-track` | bar track |
| `--bar-fill` | `#9A9A9A` | `--bar-fill` | bar fill |
| `--bar-marker` | `#CCCCCC` | `--bar-marker` | marker |

### Collapse 1 — `--surface-container-high` (`#333337`)

Two different roles wore this hex. As a **raised panel** it collapses to `--surface`
(`#2D2D30`) per §6.4; the ~2% luminance step it carried was decoration, and dropping it is
the intended 5→3 simplification. As the **hover / selected / open-menu raise** it was
semantic, so that role survives verbatim on `--selection`:
`NavRail.LINK_ACTIVE` was `bg-surface-container-high`, and `dropdown-menu` items were
`focus:bg-surface-container-high data-[state=open]:bg-surface-container-high` — the exact
role `data-[highlighted]:bg-selection` plays in the v2 `Select` / `DropdownMenu`. `#E0E0E0`
on `#333337` is 9.53:1.

### Collapse 2 — `--border` + `--divider` → `--rule`

Two hexes, one name. Arbitrated by usage weight in the pre-rewrite tree:

| Old class | Uses | v2 counterpart | Uses |
|---|---|---|---|
| `border-border` | 65 | `border-rule` | 60 |
| `border-border-strong` | 27 | `border-rule-strong` | 27 |
| `border-divider` + `bg-divider` | 10 | — | — |

`--rule` therefore takes `#454548` (old `--border`). The residual delta is the 10 former
divider hairlines, which render one step lighter (`#3A3A3D` → `#454548`, ΔL* ≈ 3). The
divider hex is **not** lost: `--trend-grid` keeps `#3A3A3D` unchanged, which is where it did
the most visible work.

> The phase-11 plan's table listed the page-background row as `--surface-base` → `--bg`.
> No `--surface-base` token ever existed (`git grep -- '--surface-base' ca0a6f6` is empty);
> the old name was plain `--bg`. The plan's stated authority — "the exact old hex read from
> git" — is what this table follows.

### Collapse 3 — the fourth severity

The domain has four severities (`CRITICAL/WARNING/ADVISORY/LOG`, `features/alarms/severity.ts`)
but v1 styled only three: `index.css` had `.sev-critical`, `.sev-warning` and
`.sev-advisory` rules and **no `.sev-log`** — §6.4's "`sev-log` resolved to nothing".

LOG was not colorless, though. Its glyph is the dot (`GLYPH.LOG = 'dot'`) and
`.sev-icon--dot { color: var(--text-secondary) }`. So `--alarm-log: #ABABAB` is the old LOG
color, not a new invention — and it matches the pattern in the other two themes, where
`--alarm-log` equals `--text-soft` (Recorder `#5A6875`, Phosphor `#8894A3`).

The old `--alarm-info: #33AAFF` occupied the unused fourth slot. It is **not** carried into
`--alarm-log`: it is the same blue as the ISA SP trace, and §6.3 forbids an alarm color
doubling as a trace color. Its hex survives on `--trace-sp`.

### Accent — ISA-101 has no accent hue

The old palette defined no `--accent`; ISA-101 reserves saturated color for abnormal
conditions, so interactive chrome was neutral. The old primary control was
`bg-surface-container-high border-border-strong text-text` (`LoginPage.tsx:100`). The v2
accent family is that same neutral ladder:

| Token | Value | Source |
|---|---|---|
| `--accent` | `#57575B` | old `--border-strong` — the boundary that carried the affordance |
| `--accent-hover` | `#666666` | old `--text-disabled`, the next neutral step up |
| `--accent-sunk` | `#454548` | old `--border`, the next neutral step down |
| `--accent-soft` | `#333337` | old `--surface-container-high` — the old button fill |
| `--on-accent` | `#FFFFFF` | old `--on-alarm` (7.19:1 on `--accent`) |

`--accent` takes the *strongest* neutral rather than the old fill because in v2 the token
also drives `text-accent`, `border-accent` and the trend's AI-intervention ticks
(`uplotTheme.accent`). At `#333337` those would be invisible on `--surface` (1.1:1) and on
`--trend-bg` (1.2:1); `#57575B` keeps them readable while staying inside the old palette.
The old *fill* is preserved exactly on `--accent-soft`.

## Values with no pre-rewrite equivalent

| Token | Value | Justification |
|---|---|---|
| `--scrim` | `rgba(0, 0, 0, 0.6)` | Byte-equivalent to the old hard-coded `bg-black/60` dialog scrim (`__lintfixtures__/scrim-allowed.tsx`, `isa101-guard.test.ts` "sanctioned dialog scrim"). Promoted from a magic class to a token. |
| `--trend-sp-dash` | `none` | New in phase 11. §6.3 requires ISA-101 to keep a **solid** blue SP while Recorder/Phosphor use dashed graphite, but v1 and the phase-2 rewrite both hard-coded `dash: [6, 4]` in `buildUplotTheme` for every theme. The dash pattern is now a token (`6 4` for Recorder/Phosphor, `none` for ISA-101) and `readTrendTokens` parses it. This is the one place where phase 11 changes ISA-101 pixels — it *restores* the documented rule rather than preserving the bug. |

## Old tokens with no new home

Four names disappear without a dedicated target, each deliberately:

- `--surface-container` (`#2D2D30`) — byte-identical to `--surface`; pure duplication.
- `--divider` (`#3A3A3D`) — folded into `--rule` (Collapse 2); hex retained on `--trend-grid`.
- `--alarm-info` (`#33AAFF`) — unused fourth severity slot (Collapse 3); hex retained on `--trace-sp`.
- `--text-on-alarm` (`#1E1E1E`) — defined but never referenced. The old app painted
  foregrounds on severity fills with `--on-alarm` (`toast.tsx`:
  `bg-alarm-critical text-on-alarm`), so `--on-alarm: #FFFFFF` is the faithful carry-over.

`isa101Mapping.test.ts` asserts this orphan list exactly, so a future edit cannot quietly
drop a fifth token.

## Contrast — why ISA-101 is outside the WCAG gate

`themeContrast.ts` gates `recorder` and `phosphor` only (`GateThemeId`). ISA-101 is a
**preserved legacy palette**: re-verifying it to WCAG would require changing its values,
which the phase-11 constraint forbids. Measured values for the record:

| Pair | Ratio | |
|---|---|---|
| `--text` on `--surface` / `--bg` / `--surface-sunk` | 10.40 / 12.63 / 11.60 | pass |
| `--text-soft` on `--surface` | 5.98 | pass |
| `--text` on `--selection` | 9.53 | pass |
| `--on-accent` on `--accent` / `--accent-hover` | 7.19 / 5.74 | pass |
| `--focus-ring` on `--bg` / `--surface` | 9.96 / 8.21 | pass |
| traces PV / SP / CO on `--trend-bg` | 11.60 / 6.08 / 8.36 | pass |
| `--bar-fill` / `--bar-marker` on `--bar-track` | 5.44 / 9.54 | pass |
| severity on its own tint bg (crit/warn/adv) | 4.62 / 6.23 / 4.59 | pass |
| `--rule-strong` on `--surface` | 1.91 | **below the 3:1 non-text floor** |
| `--on-alarm` on `--alarm-crit` / `-warn` / `-adv` / `-log` | 3.64 / 2.39 / 3.85 / 2.30 | **below 4.5:1** |

Both failures are inherited verbatim from the pre-rewrite theme and are the reason
Recorder is the default (§6.8). Operators who need a compliant dark theme should use
Phosphor.
