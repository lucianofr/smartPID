import { useState } from 'react';
import { apiDownload } from '../../api/client';
import { useExport, type ExportRequest } from './useExport';

interface Props {
  request: ExportRequest;
}

export function ExportButton({ request }: Props): JSX.Element {
  const { phase, job, start } = useExport();
  const [downloadError, setDownloadError] = useState(false);

  if (phase === 'generating') {
    return (
      <span
        className="export-btn export-btn--busy inline-flex items-center text-text-secondary"
        aria-live="polite"
      >
        Gerando…
      </span>
    );
  }

  if (phase === 'done' && job) {
    // The download route requires the Bearer JWT header (no auth cookie), so a plain
    // anchor navigation would 401. Fetch the bytes authenticated, then trigger a save.
    // Any failure (expired token -> 401, evicted job -> 404, 500, network drop) must
    // surface a recovery affordance instead of silently doing nothing.
    const handleDownload = async (): Promise<void> => {
      setDownloadError(false);
      let url: string | undefined;
      try {
        const blob = await apiDownload(`/export/${job.id}/download`);
        url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `export_${job.id}.${job.format}`;
        a.click();
      } catch {
        setDownloadError(true);
      } finally {
        if (url) URL.revokeObjectURL(url);
      }
    };
    return (
      <button
        type="button"
        className={
          downloadError
            ? 'export-btn export-btn--error border border-border-strong font-semibold'
            : 'export-btn export-btn--ready'
        }
        onClick={() => void handleDownload()}
      >
        {downloadError ? 'Download failed — retry' : 'Download'}
      </button>
    );
  }

  return (
    <button type="button" className="export-btn" onClick={() => start(request)}>
      {phase === 'error' ? 'Retry export' : 'Export'}
    </button>
  );
}
