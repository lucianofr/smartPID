import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

const useExportMock = vi.fn();
vi.mock('./useExport', () => ({ useExport: () => useExportMock() }));
vi.mock('../../api/client', () => ({ apiDownload: vi.fn() }));

import { ExportButton } from './ExportButton';
import { apiDownload } from '../../api/client';

const request = { controller_id: 1, start: 's', end: 'e', format: 'csv' as const };

describe('ExportButton', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // jsdom lacks blob URL APIs; shim them so the download click does not throw.
    URL.createObjectURL = vi.fn(() => 'blob:x');
    URL.revokeObjectURL = vi.fn();
  });

  it('shows the generating state while a job runs', () => {
    useExportMock.mockReturnValue({ phase: 'generating', downloadHref: null, start: vi.fn(), job: null });
    render(<ExportButton request={request} />);
    expect(screen.getByText(/gerando/i)).toBeInTheDocument();
  });

  it('offers a working authenticated download when done', async () => {
    vi.mocked(apiDownload).mockResolvedValue(new Blob(['x']));
    useExportMock.mockReturnValue({
      phase: 'done',
      downloadHref: '/api/export/abc/download',
      start: vi.fn(),
      job: { id: 'abc', format: 'csv' },
    });
    render(<ExportButton request={request} />);
    const button = screen.getByRole('button', { name: /download/i });
    fireEvent.click(button);
    await waitFor(() => expect(apiDownload).toHaveBeenCalledWith('/export/abc/download'));
  });

  it('surfaces a retry affordance when the download fails', async () => {
    vi.mocked(apiDownload).mockRejectedValue(new Error('boom'));
    useExportMock.mockReturnValue({
      phase: 'done',
      downloadHref: '/api/export/abc/download',
      start: vi.fn(),
      job: { id: 'abc', format: 'csv' },
    });
    render(<ExportButton request={request} />);
    fireEvent.click(screen.getByRole('button', { name: /download/i }));
    // The rejection must be caught and surfaced as a recovery affordance,
    // not discarded as an unhandled rejection.
    const retry = await screen.findByRole('button', { name: /download failed|retry/i });
    expect(retry).toBeInTheDocument();
  });
});
