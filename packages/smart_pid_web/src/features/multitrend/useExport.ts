import { useCallback, useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import type { ApiError } from '@/api/client';
import { endpoints } from '@/api/endpoints';
import { queryKeys } from '@/api/queryKeys';
import type { ExportJob, ExportRequest } from '@/api/types';

/**
 * CSV export as a JOB, not a link (§6.8 / TD-008).
 *
 * `POST /export` returns a job; the file is produced asynchronously, so the
 * status is polled until `done` or `error` and only then downloaded. There is
 * no `GET /export/list` on the backend, so there is deliberately no export
 * history here — a list UI would have nothing truthful to render.
 *
 * The download is an AUTHENTICATED fetch: the Bearer token lives in a header,
 * which a plain `<a href>` navigation cannot carry, so the bytes come back as
 * a blob and are handed to the browser through an object URL.
 */

const POLL_INTERVAL_MS = 800;

export type ExportPhase = 'idle' | 'generating' | 'done' | 'error';

export interface UseExportResult {
  job: ExportJob | null;
  phase: ExportPhase;
  /** A completed job whose bytes failed to arrive — retryable, not fatal. */
  downloadError: boolean;
  start(request: ExportRequest): void;
  download(): Promise<void>;
}

export function useExport(): UseExportResult {
  const [jobId, setJobId] = useState<string | null>(null);
  const [downloadError, setDownloadError] = useState(false);

  const create = useMutation<ExportJob, ApiError, ExportRequest>({
    mutationFn: (request) => endpoints.createExport(request),
    onSuccess: (job) => setJobId(job.id),
  });

  const poll = useQuery<ExportJob, ApiError>({
    queryKey: queryKeys.exportJob(jobId ?? ''),
    queryFn: () => {
      if (jobId === null) throw new Error('export poll ran without a job');
      return endpoints.exportStatus(jobId);
    },
    enabled: jobId !== null,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === 'done' || status === 'error' ? false : POLL_INTERVAL_MS;
    },
  });

  const job = poll.data ?? create.data ?? null;
  const status = job?.status;
  const phase: ExportPhase =
    status === 'done'
      ? 'done'
      : status === 'error' || create.isError || poll.isError
        ? 'error'
        : jobId !== null || create.isPending
          ? 'generating'
          : 'idle';

  const start = useCallback(
    (request: ExportRequest) => {
      setDownloadError(false);
      setJobId(null);
      create.mutate(request);
    },
    [create],
  );

  const download = useCallback(async () => {
    if (job === null || job.status !== 'done') return;
    setDownloadError(false);
    let url: string | undefined;
    try {
      const blob = await endpoints.downloadExport(job.id);
      url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = `export_${job.id}.${job.format}`;
      document.body.append(anchor);
      anchor.click();
      anchor.remove();
    } catch {
      setDownloadError(true);
    } finally {
      // Revoking inside the click's own turn can cancel the transfer; the
      // browser has captured the URL by the next macrotask.
      if (url !== undefined) {
        const captured = url;
        setTimeout(() => URL.revokeObjectURL(captured), 0);
      }
    }
  }, [job]);

  return { job, phase, downloadError, start, download };
}
