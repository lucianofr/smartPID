/**
 * Fixed-decimal tabular formatting for process values (§6.2). The SINGLE
 * format module — phase 3 extends it (units, timestamps) without changing
 * this signature. Alignment comes from .numeric (tabular-nums, Geist Mono).
 */
export function formatNumber(value: number | null | undefined, decimals: number): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return '—';
  }
  return value.toFixed(decimals);
}