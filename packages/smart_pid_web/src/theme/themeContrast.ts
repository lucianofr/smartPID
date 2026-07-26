/**
 * Per-theme token VALUE MIRROR for the build-time contrast gate. Mirrors
 * themes.css exactly (sync-tested there); guard-exempt (token-guard EXCLUDE_FILES).
 * Field → token: camelCase of the §6.4 name (surfaceSunk → --surface-sunk, …).
 */
export type GateThemeId = 'recorder' | 'phosphor';

export interface ThemePalette {
  bg: string;
  surface: string;
  surfaceSunk: string;
  ruleStrong: string;
  text: string;
  textSoft: string;
  focusRing: string;
  selection: string;
  accent: string;
  accentHover: string;
  onAccent: string;
  alarmCrit: string;
  alarmCritBg: string;
  alarmWarn: string;
  alarmWarnBg: string;
  alarmAdv: string;
  alarmAdvBg: string;
  alarmLog: string;
  onAlarm: string;
  stateRunning: string;
  stateStopped: string;
  stateError: string;
  tracePv: string;
  traceSp: string;
  traceCo: string;
  trendBg: string;
  barTrack: string;
  barFill: string;
  barMarker: string;
}

export const PALETTES: Record<GateThemeId, ThemePalette> = {
  recorder: {
    bg: '#F7F8FA',
    surface: '#FFFFFF',
    surfaceSunk: '#EEF1F5',
    ruleStrong: '#7C8894',
    text: '#16202B',
    textSoft: '#5A6875',
    focusRing: '#16202B',
    selection: '#DCEBEB',
    accent: '#0E6B6B',
    accentHover: '#0B5757',
    onAccent: '#FFFFFF',
    alarmCrit: '#C02026',
    alarmCritBg: '#F7DCDC',
    alarmWarn: '#9E5E00',
    alarmWarnBg: '#F5E3CC',
    alarmAdv: '#6B4FA8',
    alarmAdvBg: '#E8E1F4',
    alarmLog: '#5A6875',
    onAlarm: '#FFFFFF',
    stateRunning: '#7C8894',
    stateStopped: '#5A6875',
    stateError: '#C02026',
    tracePv: '#1B4F87',
    traceSp: '#7C8894',
    traceCo: '#BC7211',
    trendBg: '#EEF1F5',
    barTrack: '#EEF1F5',
    barFill: '#5A6875',
    barMarker: '#16202B',
  },
  phosphor: {
    bg: '#0A0E14',
    surface: '#131A24',
    surfaceSunk: '#0E141C',
    ruleStrong: '#54697F',
    text: '#D6DEE8',
    textSoft: '#8894A3',
    focusRing: '#D6DEE8',
    selection: '#16304A',
    accent: '#23A6A6',
    accentHover: '#2FBDBD',
    onAccent: '#0A0E14',
    alarmCrit: '#FF4D4D',
    alarmCritBg: '#3A0E0E',
    alarmWarn: '#FFA51F',
    alarmWarnBg: '#3A2A00',
    alarmAdv: '#A98BFF',
    alarmAdvBg: '#241A3E',
    alarmLog: '#8894A3',
    onAlarm: '#0A0E14',
    stateRunning: '#5E7080',
    stateStopped: '#8894A3',
    stateError: '#FF4D4D',
    tracePv: '#9FC8F0',
    traceSp: '#6E7B8A',
    traceCo: '#E39B3D',
    trendBg: '#0A0E14',
    barTrack: '#0E141C',
    barFill: '#5E7080',
    barMarker: '#8FB6D6',
  },
};