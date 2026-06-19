export type Variable = 'pv' | 'sp' | 'co';

export interface SignalKey {
  loopId: number;
  variable: Variable;
}

export interface SeriesSelection {
  selected: ReadonlyArray<SignalKey>;
}

export interface WindowConfig {
  /** Hard cap on points kept/drawn; excess is decimated/dropped from the left. */
  maxPoints: number;
  /** Hard cap on the visible time window, in seconds. */
  maxSeconds: number;
}

export interface StatsRow {
  loopId: number;
  iae: number;
  itae: number;
  ise: number;
  mse: number;
  sigma: number;
  tv: number;
  /** 2σ/RANGE — variability relative to span. */
  varRange: number;
  /** 2σ/SP — variability relative to setpoint. */
  varSp: number;
}
