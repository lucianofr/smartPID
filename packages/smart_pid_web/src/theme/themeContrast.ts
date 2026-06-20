import type { ThemeId } from './ThemeProvider';
export type { ThemeId };

// Canonical per-theme token VALUE map used for build-time contrast assertions.
// Mirrors themes.css exactly; the test asserts the pairs designers committed to.
//
// Field -> contract token mapping (each row below links to a [data-theme] block in themes.css):
//   bg            -> --bg
//   surface       -> --surface
//   surfaceHigh   -> --surface-container-high
//   text          -> --text
//   textSecondary -> --text-secondary
//   alarmCritical -> --alarm-critical
//   alarmWarning  -> --alarm-warning
//   alarmDiag     -> --alarm-diag
//   onAlarm       -> --on-alarm
// Keep hex values in sync with themes.css; the hardened gate in themeContrast.test.ts
// (wcag-contrast source of truth + APCA cross-check) fails the build on regression.
export interface ThemePalette {
  bg: string;
  surface: string;
  surfaceHigh: string;
  text: string;
  textSecondary: string;
  alarmCritical: string;
  alarmWarning: string;
  alarmDiag: string;
  onAlarm: string;
}

export const PALETTES: Record<ThemeId, ThemePalette> = {
  isa101: {
    bg: '#1E1E1E',
    surface: '#2D2D30',
    surfaceHigh: '#333337',
    text: '#E0E0E0',
    textSecondary: '#ABABAB',
    alarmCritical: '#FF3333',
    alarmWarning: '#FF8800',
    alarmDiag: '#AA55FF',
    onAlarm: '#FFFFFF',
  },
  'dark-room': {
    bg: '#000000',
    surface: '#0D0D11',
    surfaceHigh: '#15151A',
    text: '#B0B0B8',
    textSecondary: '#666670',
    alarmCritical: '#D92525',
    alarmWarning: '#D9A000',
    alarmDiag: '#8A6AD9',
    onAlarm: '#F2E6E6',
  },
  'md3-dark': {
    bg: '#141218',
    surface: '#211F26',
    surfaceHigh: '#2B2930',
    text: '#E6E0E9',
    textSecondary: '#CAC4D0',
    alarmCritical: '#F2B8B5',
    alarmWarning: '#FFDC99',
    alarmDiag: '#D0BCFF',
    onAlarm: '#F9DEDC',
  },
  'md3-light': {
    bg: '#FDF8FD',
    surface: '#F7F2FA',
    surfaceHigh: '#ECE6F0',
    text: '#1D1B20',
    textSecondary: '#49454F',
    alarmCritical: '#B3261E',
    alarmWarning: '#8A5000',
    alarmDiag: '#6750A4',
    onAlarm: '#FFFFFF',
  },
  ocean: {
    bg: '#0A1620',
    surface: '#0F2030',
    surfaceHigh: '#16304A',
    text: '#D6E2EC',
    textSecondary: '#7E97AC',
    alarmCritical: '#FF4D4D',
    alarmWarning: '#FFB020',
    alarmDiag: '#9B6BFF',
    onAlarm: '#FFFFFF',
  },
};
