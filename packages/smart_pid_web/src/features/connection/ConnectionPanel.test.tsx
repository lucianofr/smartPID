import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { describe, expect, it, vi } from 'vitest';

const connect = vi.fn().mockResolvedValue({ state: 'ONLINE', endpoint: 'opc.tcp://x:4840' });
const disconnect = vi.fn().mockResolvedValue({ state: 'OFFLINE', endpoint: 'opc.tcp://x:4840' });
const save = vi.fn().mockResolvedValue({ state: 'OFFLINE', endpoint: 'opc.tcp://x:4840' });
vi.mock('../../api/executive', () => ({
  useOpcuaStatus: () => ({ data: { state: 'OFFLINE', endpoint: 'opc.tcp://x:4840' } }),
}));
vi.mock('./useOpcua', () => ({
  useConnect: () => ({ mutateAsync: connect, isPending: false }),
  useDisconnect: () => ({ mutateAsync: disconnect, isPending: false }),
  useSaveEndpoint: () => ({ mutateAsync: save, isPending: false }),
}));
import { ConnectionPanel } from './ConnectionPanel';

function wrap(ui: ReactNode) {
  return <QueryClientProvider client={new QueryClient()}>{ui}</QueryClientProvider>;
}

describe('ConnectionPanel', () => {
  it('shows the current endpoint and state, with Connect/Disconnect (no acquisition controls)', () => {
    render(wrap(<ConnectionPanel />));
    expect(screen.getByLabelText(/endpoint/i)).toHaveValue('opc.tcp://x:4840');
    expect(screen.getByText(/OFFLINE/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /^connect$/i })).toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: /start acquisition|stop acquisition/i }),
    ).not.toBeInTheDocument();
  });

  it('saves the endpoint then connects', async () => {
    render(wrap(<ConnectionPanel />));
    fireEvent.change(screen.getByLabelText(/endpoint/i), {
      target: { value: 'opc.tcp://y:4840' },
    });
    fireEvent.click(screen.getByRole('button', { name: /^connect$/i }));
    await waitFor(() => expect(save).toHaveBeenCalledWith('opc.tcp://y:4840'));
    await waitFor(() => expect(connect).toHaveBeenCalled());
  });
});
