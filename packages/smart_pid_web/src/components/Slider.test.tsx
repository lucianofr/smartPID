import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { Slider } from './Slider';

describe('Slider', () => {
  it('exposes a labeled slider thumb with value semantics', () => {
    render(<Slider defaultValue={[40]} min={0} max={100} step={5} thumbLabel="CO manual" />);
    const thumb = screen.getByRole('slider', { name: 'CO manual' });
    expect(thumb).toHaveAttribute('aria-valuenow', '40');
    expect(thumb).toHaveAttribute('aria-valuemin', '0');
    expect(thumb).toHaveAttribute('aria-valuemax', '100');
  });

  it('keyboard steps the value (Radix keyboard support)', () => {
    render(<Slider defaultValue={[40]} min={0} max={100} step={5} thumbLabel="CO manual" />);
    const thumb = screen.getByRole('slider', { name: 'CO manual' });
    thumb.focus();
    fireEvent.keyDown(thumb, { key: 'ArrowRight' });
    expect(thumb).toHaveAttribute('aria-valuenow', '45');
  });

  it('thumb carries the responsive 44px floor below lg (retained e2e contract)', () => {
    render(<Slider defaultValue={[40]} thumbLabel="x" />);
    const thumb = screen.getByRole('slider');
    expect(thumb.className).toContain('max-lg:h-11');
    expect(thumb.className).toContain('max-lg:w-11');
  });
});