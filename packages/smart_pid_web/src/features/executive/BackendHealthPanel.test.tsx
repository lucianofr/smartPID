import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { AiRoiPanel } from './AiRoiPanel';
import { BackendHealthPanel, formatUptime } from './BackendHealthPanel';
import type { AiRoi, ExecutiveLoop } from './types';

const LOOPS: ExecutiveLoop[] = [
  { loopId: 1, name: 'FIC-101', mode: 'AUTO', ai: true, health: 'running' },
  { loopId: 2, name: 'TIC-202', mode: 'OOS', ai: false, health: 'error' },
];

const ROI: AiRoi = {
  loopsCompared: 2,
  tuningEvents: 6,
  metricBefore: 8,
  metricAfter: 2,
  improvement: 0.75,
};

describe('formatUptime', () => {
  it('reads in the largest two units that matter', () => {
    expect(formatUptime(3661)).toBe('1 h 1 min');
    expect(formatUptime(90)).toBe('1 min');
    expect(formatUptime(180_061)).toBe('2 d 2 h');
  });

  it('has nothing to say about an absent uptime', () => {
    expect(formatUptime(undefined)).toBe('—');
    expect(formatUptime(Number.NaN)).toBe('—');
  });
});

describe('BackendHealthPanel', () => {
  it('renders every counter as a tabular figure', () => {
    render(<BackendHealthPanel state={{ cpu_percent: 12.4, memory_percent: 31.0, uptime_s: 3661 }} />);
    expect(screen.getByText('12.4%')).toHaveClass('numeric');
    expect(screen.getByText('31.0%')).toHaveClass('numeric');
    expect(screen.getByText('1 h 1 min')).toHaveClass('numeric');
  });

  it('shows an em dash for a counter this backend build does not publish', () => {
    render(<BackendHealthPanel state={{ uptime_s: 60 }} />);
    // /system/status carries no CPU or memory today — absent, not zero.
    expect(screen.getAllByText('—').length).toBeGreaterThanOrEqual(2);
  });

  it('keeps a healthy backend grey and promotes only the abnormal state', () => {
    const { rerender } = render(
      <BackendHealthPanel state={{ status: 'running', bus_active: true }} opc="ONLINE" />,
    );
    expect(screen.getByTestId('health-bus')).toHaveAttribute('data-abnormal', 'false');
    expect(screen.getByTestId('health-opc')).toHaveAttribute('data-abnormal', 'false');

    rerender(<BackendHealthPanel state={{ status: 'running', bus_active: false }} opc="OFFLINE" />);
    expect(screen.getByTestId('health-bus')).toHaveAttribute('data-abnormal', 'true');
    expect(screen.getByTestId('health-opc')).toHaveAttribute('data-abnormal', 'true');
  });

  it('reports mode, state and OPC reachability per loop', () => {
    render(<BackendHealthPanel state={{}} opc="ONLINE" loops={LOOPS} />);
    expect(screen.getByTestId('health-FIC-101-opc')).toHaveTextContent('ONLINE');
    expect(screen.getByTestId('health-FIC-101-state')).toHaveTextContent('Em operação');
    expect(screen.getByTestId('health-TIC-202-state')).toHaveTextContent('Falha');
    expect(screen.getByTestId('health-TIC-202')).toHaveAttribute('data-health', 'error');
  });

  it('surfaces the last system event and flags a non-INFO severity', () => {
    const { rerender } = render(
      <BackendHealthPanel
        state={{}}
        event={{ source: 'opcua', severity: 'INFO', message: 'Reconectado', timestamp: '2026-01-01T00:00:00Z' }}
      />,
    );
    expect(screen.getByTestId('health-event')).toHaveTextContent('Reconectado');
    expect(screen.getByTestId('health-event')).toHaveAttribute('data-abnormal', 'false');

    rerender(
      <BackendHealthPanel
        state={{}}
        event={{ source: 'bus', severity: 'ERROR', message: 'Barramento caiu', timestamp: '2026-01-01T00:00:00Z' }}
      />,
    );
    expect(screen.getByTestId('health-event')).toHaveAttribute('data-abnormal', 'true');
  });

  it('offers a retry when the health snapshot could not be read', () => {
    const onRetry = vi.fn();
    render(<BackendHealthPanel state={{}} isError onRetry={onRetry} />);
    expect(screen.getByRole('button', { name: 'Tentar novamente' })).toBeVisible();
    expect(onRetry).not.toHaveBeenCalled();
  });
});

describe('AiRoiPanel', () => {
  it('compares the before and after aggregates', () => {
    render(<AiRoiPanel roi={ROI} tuningEvents={6} periodLabel="Últimas 24 h" />);
    expect(screen.getByTestId('roi-before')).toHaveTextContent('8.00');
    expect(screen.getByTestId('roi-after')).toHaveTextContent('2.00');
    expect(screen.getByTestId('roi-improvement')).toHaveTextContent('75.0%');
    expect(screen.getByText('Últimas 24 h')).toBeVisible();
  });

  it('marks a regression instead of dressing it up as a gain', () => {
    render(<AiRoiPanel roi={{ ...ROI, metricAfter: 12, improvement: -0.5 }} tuningEvents={6} periodLabel="1 h" />);
    expect(screen.getByTestId('roi-improvement')).toHaveAttribute('data-out-of-target', 'true');
    expect(screen.getByTestId('roi-improvement')).toHaveTextContent('-50.0%');
  });

  it('explains insufficient data instead of showing a zeroed comparison', () => {
    render(<AiRoiPanel roi={null} tuningEvents={1} periodLabel="1 h" />);
    expect(screen.getByText('Dados insuficientes para comparar antes e depois.')).toBeVisible();
    expect(screen.queryByTestId('roi-improvement')).toBeNull();
  });

  it('counts the tunings that did happen even when it cannot score them', () => {
    render(<AiRoiPanel roi={null} tuningEvents={3} periodLabel="1 h" />);
    expect(screen.getByTestId('roi-events')).toHaveTextContent('3');
  });
});
