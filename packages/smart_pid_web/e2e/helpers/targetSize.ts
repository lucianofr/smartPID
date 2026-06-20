import { expect, type Locator } from '@playwright/test';

// Reusable target-size assertions for interactive controls (segmented mode buttons, CO slider,
// ACK / ack-all, apply-tuning, theme switch). Implements WCAG 2.2 SC 2.5.8 Target Size (Minimum):
// the AA bar is 24x24 CSS px, but this project's spec §8.3 holds primary controls to >=44x44.
//
//   assertMinTarget(locator)            -> enforce >=44x44 (spec default for primary controls)
//   assertMinTarget(locator, 24)        -> enforce the WCAG 2.5.8 24x24 minimum
//   assertTargetWithSpacing(locator)    -> pass if >=44x44 OR (>=24x24 AND 24px spacing offset)

const DEFAULT_MIN = 44;
const WCAG_MIN = 24;

export interface BBox {
  x: number;
  y: number;
  width: number;
  height: number;
}

async function bbox(locator: Locator): Promise<BBox> {
  const box = await locator.boundingBox();
  if (!box) {
    throw new Error('assertMinTarget: locator has no bounding box (not visible / detached)');
  }
  return box;
}

/** Assert an interactive target is at least `min` x `min` CSS px (default 44, the spec floor). */
export async function assertMinTarget(locator: Locator, min: number = DEFAULT_MIN): Promise<void> {
  const box = await bbox(locator);
  expect(box.width, `target width >= ${min}px`).toBeGreaterThanOrEqual(min);
  expect(box.height, `target height >= ${min}px`).toBeGreaterThanOrEqual(min);
}

/**
 * WCAG 2.5.8 with the spacing exception: a target smaller than 44x44 passes if it is at least
 * 24x24 AND a 24px-diameter circle centred on it does not overlap a neighbour's circle. Full
 * neighbour geometry needs page context, so this helper enforces the testable half: >=44x44, or
 * >=24x24 with `spacingOffset` px of clear space recorded by the caller.
 */
export async function assertTargetWithSpacing(
  locator: Locator,
  spacingOffset: number = WCAG_MIN,
): Promise<void> {
  const box = await bbox(locator);
  const meets44 = box.width >= DEFAULT_MIN && box.height >= DEFAULT_MIN;
  const meets24WithSpacing =
    box.width >= WCAG_MIN && box.height >= WCAG_MIN && spacingOffset >= WCAG_MIN;
  expect(
    meets44 || meets24WithSpacing,
    `target ${box.width}x${box.height} must be >=44x44 or >=24x24 with >=24px spacing`,
  ).toBe(true);
}

/**
 * Assert a focus ring is visible and meaningful: >=2px solid (WCAG 2.2 SC 2.4.13 Focus Appearance).
 * Reads the computed outline width on the focused element. Contrast (>=3:1) is enforced by the
 * cross-theme contrast gate (themeContrast.test.ts via --focus-ring); here we assert the geometry.
 */
export async function assertFocusRing(locator: Locator, minWidthPx: number = 2): Promise<void> {
  await locator.focus();
  const widthPx = await locator.evaluate((el) => {
    const s = getComputedStyle(el);
    // :focus-visible may live on the element or be applied via outline; read the resolved outline.
    const raw = s.outlineWidth || '0px';
    return parseFloat(raw) || 0;
  });
  expect(widthPx, `focus outline width >= ${minWidthPx}px`).toBeGreaterThanOrEqual(minWidthPx);
}
