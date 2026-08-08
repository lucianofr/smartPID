import { render, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { FuzzyRuleTable } from './FuzzyRuleTable';
import { OUTPUT_TERMS } from './glossary';
import type { FuzzyOutput, FuzzyRule } from './types';

const RULES: FuzzyRule[] = [
  { index: 0, conditions: { iae: 'LOW', osc: 'STABLE' }, output: 'M', strength: 0, fired: false },
  { index: 1, conditions: { iae: 'HIGH', osc: 'STABLE' }, output: 'R', strength: 0.8, fired: true },
  { index: 2, conditions: { iae: 'HIGH', osc: 'OSCILLATING' }, output: 'R', strength: 0.2, fired: true },
];

const OUTPUTS: FuzzyOutput[] = [
  { label: 'M', center: 0, strength: 0 },
  { label: 'R', center: -0.15, strength: 0.8 },
];

describe('FuzzyRuleTable', () => {
  it('renders every rule, including non-fired ones — never filters to fired-only', () => {
    render(<FuzzyRuleTable rules={RULES} outputs={OUTPUTS} />);
    for (const rule of RULES) {
      expect(screen.getByTestId(`rule-row-${rule.index}`)).toBeInTheDocument();
    }
    // One header row per table (rules + outputs) plus one row per data item.
    expect(screen.getAllByRole('row')).toHaveLength(RULES.length + OUTPUTS.length + 2);
  });

  it('renders the readable IF/THEN condition label from the conditions map', () => {
    render(<FuzzyRuleTable rules={RULES} outputs={OUTPUTS} />);
    expect(screen.getByText('iae=HIGH AND osc=STABLE')).toBeInTheDocument();
    expect(screen.getByText('iae=LOW AND osc=STABLE')).toBeInTheDocument();
  });

  it('marks fired rules with a non-colour affordance, not colour alone', () => {
    render(<FuzzyRuleTable rules={RULES} outputs={OUTPUTS} />);
    const fired = screen.getByTestId('rule-row-1');
    const notFired = screen.getByTestId('rule-row-0');
    expect(fired).toHaveAttribute('data-fired', 'true');
    expect(notFired).toHaveAttribute('data-fired', 'false');
    // Text marker survives with CSS stripped — the actual a11y/no-colour signal.
    expect(within(fired).getByText('0.80 (disparada)')).toBeInTheDocument();
    expect(within(notFired).queryByText(/disparada/)).not.toBeInTheDocument();
  });

  it('scales the fired-row tint by strength via a token color-mix, never a colour literal', () => {
    render(<FuzzyRuleTable rules={RULES} outputs={OUTPUTS} />);
    const strong = screen.getByTestId('rule-row-1'); // strength 0.8
    const weak = screen.getByTestId('rule-row-2'); // strength 0.2
    expect(strong.style.backgroundColor).toContain('color-mix');
    expect(strong.style.backgroundColor).toContain('var(--state-ai)');
    expect(strong.style.backgroundColor).not.toBe(weak.style.backgroundColor);
    expect(screen.getByTestId('rule-row-0').style.backgroundColor).toBe('');
  });

  it('renders the aggregated outputs as a companion summary', () => {
    render(<FuzzyRuleTable rules={RULES} outputs={OUTPUTS} />);
    expect(screen.getByText('Saídas agregadas')).toBeInTheDocument();
    expect(screen.getByText('-0.15')).toBeInTheDocument();
  });

  it('spells out each aggregated output level next to it, not only in the page legend', () => {
    // RM/R/M/A/AM are opaque on their own, and the page legend is a collapsed
    // <details> far below a 21-row rule base — the meaning has to be readable
    // where the level is shown.
    render(<FuzzyRuleTable rules={RULES} outputs={OUTPUTS} />);
    for (const output of OUTPUTS) {
      const row = screen.getByRole('row', { name: new RegExp(`^${output.label}\\b`) });
      expect(within(row).getByText(OUTPUT_TERMS[output.label])).toBeInTheDocument();
    }
  });

  it('marks an undocumented output level with an em dash instead of a blank cell', () => {
    render(<FuzzyRuleTable rules={[]} outputs={[{ label: 'ZZ', center: 0, strength: 0 }]} />);
    const row = screen.getByRole('row', { name: /^ZZ\b/ });
    expect(within(row).getByText('—')).toBeInTheDocument();
  });

  it('explains a rule THEN level on hover so the 21-row base is readable in place', () => {
    render(<FuzzyRuleTable rules={RULES} outputs={OUTPUTS} />);
    const cell = within(screen.getByTestId('rule-row-1')).getByText('R');
    expect(cell).toHaveAttribute('title', OUTPUT_TERMS.R);
  });
});
