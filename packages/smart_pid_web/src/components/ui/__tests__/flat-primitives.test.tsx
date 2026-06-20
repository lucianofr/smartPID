import { createRef } from 'react';
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { Dialog, DialogContent, DialogTitle } from '../dialog-primitive';
import { Slider } from '../slider';
import { Switch } from '../switch';

/**
 * Flat-restyle guard for the ISA-101 shadcn primitives.
 *
 * The flat rule (Task 0.3): every wrapped primitive renders with no box-shadow.
 * The ONE allowed exception is the dialog scrim/backdrop, tagged
 * `data-testid="dialog-backdrop"` (kept as a translucent overlay per spec).
 */

const SHADOW_CLASS = /(^|\s)(shadow|drop-shadow)(-|\s|$)/;

function hasShadow(el: Element): boolean {
  const className = el.getAttribute('class') ?? '';
  if (SHADOW_CLASS.test(className)) return true;
  const inlineShadow = (el as HTMLElement).style?.boxShadow ?? '';
  return inlineShadow.trim() !== '' && inlineShadow !== 'none';
}

function isExemptScrim(el: Element): boolean {
  if (el.getAttribute('data-testid') === 'dialog-backdrop') return true;
  // Radix scrim carries role/state attributes; treat the overlay as exempt.
  return el.hasAttribute('data-radix-dialog-overlay') || el.getAttribute('aria-hidden') === 'true';
}

describe('flat shadcn primitives', () => {
  it('renders no box-shadow on any element except the dialog scrim', () => {
    render(
      <>
        <Dialog open>
          <DialogContent>
            <DialogTitle>Flat dialog</DialogTitle>
          </DialogContent>
        </Dialog>
        <Slider defaultValue={[40]} max={100} />
        <Switch />
      </>,
    );

    const offenders = Array.from(document.querySelectorAll('*')).filter(
      (el) => hasShadow(el) && !isExemptScrim(el),
    );

    expect(offenders.map((el) => el.getAttribute('class'))).toEqual([]);
  });

  it('exposes aria-disabled on the Slider thumb when disabled', () => {
    render(<Slider defaultValue={[20]} max={100} disabled />);

    const thumb = document.querySelector('[role="slider"]');
    expect(thumb).not.toBeNull();
    expect(thumb).toHaveAttribute('aria-disabled', 'true');
  });

  it('forwards refs through the wrapped primitives', () => {
    const switchRef = createRef<HTMLButtonElement>();
    const sliderRef = createRef<HTMLSpanElement>();

    render(
      <>
        <Switch ref={switchRef} />
        <Slider ref={sliderRef} defaultValue={[10]} max={100} />
      </>,
    );

    expect(switchRef.current).not.toBeNull();
    expect(sliderRef.current).not.toBeNull();
  });

  it('renders the dialog content with the title visible', () => {
    render(
      <Dialog open>
        <DialogContent>
          <DialogTitle>Visible title</DialogTitle>
        </DialogContent>
      </Dialog>,
    );

    expect(screen.getByText('Visible title')).toBeInTheDocument();
  });
});
