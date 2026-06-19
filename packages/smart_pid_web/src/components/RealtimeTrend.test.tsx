import { render } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { RealtimeTrend } from './RealtimeTrend';

// uPlot touches canvas/measure APIs jsdom lacks; assert it mounts without throwing.
describe('RealtimeTrend', () => {
  it('mounts with empty data', () => {
    const { container } = render(<RealtimeTrend data={[[], [], [], []]} />);
    expect(container.firstChild).toBeTruthy();
  });
});
