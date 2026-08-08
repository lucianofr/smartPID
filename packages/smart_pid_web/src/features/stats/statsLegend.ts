import type { LegendGroup } from '@/components/Legend';
import { EXEC_MODE_TITLE, UNKNOWN_MODE_TITLE } from '@/features/dashboard/modeChip';
import { METRIC_GROUPS } from './LoopStatsCard';

/**
 * Stats screen (§6.8) legend. The metric groups are a pure projection of
 * `LoopStatsCard`'s `METRIC_GROUPS` — never a second set of descriptions —
 * so a tooltip and its legend entry can never drift apart.
 */

const MODE_TITLE: Record<string, string> = {
  OOS: 'Fora de serviço: o bloco não executa',
  IMAN: 'Manual de inicialização: a saída rastreia um valor externo',
  LO: 'Local override: um intertravamento local força a saída',
  MAN: 'Manual: o operador escreve a saída',
  AUTO: 'Automático: o PID segue o setpoint local',
  CAS: 'Cascata: o setpoint vem do bloco mestre',
  RCAS: 'Cascata remota: o setpoint vem de um supervisório',
  ROUT: 'Saída remota: a saída vem de um supervisório',
  BYPASS: 'Bypass: o PID não atua sobre a saída',
  UNKNOWN: UNKNOWN_MODE_TITLE,
};

const AI_ENGINE_TITLE: Record<string, string> = {
  FUZZY: 'Otimizador por inferência fuzzy',
  RL: 'Otimizador por aprendizado por reforço',
};

export function statsLegendGroups(): readonly LegendGroup[] {
  return [
    ...METRIC_GROUPS.map((group) => ({
      title: group.title,
      entries: group.metrics.map((metric) => ({ term: metric.label, description: metric.title })),
    })),
    {
      title: 'Modo de operação',
      entries: Object.entries(MODE_TITLE).map(([term, description]) => ({ term, description })),
    },
    {
      title: 'Motor de IA',
      entries: Object.entries(AI_ENGINE_TITLE).map(([term, description]) => ({ term, description })),
    },
    {
      title: 'Modo de execução',
      // EXEC_MODE_TITLE is authored as a standalone badge tooltip, so each
      // value repeats its own term ("SUPERVISORY: o PID roda ..."). Beside a
      // term column that reads twice, so drop the prefix here rather than
      // forking the strings and letting badge and legend drift.
      entries: Object.entries(EXEC_MODE_TITLE).map(([term, title]) => {
        const prefix = `${term}: `;
        if (!title.startsWith(prefix)) return { term, description: title };
        const rest = title.slice(prefix.length);
        return { term, description: rest.charAt(0).toUpperCase() + rest.slice(1) };
      }),
    },
  ];
}
