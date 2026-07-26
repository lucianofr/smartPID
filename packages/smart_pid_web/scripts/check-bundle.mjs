#!/usr/bin/env node
/* eslint-disable no-undef -- Node build script: process/console are Node globals,
   and the flat ESLint config only declares browser globals for src/** + e2e/**. */
// Perf budget gate (§12): gzip size of the app-page entry JS + CSS produced by
// `vite build`, plus the RAW sum of dist/assets/*.woff2 (§6.2 font budget —
// woff2 is pre-compressed, raw ≈ transfer). Fails on budget breach or
// regression vs the committed baseline.
//
// Budgets: app-page JS <= 300 KB gzip, CSS <= 50 KB gzip, fonts <= 160 KB raw.
// Run AFTER `vite build`:  node scripts/check-bundle.mjs
//   --update-baseline   rewrite bundle-baseline.json to current sizes
//
// Zero runtime deps: gzip via Node's built-in zlib.

import { gzipSync } from 'node:zlib';
import { existsSync, readFileSync, readdirSync, statSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join, resolve } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const webRoot = resolve(__dirname, '..');
const distDir = join(webRoot, 'dist');
const assetsDir = join(distDir, 'assets');
const manifestPath = join(distDir, '.vite', 'manifest.json');
const baselinePath = join(webRoot, 'bundle-baseline.json');

const KB = 1024;
const BUDGET = { jsKb: 300, cssKb: 50, fontsKb: 160 };
// Allowed growth over the committed baseline before a regression fails CI.
const REGRESSION_TOLERANCE_KB = 10;

const updateBaseline = process.argv.includes('--update-baseline');

function fail(msg) {
  console.error(`✗ ${msg}`);
  process.exit(1);
}

function gzipKb(absPath) {
  return gzipSync(readFileSync(absPath), { level: 9 }).length / KB;
}

if (!existsSync(distDir)) {
  fail('dist/ not found. Run `npm run build` before the bundle budget check.');
}

// Resolve the app-page entry chunk + its CSS from the Vite manifest when present
// (reliable), else fall back to the largest hashed asset of each type.
let entryJs;
let entryCss;

if (existsSync(manifestPath)) {
  const manifest = JSON.parse(readFileSync(manifestPath, 'utf8'));
  const entry = Object.values(manifest).find((e) => e.isEntry);
  if (!entry) fail('No entry chunk found in Vite manifest.');
  entryJs = join(distDir, entry.file);
  if (Array.isArray(entry.css) && entry.css.length > 0) {
    entryCss = join(distDir, entry.css[0]);
  }
}

if (!entryJs) {
  // Fallback: pick the largest JS/CSS in dist/assets.
  if (!existsSync(assetsDir)) fail('dist/assets/ not found.');
  const files = readdirSync(assetsDir);
  const pickLargest = (ext) =>
    files
      .filter((f) => f.endsWith(ext))
      .map((f) => ({ f, size: readFileSync(join(assetsDir, f)).length }))
      .sort((a, b) => b.size - a.size)[0]?.f;
  const js = pickLargest('.js');
  const css = pickLargest('.css');
  if (!js) fail('No JS asset found in dist/assets/.');
  entryJs = join(assetsDir, js);
  if (css) entryCss = join(assetsDir, css);
}

const jsKb = gzipKb(entryJs);
const cssKb = entryCss ? gzipKb(entryCss) : 0;

// §6.2 font budget: sum RAW dist/assets/*.woff2 (woff2 does not gzip further).
const fontFiles = existsSync(assetsDir)
  ? readdirSync(assetsDir).filter((f) => f.endsWith('.woff2'))
  : [];
const fontsKb = fontFiles.reduce((sum, f) => sum + statSync(join(assetsDir, f)).size, 0) / KB;

const current = {
  appPageJsGzipKb: Number(jsKb.toFixed(1)),
  cssGzipKb: Number(cssKb.toFixed(1)),
  fontsRawKb: Number(fontsKb.toFixed(1)),
};

console.log('Bundle budget check:');
console.log(`  app-page JS: ${current.appPageJsGzipKb} KB gzip  (budget ${BUDGET.jsKb} KB)`);
console.log(`  CSS:         ${current.cssGzipKb} KB gzip  (budget ${BUDGET.cssKb} KB)`);
console.log(`  fonts:       ${current.fontsRawKb} KB raw (${fontFiles.length} woff2)  (budget ${BUDGET.fontsKb} KB)`);

if (updateBaseline) {
  writeFileSync(baselinePath, `${JSON.stringify(current, null, 2)}\n`);
  console.log(`✓ Baseline written to ${baselinePath}`);
  process.exit(0);
}

let baseline;
if (existsSync(baselinePath)) {
  baseline = JSON.parse(readFileSync(baselinePath, 'utf8'));
} else {
  writeFileSync(baselinePath, `${JSON.stringify(current, null, 2)}\n`);
  baseline = current;
  console.log(`ℹ No baseline found; captured current sizes to ${baselinePath}`);
}

const errors = [];

if (current.appPageJsGzipKb > BUDGET.jsKb) {
  errors.push(`app-page JS ${current.appPageJsGzipKb} KB exceeds budget ${BUDGET.jsKb} KB`);
}
if (current.cssGzipKb > BUDGET.cssKb) {
  errors.push(`CSS ${current.cssGzipKb} KB exceeds budget ${BUDGET.cssKb} KB`);
}
if (current.fontsRawKb > BUDGET.fontsKb) {
  errors.push(`fonts ${current.fontsRawKb} KB exceed the §6.2 budget ${BUDGET.fontsKb} KB`);
}

const jsDelta = current.appPageJsGzipKb - baseline.appPageJsGzipKb;
const cssDelta = current.cssGzipKb - baseline.cssGzipKb;
const fontsDelta = current.fontsRawKb - (baseline.fontsRawKb ?? 0);
console.log(
  `  delta vs baseline: JS ${jsDelta >= 0 ? '+' : ''}${jsDelta.toFixed(1)} KB, ` +
    `CSS ${cssDelta >= 0 ? '+' : ''}${cssDelta.toFixed(1)} KB, ` +
    `fonts ${fontsDelta >= 0 ? '+' : ''}${fontsDelta.toFixed(1)} KB`,
);

if (jsDelta > REGRESSION_TOLERANCE_KB) {
  errors.push(
    `app-page JS grew ${jsDelta.toFixed(1)} KB over baseline ` +
      `(> ${REGRESSION_TOLERANCE_KB} KB tolerance). Run with --update-baseline if intentional.`,
  );
}
if (cssDelta > REGRESSION_TOLERANCE_KB) {
  errors.push(
    `CSS grew ${cssDelta.toFixed(1)} KB over baseline ` +
      `(> ${REGRESSION_TOLERANCE_KB} KB tolerance). Run with --update-baseline if intentional.`,
  );
}
if (fontsDelta > REGRESSION_TOLERANCE_KB) {
  errors.push(
    `fonts grew ${fontsDelta.toFixed(1)} KB over baseline ` +
      `(> ${REGRESSION_TOLERANCE_KB} KB tolerance). Run with --update-baseline if intentional.`,
  );
}

if (errors.length > 0) {
  for (const e of errors) console.error(`✗ ${e}`);
  process.exit(1);
}

console.log('✓ Bundle within budget and baseline tolerance.');