import { describe, expect, it } from 'vitest';
import { EXEC_MODE_TITLE, UNKNOWN_MODE_TITLE } from '@/features/dashboard/modeChip';
import { CONTROLLER_MODES, type ExecutionMode } from '@/features/loop-config/types';
import { METRIC_GROUPS } from './LoopStatsCard';
import { statsLegendGroups } from './statsLegend';

describe('statsLegendGroups', () => {
  it('covers every metric label in METRIC_GROUPS with its exact title', () => {
    const groups = statsLegendGroups();
    for (const metricGroup of METRIC_GROUPS) {
      const legendGroup = groups.find((g) => g.title === metricGroup.title);
      expect(legendGroup, `missing legend group "${metricGroup.title}"`).toBeDefined();
      for (const metric of metricGroup.metrics) {
        const entry = legendGroup!.entries.find((e) => e.term === metric.label);
        expect(entry, `missing legend entry for "${metric.label}"`).toBeDefined();
        expect(entry!.description).toBe(metric.title);
      }
    }
  });

  it('describes every ControllerMode plus UNKNOWN with a non-empty description', () => {
    const modeGroup = statsLegendGroups().find((g) => g.title === 'Modo de operação');
    expect(modeGroup).toBeDefined();
    for (const mode of [...CONTROLLER_MODES, 'UNKNOWN']) {
      const entry = modeGroup!.entries.find((e) => e.term === mode);
      expect(entry, `missing legend entry for mode "${mode}"`).toBeDefined();
      expect(entry!.description.length).toBeGreaterThan(0);
    }
    const unknownEntry = modeGroup!.entries.find((e) => e.term === 'UNKNOWN');
    expect(unknownEntry!.description).toBe(UNKNOWN_MODE_TITLE);
  });

  it('describes both AI engines and both execution modes', () => {
    const groups = statsLegendGroups();
    const engineGroup = groups.find((g) => g.title === 'Motor de IA');
    expect(engineGroup!.entries.map((e) => e.term).sort()).toEqual(['FUZZY', 'RL']);
    const execGroup = groups.find((g) => g.title === 'Modo de execução');
    expect(execGroup!.entries.map((e) => e.term).sort()).toEqual(['DDC', 'SUPERVISORY']);
  });

  it('drops the term that EXEC_MODE_TITLE repeats inside its own tooltip text', () => {
    // The badge tooltip is standalone prose ("SUPERVISORY: o PID roda ..."),
    // but the legend already shows the term in its own column.
    const execGroup = statsLegendGroups().find((g) => g.title === 'Modo de execução');
    for (const entry of execGroup!.entries) {
      expect(entry.description.startsWith(`${entry.term}:`)).toBe(false);
      // Still the real text, not a hand-written fork of it.
      expect(EXEC_MODE_TITLE[entry.term as ExecutionMode]).toContain(
        entry.description.charAt(0).toLowerCase() + entry.description.slice(1),
      );
    }
  });
});
