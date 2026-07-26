import { expect, test, type Locator, type Page } from '@playwright/test';
import { assertMinTarget } from './helpers/targetSize';
import { FIC101, TIC202, faceplate, gotoDashboard, loopCard } from './helpers/harness';

// §6.9 responsive contract:
//  - >=1024: trend and the ~320px faceplate sit side by side (trend >=65% at 1440)
//  - <1024 : the faceplate stacks under the trend
//  - <768  : cards stay a horizontal scroller and the alarm bar collapses to a chip
//  - 320   : degraded but usable — monitoring, acknowledgement and SP entry survive
//
// Card wrapping is forbidden at every width: it pushes the trend below the fold.

const TARGET_MIN = 44;
const LOOPS = [FIC101, TIC202];

const trend = (page: Page) => page.getByRole('img', { name: 'Tendência FIC-101' });

interface Box {
  x: number;
  y: number;
  width: number;
  height: number;
}

async function box(locator: Locator): Promise<Box> {
  const b = await locator.boundingBox();
  expect(b, 'element has a bounding box').not.toBeNull();
  return b as Box;
}

test.describe('responsive dashboard (§6.9)', () => {
  test('trend and faceplate split at >=1024 and stack below it', async ({ page }) => {
    await gotoDashboard(page, { loops: LOOPS, width: 1280, height: 900 });
    let t = await box(trend(page));
    let fp = await box(faceplate(page, 'FIC-101'));
    expect(fp.x, 'faceplate sits to the right of the trend').toBeGreaterThan(t.x + t.width - 1);

    await page.setViewportSize({ width: 900, height: 900 });
    t = await box(trend(page));
    fp = await box(faceplate(page, 'FIC-101'));
    expect(fp.y, 'faceplate stacks under the trend').toBeGreaterThanOrEqual(t.y + t.height - 1);
  });

  test('the faceplate holds ~320px and the trend keeps >=65% at 1440', async ({ page }) => {
    await gotoDashboard(page, { loops: LOOPS, width: 1440, height: 900 });
    const fp = await box(faceplate(page, 'FIC-101'));
    expect(Math.abs(fp.width - 320), 'faceplate is the fixed ~320px column').toBeLessThanOrEqual(8);

    const t = await box(trend(page));
    expect(t.width / 1440, 'trend keeps at least 65% of 1440').toBeGreaterThanOrEqual(0.65);
  });

  test('loop cards never wrap — one row at 320, 768 and 1440', async ({ page }) => {
    for (const width of [320, 768, 1440]) {
      await gotoDashboard(page, { loops: LOOPS, width, height: 900 });
      const first = await loopCard(page, 'FIC-101').boundingBox();
      const second = await loopCard(page, 'TIC-202').boundingBox();
      expect(first, `FIC-101 card at ${width}`).not.toBeNull();
      expect(second, `TIC-202 card at ${width}`).not.toBeNull();
      expect(Math.abs(first!.y - second!.y), `cards share a row at ${width}`).toBeLessThan(4);

      const strip = page.getByRole('region', { name: 'Malhas' }).getByRole('list');
      const style = await strip.evaluate((el) => {
        const s = getComputedStyle(el);
        return { wrap: s.flexWrap, overflowX: s.overflowX, scrolls: el.scrollWidth > el.clientWidth + 1 };
      });
      expect(style.wrap, `strip never wraps at ${width}`).toBe('nowrap');
      expect(style.overflowX, `strip scrolls horizontally at ${width}`).toBe('auto');
      // Two 280px cards only overflow once the viewport is narrower than the row.
      expect(style.scrolls, `strip overflow at ${width}`).toBe(width < 600);
    }
  });

  test('the alarm bar collapses to a count chip below 768', async ({ page }) => {
    await gotoDashboard(page, { loops: LOOPS, width: 1024, height: 900 });
    await expect(page.getByTestId('alarm-buckets')).toBeVisible();
    await expect(page.getByTestId('alarm-count-chip')).toBeHidden();

    await page.setViewportSize({ width: 767, height: 900 });
    await expect(page.getByTestId('alarm-buckets')).toBeHidden();
    await expect(page.getByTestId('alarm-count-chip')).toBeVisible();
  });

  test('320 keeps monitoring, acknowledgement and SP entry', async ({ page }) => {
    await gotoDashboard(page, { loops: LOOPS, width: 320, height: 720 });

    // Monitoring.
    await expect(loopCard(page, 'FIC-101').getByRole('meter', { name: 'PV' })).toHaveAttribute(
      'aria-valuenow',
      '50',
    );
    await expect(trend(page)).toBeVisible();
    // Acknowledgement.
    await expect(page.getByRole('button', { name: 'ACK ALL' })).toBeVisible();
    // SP entry.
    const fp = faceplate(page, 'FIC-101');
    await expect(fp.getByLabel('Setpoint')).toBeVisible();
    await expect(fp.getByRole('button', { name: 'Set setpoint' })).toBeVisible();
  });

  test('touch targets stay >=44x44 below 1024', async ({ page }) => {
    await gotoDashboard(page, { loops: LOOPS, width: 768, height: 1100 });

    await assertMinTarget(page.getByRole('link', { name: 'Loops' }), TARGET_MIN);
    await assertMinTarget(page.getByRole('button', { name: 'Comandos' }), TARGET_MIN);
    await assertMinTarget(page.getByRole('button', { name: 'Sair' }), TARGET_MIN);
    await assertMinTarget(page.getByRole('button', { name: 'ACK ALL' }), TARGET_MIN);
    await assertMinTarget(loopCard(page, 'FIC-101').getByRole('button', { name: 'Abrir FIC-101' }), TARGET_MIN);

    const fp = faceplate(page, 'FIC-101');
    await assertMinTarget(fp.getByRole('button', { name: 'AUTO' }), TARGET_MIN);
    await assertMinTarget(fp.getByRole('slider', { name: 'Manual CO' }), TARGET_MIN);
  });
});
