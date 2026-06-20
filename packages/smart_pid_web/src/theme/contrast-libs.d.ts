// Ambient declarations for the contrast libraries used by the cross-theme contrast gate.
// Both ship as untyped JS; we declare only the surface the gate consumes.

declare module 'wcag-contrast' {
  /** WCAG 2.x contrast ratio between two hex colors (e.g. '#E0E0E0', '#2D2D30'). */
  export function hex(a: string, b: string): number;
}

declare module 'apca-w3' {
  /** APCA Lc value (signed) for a text color over a background color, accepting hex strings. */
  export function calcAPCA(text: string, background: string): number;
}
