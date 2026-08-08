import { cn } from '@/lib/utils';
import type { FuzzyInput, MembershipFunction } from './types';

/**
 * One fuzzy input variable: every membership function as a curve over its
 * domain, the crisp input as a vertical marker, and a dot on each curve the
 * crisp input activates.
 *
 * Hand-authored SVG, not uPlot — a decided constraint (see the fuzzy feature
 * plan). Both uPlot wrappers in this app (`components/Trend.tsx`,
 * `features/multitrend/MultiTrendChart.tsx`) hardwire a time x-scale, which
 * this domain-value plot is not, and `src/test/setup.ts` stubs canvas
 * `getContext` to null — jsdom cannot observe canvas geometry, so the
 * marker-position assertion this screen exists to prove would be
 * untestable. Declarative SVG children keep it plain-props-in, JSX-out and
 * fully assertable from the DOM.
 */

/** Plot area in the 0..VIEW_WIDTH × 0..VIEW_HEIGHT viewBox (SVG units). */
export const PLOT_LEFT = 34;
export const PLOT_RIGHT = 300;
export const PLOT_TOP = 20;
export const PLOT_BOTTOM = 100;
export const VIEW_WIDTH = 320;
export const VIEW_HEIGHT = 128;
const AXIS_LABEL_Y = PLOT_BOTTOM + 14;
/**
 * Membership labels alternate between two rows. Neighbouring functions can
 * peak a few domain units apart (`MF_OVS`: NONE at 0, MOD at 0.12), and a
 * single row renders those as one run-together token. Staggering separates
 * them without measuring text.
 */
const MF_LABEL_ROWS = [PLOT_TOP - 12, PLOT_TOP - 2] as const;
/** A label centred within this many SVG units of an edge is anchored to it instead. */
const EDGE_ANCHOR_MARGIN = 24;

/**
 * Clamp a domain value into `[domainMin, domainMax]`. Some membership
 * functions (e.g. `MF_E_MAX_DR` / `MF_T_REC_DR`) use a `1.0e9` right-side
 * saturation plateau; without this clamp that breakpoint would scale to a
 * coordinate far outside the viewBox instead of terminating at the plot's
 * right edge.
 */
export function clampToDomain(x: number, domainMin: number, domainMax: number): number {
  if (domainMax <= domainMin) return domainMin;
  return Math.min(domainMax, Math.max(domainMin, x));
}

/** Domain value -> SVG x, clamped into the plot area. */
export function scaleX(x: number, domainMin: number, domainMax: number): number {
  const span = domainMax - domainMin;
  if (span <= 0) return PLOT_LEFT;
  const clamped = clampToDomain(x, domainMin, domainMax);
  return PLOT_LEFT + ((clamped - domainMin) / span) * (PLOT_RIGHT - PLOT_LEFT);
}

/** Membership degree in `[0, 1]` -> SVG y (inverted: degree 1 is at the top). */
export function scaleY(degree: number): number {
  const clamped = Math.min(1, Math.max(0, degree));
  return PLOT_BOTTOM - clamped * (PLOT_BOTTOM - PLOT_TOP);
}

/** The (x, degree) breakpoints of a membership function's shape, in domain units. */
function breakpoints(mf: MembershipFunction): ReadonlyArray<readonly [number, number]> {
  const [a, b, c, d] = mf.params;
  if (mf.kind === 'trap') {
    return [
      [a, 0],
      [b, 1],
      [c, 1],
      [d, 0],
    ];
  }
  // 'tri' and any other 3-parameter kind share the same triangular shape.
  return [
    [a, 0],
    [b, 1],
    [c, 0],
  ];
}

/** SVG `points` attribute for one membership function, scaled and clamped into the plot area. */
export function mfPolylinePoints(
  mf: MembershipFunction,
  domainMin: number,
  domainMax: number,
): string {
  return breakpoints(mf)
    .map(([x, degree]) => `${scaleX(x, domainMin, domainMax)},${scaleY(degree)}`)
    .join(' ');
}

export interface MembershipFunctionPlotProps {
  input: FuzzyInput;
  className?: string;
}

