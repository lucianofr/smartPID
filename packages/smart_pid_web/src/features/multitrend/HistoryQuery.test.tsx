import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { HistoryQuery } from './HistoryQuery';

describe('HistoryQuery', () => {
  it('submits the entered window to the onQuery callback', () => {
    const onQuery = vi.fn();
    render(<HistoryQuery controllerId={5} onQuery={onQuery} frames={[]} count={0} isLoading={false} />);
    fireEvent.change(screen.getByLabelText(/start/i), { target: { value: '2026-06-18T00:00' } });
    fireEvent.change(screen.getByLabelText(/limit/i), { target: { value: '250' } });
    fireEvent.click(screen.getByRole('button', { name: /query/i }));
    expect(onQuery).toHaveBeenCalledWith(expect.objectContaining({ controllerId: 5, limit: 250 }));
  });

  it('renders the returned frame count', () => {
    render(
      <HistoryQuery
        controllerId={5}
        onQuery={vi.fn()}
        frames={[{ timestamp: 't', pv: 1, sp: 2, co: 3, mode: 'AUTO', status: 'GOOD' }]}
        count={1}
        isLoading={false}
      />,
    );
    expect(screen.getByText(/1 frame/i)).toBeInTheDocument();
  });
});
