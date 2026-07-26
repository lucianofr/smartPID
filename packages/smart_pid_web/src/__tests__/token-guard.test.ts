import { readdirSync, readFileSync } from 'node:fs';
import { dirname, join, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

/**
 * Token-only color source guard (§6.4 / §12 "Source guard" row). Successor of
 * the ISA-101 guard ("Task 0.4 Vitest pivot" — this is a Vitest gate, not an
 * ESLint rule). Color-only: the ISA-era box-shadow/gradient/bevel bans are NOT
 * carried over (the §6.9 edge fade is a token-var gradient).
 *
 * Scope: ALL of src/**.{ts,tsx} except:
 *  - *.test.ts(x)            tests may hold hex (contrast mirrors, style injection)
 *  - __lintfixtures__/        the violation fixtures themselves
 *  - api/generated/           machine output
 *  - assets/                  fonts (no TS anyway)
 *  - theme/themeContrast.ts   the palette VALUE MIRROR for the contrast gate
 */

const here = dirname(fileURLToPath(import.meta.url));
const srcRoot = resolve(here, '..'); // .../src

const EXCLUDE_DIRS: ReadonlySet<string> = new Set(['__lintfixtures__', 'generated', 'assets']);
const EXCLUDE_FILES: ReadonlySet<string> = new Set(['theme/themeContrast.ts']);
const TEST_FILE = /\.test\.(?:ts|tsx)$/;
const SOURCE_EXT = /\.(?:ts|tsx)$/;

type Pattern = { readonly id: string; readonly re: RegExp; readonly label: string };

export const FORBIDDEN_PATTERNS: readonly Pattern[] = [
  { id: 'hex-literal', label: 'raw hex color literal (#rgb/#rrggbb)', re: /#[0-9a-fA-F]{3}(?:[0-9a-fA-F])?(?:[0-9a-fA-F]{2})?\b/ },
  { id: 'rgb', label: 'rgb()/rgba() color function', re: /\brgba?\s*\(/ },
  { id: 'hsl', label: 'hsl()/hsla() color function', re: /\bhsla?\s*\(/ },
  { id: 'oklch', label: 'oklch() color function', re: /\boklch\s*\(/ },
  { id: 'arbitrary-color', label: 'Tailwind arbitrary color utility ([#...])', re: /\[#[0-9a-fA-F]{3,8}\]/ },
  {
    id: 'named-palette',
    label: 'named-palette Tailwind color utility (e.g. text-red-500)',
    re: /\b(?:bg|text|border|ring|fill|stroke|from|to|via)-(?:red|orange|amber|yellow|green|teal|cyan|blue|indigo|violet|purple|pink|rose|slate|gray|zinc|neutral|stone)-\d/,
  },
];

/** Strip JS/TS comments so prose does not trip the matcher (keeps `http://`). */
function stripComments(src: string): string {
  return src.replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|[^:])\/\/[^\n]*/g, '$1');
}

type Violation = { readonly file: string; readonly line: number; readonly pattern: string; readonly snippet: string };

export function findViolations(text: string, file = '<input>'): Violation[] {
  const lines = stripComments(text).split('\n');
  const out: Violation[] = [];
  lines.forEach((line, i) => {
    for (const p of FORBIDDEN_PATTERNS) {
      if (p.re.test(line)) {
        out.push({ file, line: i + 1, pattern: p.label, snippet: line.trim().slice(0, 100) });
      }
    }
  });
  return out;
}

function walkSourceFiles(dir: string): string[] {
  const out: string[] = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const abs = join(dir, entry.name);
    if (entry.isDirectory()) {
      if (EXCLUDE_DIRS.has(entry.name)) continue;
      out.push(...walkSourceFiles(abs));
    } else if (entry.isFile() && SOURCE_EXT.test(entry.name) && !TEST_FILE.test(entry.name)) {
      if (EXCLUDE_FILES.has(relative(srcRoot, abs))) continue;
      out.push(abs);
    }
  }
  return out;
}

const FIXTURES_DIR = resolve(srcRoot, '__lintfixtures__');
const readFixture = (name: string): string => readFileSync(resolve(FIXTURES_DIR, name), 'utf8');

describe('token-only color source guard', () => {
  it('the whole runtime source tree is free of raw colors', () => {
    const files = walkSourceFiles(srcRoot);
    expect(files.length).toBeGreaterThan(5); // guard against a broken walk silently passing

    const violations = files.flatMap((f) => findViolations(readFileSync(f, 'utf8'), relative(srcRoot, f)));
    if (violations.length > 0) {
      const report = violations
        .map((v) => `  ${v.file}:${v.line} — ${v.pattern}\n    ${v.snippet}`)
        .join('\n');
      throw new Error(`raw-color violations in src/:\n${report}`);
    }
    expect(violations).toEqual([]);
  });

  it('flags the raw-color violation fixture', () => {
    const v = findViolations(readFixture('raw-color-violation.tsx'));
    expect(v.map((x) => x.pattern)).toEqual(
      expect.arrayContaining([
        'raw hex color literal (#rgb/#rrggbb)',
        'Tailwind arbitrary color utility ([#...])',
        'named-palette Tailwind color utility (e.g. text-red-500)',
      ]),
    );
  });

  it('passes the token-only clean fixture', () => {
    expect(findViolations(readFixture('token-color-clean.tsx'))).toEqual([]);
  });

  it('passes the token-var gradient fixture (edge-fade stays legal)', () => {
    expect(findViolations(readFixture('gradient-token-allowed.tsx'))).toEqual([]);
  });
});