export function MembershipFunctionPlot({ input, className }: MembershipFunctionPlotProps) {
  const markerX = scaleX(input.value, input.domainMin, input.domainMax);

  return (
    <figure
      className={cn(
        'flex flex-col gap-1 rounded-control border border-rule bg-surface p-2',
        className,
      )}
    >
      <figcaption className="text-2xs font-medium uppercase tracking-wider text-text-soft">
        {input.name}
      </figcaption>
      <svg
        role="img"
        aria-label={`Funções de pertinência de ${input.name}`}
        viewBox={`0 0 ${VIEW_WIDTH} ${VIEW_HEIGHT}`}
        className="h-auto w-full"
      >
        {/* Axes */}
        <line
          x1={PLOT_LEFT}
          y1={PLOT_TOP}
          x2={PLOT_LEFT}
          y2={PLOT_BOTTOM}
          className="stroke-rule-strong"
          strokeWidth="1"
        />
        <line
          x1={PLOT_LEFT}
          y1={PLOT_BOTTOM}
          x2={PLOT_RIGHT}
          y2={PLOT_BOTTOM}
          className="stroke-rule-strong"
          strokeWidth="1"
        />
        <text x={PLOT_LEFT - 4} y={PLOT_TOP + 4} textAnchor="end" className="fill-text-soft text-[9px]">
          1
        </text>
        <text x={PLOT_LEFT - 4} y={PLOT_BOTTOM} textAnchor="end" className="fill-text-soft text-[9px]">
          0
        </text>
        {/* Domain bounds, dropped when the crisp readout would sit on top of
            them. The crisp value is the one the operator came here to read. */}
        {markerX - PLOT_LEFT > EDGE_ANCHOR_MARGIN ? (
          <text x={PLOT_LEFT} y={AXIS_LABEL_Y} textAnchor="start" className="fill-text-soft text-[9px]">
            {input.domainMin.toFixed(2)}
          </text>
        ) : null}
        {PLOT_RIGHT - markerX > EDGE_ANCHOR_MARGIN ? (
          <text x={PLOT_RIGHT} y={AXIS_LABEL_Y} textAnchor="end" className="fill-text-soft text-[9px]">
            {input.domainMax.toFixed(2)}
          </text>
        ) : null}

        {/* Membership function curves */}
        {input.functions.map((mf, i) => {
          const active = mf.degree > 0;
          const peakX = scaleX(breakpoints(mf)[1]?.[0] ?? input.domainMin, input.domainMin, input.domainMax);
          // Anchor to the edge a label would otherwise overhang, so no text
          // spills outside the plot area.
          const nearLeft = peakX - PLOT_LEFT < EDGE_ANCHOR_MARGIN;
          const nearRight = PLOT_RIGHT - peakX < EDGE_ANCHOR_MARGIN;
          const labelX = nearLeft ? PLOT_LEFT : nearRight ? PLOT_RIGHT : peakX;
          const labelAnchor = nearLeft ? 'start' : nearRight ? 'end' : 'middle';
          return (
            <g key={mf.label}>
              <title>{`${mf.label} (${mf.kind}) — grau ${mf.degree.toFixed(2)}`}</title>
              <polyline
                data-testid={`mf-polyline-${mf.label}`}
                points={mfPolylinePoints(mf, input.domainMin, input.domainMax)}
                fill="none"
                className={active ? 'stroke-state-ai' : 'stroke-rule-strong'}
                strokeWidth={active ? 2 : 1}
              />
              {active ? (
                <circle
                  data-testid={`mf-degree-dot-${mf.label}`}
                  cx={markerX}
                  cy={scaleY(mf.degree)}
                  r={3}
                  className="fill-state-ai"
                />
              ) : null}
              <text
                x={labelX}
                y={MF_LABEL_ROWS[i % MF_LABEL_ROWS.length]}
                textAnchor={labelAnchor}
                className={cn('text-[9px]', active ? 'fill-state-ai font-semibold' : 'fill-text-soft')}
              >
                {active ? `${mf.label} ${mf.degree.toFixed(2)}` : mf.label}
              </text>
            </g>
          );
        })}

        {/* Crisp input marker */}
        <line
          data-testid="crisp-input-marker"
          x1={markerX}
          y1={PLOT_TOP}
          x2={markerX}
          y2={PLOT_BOTTOM}
          className="stroke-accent"
          strokeWidth="1.5"
          strokeDasharray="3 2"
        />
        <text x={markerX} y={AXIS_LABEL_Y} textAnchor="middle" className="fill-accent text-[9px] font-semibold">
          {input.value.toFixed(2)}
        </text>
      </svg>
    </figure>
  );
}
