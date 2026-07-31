import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { createFakeRealtime, createQueryClient, TestProviders } from '@/test/providers';
import { TwinTrend } from './TwinTrend';

function renderTrend() {
  const queryClient = createQueryClient();
  const realtime = createFakeRealtime();
  return render(
    <TestProviders queryClient={queryClient} realtime={realtime.value}>
      <TwinTrend controllerId={5} />
    </TestProviders>,
  );
}

describe('TwinTrend controls', () => {
  it('offers a time-window control defaulting to 5 minutes (TWIN_WINDOW_SECONDS)', () => {
    renderTrend();
    expect((screen.getByLabelText('Janela de tempo') as HTMLInputElement).value).toBe('5');
    expect(screen.getByLabelText('Unidade da janela')).toBeInTheDocument();
  });

  it('reveals PV and CO scale bounds only when autoscale is off', () => {
    renderTrend();
    expect(screen.queryByLabelText('PV mínimo')).not.toBeInTheDocument();
    fireEvent.click(screen.getByLabelText('Autoescala'));
    for (const name of ['PV mínimo', 'PV máximo', 'CO mínimo', 'CO máximo']) {
      expect(screen.getByLabelText(name)).toBeInTheDocument();
    }
  });
});
