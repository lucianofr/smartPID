import { act, renderHook } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { DEFAULT_PREFERENCES, useSettings } from './useSettings';

afterEach(() => localStorage.clear());

describe('useSettings', () => {
  it('returns defaults when nothing is persisted', () => {
    const { result } = renderHook(() => useSettings());
    expect(result.current.preferences).toEqual(DEFAULT_PREFERENCES);
  });

  it('persists a changed preference immutably and reloads it', () => {
    const first = renderHook(() => useSettings());
    const before = first.result.current.preferences;
    act(() => first.result.current.setPreference('numberDecimals', 4));
    expect(first.result.current.preferences.numberDecimals).toBe(4);
    // original object not mutated
    expect(before.numberDecimals).toBe(DEFAULT_PREFERENCES.numberDecimals);
    // survives a remount (read back from localStorage)
    const second = renderHook(() => useSettings());
    expect(second.result.current.preferences.numberDecimals).toBe(4);
  });

  it('reset() restores defaults', () => {
    const { result } = renderHook(() => useSettings());
    act(() => result.current.setPreference('confirmDestructive', false));
    act(() => result.current.reset());
    expect(result.current.preferences).toEqual(DEFAULT_PREFERENCES);
  });
});
