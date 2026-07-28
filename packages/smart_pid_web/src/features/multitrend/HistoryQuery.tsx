import { useId, useState } from 'react';
import type { TelemetryFrame } from '@/api/types';
import { Button } from '@/components/Button';
import { EmptyState, ErrorState, LoadingState } from '@/components/MissingState';
import { cn } from '@/lib/utils';
import { MultiTrendChart } from './MultiTrendChart';
import { historySeries, historyWindow, HISTORY_UNITS, type HistoryUnit, type HistoryWindow } from './useHistory';

/**
 * Duration-based history replay (§6.8). The window is `Janela` × `Unidade`
 * ending now; the request never fires on keystroke, only on
 * `Carregar histórico` — a half-typed duration is not a question.
 */

const CONTROL = cn(
  'min-h-11 rounded-control border border-rule-strong bg-surface-sunk px-2 text-sm text-text',
  'outline-none focus-visible:ring-2 focus-visible:ring-focus-ring',
);

const UNIT_LABEL: Record<HistoryUnit, string> = {
  segundo: 'Segundos',
  minuto: 'Minutos',
  hora: 'Horas',
};

export interface HistoryQueryProps {
  /** null = no loop selected; the form cannot be submitted. */
  controllerId: number | null;
  frames: readonly TelemetryFrame[];
  count: number;
  isPending: boolean;
  isError: boolean;
  /** Distinguishes "not asked yet" from "asked, nothing there". */
  hasQueried: boolean;
  onLoad(window: HistoryWindow): void;
}

export function HistoryQuery({
  controllerId,
  frames,
  count,
  isPending,
  isError,
  hasQueried,
  onLoad,
}: HistoryQueryProps) {
  const amountId = useId();
  const unitId = useId();
  const [amount, setAmount] = useState(30);
  const [unit, setUnit] = useState<HistoryUnit>('minuto');
  const [pxWidth, setPxWidth] = useState(800);

  const submit = () => {
    if (controllerId === null) return;
    onLoad(historyWindow(controllerId, amount, unit));
  };

  return (
    <section
      aria-label="Histórico"
      className="flex min-w-0 flex-col gap-2 border border-rule bg-surface-sunk p-3"
    >
      <h2 className="text-2xs uppercase tracking-wider text-text-soft">Histórico</h2>
      <div className="flex flex-wrap items-end gap-2">
        <label htmlFor={amountId} className="flex flex-col gap-1 text-2xs text-text-soft">
          Janela
          <input
            id={amountId}
            type="number"
            min={1}
            max={9999}
            value={amount}
            onChange={(e) => setAmount(Number(e.target.value))}
            className={cn(CONTROL, 'numeric w-24')}
          />
        </label>
        <label htmlFor={unitId} className="flex flex-col gap-1 text-2xs text-text-soft">
          Unidade
          <select
            id={unitId}
            value={unit}
            onChange={(e) => setUnit(e.target.value as HistoryUnit)}
            className={cn(CONTROL, 'w-32')}
          >
            {HISTORY_UNITS.map((u) => (
              <option key={u} value={u}>
                {UNIT_LABEL[u]}
              </option>
            ))}
          </select>
        </label>
        <Button variant="secondary" onClick={submit} disabled={controllerId === null}>
          Carregar histórico
        </Button>
      </div>

      {isPending && hasQueried ? <LoadingState label="Carregando histórico…" bars={2} /> : null}

      {isError ? (
        <ErrorState message="Não foi possível carregar o histórico." onRetry={submit} />
      ) : null}

      {!isPending && !isError && hasQueried && frames.length === 0 ? (
        <EmptyState
          message="Sem histórico nesta janela."
          hint="Aumente a janela ou verifique se o historiador está gravando."
        />
      ) : null}

      {frames.length > 0 && controllerId !== null ? (
        <>
          <p className="numeric text-2xs text-text-soft">{count} amostras</p>
          <MultiTrendChart
            id="history"
            testId="multitrend-history-chart"
            ariaLabel={`Histórico Loop ${controllerId}`}
            series={historySeries(controllerId, frames, pxWidth)}
            onPxWidth={setPxWidth}
            height={200}
          />
        </>
      ) : null}
    </section>
  );
}
