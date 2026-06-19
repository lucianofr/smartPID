import { useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { apiGet, apiPost } from '../../api/client';

export type ExportFormat = 'csv' | 'json';
export type ExportStatus = 'pending' | 'running' | 'done' | 'error';

export interface ExportRequest {
  controller_id: number;
  start: string;
  end: string;
  format: ExportFormat;
}

export interface ExportJob {
  id: string;
  controller_id: number;
  start: string;
  end: string;
  format: ExportFormat;
  status: ExportStatus;
  progress: number;
  file_path: string | null;
}

export type ExportPhase = 'idle' | 'generating' | 'done' | 'error';

const POLL_INTERVAL_MS = 800;

export function useExport() {
  const [jobId, setJobId] = useState<string | null>(null);

  const create = useMutation({
    mutationFn: (req: ExportRequest) => apiPost<ExportJob>('/export', req),
    onSuccess: (job) => setJobId(job.id),
  });

  const poll = useQuery({
    queryKey: ['export', jobId],
    queryFn: () => apiGet<ExportJob>(`/export/${jobId}`),
    enabled: jobId !== null,
    refetchInterval: (q) => {
      const s = q.state.data?.status;
      return s === 'done' || s === 'error' ? false : POLL_INTERVAL_MS;
    },
  });

  const job = poll.data ?? create.data ?? null;
  const status: ExportStatus | undefined = job?.status;
  const phase: ExportPhase =
    status === 'done'
      ? 'done'
      : status === 'error' || create.isError
        ? 'error'
        : jobId !== null || create.isPending
          ? 'generating'
          : 'idle';

  // /api prefix matches the client.ts base; download is a streamed FileResponse.
  const downloadHref = status === 'done' && jobId ? `/api/export/${jobId}/download` : null;

  return {
    job,
    phase,
    downloadHref,
    start: (req: ExportRequest) => {
      setJobId(null);
      create.mutate(req);
    },
  };
}
