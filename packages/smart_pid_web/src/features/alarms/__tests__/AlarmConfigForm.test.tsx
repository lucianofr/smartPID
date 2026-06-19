import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AlarmConfigForm } from '../AlarmConfigForm';
import * as client from '../../../api/client';

vi.mock('../../../api/client');

const config = {
  controller_id: 7,
  thresholds: [
    { alarm_type: 'HIHI', priority: 'CRITICAL', limit: 90, enabled: true, deadband: 1, delay_on_s: 0, delay_off_s: 0 },
    { alarm_type: 'HI', priority: 'WARNING', limit: 80, enabled: true, deadband: 1, delay_on_s: 0, delay_off_s: 0 },
  ],
};

function renderForm() {
  vi.spyOn(client, 'apiGet').mockResolvedValue(config);
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}><AlarmConfigForm controllerId={7} /></QueryClientProvider>);
}

beforeEach(() => vi.clearAllMocks());

describe('AlarmConfigForm', () => {
  it('loads GET /controllers/{id}/alarm-config and renders a row per threshold', async () => {
    renderForm();
    expect(await screen.findByTestId('threshold-HIHI')).toBeInTheDocument();
    expect(screen.getByTestId('threshold-HI')).toBeInTheDocument();
    expect(client.apiGet).toHaveBeenCalledWith('/controllers/7/alarm-config');
  });

  it('saves with PUT carrying the full thresholds array and the edited limit', async () => {
    const put = vi.spyOn(client, 'apiPut').mockResolvedValue(config);
    renderForm();
    const hihi = await screen.findByTestId('threshold-HIHI');
    const limit = within(hihi).getByLabelText(/limit/i);
    fireEvent.change(limit, { target: { value: '95' } });
    fireEvent.click(screen.getByRole('button', { name: /save/i }));
    await waitFor(() => expect(put).toHaveBeenCalled());
    const [url, body] = put.mock.calls[0];
    expect(url).toBe('/controllers/7/alarm-config');
    expect(body).toMatchObject({ thresholds: expect.any(Array) });
    const payload = body as { thresholds: { alarm_type: string; limit: number }[] };
    expect(payload.thresholds).toHaveLength(6);
    expect(payload.thresholds.find((t) => t.alarm_type === 'HIHI')?.limit).toBe(95);
  });
});
