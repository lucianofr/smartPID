import { fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ConfirmApplyTuningDialog } from '../ConfirmApplyTuningDialog';
import type { TuningRecommendation } from '../commandApi';

const REC: TuningRecommendation = {
  controller_id: 7,
  current_kp: 1.5,
  current_ti: 30,
  current_td: 2,
  recommended_kp: 1.8,
  recommended_ti: 25,
  recommended_td: 1.5,
  reason: 'IAE improvement of 18% observed over last window',
  timestamp: 1,
  status: 'pending',
  source: 'fuzzy',
};

function renderConfirm(
  props: Partial<Parameters<typeof ConfirmApplyTuningDialog>[0]> = {},
): { onConfirm: ReturnType<typeof vi.fn>; onCancel: ReturnType<typeof vi.fn> } {
  const onConfirm = vi.fn();
  const onCancel = vi.fn();
  render(
    <ConfirmApplyTuningDialog
      controllerId={7}
      recommendation={REC}
      open
      onConfirm={onConfirm}
      onCancel={onCancel}
      {...props}
    />,
  );
  return { onConfirm, onCancel };
}

describe('ConfirmApplyTuningDialog', () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it('renders nothing when not open', () => {
    renderConfirm({ open: false });
    expect(screen.queryByRole('dialog')).toBeNull();
  });

  it('renders current and recommended Kp/Ti/Td and the reason', () => {
    renderConfirm();
    const dialog = screen.getByRole('dialog');
    const text = dialog.textContent ?? '';
    // current
    expect(text).toContain('1.5');
    expect(text).toContain('30');
    // recommended
    expect(text).toContain('1.8');
    expect(text).toContain('25');
    expect(text).toContain('1.5');
    // reason
    expect(screen.getByText(/IAE improvement/i)).toBeInTheDocument();
  });

  it('does NOT call onConfirm on render (apply-tuning guard)', () => {
    const { onConfirm } = renderConfirm();
    expect(onConfirm).not.toHaveBeenCalled();
  });

  it('calls onConfirm only after clicking "Confirm Write"', () => {
    const { onConfirm, onCancel } = renderConfirm();
    expect(onConfirm).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: /confirm write/i }));
    expect(onConfirm).toHaveBeenCalledTimes(1);
    expect(onCancel).not.toHaveBeenCalled();
  });

  it('Cancel calls onCancel without onConfirm', () => {
    const { onConfirm, onCancel } = renderConfirm();
    fireEvent.click(screen.getByRole('button', { name: /cancel/i }));
    expect(onCancel).toHaveBeenCalledTimes(1);
    expect(onConfirm).not.toHaveBeenCalled();
  });
});
