/**
 * Persistent simulation-mode banner (Task 8.3 — CSS migrated to flat ISA-101
 * token utilities). Background uses the --alarm-diag token (digital-twin / diag
 * semantic) with its paired --on-alarm contrast text (both theme-defined tokens,
 * never a raw color). `role="status"` + the accessible name are frozen
 * (SimulationModeBanner.test).
 */
export function SimulationModeBanner(): JSX.Element {
  return (
    <div
      className="bg-alarm-diag px-3 py-2 font-semibold tracking-[0.04em] text-center"
      style={{ color: 'var(--on-alarm)' }}
      role="status"
      aria-label="Simulation mode"
    >
      MODO SIMULAÇÃO — digital twin
    </div>
  );
}
