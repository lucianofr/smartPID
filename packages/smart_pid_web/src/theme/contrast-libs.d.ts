// Ambient declarations for the contrast library used by the cross-theme gate.
declare module 'wcag-contrast' {
  /** WCAG 2.x contrast ratio between two hex colors (e.g. '#16202B', '#FFFFFF'). */
  export function hex(a: string, b: string): number;
}