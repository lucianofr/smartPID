import type { ExportRequest } from '@/api/types';
import { useCan } from '@/auth/useCan';
import { Button } from '@/components/Button';
import { useExport } from './useExport';

/**
 * Create → poll → authenticated download, in one control (§6.8).
 *
 * There is no list/history affordance by design: the backend exposes no
 * `GET /export/list`, so anything resembling "your exports" would be fiction.
 */

export interface ExportButtonProps {
  /** null disables the control — an export needs exactly one loop (TD-008). */
  request: ExportRequest | null;
}

export function ExportButton({ request }: ExportButtonProps) {
  const allowed = useCan('export.data');
  const { phase, downloadError, start, download } = useExport();

  if (!allowed) return null;

  if (phase === 'generating') {
    return (
      <span role="status" aria-live="polite" className="inline-flex min-h-11 items-center text-sm text-text-soft">
        Gerando…
      </span>
    );
  }

  if (phase === 'done') {
    return (
      <Button variant={downloadError ? 'secondary' : 'primary'} onClick={() => void download()}>
        {downloadError ? 'Download falhou — repetir' : 'Download CSV'}
      </Button>
    );
  }

  return (
    <Button
      variant="secondary"
      disabled={request === null}
      onClick={() => request !== null && start(request)}
    >
      {phase === 'error' ? 'Exportar novamente' : 'Exportar CSV'}
    </Button>
  );
}
