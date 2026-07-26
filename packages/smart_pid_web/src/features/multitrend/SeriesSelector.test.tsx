import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { SeriesSelector } from './SeriesSelector';

function renderSelector(overrides: Partial<Parameters<typeof SeriesSelector>[0]> = {}) {
  const onToggle = vi.fn();
  render(
    <SeriesSelector
      loops={[1, 2]}
      isSelected={() => false}
      isFull={false}
      occupiedLoops={[]}
      onToggle={onToggle}
      {...overrides}
    />,
  );
  return { onToggle };
}

describe('SeriesSelector', () => {
  it('exposes one checkbox per loop and signal under the frozen accessible name', () => {
    renderSelector();
    for (const name of ['Loop 1 · PV', 'Loop 1 · SP', 'Loop 1 · CO', 'Loop 2 · CO']) {
      expect(screen.getByLabelText(name)).toBeInTheDocument();
    }
    expect(screen.getAllByRole('checkbox')).toHaveLength(6);
  });

  it('reflects the model selection and reports toggles', () => {
    const { onToggle } = renderSelector({
      isSelected: (loopId, signal) => loopId === 2 && signal === 'co',
    });
    expect(screen.getByLabelText('Loop 2 · CO')).toBeChecked();
    expect(screen.getByLabelText('Loop 1 · PV')).not.toBeChecked();

    fireEvent.click(screen.getByLabelText('Loop 1 · PV'));
    expect(onToggle).toHaveBeenCalledWith(1, 'pv');
  });

  it('locks loops out once the four-slot grid is full', () => {
    renderSelector({ loops: [1, 2], isFull: true, occupiedLoops: [1] });
    expect(screen.getByLabelText('Loop 1 · PV')).toBeEnabled();
    expect(screen.getByLabelText('Loop 2 · PV')).toBeDisabled();
    expect(screen.getByText('Limite de 4 malhas atingido.')).toBeVisible();
  });

  it('renders an empty state when no loop is available', () => {
    renderSelector({ loops: [] });
    expect(screen.getByText('Nenhuma malha disponível.')).toBeVisible();
    expect(screen.queryAllByRole('checkbox')).toHaveLength(0);
  });
});
