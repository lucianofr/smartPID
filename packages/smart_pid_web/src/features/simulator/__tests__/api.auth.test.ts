import { describe, it, expect, vi, beforeEach } from 'vitest';
import * as client from '../../../api/client';
import { setPreset } from '../api';

vi.mock('../../../api/client');

beforeEach(() => vi.clearAllMocks());

describe('simulator api unauthenticated', () => {
  it('propagates a 401 ApiError when no/invalid admin token', async () => {
    vi.mocked(client.apiPost).mockRejectedValue(
      Object.assign(new Error('Unauthorized'), { status: 401, detail: 'Not authenticated' }),
    );
    await expect(setPreset({ controller_id: 1, preset: 'FLOW' })).rejects.toMatchObject({
      status: 401,
    });
  });
});
