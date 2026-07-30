import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { Tabs, TabsContent, TabsList, TabsTrigger } from './Tabs';

function Harness() {
  return (
    <Tabs defaultValue="pid">
      <TabsList aria-label="Configuração">
        <TabsTrigger value="pid">PID</TabsTrigger>
        <TabsTrigger value="fuzzy">Fuzzy</TabsTrigger>
      </TabsList>
      <TabsContent value="pid">Ganhos PID</TabsContent>
      <TabsContent value="fuzzy">Regras fuzzy</TabsContent>
    </Tabs>
  );
}

describe('Tabs', () => {
  it('shows the default panel and switches on activation', () => {
    render(<Harness />);
    expect(screen.getByText('Ganhos PID')).toBeInTheDocument();
    expect(screen.queryByText('Regras fuzzy')).not.toBeInTheDocument();
    // Radix Tabs in automatic activationMode react to focus + Enter/Space.
    // jsdom's fireEvent.click alone doesn't move focus reliably; activate via
    // keyboard (the same public API every keyboard user exercises).
    const fuzzy = screen.getByRole('tab', { name: 'Fuzzy' });
    fuzzy.focus();
    fireEvent.keyDown(fuzzy, { key: 'Enter' });
    expect(screen.getByText('Regras fuzzy')).toBeInTheDocument();
  });

  it('active state styles via a brand-amber underline; triggers meet the touch floor', () => {
    render(<Harness />);
    const tab = screen.getByRole('tab', { name: 'PID' });
    expect(tab).toHaveAttribute('data-state', 'active');
    // The active rule is brand amber, matching the shell's primary nav, and it
    // is the bottom-edge longhand because `border-b-2` is the only edge with
    // width. Verified against a real browser: the active tab computes
    // borderBottomColor === --brand-accent (#FF8C42), with borderTopWidth 0.
    expect(tab.className).toContain('data-[state=active]:border-b-brand-accent');
    // A `border-*` shorthand alongside it can only repaint the three
    // zero-width edges, so it is dead weight — keep it from creeping back.
    expect(tab.className).not.toContain('data-[state=active]:border-accent');
    expect(tab.className).toContain('min-h-11');
  });
});