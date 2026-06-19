import { apiDelete, apiDownload, apiGet, apiPost, apiUpload } from '../../api/client';

export interface ProjectItem {
  name: string;
  controller_count: number;
  size_bytes: number;
}

export interface ProjectMeta {
  name: string;
  path: string;
  controller_count: number;
}

export const projectApi = {
  list: (): Promise<{ projects: ProjectItem[] }> => apiGet('/project/list'),
  create: (name: string): Promise<ProjectMeta> => apiPost('/project/new', { name }),
  open: (name: string): Promise<ProjectMeta> => apiPost('/project/open', { name }),
  import: (file: File, name?: string): Promise<ProjectMeta> => {
    const form = new FormData();
    form.append('file', file);
    if (name) form.append('name', name);
    return apiUpload('/project/import', form);
  },
  download: (): Promise<Blob> => apiDownload('/project/download'),
  remove: (name: string): Promise<void> => apiDelete(`/project/${encodeURIComponent(name)}`),
};
