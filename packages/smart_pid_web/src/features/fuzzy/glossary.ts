import type { LegendGroup } from '@/components/Legend';
import type { FuzzyTraceView } from './useFuzzyTrace';

/**
 * Fuzzy input variable descriptions (§ fuzzy screen legend). Covers every
 * variable any strategy can put on screen; `fuzzyLegendGroups` below narrows
 * this down to the ones the current trace actually uses.
 */
export const INPUT_TERMS: Record<string, string> = {
  iae: 'Integral do erro absoluto normalizada (0-1): quanto erro a malha acumula',
  osc: 'Indicador de oscilação (0-1): amplitude do erro confirmada por cruzamentos por zero',
  eff: 'Esforço de controle (0-1): variação total da saída por amostra',
  ovs: 'Sobressinal do último degrau de SP, como fração do degrau',
  e_max: 'Desvio máximo do erro durante o distúrbio, em fração do span',
  t_rec: 'Tempo de recuperação do distúrbio, em múltiplos da constante de tempo',
  pos: 'Posição do nível dentro da faixa de amortecimento',
  dpos: 'Velocidade e sentido do nível em relação à faixa',
  err: 'Erro absoluto normalizado pela banda de erro pequeno',
  tv: 'Variação total da saída: movimento acumulado da válvula',
};

/**
 * Membership levels, keyed by input name then level label. The same token
 * means different things under different inputs — `HIGH` is a large error
 * under `iae` and a strong oscillation under `osc` — so the legend always
 * groups levels per input rather than merging them into one flat list.
 */
export const LEVEL_TERMS: Record<string, Record<string, string>> = {
  iae: {
    LOW: 'Erro acumulado baixo',
    MED: 'Erro acumulado moderado',
    HIGH: 'Erro acumulado alto',
  },
  osc: {
    STABLE: 'Sem oscilação sustentada',
    OSC: 'Oscilação moderada',
    UNSTABLE: 'Oscilação forte, próxima de ciclo limite',
    MED: 'Oscilação moderada',
    HIGH: 'Oscilação forte',
  },
  eff: {
    SMOOTH: 'Válvula calma',
    MODERATE: 'Válvula trabalhando de forma moderada',
    EXCESS: 'Válvula em chattering',
  },
  ovs: {
    NONE: 'Sem sobressinal',
    MOD: 'Sobressinal moderado',
    HIGH: 'Sobressinal alto',
  },
  e_max: {
    LOW: 'Desvio pequeno',
    MED: 'Desvio médio',
    HIGH: 'Desvio grande',
  },
  t_rec: {
    FAST: 'Recuperação rápida',
    MED: 'Recuperação média',
    SLOW: 'Recuperação lenta',
  },
  pos: {
    SAFE: 'Nível dentro da faixa segura',
    NEAR: 'Nível próximo do limite',
    OUT: 'Nível fora da faixa',
  },
  dpos: {
    ESCAPING: 'Nível afastando-se da faixa',
    STILL: 'Nível praticamente parado',
    TOWARD: 'Nível retornando à faixa',
  },
  err: {
    SMALL: 'Erro dentro da banda considerada pequena',
    LARGE: 'Erro acima da banda',
  },
  tv: {
    LOW: 'Pouco movimento da válvula',
    MEDIUM: 'Movimento moderado da válvula',
    HIGH: 'Muito movimento da válvula',
  },
};

/** Fuzzy output levels — direction only; magnitude is the `center` column. */
export const OUTPUT_TERMS: Record<string, string> = {
  RD: 'Reduzir Ti drasticamente: ação integral muito mais agressiva',
  RM: 'Reduzir Ti muito: ação integral bem mais agressiva',
  R: 'Reduzir Ti: ação integral mais rápida',
  M: 'Manter Ti: nenhum ajuste',
  A: 'Aumentar Ti: ação integral mais lenta e amortecida',
  AM: 'Aumentar Ti muito: forte amortecimento da ação integral',
};

function uniqueLabels(functions: FuzzyTraceView['inputs'][number]['functions']): string[] {
  const seen = new Set<string>();
  const labels: string[] = [];
  for (const fn of functions) {
    if (seen.has(fn.label)) continue;
    seen.add(fn.label);
    labels.push(fn.label);
  }
  return labels;
}

/**
 * Legend groups built from the trace actually on screen, never the full
 * catalogue above. The three strategies use different inputs and different
 * level sets, so dumping every strategy's terms at once would show the
 * operator contradictory entries for tokens not even on their screen. A term
 * absent from the maps above (an input, level, or output the trace carries
 * but the legend does not yet document) is skipped rather than rendered with
 * a blank description.
 */
export function fuzzyLegendGroups(view: FuzzyTraceView): readonly LegendGroup[] {
  const inputGroup: LegendGroup = {
    title: 'Variáveis de entrada',
    entries: view.inputs.flatMap((input) => {
      const description = INPUT_TERMS[input.name];
      return description ? [{ term: input.name, description }] : [];
    }),
  };

  const levelGroups: LegendGroup[] = view.inputs.map((input) => {
    const levels = LEVEL_TERMS[input.name] ?? {};
    const entries = uniqueLabels(input.functions).flatMap((label) => {
      const description = levels[label];
      return description ? [{ term: label, description }] : [];
    });
    return { title: input.name, entries };
  });

  const outputGroup: LegendGroup = {
    title: 'Níveis de saída',
    entries: Array.from(new Set(view.outputs.map((output) => output.label))).flatMap((label) => {
      const description = OUTPUT_TERMS[label];
      return description ? [{ term: label, description }] : [];
    }),
  };

  const adjustmentGroup: LegendGroup = {
    title: 'Ajuste',
    entries: [
      {
        term: 'ΔTi',
        description: 'Ajuste relativo proposto para Ti: Ti_novo = Ti_atual x (1 + ΔTi)',
      },
    ],
  };

  return [inputGroup, ...levelGroups, outputGroup, adjustmentGroup];
}
