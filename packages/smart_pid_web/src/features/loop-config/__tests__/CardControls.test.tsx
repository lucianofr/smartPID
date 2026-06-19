import type { ReactNode } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { CardControls } from '../CardControls';
import { CONTROLLER_MODES } from '../types';

const setpointMutate = vi.fn();
const modeMutate = vi.fn();
const outputMutate = vi.fn();
const optimizationMutate = vi.fn();

function stub(mutate: ReturnType<typeof vi.fn>) {
  return { mutate, isPending: false, error: null };
}

vi.mock('../useCommands', () => ({
  useSetpointMutation: () => stub(setpointMutate),
  useModeMutation: () => stub(modeMutate),
  useOutputMutation: () => stub(outputMutate),
  useOptimizationMutation: () => stub(optimizationMutate),
}));

function renderControls(
  props: Partial<Parameters<typeof CardControls>[0]> = {},
): void {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
  render(
    <CardControls
      controllerId={7}
      mode="AUTO"
      optimizationEnabled={false}
      onOpenConfig={vi.fn()}
      {...props}
    />,
    { wrapper },
  );
}

describe('CardControls', () => {
  beforeEach(() => {
    setpointMutate.mockReset();
    modeMutate.mockReset();
    outputMutate.mockReset();
    optimizationMutate.mockReset();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('renders a mode select with all CONTROLLER_MODES as options', () => {
    renderControls();
    const select = screen.getByLabelText(/mode/i) as HTMLSelectElement;
    const optionValues = Array.from(select.options).map((o) => o.value);
    expect(optionValues).toEqual(CONTROLLER_MODES);
  });

  it('calls the setpoint mutation with { id, value } on Set', () => {
    renderControls();
    fireEvent.change(screen.getByLabelText(/setpoint/i, { selector: 'input' }), {
      target: { value: '60' },
    });
    fireEvent.click(screen.getByRole('button', { name: /set setpoint/i }));
    expect(setpointMutate).toHaveBeenCalledWith({ id: 7, value: 60 });
  });

  it('disables the manual CO input when mode !== MAN', () => {
    renderControls({ mode: 'AUTO' });
    expect(screen.getByLabelText(/output/i, { selector: 'input' })).toBeDisabled();
  });

  it('enables the manual CO input when mode === MAN', () => {
    renderControls({ mode: 'MAN' });
    expect(screen.getByLabelText(/output/i, { selector: 'input' })).not.toBeDisabled();
  });

  it('calls the optimization mutation with { id, enabled: !optimizationEnabled }', () => {
    renderControls({ optimizationEnabled: false });
    fireEvent.click(screen.getByRole('button', { name: /optimization/i }));
    expect(optimizationMutate).toHaveBeenCalledWith({ id: 7, enabled: true });
  });

  it('labels the optimizer toggle with "Optimization", not "Enable PID"', () => {
    renderControls();
    const toggle = screen.getByRole('button', { name: /optimization/i });
    expect(toggle.textContent).toMatch(/Optimization/);
    expect(toggle.textContent).not.toMatch(/Enable PID/i);
  });
});
