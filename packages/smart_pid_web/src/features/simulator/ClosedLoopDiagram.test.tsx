import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { ClosedLoopDiagram } from './ClosedLoopDiagram';
import type { ControllerSimStatus } from './types';

const CONTROLLER: ControllerSimStatus = {
  preset: 'FLOW',
  gain: 1.2,
  tau1: 3,
  tau2: null,
  dead_time: 1,
  step_active: true,
  step_amplitude: 5,
  noise_active: false,
  noise_amplitude: 0,
  pid_kp: 0.87,
  pid_ti: 1.25,
  pid_td: 0.3,
  pid_mode: 1,
  pid_cv: 42,
  co: 42,
  sp: 55,
  pv: 50.65,
  error: -4.35,
  process_input: 0,
  process_output: 47.45,
  disturbance_output: 3.2,
  auto_sp: null,
  auto_disturbance: null,
};

describe('ClosedLoopDiagram', () => {
  it('renders live SP, ERRO, CO, PV and disturbance readouts from the snapshot', () => {
    render(<ClosedLoopDiagram controller={CONTROLLER} />);
    // Signal labels are always present.
    for (const label of ['SP', 'ERRO', 'CO', 'PV', 'Perturbação']) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
    // Live values, formatted to 2 decimals (fmt convention).
    expect(screen.getByText('55.00')).toBeInTheDocument(); // sp
    expect(screen.getByText('-4.35')).toBeInTheDocument(); // error
    expect(screen.getByText('42.00')).toBeInTheDocument(); // co
    expect(screen.getByText('50.65')).toBeInTheDocument(); // pv
    expect(screen.getByText('3.20')).toBeInTheDocument(); // disturbance_output
    // Internal PID params fit in the widened block.
    expect(screen.getByText('Kp 0.87 · Ti 1.25 · Td 0.30')).toBeInTheDocument();
    // The wire int AND its meaning — 1 alone is unreadable at a glance.
    expect(screen.getByText('MODE: 1 - AUTO')).toBeInTheDocument();
  });

  it('reads pid_mode 0 as MAN', () => {
    render(<ClosedLoopDiagram controller={{ ...CONTROLLER, pid_mode: 0 }} />);
    expect(screen.getByText('MODE: 0 - MAN')).toBeInTheDocument();
    expect(screen.queryByText('MODE: 1 - AUTO')).not.toBeInTheDocument();
  });

  it('shows an unknown mode instead of silently reading as MAN', () => {
    // An absent (or out-of-range) mode is NOT manual — claiming MAN would be a lie.
    render(
      <ClosedLoopDiagram
        controller={{ ...CONTROLLER, pid_mode: undefined as unknown as number }}
      />,
    );
    expect(screen.getByText('MODE: --')).toBeInTheDocument();
    expect(screen.queryByText('MODE: 0 - MAN')).not.toBeInTheDocument();
  });

  it('shows generic topology labels but no numeric readouts without a snapshot', () => {
    render(<ClosedLoopDiagram controller={null} />);
    expect(screen.getByText('SP')).toBeInTheDocument();
    expect(screen.getByText('ERRO')).toBeInTheDocument();
    expect(screen.queryByText('55.00')).not.toBeInTheDocument();
    expect(screen.queryByText('3.20')).not.toBeInTheDocument();
    expect(screen.getByText('MODE: --')).toBeInTheDocument();
  });
});
