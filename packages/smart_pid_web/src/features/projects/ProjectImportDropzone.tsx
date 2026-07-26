import { useState } from 'react';
import { ApiError } from '@/api/client';
import { useCan } from '@/auth/useCan';
import { cn } from '@/lib/utils';
import { projectErrorMessage, useImportProject } from './useProjects';

/**
 * `.spid` upload (§9 `projects.manage`, admin-only).
 *
 * The two refusals the backend really produces are distinct states, not one
 * "upload failed": 413 means the archive is bigger than `max_upload_bytes`
 * (50 MB by default) and 400 means it is not a valid project archive.
 */
export function ProjectImportDropzone() {
  const canManage = useCan('projects.manage');
  const importProject = useImportProject();
  const [failure, setFailure] = useState<string | null>(null);

  if (!canManage) return null;

  const handleFile = async (input: HTMLInputElement): Promise<void> => {
    const file = input.files?.[0];
    if (file === undefined) return;
    setFailure(null);
    try {
      await importProject.mutateAsync({ file, name: file.name.replace(/\.spid$/i, '') });
    } catch (error) {
      setFailure(
        error instanceof ApiError
          ? projectErrorMessage(error, 'Não foi possível importar o projeto.')
          : 'Não foi possível importar o projeto.',
      );
    } finally {
      // Re-picking the same file must fire another change event.
      input.value = '';
    }
  };

  return (
    <div
      className={cn(
        'flex flex-col gap-2 border border-dashed border-rule-strong bg-surface p-3',
      )}
    >
      <label htmlFor="project-import" className="text-sm font-medium text-text">
        Import .spid
      </label>
      <input
        id="project-import"
        type="file"
        accept=".spid"
        aria-describedby="project-import-desc"
        className="text-sm text-text file:mr-3 file:min-h-9 file:rounded-control file:border file:border-rule-strong file:bg-surface-sunk file:px-3 file:text-sm file:text-text"
        onChange={(e) => void handleFile(e.currentTarget)}
      />
      <p id="project-import-desc" className="text-xs text-text-soft">
        Arquivo de projeto portátil exportado por outra instalação.
      </p>
      {importProject.isPending ? (
        <p role="status" className="text-xs text-text-soft">
          Enviando…
        </p>
      ) : null}
      {failure !== null ? (
        <p role="alert" className="text-xs font-medium text-alarm-crit">
          {failure}
        </p>
      ) : null}
    </div>
  );
}
