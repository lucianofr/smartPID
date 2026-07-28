import { Activity, BrainCircuit, Gauge, Target, type LucideIcon } from 'lucide-react';
import { cn } from '@/lib/utils';

export interface KpiBandProps {
  /** Loops the backend is currently monitoring. */
  loops: number;
  /** Of those, how many have an AI optimizer running. */
  aiActive: number;
  /** Pre-formatted — the band never does unit or locale work. */
  variability: string;
  /** Pre-formatted currency figure. */
  savings: string;
}

interface Cell {
  readonly icon: LucideIcon;
  readonly caption: string;
  /** Hairline between this cell and the next: none on the last of a row. */
  readonly divider: string;
}

/**
 * Order is the operator's reading order: how much am I watching, how much is
 * the optimizer touching, how well is it holding, what did that buy.
 *
 * `divider` encodes both layouts at once. Under `md` the band is a 2x2 grid, so
 * only the left column (0, 2) carries a rule; from `md` it is a single row of
 * four, so 0, 1 and 2 do and the last never does.
 */
const CELLS: readonly Cell[] = [
  { icon: Gauge, caption: 'malhas monitoradas', divider: 'border-r' },
  { icon: BrainCircuit, caption: 'em otimização ativa por IA', divider: 'md:border-r' },
  { icon: Activity, caption: 'variabilidade média', divider: 'border-r' },
  { icon: Target, caption: 'economia estimada', divider: '' },
];

/**
 * The band is dark under every theme (`--kpi-band` is a brand-ink gradient in
 * all six), so its own ink cannot come from `--text*` — those flip with the
 * workspace and would be near-black on navy under the light palettes. Both
 * inline values below are derived from brand tokens that are guaranteed light
 * on that ground, so they still re-resolve with [data-theme].
 */
const TILE_TINT = { backgroundColor: 'color-mix(in srgb, var(--brand-accent) 15%, transparent)' };
const HAIRLINE = { borderColor: 'color-mix(in srgb, var(--brand-accent-soft) 20%, transparent)' };

/**
 * The navy hero band under the shell header (design direction 1a).
 *
 * Deviation from the mock, noted deliberately: 1a paints the first two figures
 * white and the last two amber. There is no white token in the §6.4 contract
 * and `--on-accent` is navy under optimizer-dark, so all four figures take
 * `--brand-accent-soft`. The hierarchy the mock got from the colour split is
 * carried by order and caption instead.
 *
 * The figures use the display face rather than `.numeric`. src/index.css
 * reserves the display face away from numerals because tabular alignment
 * matters for live PV/SP/CO columns; these are static summary figures in
 * separate cells with nothing to align against, and the display face is what
 * makes the band read as a hero rather than a fifth readout row.
 */
export function KpiBand({ loops, aiActive, variability, savings }: KpiBandProps) {
  const values = [String(loops), String(aiActive), variability, savings];

  return (
    <div
      role="group"
      aria-label="Indicadores gerais"
      data-testid="kpi-band"
      style={{ backgroundImage: 'var(--kpi-band)' }}
      className={cn(
        'grid shrink-0 grid-cols-2 items-center gap-y-4 px-4 py-4.5 md:grid-cols-4 md:px-7',
        // Short viewport (<=820px tall): collapse to design direction 1c's
        // compact treatment. The band is a summary and the faceplate is
        // operational, so on a 768px-tall screen the band gives its vertical
        // budget back rather than pushing the rail into a scroll
        // (e2e/responsive.spec.ts asserts the rail never scrolls).
        '[@media(max-height:820px)]:gap-y-2 [@media(max-height:820px)]:py-1.5',
      )}
    >
      {CELLS.map((cell, index) => {
        const Icon = cell.icon;
        return (
          <div
            key={cell.caption}
            style={cell.divider === '' ? undefined : HAIRLINE}
            className={cn('flex min-w-0 items-center gap-3.5 px-0 md:px-5.5', cell.divider)}
          >
            {/* The tile is the band's decoration, so it is the first thing to
                go when vertical budget is scarce. */}
            <span
              aria-hidden="true"
              style={TILE_TINT}
              className="flex h-[38px] w-[38px] shrink-0 items-center justify-center rounded-control [@media(max-height:820px)]:hidden"
            >
              <Icon size={19} className="text-brand-accent-soft" aria-hidden="true" />
            </span>
            <div className="min-w-0">
              <div className="type-display text-2xl font-bold leading-none text-brand-accent-soft [@media(max-height:820px)]:text-lg">
                {values[index]}
              </div>
              <div className="mt-1.5 truncate text-2xs uppercase tracking-caps text-brand-accent-soft opacity-70 [@media(max-height:820px)]:mt-0.5">
                {cell.caption}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

// Mount point: DashboardPage renders this directly under the shell header and
// above the loop rail. Owned by the DashboardPage agent — not wired here.
