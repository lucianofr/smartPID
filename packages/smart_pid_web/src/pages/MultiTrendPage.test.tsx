import { describe, expect, it } from 'vitest';
import { reconcilableRoster } from './MultiTrendPage';

describe('reconcilableRoster', () => {
  it('is null while the stats query is pending', () => {
    expect(reconcilableRoster({ isPending: true, isError: false, loops: [] })).toBeNull();
  });

  it('is null when the stats query errored, even with a stale-empty loops array', () => {
    // React Query settles isPending=false as soon as the query lands in an
    // error state (after its retry budget), leaving `loops` at its `[]`
    // default. That must never be read as "the roster really is empty" —
    // reconciling against it would permanently wipe a saved trend layout for
    // a transient backend hiccup.
    expect(reconcilableRoster({ isPending: false, isError: true, loops: [] })).toBeNull();
  });

  it('passes the real roster through once the query has resolved successfully', () => {
    expect(reconcilableRoster({ isPending: false, isError: false, loops: [1, 2] })).toEqual([
      1, 2,
    ]);
  });
});
