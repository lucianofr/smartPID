import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '@/api/client';
import { endpoints } from '@/api/endpoints';
import { TestProviders } from '@/test/providers';
import { FEEDBACK_PROMPT, FeedbackBanner } from './FeedbackBanner';

function renderBanner(username = 'demo') {
  localStorage.setItem('smart-pid-token', 'jwt');
  vi.spyOn(endpoints, 'me').mockResolvedValue({ user_id: 3, username, role: 'user' });
  return render(
    <TestProviders>
      <FeedbackBanner />
    </TestProviders>,
  );
}

beforeEach(() => {
  localStorage.clear();
  sessionStorage.clear();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('FeedbackBanner', () => {
  it('stays invisible for every account that is not demo', async () => {
    const me = renderBanner('operator');
    // Wait for the same /auth/me round trip the demo case needs, so this is a
    // real absence and not just a claim made before the user resolved.
    await waitFor(() => expect(endpoints.me).toHaveBeenCalled());
    expect(screen.queryByText(FEEDBACK_PROMPT)).toBeNull();
    expect(me.container.querySelector('button')).toBeNull();
  });

  it('invites the demo operator and opens the dialog', async () => {
    renderBanner();
    expect(await screen.findByText(FEEDBACK_PROMPT)).toBeVisible();
    fireEvent.click(screen.getByRole('button', { name: 'Enviar mensagem' }));
    expect(screen.getByRole('dialog')).toBeVisible();
    // The operator can type immediately — the reason no autoFocus prop is needed.
    expect(await screen.findByLabelText('Mensagem')).toHaveFocus();
  });

  it('refuses to send an empty or whitespace-only message', async () => {
    renderBanner();
    fireEvent.click(await screen.findByRole('button', { name: 'Enviar mensagem' }));
    const send = screen.getByRole('button', { name: 'Enviar' });
    const box = screen.getByLabelText('Mensagem');

    expect(send).toBeDisabled();
    fireEvent.change(box, { target: { value: '   ' } });
    expect(send).toBeDisabled();
    fireEvent.change(box, { target: { value: 'ideia' } });
    expect(send).toBeEnabled();
  });

  it('sends the trimmed message and closes the dialog', async () => {
    const spy = vi.spyOn(endpoints, 'sendFeedback').mockResolvedValue(undefined);
    renderBanner();
    fireEvent.click(await screen.findByRole('button', { name: 'Enviar mensagem' }));
    fireEvent.change(screen.getByLabelText('Mensagem'), {
      target: { value: '  faltou um gráfico  ' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Enviar' }));

    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
    expect(spy).toHaveBeenCalledWith('faltou um gráfico');
  });

  it('explains a 429 cooldown in the dialog instead of losing the text', async () => {
    vi.spyOn(endpoints, 'sendFeedback').mockRejectedValue(
      new ApiError(429, 'server', 'Wait a minute before sending another message'),
    );
    renderBanner();
    fireEvent.click(await screen.findByRole('button', { name: 'Enviar mensagem' }));
    fireEvent.change(screen.getByLabelText('Mensagem'), { target: { value: 'de novo' } });
    fireEvent.click(screen.getByRole('button', { name: 'Enviar' }));

    expect(
      await screen.findByText('Aguarde um minuto antes de enviar outra mensagem.'),
    ).toBeVisible();
    expect(screen.getByRole('dialog')).toBeVisible();
    expect(screen.getByLabelText('Mensagem')).toHaveValue('de novo');
  });

  it('explains an unconfigured mailbox (503) rather than a generic failure', async () => {
    vi.spyOn(endpoints, 'sendFeedback').mockRejectedValue(
      new ApiError(503, 'server', 'Email delivery is not configured on this server'),
    );
    renderBanner();
    fireEvent.click(await screen.findByRole('button', { name: 'Enviar mensagem' }));
    fireEvent.change(screen.getByLabelText('Mensagem'), { target: { value: 'oi' } });
    fireEvent.click(screen.getByRole('button', { name: 'Enviar' }));

    expect(
      await screen.findByText('O envio de email não está configurado no servidor.'),
    ).toBeVisible();
  });
});
