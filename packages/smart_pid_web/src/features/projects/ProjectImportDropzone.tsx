import { useImportProject } from './useProjects';
import './ProjectImportDropzone.css';

export function ProjectImportDropzone(): JSX.Element {
  const importProject = useImportProject();

  async function handleFile(file: File | undefined): Promise<void> {
    if (!file) return;
    const name = file.name.replace(/\.spid$/i, '');
    await importProject.mutateAsync({ file, name });
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
        onChange={(e) => handleFile(e.target.files?.[0])}
      />
      {importProject.isPending && <progress className="import-dropzone__progress" aria-label="Uploading" />}
      {importProject.isError && (
        <p className="import-dropzone__error" role="alert">
          Upload failed: {(importProject.error as Error).message}
        </p>
      )}
    </div>
  );
}
