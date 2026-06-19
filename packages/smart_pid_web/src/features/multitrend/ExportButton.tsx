import { apiDownload } from '../../api/client';
import { useExport, type ExportRequest } from './useExport';

interface Props {
  request: ExportRequest;
}

export function ExportButton({ request }: Props): JSX.Element {
  const { phase, job, start } = useExport();

  if (phase === 'generating') {
    return (
      <span className="export-btn export-btn--busy" aria-live="polite">
        Gerando…
      </span>
    );
  }

  if (phase === 'done' && job) {
    // The download route requires the Bearer JWT header (no auth cookie), so a plain
    // anchor navigation would 401. Fetch the bytes authenticated, then trigger a save.
    const handleDownload = async (): Promise<void> => {
      const blob = await apiDownload(`/export/${job.id}/download`);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `export_${job.id}.${job.format}`;
      a.click();
      URL.revokeObjectURL(url);
    };
    return (
      <button
        type="button"
        className="export-btn export-btn--ready"
        onClick={() => void handleDownload()}
      >
        Download
      </button>
    );
  }

  return (
    <button type="button" className="export-btn" onClick={() => start(request)}>
      {phase === 'error' ? 'Retry export' : 'Export'}
    </button>
  );
}
