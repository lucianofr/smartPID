import { formatNumber } from '@/lib/format';
import { cn } from '@/lib/utils';
import type { FuzzyOutput, FuzzyRule } from './types';

/**
 * Full fuzzy rule base with fired rules highlighted, plus the aggregated
 * output singletons the fired rules produced. Every rule is rendered — this
 * is an inference trace, not a "what fired" filter — so an operator can see
 * both what fired and what almost fired.
 */

const HEADER_CELL = 'border-b border-rule px-2 py-1.5 text-left';
const NUMERIC_CELL = 'border-b border-rule px-2 py-1.5 text-right';
const STRENGTH_DECIMALS = 2;

/**
 * Fired-row tint whose intensity tracks `strength`, same `color-mix` pattern
 * as `dashboard/modeChip.ts`'s `RUNNING_TINT`: there is no `--state-ai`-soft
 * scale in the §6.4 token contract, and Tailwind's opacity modifier falls
 * back to full opacity outside `@supports color-mix`, which would paint a
 * solid purple bar over the row text.
 */
function firedTint(strength: number): string {
  const pct = Math.round(Math.min(1, Math.max(0, strength)) * 40 + 10); // 10–50%
  return `color-mix(in srgb, var(--state-ai) ${pct}%, transparent)`;
}

/** "iae=HIGH AND osc=STABLE" — condition entries in rule-base order. */
function conditionsLabel(conditions: Record<string, string>): string {
  return Object.entries(conditions)
    .map(([variable, level]) => `${variable}=${level}`)
    .join(' AND ');
}

export interface FuzzyRuleTableProps {
  rules: readonly FuzzyRule[];
  outputs: readonly FuzzyOutput[];
  className?: string;
}

export function FuzzyRuleTable({ rules, outputs, className }: FuzzyRuleTableProps) {
  return (
    <div className={cn('flex flex-col gap-3', className)}>
      <div className="min-w-0 overflow-x-auto border border-rule bg-surface-sunk">
        <table className="w-full border-collapse text-xs">
          <caption className="px-2 py-1.5 text-left text-2xs uppercase tracking-wider text-text-soft">
            Base de regras fuzzy
          </caption>
          <thead className="text-text-soft">
            <tr>
              <th scope="col" className={HEADER_CELL}>
                Regra
              </th>
              <th scope="col" className={HEADER_CELL}>
                SE
              </th>
              <th scope="col" className={HEADER_CELL}>
                ENTÃO
              </th>
              <th scope="col" className={NUMERIC_CELL}>
                Força
              </th>
            </tr>
          </thead>
          <tbody className="text-text">
            {rules.map((rule) => (
              <tr
                key={rule.index}
                data-testid={`rule-row-${rule.index}`}
                data-fired={String(rule.fired)}
                style={rule.fired ? { backgroundColor: firedTint(rule.strength) } : undefined}
              >
                <th scope="row" className={cn('numeric font-normal', HEADER_CELL)}>
                  {rule.index}
                </th>
                <td className={HEADER_CELL}>{conditionsLabel(rule.conditions)}</td>
                <td className={cn(HEADER_CELL, rule.fired && 'font-semibold text-state-ai')}>
                  {rule.output}
                </td>
                <td className={cn('numeric', NUMERIC_CELL, rule.fired && 'font-semibold text-state-ai')}>
                  {formatNumber(rule.strength, STRENGTH_DECIMALS)}
                  {rule.fired ? ' (disparada)' : ''}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="min-w-0 overflow-x-auto border border-rule bg-surface-sunk">
        <table className="w-full border-collapse text-xs">
          <caption className="px-2 py-1.5 text-left text-2xs uppercase tracking-wider text-text-soft">
            Saídas agregadas
          </caption>
          <thead className="text-text-soft">
            <tr>
              <th scope="col" className={HEADER_CELL}>
                Nível
              </th>
              <th scope="col" className={NUMERIC_CELL}>
                Centro
              </th>
              <th scope="col" className={NUMERIC_CELL}>
                Força
              </th>
            </tr>
          </thead>
          <tbody className="text-text">
            {outputs.map((output) => (
              <tr key={output.label}>
                <th scope="row" className={cn('font-normal', HEADER_CELL)}>
                  {output.label}
                </th>
                <td className={cn('numeric', NUMERIC_CELL)}>
                  {formatNumber(output.center, STRENGTH_DECIMALS)}
                </td>
                <td className={cn('numeric', NUMERIC_CELL)}>
                  {formatNumber(output.strength, STRENGTH_DECIMALS)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
