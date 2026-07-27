import { describe, expect, it } from 'vitest';

import openapi from '../../../openapi.json';
import { HISTORY_LIMIT } from './useHistory';

/**
 * The multitrend history request used to send limit=100_000 against a backend
 * that declares `maximum: 10000`, so every "Carregar historico" returned 422
 * and the window never loaded. Unit tests missed it because they mock the
 * client; only a real request against the real daemon surfaced it.
 *
 * Pin the constant to the CONTRACT rather than to a hand-copied number, so a
 * backend that tightens its cap fails here instead of in the browser.
 */

interface LimitSchema {
  maximum?: number;
  minimum?: number;
}

/** Narrowed read of the generated spec — no unchecked assertion. */
function limitSchema(spec: unknown, path: string): LimitSchema | null {
  if (typeof spec !== 'object' || spec === null || !('paths' in spec)) return null;
  const paths = spec.paths;
  if (typeof paths !== 'object' || paths === null || !(path in paths)) return null;
  const entry: unknown = Reflect.get(paths, path);
  if (typeof entry !== 'object' || entry === null || !('get' in entry)) return null;
  const get = entry.get;
  if (typeof get !== 'object' || get === null || !('parameters' in get)) return null;
  const params = get.parameters;
  if (!Array.isArray(params)) return null;
  for (const p of params) {
    if (typeof p !== 'object' || p === null) continue;
    if (!('name' in p) || p.name !== 'limit') continue;
    if (!('schema' in p) || typeof p.schema !== 'object' || p.schema === null) return null;
    const { maximum, minimum } = p.schema as LimitSchema;
    return {
      maximum: typeof maximum === 'number' ? maximum : undefined,
      minimum: typeof minimum === 'number' ? minimum : undefined,
    };
  }
  return null;
}

describe('multitrend history limit', () => {
  const schema = limitSchema(openapi, '/history/{controller_id}');

  it('the backend still declares a maximum for limit', () => {
    expect(schema?.maximum).toBeTypeOf('number');
  });

  it('never requests more rows than the backend accepts', () => {
    expect(HISTORY_LIMIT).toBeLessThanOrEqual(schema?.maximum ?? 0);
  });

  it('still requests at least the declared minimum', () => {
    expect(HISTORY_LIMIT).toBeGreaterThanOrEqual(schema?.minimum ?? 1);
  });
});
