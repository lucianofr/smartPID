import { useMemo, useState } from 'react';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/Select';
import { EmptyState, ErrorState, LoadingState } from '@/components/MissingState';
import { Legend } from '@/components/Legend';
import { activeAiStrategy } from '@/features/dashboard/LoopCard';
import { useControllers } from '@/features/dashboard/useControllers';
import { FuzzyRuleTable } from '@/features/fuzzy/FuzzyRuleTable';
import { MembershipFunctionPlot } from '@/features/fuzzy/MembershipFunctionPlot';
import { fuzzyLegendGroups } from '@/features/fuzzy/glossary';
import { useFuzzyTrace } from '@/features/fuzzy/useFuzzyTrace';
import { formatDateTime, formatNumber } from '@/lib/format';

/**
 * Fuzzy inference screen (§ fuzzy screen). Only loops actually running the
 * FUZZY engine (`activeAiStrategy`, which honours `optimization_enabled`) are
 * selectable — the roster is `GET /controllers`, same source `useControllers`
 * gives the rest of the app.
 */
export function FuzzyPage() {
  const controllers = useControllers();
  const fuzzyLoops = useMemo(
    () => (controllers.data ?? []).filter((c) => activeAiStrategy(c) === 'FUZZY'),
    [controllers.data],
  );

  // Manual pick overrides the default; unset, the first FUZZY loop wins on
  // every render — stable across polls unless the operator picks another,
  // same pattern as MultiTrendPage's `focusLoop`. A pick that LEAVES the
  // fuzzy set (optimizer switched off, engine changed to RL) falls back to
  // the default: keeping it would leave the trigger blank against a missing
  // SelectItem and go on polling a loop no longer on the list.
  const [manualId, setManualId] = useState<number | null>(null);
  const selectedId =
    manualId !== null && fuzzyLoops.some((loop) => loop.id === manualId)
      ? manualId
      : (fuzzyLoops[0]?.id ?? null);

  const trace = useFuzzyTrace(selectedId);

  if (controllers.isPending) {
    return <LoadingState label="Carregando malhas…" />;
  }
  if (controllers.isError) {
    return (
      <ErrorState message="Falha ao carregar malhas." onRetry={() => void controllers.refetch()} />
    );
  }
  if (fuzzyLoops.length === 0) {
    return (
      <EmptyState
        message="Nenhuma malha usa o motor fuzzy."
        hint="Ative o otimizador com o motor Fuzzy em uma malha para usar esta tela."
      />
    );
  }

  return (
    <section
      aria-label="Inferência fuzzy"
      className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto p-4"
    >
      <div className="flex items-center justify-between gap-2">
        <h1 className="text-sm font-medium text-text">Fuzzy</h1>
        <Select value={String(selectedId)} onValueChange={(v) => setManualId(Number(v))}>
          <SelectTrigger aria-label="Malha" className="w-48">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {fuzzyLoops.map((loop) => (
              <SelectItem key={loop.id} value={String(loop.id)}>
                {loop.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {trace.isPending ? (
        <LoadingState label="Carregando inferência fuzzy…" />
      ) : trace.notRun ? (
        <EmptyState
          message="Nenhuma execução fuzzy registrada para esta malha ainda."
          hint="O otimizador precisa estar rodando com o motor Fuzzy para gerar uma inferência."
        />
      ) : trace.isError ? (
        <ErrorState message="Falha ao carregar a inferência fuzzy." onRetry={trace.refetch} />
      ) : trace.view ? (
        <div className="flex flex-col gap-3">
          <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1 text-xs text-text-soft">
            <span>
              ΔTi: <span className="numeric text-text">{formatNumber(trace.view.deltaTi, 2)}</span>
            </span>
            <span>Executado em {formatDateTime(trace.view.timestamp)}</span>
          </div>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            {trace.view.inputs.map((input) => (
              <MembershipFunctionPlot key={input.name} input={input} />
            ))}
          </div>
          <FuzzyRuleTable rules={trace.view.rules} outputs={trace.view.outputs} />
          <Legend groups={fuzzyLegendGroups(trace.view)} />
        </div>
      ) : null}
    </section>
  );
}
