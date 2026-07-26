import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { Badge } from './Badge';

describe('Badge', () => {
  it('renders its text content (severity never color-only)', () => {
    render(<Badge tone="crit">2 CRITICAL</Badge>);
    expect(screen.getByText('2 CRITICAL')).toBeInTheDocument();
  });

  it('severity tones color text+border with the severity token, not a tint bg', () => {
    render(<Badge tone="warn">1 WARNING</Badge>);
    const el = screen.getByText('1 WARNING');
    expect(el.className).toContain('text-alarm-warn');
    expect(el.className).toContain('border-alarm-warn');
    expect(el.className).not.toContain('bg-alarm-warn');
  });

  it('neutral (quiet) is the default — counts in --text-soft (§6.9 quiet alarm bar)', () => {
    render(<Badge>0 alarmes</Badge>);
    expect(screen.getByText('0 alarmes').className).toContain('text-text-soft');
  });
});