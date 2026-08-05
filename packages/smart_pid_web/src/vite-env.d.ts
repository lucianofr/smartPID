/// <reference types="vite/client" />

interface ImportMetaEnv {
  /**
   * Prefix prepended to every REST path by `src/api/client.ts`.
   *
   * Unset (dev, `vite preview`): defaults to `/api`, which the vite proxy
   * strips before forwarding to the daemon. Empty string (container build):
   * the daemon serves this bundle itself and mounts its routers at the root.
   */
  readonly VITE_API_BASE?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
