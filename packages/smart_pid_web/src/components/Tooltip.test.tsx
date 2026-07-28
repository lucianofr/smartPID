import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from './Tooltip';

describe('Tooltip', () => {
  it('exposes token-only styling on the content bubble', () => {
    // jsdom does not synchronously mount Radix's portal on defaultOpen —
    // use the controlled `open` prop so the content is rendered immediately.
    render(
      <TooltipProvider delayDuration={0}>
        <Tooltip open>
          <TooltipTrigger asChild>
            <button type="button">IAE</button>
          </TooltipTrigger>
          <TooltipContent>Integral do erro absoluto</TooltipContent>
        </Tooltip>
      </TooltipProvider>,
    );
    // Radix renders an a11y-only <span role="tooltip"> next to the visual
    // bubble (data-side="top"). The visible bubble carries the styling; the
    // a11y node carries the role. Both must agree.
    const bubble = document.querySelector('[data-side]') as HTMLElement | null;
    expect(bubble).not.toBeNull();
    expect(bubble!.className).toContain('bg-surface');
    expect(bubble!.className).toContain('border-rule-strong');
    expect(screen.getByRole('tooltip')).toHaveTextContent('Integral do erro absoluto');
  });
});