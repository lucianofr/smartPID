/**
 * Transport-only REST client. Single base URL, single auth-injection point,
 * §11 error taxonomy. Endpoint definitions live in ./endpoints.ts; generated
 * OpenAPI types in ./generated/openapi.ts (phase-2 hermetic codegen).
 */

export type ApiErrorKind =
  | 'unauthorized' // 401 → clear session, redirect to login (§11)
  | 'forbidden' // 403 → toast "sem permissão", refetch me/capabilities (§11)
  | 'not-found' // 404 → remove stale entity, MissingState (§11)
  | 'conflict' // 409 → show reason, preserve form state (§11)
  | 'validation' // 422 → field-level messages (§11)
  | 'opcua-down' // 502 → loop-level banner, writes disabled (§11)
  | 'server' // other 5xx → generic failure with retry (§11)
  | 'network'; // transport failure → offline banner (§11)

export interface ValidationIssue {
  loc: (string | number)[];
  msg: string;
  type: string;
}

export function classifyStatus(status: number): ApiErrorKind {
  if (status === 401) return 'unauthorized';
  if (status === 403) return 'forbidden';
  if (status === 404) return 'not-found';
  if (status === 409) return 'conflict';
  if (status === 422) return 'validation';
  if (status === 502) return 'opcua-down';
  return 'server';
}

export class ApiError extends Error {
  readonly status: number;
  readonly kind: ApiErrorKind;
  readonly detail: string;
  readonly fields: ValidationIssue[];

  constructor(status: number, kind: ApiErrorKind, detail: string, fields: ValidationIssue[] = []) {
    super(detail);
    this.name = 'ApiError';
    this.status = status;
    this.kind = kind;
    this.detail = detail;
    this.fields = fields;
  }
}

export interface AuthHooks {
  getToken(): string | null;
  onUnauthorized?(error: ApiError): void;
  onForbidden?(error: ApiError): void;
}

let hooks: AuthHooks = { getToken: () => null };

/** AuthProvider registers itself here — the ONLY coupling between api and auth. */
export function setAuthHooks(next: AuthHooks): void {
  hooks = next;
}

const BASE = '/api';

function isValidationIssue(v: unknown): v is ValidationIssue {
  if (typeof v !== 'object' || v === null) return false;
  const i = v as Record<string, unknown>;
  return Array.isArray(i.loc) && typeof i.msg === 'string' && typeof i.type === 'string';
}

async function toApiError(res: Response): Promise<ApiError> {
  const kind = classifyStatus(res.status);
  let detail = res.statusText;
  let fields: ValidationIssue[] = [];
  try {
    const body: unknown = await res.json();
    const d = (body as { detail?: unknown }).detail;
    if (typeof d === 'string') {
      detail = d; // error_handlers.py:22-34 shape
    } else if (Array.isArray(d)) {
      fields = d.filter(isValidationIssue); // FastAPI 422 shape
      detail = fields.map((f) => f.msg).join('; ') || detail;
    }
  } catch {
    /* non-JSON error body */
  }
  return new ApiError(res.status, kind, detail, fields);
}

function dispatchAuthSideEffects(err: ApiError): void {
  if (err.kind === 'unauthorized') hooks.onUnauthorized?.(err);
  if (err.kind === 'forbidden') hooks.onForbidden?.(err);
}

function authHeaders(): Record<string, string> {
  const token = hooks.getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function run(path: string, init: RequestInit): Promise<Response> {
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, init);
  } catch {
    throw new ApiError(0, 'network', 'network failure');
  }
  if (!res.ok) {
    const err = await toApiError(res);
    dispatchAuthSideEffects(err);
    throw err;
  }
  return res;
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = { ...authHeaders() };
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  const res = await run(path, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const api = {
  get: <T>(path: string) => request<T>('GET', path),
  post: <T>(path: string, body?: unknown) => request<T>('POST', path, body),
  put: <T>(path: string, body?: unknown) => request<T>('PUT', path, body),
  delete: <T>(path: string) => request<T>('DELETE', path),

  /** Authenticated binary GET (Bearer travels in a header; <a href> would lose it). */
  async download(path: string): Promise<Blob> {
    const res = await run(path, { method: 'GET', headers: authHeaders() });
    return res.blob();
  },

  /** Authenticated multipart POST — no manual Content-Type (browser sets the boundary). */
  async upload<T>(path: string, form: FormData): Promise<T> {
    const res = await run(path, { method: 'POST', headers: authHeaders(), body: form });
    if (res.status === 204) return undefined as T;
    return (await res.json()) as T;
  },
};