import { describe, expect, it } from 'vitest';
import type { LegendGroup } from '@/components/Legend';
import { fuzzyLegendGroups, INPUT_TERMS, LEVEL_TERMS, OUTPUT_TERMS } from './glossary';
import type { FuzzyTraceView } from './useFuzzyTrace';

function input(
  name: string,
  labels: readonly string[],
): FuzzyTraceView['inputs'][number] {
  return {
    name,
    value: 0,
    domainMin: 0,
    domainMax: 1,
    functions: labels.map((label) => ({ label, kind: 'triangle', params: [0, 0.5, 1], degree: 0 })),
  };
}

function view(overrides: Partial<FuzzyTraceView>): FuzzyTraceView {
  return {
    controllerId: 1,
    objective: 'SP_TRACKING',
    timestamp: 0,
    deltaTi: 0.1,
    inputs: [],
    rules: [],
    outputs: [],
    ...overrides,
  };
}

function group(groups: readonly LegendGroup[], title: string) {
  return groups.find((g) => g.title === title);
}

describe('fuzzyLegendGroups', () => {
  it('shows only the selected trace\'s terms — a SP_TRACKING view never leaks DISTURBANCE_REJECTION inputs', () => {
    const groups = fuzzyLegendGroups(
      view({
        inputs: [
          input('iae', ['HIGH']),
          input('osc', ['STABLE']),
          input('eff', ['SMOOTH']),
          input('ovs', ['NONE']),
        ],
        outputs: [{ label: 'R', center: -0.1, strength: 0.5 }],
      }),
    );

    const titles = groups.map((g) => g.title);
    expect(titles).toEqual([
      'Variáveis de entrada',
      'iae',
      'osc',
      'eff',
      'ovs',
      'Níveis de saída',
      'Ajuste',
    ]);
    expect(titles).not.toContain('e_max');
    expect(titles).not.toContain('pos');
    expect(titles).not.toContain('dpos');

    const inputGroup = group(groups, 'Variáveis de entrada');
    expect(inputGroup?.entries.map((e) => e.term)).toEqual(['iae', 'osc', 'eff', 'ovs']);
  });

  it('resolves HIGH differently under iae than under osc', () => {
    const groups = fuzzyLegendGroups(
      view({ inputs: [input('iae', ['HIGH']), input('osc', ['HIGH'])] }),
    );

    const iaeHigh = group(groups, 'iae')?.entries.find((e) => e.term === 'HIGH');
    const oscHigh = group(groups, 'osc')?.entries.find((e) => e.term === 'HIGH');

    expect(iaeHigh?.description).toBe(LEVEL_TERMS.iae.HIGH);
    expect(oscHigh?.description).toBe(LEVEL_TERMS.osc.HIGH);
    expect(iaeHigh?.description).not.toBe(oscHigh?.description);
  });

  it('skips a level absent from LEVEL_TERMS rather than rendering it blank', () => {
    const groups = fuzzyLegendGroups(view({ inputs: [input('iae', ['HIGH', 'UNMAPPED'])] }));

    const iae = group(groups, 'iae');
    expect(iae?.entries.map((e) => e.term)).toEqual(['HIGH']);
    expect(iae?.entries.some((e) => e.term === 'UNMAPPED')).toBe(false);
  });

  it('gives every output label an entry, including RD for a SURGE_LEVEL-shaped view', () => {
    const groups = fuzzyLegendGroups(
      view({
        objective: 'SURGE_LEVEL',
        outputs: [
          { label: 'RD', center: -0.6, strength: 0.8 },
          { label: 'M', center: 0, strength: 0.2 },
        ],
      }),
    );

    const outputs = group(groups, 'Níveis de saída');
    expect(outputs?.entries).toEqual([
      { term: 'RD', description: OUTPUT_TERMS.RD },
      { term: 'M', description: OUTPUT_TERMS.M },
    ]);
  });

  it('always carries the ΔTi adjustment entry', () => {
    const groups = fuzzyLegendGroups(view({}));
    const adjustment = group(groups, 'Ajuste');
    expect(adjustment?.entries).toEqual([
      {
        term: 'ΔTi',
        description: 'Ajuste relativo proposto para Ti: Ti_novo = Ti_atual x (1 + ΔTi)',
      },
    ]);
  });

  it('documents every declared input and output term with a non-empty description', () => {
    for (const description of Object.values(INPUT_TERMS)) {
      expect(description.length).toBeGreaterThan(0);
    }
    for (const description of Object.values(OUTPUT_TERMS)) {
      expect(description.length).toBeGreaterThan(0);
    }
  });
});
