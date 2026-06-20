import { useImportProject } from './useProjects';
import './ProjectImportDropzone.css';

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
    <div className="import-dropzone" aria-label="Import project">
      <label className="import-dropzone__label" htmlFor="import-input">
        Import .spid
      </label>
      <input
        id="import-input"
        type="file"
        accept=".spid"
        onChange={(e) => void handleFile(e.currentTarget)}
      />
      {importProject.isPending && <progress className="import-dropzone__progress" aria-label="Uploading" />}
      {importProject.isError && (
        <p className="import-dropzone__error" role="alert">
          Upload failed:{' '}
          {importProject.error instanceof Error ? importProject.error.message : 'Unknown error'}
        </p>
      )}
    </div>
  );
}
