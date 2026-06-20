import { useImportProject } from './useProjects';

/**
 * Project import dropzone (Fatia 7; Task 8.3 — CSS migrated to flat ISA-101 token
 * utilities). Dashed token-border surface with a `.spid` file picker; upload
 * errors surface via the --alarm-critical token (`text-alarm-critical`).
 */
export function ProjectImportDropzone(): JSX.Element {
  const importProject = useImportProject();

  async function handleFile(input: HTMLInputElement): Promise<void> {
    const file = input.files?.[0];
    if (!file) return;
    const name = file.name.replace(/\.spid$/i, '');
    try {
      await importProject.mutateAsync({ file, name });
    } catch {
      /* surfaced via importProject.isError */
    } finally {
      input.value = '';
    }
  }

  return (
    <div
      className="flex flex-col gap-2 p-4 bg-surface-container text-text border border-dashed border-border-strong rounded-card"
      aria-label="Import project"
    >
      <label
        className="uppercase tracking-[0.04em] text-text-secondary"
        style={{ fontSize: 'var(--text-xs)' }}
        htmlFor="import-input"
      >
        Import .spid
      </label>
      <input
        id="import-input"
        className="text-text"
        style={{ fontSize: 'var(--text-sm)' }}
        type="file"
        accept=".spid"
        onChange={(e) => void handleFile(e.currentTarget)}
      />
      {importProject.isPending && <progress className="w-full" aria-label="Uploading" />}
      {importProject.isError && (
        <p className="m-0 text-alarm-critical" style={{ fontSize: 'var(--text-sm)' }} role="alert">
          Upload failed:{' '}
          {importProject.error instanceof Error ? importProject.error.message : 'Unknown error'}
        </p>
      )}
    </div>
  );
}
