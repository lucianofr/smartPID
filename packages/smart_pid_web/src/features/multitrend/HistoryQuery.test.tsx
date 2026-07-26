import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { HistoryQuery, type HistoryQueryProps } from './HistoryQuery';

function frame(timestamp: string, pv: number) {
  return { timestamp, pv, sp: pv + 1, co: 40, mode: 'AUTO', status: 'GOOD' };
}

function renderQuery(overrides: Partial<HistoryQueryProps> = {}) {
  const onLoad = vi.fn();
  render(
    <HistoryQuery
      controllerId={1}
      frames={[]}
      count={0}
      isPending={false}
      isError={false}
      hasQueried={false}
      onLoad={onLoad}
      {...overrides}
    />,
  );
  return { onLoad };
}

describe('HistoryQuery', () => {
  it('requests the chosen duration for the chosen loop', () => {
    const { onLoad } = renderQuery();
    fireEvent.change(screen.getByLabelText('Janela'), { target: { value: '2' } });
    fireEvent.change(screen.getByLabelText('Unidade'), { target: { value: 'hora' } });
    fireEvent.click(screen.getByRole('button', { name: 'Carregar histórico' }));

    expect(onLoad).toHaveBeenCalledWith(expect.objectContaining({ controllerId: 1, hours: 2 }));
  });

  it('converts minutes and seconds to the same canonical hours field', () => {
    const { onLoad } = renderQuery();
    fireEvent.change(screen.getByLabelText('Janela'), { target: { value: '30' } });
    fireEvent.change(screen.getByLabelText('Unidade'), { target: { value: 'minuto' } });
    fireEvent.click(screen.getByRole('button', { name: 'Carregar histórico' }));
    expect(onLoad).toHaveBeenCalledWith(expect.objectContaining({ hours: 0.5 }));

    fireEvent.change(screen.getByLabelText('Unidade'), { target: { value: 'segundo' } });
    fireEvent.click(screen.getByRole('button', { name: 'Carregar histórico' }));
    expect(onLoad).toHaveBeenLastCalledWith(expect.objectContaining({ hours: 30 / 3600 }));
  });

  it('sends ISO bounds that span exactly the requested duration', () => {
    const { onLoad } = renderQuery();
    fireEvent.change(screen.getByLabelText('Janela'), { target: { value: '1' } });
    fireEvent.change(screen.getByLabelText('Unidade'), { target: { value: 'hora' } });
    fireEvent.click(screen.getByRole('button', { name: 'Carregar histórico' }));

    const [{ start, end }] = onLoad.mock.calls[0];
    expect(Date.parse(end) - Date.parse(start)).toBe(3_600_000);
  });

  it('cannot be submitted without a loop', () => {
    const { onLoad } = renderQuery({ controllerId: null });
    expect(screen.getByRole('button', { name: 'Carregar histórico' })).toBeDisabled();
    expect(onLoad).not.toHaveBeenCalled();
  });

  it('reports an empty window instead of a blank panel', () => {
    renderQuery({ hasQueried: true });
    expect(screen.getByText('Sem histórico nesta janela.')).toBeVisible();
  });

  it('surfaces a failed replay with a retry', () => {
    const { onLoad } = renderQuery({ hasQueried: true, isError: true });
    fireEvent.click(screen.getByRole('button', { name: 'Tentar novamente' }));
    expect(onLoad).toHaveBeenCalled();
  });

  it('plots the returned window and states its sample count', () => {
    renderQuery({
      hasQueried: true,
      count: 2,
      frames: [frame('2026-07-26T00:00:00Z', 10), frame('2026-07-26T00:00:01Z', 11)],
    });
    expect(screen.getByTestId('multitrend-history-chart')).toBeVisible();
    expect(screen.getByText('2 amostras')).toBeVisible();
  });
});
