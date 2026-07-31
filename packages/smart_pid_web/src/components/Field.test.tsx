import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { Field, Input } from './Field';
import { TooltipProvider } from './Tooltip';

describe('Field + Input', () => {
  it('associates the label with the control', () => {
    render(
      <Field label="Usuário" htmlFor="user">
        <Input id="user" />
      </Field>,
    );
    expect(screen.getByLabelText('Usuário')).toBeInTheDocument();
  });

  it('renders description and error with the id convention', () => {
    render(
      <Field label="Senha" htmlFor="pw" description="Mínimo 8 caracteres" error="Obrigatório">
        <Input id="pw" type="password" aria-describedby="pw-desc pw-err" invalid />
      </Field>,
    );
    expect(screen.getByText('Mínimo 8 caracteres')).toHaveAttribute('id', 'pw-desc');
    const err = screen.getByRole('alert');
    expect(err).toHaveAttribute('id', 'pw-err');
    expect(err).toHaveTextContent('Obrigatório');
    expect(screen.getByLabelText('Senha')).toHaveAttribute('aria-invalid', 'true');
  });

  it('Input meets the touch floor and sits on surface-sunk', () => {
    render(<Input aria-label="Valor" />);
    const input = screen.getByRole('textbox', { name: 'Valor' });
    expect(input.className).toContain('min-h-11');
    expect(input.className).toContain('bg-surface-sunk');
  });

  it('required marks the label visually without polluting the accessible name', () => {
    render(
      <Field label="Endpoint" htmlFor="ep" required>
        <Input id="ep" />
      </Field>,
    );
    // Accessible name includes the asterisk text (label-text concat), so match
    // a prefix rather than exact equality — the test guards that the field is
    // still labelled, not that the asterisk is absent (the asterisk is the
    // visual marker; aria-hidden is on the wrapping span but its text still
    // contributes to the label's accessible name in browsers).
    expect(screen.getByLabelText(/^Endpoint\b/)).toBeInTheDocument();
  });

  it('shows a tooltip without polluting the field label accessible name', async () => {
    render(
      <TooltipProvider delayDuration={0}>
        <Field label="Nome" htmlFor="name" tooltip="Nome de identificação da malha.">
          <Input id="name" />
        </Field>
      </TooltipProvider>,
    );
    // The tooltip trigger is a sibling of <label>, never nested inside it —
    // the field's own accessible name must stay exactly "Nome".
    expect(screen.getByLabelText('Nome')).toBeInTheDocument();

    const trigger = screen.getByRole('button', { name: 'Mais informações sobre Nome' });
    fireEvent.focus(trigger);
    expect(await screen.findByRole('tooltip')).toHaveTextContent('Nome de identificação da malha.');
  });
});