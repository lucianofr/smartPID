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

  it('active state styles via accent underline; triggers meet the touch floor', () => {
    render(<Harness />);
    const tab = screen.getByRole('tab', { name: 'PID' });
    expect(tab).toHaveAttribute('data-state', 'active');
    expect(tab.className).toContain('data-[state=active]:border-accent');
    expect(tab.className).toContain('min-h-11');
  });
});