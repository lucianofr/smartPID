import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { StatsPanel } from './StatsPanel';
import { toStatsRow, type StatsRow } from './useStats';

const ROW: StatsRow = {
  loopId: 1,
  iae: 4.2,
  ise: 7.5,
  itae: 11.25,
  mse: 0.125,
  sigma: 1.5,
  tv: 33.75,
  varSp: 0.0812,
  varRange: 0.0431,
  sampleCount: 900,
};

describe('StatsPanel', () => {
  it('names every metric the stats schema carries', () => {
    render(<StatsPanel rows={[ROW]} />);
    for (const label of ['IAE', 'ISE', 'ITAE', 'MSE', 'σ', '2σ/SP', '2σ/Range', 'TV']) {
      expect(screen.getByText(label)).toBeVisible();
    }
  });

  it('renders metrics as fixed-decimal tabular figures', () => {
    render(<StatsPanel rows={[ROW]} />);
    expect(screen.getByText('4.20')).toHaveClass('numeric');
    expect(screen.getByText('0.13')).toHaveClass('numeric');
    expect(screen.getByText('33.75')).toBeVisible();
  });

  it('renders variability ratios as percentages', () => {
    render(<StatsPanel rows={[ROW]} />);
    expect(screen.getByText('8.1%')).toBeVisible();
    expect(screen.getByText('4.3%')).toBeVisible();
  });

  it('keeps one column per metric across several loops', () => {
    render(<StatsPanel rows={[ROW, { ...ROW, loopId: 2, iae: 9.5 }]} />);
    expect(screen.getAllByText('IAE')).toHaveLength(1);
    expect(screen.getByText('Loop 1')).toBeVisible();
    expect(screen.getByText('Loop 2')).toBeVisible();
    expect(screen.getByText('9.50')).toBeVisible();
  });

  it('states the absence of stats instead of rendering an empty table', () => {
    render(<StatsPanel rows={[]} />);
    expect(screen.getByText('Sem estatísticas disponíveis.')).toBeVisible();
    expect(screen.queryByRole('table')).toBeNull();
  });

  it('offers a retry when the poll failed', () => {
    const onRetry = vi.fn();
    render(<StatsPanel rows={[]} isError onRetry={onRetry} />);
    fireEvent.click(screen.getByRole('button', { name: 'Tentar novamente' }));
    expect(onRetry).toHaveBeenCalled();
  });
});

describe('toStatsRow', () => {
  it('maps the wire field names onto the panel vocabulary', () => {
    expect(
      toStatsRow(3, {
        iae: 1,
        ise: 2,
        itae: 3,
        mse: 4,
        std_dev: 5,
        total_variation: 6,
        variability_range: 0.1,
        variability_sp: 0.2,
        sample_count: 100,
      }),
    ).toEqual({
      loopId: 3,
      iae: 1,
      ise: 2,
      itae: 3,
      mse: 4,
      sigma: 5,
      tv: 6,
      varRange: 0.1,
      varSp: 0.2,
      sampleCount: 100,
    });
  });
});
