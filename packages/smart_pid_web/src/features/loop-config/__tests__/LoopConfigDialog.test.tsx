import type { ReactNode } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { LoopConfigDialog } from '../LoopConfigDialog';
import type { AiConfigForm, LimitsForm, PidParamsForm, PidStructure } from '../types';

const updateMutate = vi.fn();

vi.mock('../useCommands', () => ({
  useUpdateControllerMutation: () => ({
    mutate: updateMutate,
    isPending: false,
    error: null,
  }),
}));

const PID: PidParamsForm = { gain: 1.5, reset: 30, rate: 2, alpha: 0.1, deadband: 0.5 };
const LIMITS: LimitsForm = {
  out_hi_lim: 100,
  out_lo_lim: 0,
  arw_hi_lim: 105,
  arw_lo_lim: -5,
  pv_ftime: 1,
  sp_ftime: 0,
  sp_rate_up: 0,
  sp_rate_dn: 0,
};
const AI: AiConfigForm = {
  engine: 'NONE',
  objective: 'SP_TRACKING',
  dead_time_l: 5,
  limit_min: 0.5,
  limit_max: 2,
  rl_fallback_kp: 1,
  rl_fallback_kd: 0.2,
  rl_learning_rate: 0.0003,
  rl_train_interval: 256,
};
const STRUCTURE: PidStructure = 'ISA';

function renderDialog(
  props: Partial<Parameters<typeof LoopConfigDialog>[0]> = {},
): void {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
  render(
    <LoopConfigDialog
      controllerId={7}
      open
      onClose={vi.fn()}
      initial={{ pid: PID, limits: LIMITS, pidStructure: STRUCTURE, ai: AI }}
      {...props}
    />,
    { wrapper },
  );
}

describe('LoopConfigDialog', () => {
  beforeEach(() => {
    updateMutate.mockReset();
  });
  afterEach(() => {
    vi.clearAllMocks();
  });

  it('renders nothing when not open', () => {
    renderDialog({ open: false });
    expect(screen.queryByRole('dialog')).toBeNull();
  });

  it('renders three section headers: PID, Otimização IA, Limites', () => {
    renderDialog();
    expect(screen.getByRole('button', { name: /^PID$/ })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Otimiza/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Limites/i })).toBeInTheDocument();
  });

  it('binds PID fields to initial.pid', () => {
    renderDialog();
    expect(screen.getByLabelText(/gain/i)).toHaveValue(1.5);
    expect(screen.getByLabelText(/reset/i)).toHaveValue(30);
    expect(screen.getByLabelText(/rate/i)).toHaveValue(2);
  });

  it('shows "must be greater than 0" and disables Salvar when reset=0', () => {
    renderDialog();
    fireEvent.change(screen.getByLabelText(/reset/i), { target: { value: '0' } });
    expect(screen.getByText(/greater than 0/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Salvar/i })).toBeDisabled();
  });

  it('engine FUZZY reveals shared AI params and hides the rl_* group', () => {
    renderDialog();
    fireEvent.click(screen.getByLabelText('FUZZY'));
    expect(screen.getByLabelText(/objective/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/dead time/i)).toBeInTheDocument();
    expect(screen.queryByLabelText(/learning rate/i)).toBeNull();
    expect(screen.queryByLabelText(/train interval/i)).toBeNull();
  });

  it('engine RL reveals the rl_* group', () => {
    renderDialog();
    fireEvent.click(screen.getByLabelText('RL'));
    expect(screen.getByLabelText(/learning rate/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/train interval/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/fallback kp/i)).toBeInTheDocument();
  });

  it('engine NONE shows no AI params', () => {
    renderDialog();
    expect(screen.queryByLabelText(/objective/i)).toBeNull();
    expect(screen.queryByLabelText(/dead time/i)).toBeNull();
  });

  it('Salvar with valid data calls updateController with full pid_params, limits, and complete ai_config', () => {
    renderDialog();
    fireEvent.click(screen.getByLabelText('RL'));
    fireEvent.click(screen.getByRole('button', { name: /Salvar/i }));

    expect(updateMutate).toHaveBeenCalledTimes(1);
    const arg = updateMutate.mock.calls[0][0];
    expect(arg.id).toBe(7);
    const patch = arg.patch;
    expect(patch.pid_params).toEqual({
      gain: 1.5,
      reset: 30,
      rate: 2,
      alpha: 0.1,
      deadband: 0.5,
    });
    expect(patch.out_hi_lim).toBe(100);
    expect(patch.out_lo_lim).toBe(0);
    expect(patch.arw_hi_lim).toBe(105);
    expect(patch.arw_lo_lim).toBe(-5);
    expect(patch.pv_ftime).toBe(1);
    expect(patch.sp_ftime).toBe(0);
    expect(patch.pid_structure).toBe('ISA');

    // Complete ai_config: all 9 fields round-tripped, only engine changed.
    expect(patch.ai_config).toEqual({
      engine: 'RL',
      objective: 'SP_TRACKING',
      dead_time_l: 5,
      limit_min: 0.5,
      limit_max: 2,
      rl_fallback_kp: 1,
      rl_fallback_kd: 0.2,
      rl_learning_rate: 0.0003,
      rl_train_interval: 256,
    });
  });

  it('Cancelar calls onClose without mutating', () => {
    const onClose = vi.fn();
    renderDialog({ onClose });
    fireEvent.click(screen.getByRole('button', { name: /Cancelar/i }));
    expect(onClose).toHaveBeenCalledTimes(1);
    expect(updateMutate).not.toHaveBeenCalled();
  });

  it('engine radios reflect the initial engine', () => {
    renderDialog();
    const dialog = screen.getByRole('dialog');
    const noneRadio = within(dialog).getByLabelText('NONE') as HTMLInputElement;
    expect(noneRadio.checked).toBe(true);
  });
});
