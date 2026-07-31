import { describe, expect, it } from 'vitest';
import { cn } from './utils';

/**
 * `cn` is the single class-name merge used by ~75 call sites, so a regression
 * here does not fail loudly — it silently mis-styles the whole UI. These pin
 * the two properties every caller relies on: conditionals are dropped, and a
 * later Tailwind utility beats an earlier one in the same group.
 */
describe('cn — conditional class names', () => {
  it('joins plain class names', () => {
    expect(cn('a', 'b')).toBe('a b');
  });

  it('drops false, null, undefined and empty conditionals', () => {
    expect(cn('a', false, null, undefined, '', 'b')).toBe('a b');
  });

  it('accepts the object form', () => {
    expect(cn('base', { on: true, off: false })).toBe('base on');
  });

  it('flattens arrays', () => {
    expect(cn(['a', 'b'], 'c')).toBe('a b c');
  });

  it('returns an empty string when nothing applies', () => {
    expect(cn(false, null, undefined)).toBe('');
  });
});

describe('cn — Tailwind conflict resolution', () => {
  it('last conflicting utility in a group wins', () => {
    expect(cn('p-2', 'p-4')).toBe('p-4');
    expect(cn('text-red-500', 'text-blue-500')).toBe('text-blue-500');
  });

  it('keeps utilities from different groups', () => {
    expect(cn('p-2', 'text-sm')).toBe('p-2 text-sm');
  });

  it('lets a conditional override win — the override pattern callers use', () => {
    expect(cn('bg-gray-100', { 'bg-red-500': true })).toBe('bg-red-500');
    expect(cn('bg-gray-100', { 'bg-red-500': false })).toBe('bg-gray-100');
  });

  it('does not treat differing axes as conflicting', () => {
    expect(cn('px-2', 'py-4')).toBe('px-2 py-4');
  });
});
