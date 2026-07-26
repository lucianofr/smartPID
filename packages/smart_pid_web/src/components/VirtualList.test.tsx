import { render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { VirtualList } from './VirtualList';

const offsetWidthDesc = Object.getOwnPropertyDescriptor(HTMLElement.prototype, 'offsetWidth');
const offsetHeightDesc = Object.getOwnPropertyDescriptor(HTMLElement.prototype, 'offsetHeight');

beforeEach(() => {
  Object.defineProperty(HTMLElement.prototype, 'offsetWidth', { configurable: true, value: 600 });
  Object.defineProperty(HTMLElement.prototype, 'offsetHeight', { configurable: true, value: 400 });
});

afterEach(() => {
  if (offsetWidthDesc) Object.defineProperty(HTMLElement.prototype, 'offsetWidth', offsetWidthDesc);
  if (offsetHeightDesc) Object.defineProperty(HTMLElement.prototype, 'offsetHeight', offsetHeightDesc);
});

const items = Array.from({ length: 1000 }, (_, i) => `Alarme ${i}`);

describe('VirtualList', () => {
  it('windows a 1000-row flood: renders a small subset, sizes the scroll body to the total', () => {
    render(
      <VirtualList
        items={items}
        height={400}
        estimateSize={40}
        aria-label="Alarmes ativos"
        renderItem={(item) => <span>{item}</span>}
      />,
    );
    const rendered = screen.getAllByRole('listitem');
    expect(rendered.length).toBeGreaterThan(0);
    expect(rendered.length).toBeLessThan(60); // windowed, not 1000
    const list = screen.getByRole('list', { name: 'Alarmes ativos' });
    const body = list.firstElementChild as HTMLElement;
    expect(body.style.height).toBe('40000px'); // 1000 × 40
  });

  it('renders the first row content', () => {
    render(
      <VirtualList items={items} height={400} renderItem={(item) => <span>{item}</span>} />,
    );
    expect(screen.getByText('Alarme 0')).toBeInTheDocument();
  });
});