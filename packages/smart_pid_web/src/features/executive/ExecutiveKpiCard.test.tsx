import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { TestProviders } from '@/test/providers';
import { BadActorsTable } from './BadActorsTable';
import { ExecutiveKpiBand, ExecutiveKpiCard } from './ExecutiveKpiCard';
import { rankBadActors, type AggregateKpis, type ExecutiveLoop } from './types';

const KPIS: AggregateKpis = {
  loopCount: 4,
  autoPercent: 75,
  aiCoveragePercent: 50,
  averageIae: 12.5,
  averageVariabilityRange: 0.04,
  totalTv: 8.25,
};

function loop(overrides: Partial<ExecutiveLoop> & { loopId: number }): ExecutiveLoop {
  return {
    name: `L${overrides.loopId}`,
    mode: 'AUTO',
    ai: false,
    health: 'running',
    ...overrides,
  };
}

const inRouter = (ui: React.ReactNode) => render(<TestProviders>{ui}</TestProviders>);

describe('ExecutiveKpiBand', () => {
  it('names the four buyer KPIs in pt-BR', () => {
    render(<ExecutiveKpiBand kpis={KPIS} />);
    for (const label of ['Malhas em AUTO', 'Cobertura da IA', 'IAE médio', 'Variabilidade 2σ/RANGE']) {
      expect(screen.getByText(label)).toBeVisible();
    }
    expect(screen.getByTestId('kpi-auto').querySelector('.numeric')).not.toBeNull();
  });

  it('renders each KPI in its own unit', () => {
    render(<ExecutiveKpiBand kpis={KPIS} />);
    expect(screen.getByTestId('kpi-auto')).toHaveTextContent('75.0%');
    expect(screen.getByTestId('kpi-ai')).toHaveTextContent('50.0%');
    expect(screen.getByTestId('kpi-iae')).toHaveTextContent('12.50');
    expect(screen.getByTestId('kpi-variability')).toHaveTextContent('4.0%');
  });

  it('marks variability out of target without relying on colour alone', () => {
    render(<ExecutiveKpiBand kpis={{ ...KPIS, averageVariabilityRange: 0.09 }} />);
    expect(screen.getByTestId('kpi-variability')).toHaveAttribute('data-out-of-target', 'true');
    expect(screen.getByText('Acima do alvo de 5%')).toBeVisible();
  });

  it('leaves an in-target KPI unflagged', () => {
    render(<ExecutiveKpiBand kpis={KPIS} />);
    expect(screen.getByTestId('kpi-variability')).toHaveAttribute('data-out-of-target', 'false');
  });

  it('shows an unmeasured KPI as an em dash, never as zero', () => {
    render(<ExecutiveKpiBand kpis={{ ...KPIS, averageIae: null, averageVariabilityRange: null }} />);
    expect(screen.getByTestId('kpi-iae')).toHaveTextContent('—');
    expect(screen.getByTestId('kpi-variability')).toHaveTextContent('—');
  });

  it('keeps every numeral in the tabular face', () => {
    render(<ExecutiveKpiCard label="Malhas" value="4" testId="kpi-x" />);
    expect(screen.getByText('4')).toHaveClass('numeric');
  });
});

describe('BadActorsTable', () => {
  const LOOPS = [
    loop({ loopId: 1, name: 'FIC-101', iae: 9, variabilityRange: 0.01, tv: 3 }),
    loop({ loopId: 2, name: 'TIC-202', iae: 22, variabilityRange: 0.08, tv: 7 }),
  ];

  it('puts the worst offender the ranking produced on top', () => {
    inRouter(<BadActorsTable loops={rankBadActors(LOOPS)} />);
    const tags = screen.getAllByRole('link').map((a) => a.textContent);
    expect(tags).toEqual(['TIC-202', 'FIC-101']);
  });

  it('links each row to that loop on the operational dashboard', () => {
    inRouter(<BadActorsTable loops={LOOPS} />);
    expect(screen.getByRole('link', { name: 'FIC-101' })).toHaveAttribute('href', '/?loop=1');
  });

  it('names every ranked metric', () => {
    inRouter(<BadActorsTable loops={LOOPS} />);
    for (const header of ['Malha', 'IAE', '2σ/Range', 'TV', 'Estado']) {
      expect(screen.getByText(header)).toBeVisible();
    }
    expect(screen.getByText('22.00')).toHaveClass('numeric');
    expect(screen.getByText('8.0%')).toBeVisible();
  });

  it('states the absence of scored loops instead of drawing an empty table', () => {
    inRouter(<BadActorsTable loops={[]} />);
    expect(screen.getByText('Nenhuma malha pontuada.')).toBeVisible();
    expect(screen.queryByRole('table')).toBeNull();
  });

  it('offers a retry when the ranking could not be loaded', () => {
    const onRetry = vi.fn();
    inRouter(<BadActorsTable loops={[]} isError onRetry={onRetry} />);
    fireEvent.click(screen.getByRole('button', { name: 'Tentar novamente' }));
    expect(onRetry).toHaveBeenCalled();
  });
});
