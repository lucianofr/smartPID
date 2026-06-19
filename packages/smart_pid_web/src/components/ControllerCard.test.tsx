import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { ControllerCard } from './ControllerCard';
import type { StatusData } from '../realtime/envelope';

const sig = (value: number) => ({ value, severity: 'GOOD', limit_bits: 'NONE', sub_status: 'NON_SPECIFIC' });
const status: StatusData = {
  pv: sig(150.2), sp: sig(152.0), co: sig(64.0), bkcal_in: sig(0), bkcal_out: sig(0),
  mode: 'AUTO', kp: 1, ti: 1, td: 0, integral_val: 0, timestamp: '2026-06-18T00:00:00Z',
};

describe('ControllerCard', () => {
  it('renders tag, mode and PV value', () => {
    render(
      <ControllerCard
        controller={{ id: 5, name: 'PIC-005', description: 'Pressure', pv_decimals: 1, pv_unit: '°C' }}
        status={status}
      />,
    );
    expect(screen.getByText('PIC-005')).toBeInTheDocument();
    expect(screen.getByText('AUTO')).toBeInTheDocument();
    expect(screen.getByText(/150\.2/)).toBeInTheDocument();
  });

  it('renders a placeholder when no status yet', () => {
    render(
      <ControllerCard
        controller={{ id: 6, name: 'FIC-006', description: '', pv_decimals: 1, pv_unit: '%' }}
        status={undefined}
      />,
    );
    expect(screen.getAllByText('—').length).toBeGreaterThan(0);
  });
});
