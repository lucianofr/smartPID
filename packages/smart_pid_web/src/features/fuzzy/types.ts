/**
 * View-model types for the Fuzzy inference screen. Deliberately distinct from
 * the wire DTOs (`FuzzyTraceResponse` et al. in `dtos/ai.py`): the components
 * in this feature take these camelCase shapes as plain props and never import
 * `@/api/*` themselves — the page/hook that fetches and maps the trace owns
 * that boundary.
 */

export interface MembershipFunction {
  label: string;
  kind: string;
  params: number[];
  degree: number;
}

export interface FuzzyInput {
  name: string;
  value: number;
  domainMin: number;
  domainMax: number;
  functions: MembershipFunction[];
}

export interface FuzzyRule {
  index: number;
  conditions: Record<string, string>;
  output: string;
  strength: number;
  fired: boolean;
}

export interface FuzzyOutput {
  label: string;
  center: number;
  strength: number;
}
