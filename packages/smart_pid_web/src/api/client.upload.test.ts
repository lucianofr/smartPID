import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError, apiUpload, setTokenGetter } from './client';

const originalFetch = globalThis.fetch;

beforeEach(() => {
  setTokenGetter(() => 'tok123');
});

afterEach(() => {
  globalThis.fetch = originalFetch;
  setTokenGetter(() => null);
});

describe('apiUpload', () => {
  it('POSTs FormData with Bearer header and no Content-Type, returning parsed JSON', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ name: 'imp', path: '/x/imp.spid', controller_count: 1 }),
    });
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    const form = new FormData();
    form.append('file', new File([new Uint8Array([1])], 'imp.spid'));
    const result = await apiUpload<{ name: string }>('/project/import', form);

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe('/api/project/import');
    expect(init.method).toBe('POST');
    expect(init.body).toBeInstanceOf(FormData);
    expect(init.headers.Authorization).toBe('Bearer tok123');
    expect('Content-Type' in init.headers).toBe(false);
    expect(result).toEqual({ name: 'imp', path: '/x/imp.spid', controller_count: 1 });
  });

  it('throws ApiError on a non-ok response (413)', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 413,
      statusText: 'Payload Too Large',
      json: async () => ({ detail: 'file too large' }),
    });
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    const form = new FormData();
    form.append('file', new File([new Uint8Array([1])], 'big.spid'));

    await expect(apiUpload('/project/import', form)).rejects.toBeInstanceOf(ApiError);
  });
});
