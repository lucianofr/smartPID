import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { api, ApiError, classifyStatus, setAuthHooks } from './client';

const fetchMock = vi.fn();

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal('fetch', fetchMock);
  setAuthHooks({ getToken: () => null });
});
afterEach(() => vi.unstubAllGlobals());

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });

describe('classifyStatus', () => {
  it('maps the §11 table', () => {
    expect(classifyStatus(401)).toBe('unauthorized');
    expect(classifyStatus(403)).toBe('forbidden');
    expect(classifyStatus(404)).toBe('not-found');
    expect(classifyStatus(409)).toBe('conflict');
    expect(classifyStatus(422)).toBe('validation');
    expect(classifyStatus(502)).toBe('opcua-down');
    expect(classifyStatus(500)).toBe('server');
    expect(classifyStatus(503)).toBe('server');
  });
});

describe('api core', () => {
  it('GETs JSON from /api and returns the parsed body', async () => {
    fetchMock.mockResolvedValueOnce(json({ ok: 1 }));
    await expect(api.get('/controllers')).resolves.toEqual({ ok: 1 });
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/controllers',
      expect.objectContaining({ method: 'GET' }),
    );
  });

  it('injects the Bearer token from the auth hooks', async () => {
    setAuthHooks({ getToken: () => 'tok-123' });
    fetchMock.mockResolvedValueOnce(json({}));
    await api.get('/auth/me');
    const init = fetchMock.mock.calls[0][1] as RequestInit;
    expect((init.headers as Record<string, string>).Authorization).toBe('Bearer tok-123');
  });

  it('sends JSON bodies with Content-Type and returns undefined on 204', async () => {
    fetchMock.mockResolvedValueOnce(new Response(null, { status: 204 }));
    await expect(api.post('/alarms/7/ack', { note: 'x' })).resolves.toBeUndefined();
    const init = fetchMock.mock.calls[0][1] as RequestInit;
    expect(init.body).toBe(JSON.stringify({ note: 'x' }));
    expect((init.headers as Record<string, string>)['Content-Type']).toBe('application/json');
  });

  it('throws a typed ApiError with the backend detail string', async () => {
    fetchMock.mockResolvedValueOnce(json({ detail: 'Controller 9 not found' }, 404));
    const err = await api.get('/controllers/9').catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err).toMatchObject({ status: 404, kind: 'not-found', detail: 'Controller 9 not found' });
  });

  it('parses FastAPI 422 field issues', async () => {
    fetchMock.mockResolvedValueOnce(
      json(
        { detail: [{ loc: ['body', 'sp'], msg: 'value is not a valid float', type: 'float_parsing' }] },
        422,
      ),
    );
    const err = (await api.put('/commands/setpoint', { sp: 'x' }).catch((e: unknown) => e)) as ApiError;
    expect(err.kind).toBe('validation');
    expect(err.fields).toEqual([
      { loc: ['body', 'sp'], msg: 'value is not a valid float', type: 'float_parsing' },
    ]);
    expect(err.detail).toBe('value is not a valid float');
  });

  it('fires onUnauthorized for 401 and onForbidden for 403', async () => {
    const onUnauthorized = vi.fn();
    const onForbidden = vi.fn();
    setAuthHooks({ getToken: () => 't', onUnauthorized, onForbidden });
    fetchMock.mockResolvedValueOnce(json({ detail: 'expired' }, 401));
    await api.get('/auth/me').catch(() => {});
    expect(onUnauthorized).toHaveBeenCalledTimes(1);
    fetchMock.mockResolvedValueOnce(json({ detail: 'sem permissão' }, 403));
    await api.post('/controllers', {}).catch(() => {});
    expect(onForbidden).toHaveBeenCalledTimes(1);
  });

  it('maps transport failure to kind network, status 0', async () => {
    fetchMock.mockRejectedValueOnce(new TypeError('Failed to fetch'));
    const err = (await api.get('/controllers').catch((e: unknown) => e)) as ApiError;
    expect(err).toMatchObject({ status: 0, kind: 'network' });
  });

  it('download returns a Blob and carries auth', async () => {
    setAuthHooks({ getToken: () => 'tok' });
    fetchMock.mockResolvedValueOnce(new Response(new Blob(['csv']), { status: 200 }));
    const blob = await api.download('/export/1/download');
    expect(typeof blob.size).toBe('number');
    expect(typeof blob.text).toBe('function');
    const init = fetchMock.mock.calls[0][1] as RequestInit;
    expect((init.headers as Record<string, string>).Authorization).toBe('Bearer tok');
  });

  it('upload posts FormData without a manual Content-Type (browser sets the boundary)', async () => {
    fetchMock.mockResolvedValueOnce(json({ imported: true }));
    const form = new FormData();
    await api.upload('/project/import', form);
    const init = fetchMock.mock.calls[0][1] as RequestInit;
    expect(init.body).toBe(form);
    expect((init.headers as Record<string, string>)['Content-Type']).toBeUndefined();
  });
});