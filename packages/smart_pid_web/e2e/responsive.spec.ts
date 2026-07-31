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
  test('faceplate is the left rail at >=1024 and stacks under the trend below it', async ({
    page,
  }) => {
    await gotoDashboard(page, { loops: LOOPS, width: 1280, height: 900 });
    let t = await box(trend(page));
    let fp = await box(faceplate(page, 'FIC-101'));
    expect(fp.x + fp.width, 'faceplate sits to the left of the trend').toBeLessThan(t.x + 1);

    await page.setViewportSize({ width: 900, height: 900 });
    t = await box(trend(page));
    fp = await box(faceplate(page, 'FIC-101'));
    expect(fp.y, 'faceplate stacks under the trend').toBeGreaterThanOrEqual(t.y + t.height - 1);
  });

  test('the faceplate rail never scrolls at any supported desktop viewport', async ({ page }) => {
    const sizes = [
      { width: 1920, height: 1080 },
      { width: 1600, height: 900 },
      { width: 1440, height: 900 },
      { width: 1024, height: 768 },
    ];
    for (const role of ['admin', 'user'] as const) {
      for (const { width, height } of sizes) {
        await gotoDashboard(page, { loops: LOOPS, width, height, role });
        const railOverflow = await faceplate(page, 'FIC-101').evaluate(
          (el) => el.scrollHeight - el.clientHeight,
        );
        expect(railOverflow, `rail scroll at ${role} ${width}x${height}`).toBeLessThanOrEqual(0);

        const pageOverflow = await page.evaluate(
          () => document.documentElement.scrollHeight - document.documentElement.clientHeight,
        );
        expect(pageOverflow, `page scroll at ${role} ${width}x${height}`).toBeLessThanOrEqual(0);
      }
    }
  });

  /**
   * §6.9 well containment, in two independent halves — the original defect took
   * both to fix, and each needs its own assertion or half the fix can be undone
   * silently.
   *
   * The sunken well's height is content-driven: the `TREND_WELL_INSET_PX`
   * padding ring plus the canvas. `MIN_PLOT_HEIGHT` used to outbid the flex
   * remainder (140 + 28 into a 114px plot box at 1440x900), so the well rendered
   * TALLER than its own container. That overflow did not stay put — it escaped
   * the trend card's content box, painted `bg-surface-sunk` over the card's own
   * bottom border (a descendant background paints after an ancestor's border),
   * and was finally cut by the right column's `lg:overflow-hidden`, taking the
   * bottom-anchored time ruler with it.
   *
   *  1. CONTAINMENT — the well never outgrows its plot box. Pins `max-h-full` on
   *     the well. Without it the well escapes the card at any binding floor.
   *  2. THE CANVAS FITS — the canvas never outgrows the well's content box. Pins
   *     `MIN_PLOT_HEIGHT`. Containment alone would satisfy (1) by clipping the
   *     canvas instead, which silently eats uPlot's x-axis tick labels — a
   *     quieter regression than the one originally reported, and worse.
   */
  test('the trend well never outgrows its plot box, so the time ruler stays whole', async ({
    page,
  }) => {
    const sizes = [
      { width: 1920, height: 1080 },
      { width: 1600, height: 900 },
      { width: 1440, height: 900 },
      { width: 1024, height: 900 },
      { width: 1024, height: 768 },
    ];

    const measure = async () =>
      trend(page).evaluate((well) => {
        const plotBox = well.parentElement as HTMLElement;
        const style = getComputedStyle(well);
        const ruler = [...well.querySelectorAll('span')].find((s) =>
          s.textContent?.includes('agora'),
        );
        let clipper: HTMLElement | null = plotBox;
        while (clipper !== null && getComputedStyle(clipper).overflowY === 'visible') {
          clipper = clipper.parentElement;
        }
        const ring = parseFloat(style.paddingTop) + parseFloat(style.paddingBottom);
        return {
          well: well.getBoundingClientRect().height,
          box: plotBox.clientHeight,
          // The padding ring the well cannot shed: `max-height` is a border-box
          // limit, so no clamp can squeeze the element below its own padding.
          ring,
          canvas: well.querySelector('canvas')?.getBoundingClientRect().height ?? null,
          // What the well actually has left for the canvas after its own ring.
          wellContent: well.clientHeight - ring,
          rulerBottom: ruler?.getBoundingClientRect().bottom ?? null,
          clipBottom: clipper?.getBoundingClientRect().bottom ?? null,
        };
      });

    for (const { width, height } of sizes) {
      await gotoDashboard(page, { loops: LOOPS, width, height });

      // The well is sized by a ResizeObserver, so the first paint legitimately
      // carries the initial guess. Polling settles that without hiding a real
      // regression: a genuinely oversized well never converges and times out.
      //
      // (1) The bound is `max(box, ring)`, not `box`, and that is deliberate. At
      // 1024x768 the vertical budget is so exhausted that the plot box is 17px
      // — narrower than the 28px ring — so containment there is geometrically
      // impossible and the well bottoms out at the ring. Everywhere else the
      // bound collapses to `box`.
      await expect
        .poll(
          async () => {
            const m = await measure();
            return Math.round(m.well - Math.max(m.box, m.ring));
          },
          { message: `well outgrows its plot box at ${width}x${height}` },
        )
        .toBeLessThanOrEqual(0);

      const m = await measure();
      expect(m.rulerBottom, `time ruler rendered at ${width}x${height}`).not.toBeNull();
      expect(m.clipBottom, `clipping ancestor found at ${width}x${height}`).not.toBeNull();
      // The user-visible half of (1), and it holds at every size: the ruler is
      // anchored to the well's bottom band, so a contained well is exactly what
      // keeps it on screen.
      expect(
        Math.round(m.rulerBottom! - m.clipBottom!),
        `time ruler clipped at ${width}x${height}`,
      ).toBeLessThanOrEqual(0);

      // (2) Wherever the plot box can hold the ring plus a positive canvas, the
      // canvas must actually fit — a clipped canvas loses uPlot's x-axis tick
      // labels. 1024x768 is exempt because its 17px box cannot hold the 28px
      // ring at all, so there is no canvas room to be had at that size.
      if (m.wellContent > 0) {
        expect(m.canvas, `canvas rendered at ${width}x${height}`).not.toBeNull();
        expect(
          Math.round(m.canvas! - m.wellContent),
          `canvas outgrows its well at ${width}x${height}`,
        ).toBeLessThanOrEqual(0);
      }
    }
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
    await assertMinTarget(page.getByRole('button', { name: 'Configurações' }), TARGET_MIN);
    await assertMinTarget(page.getByRole('button', { name: 'Sair' }), TARGET_MIN);
    await assertMinTarget(page.getByRole('button', { name: 'ACK ALL' }), TARGET_MIN);
    await assertMinTarget(loopCard(page, 'FIC-101').getByRole('button', { name: 'FIC-101', exact: true }), TARGET_MIN);

    const fp = faceplate(page, 'FIC-101');
    await assertMinTarget(fp.getByRole('button', { name: 'AUTO' }), TARGET_MIN);
    await assertMinTarget(fp.getByRole('button', { name: 'Set output' }), TARGET_MIN);
  });
});
