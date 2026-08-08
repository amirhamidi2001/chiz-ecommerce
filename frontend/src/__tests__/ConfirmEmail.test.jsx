// src/__tests__/ConfirmEmail.test.jsx
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { vi } from 'vitest';

import ConfirmEmail from '../pages/ConfirmEmail';
import api, { parseErrors } from '../services/api';

vi.mock('../services/api', () => ({
  default: { post: vi.fn() },
  parseErrors: vi.fn(),
}));

// useParams is set per-describe block
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useParams: vi.fn(() => ({})),   // default: no key (info mode)
  };
});

const renderPage = () =>
  render(<MemoryRouter><ConfirmEmail /></MemoryRouter>);

// ─── Info mode (no key in URL) ─────────────────────────────────────────────

describe('ConfirmEmail — info mode (post-registration, no key)', () => {
  it('shows "Check Your Inbox" heading', () => {
    renderPage();
    expect(screen.getByText('Check Your Inbox')).toBeInTheDocument();
  });

  it('shows the 24-hour expiry hint', () => {
    renderPage();
    expect(screen.getByText(/24 hours/i)).toBeInTheDocument();
  });

  it('shows a resend link button', () => {
    renderPage();
    expect(screen.getByRole('button', { name: /resend verification email/i })).toBeInTheDocument();
  });

  it('shows success alert after resend request succeeds', async () => {
    api.post.mockResolvedValue({ data: { detail: 'Sent.' } });
    const user = userEvent.setup();
    renderPage();
    await user.click(screen.getByRole('button', { name: /resend verification email/i }));

    await waitFor(() =>
      expect(
        screen.getByText('A new verification email has been sent.'),
      ).toBeInTheDocument(),
    );
  });

  it('shows error alert when resend fails', async () => {
    api.post.mockRejectedValue({ response: { status: 500 } });
    parseErrors.mockReturnValue({ non_field_errors: 'Failed to resend. Please try again.' });
    const user = userEvent.setup();
    renderPage();
    await user.click(screen.getByRole('button', { name: /resend verification email/i }));

    await waitFor(() =>
      expect(
        screen.getByText('Failed to resend. Please try again.'),
      ).toBeInTheDocument(),
    );
  });

  it('disables resend button while request is in flight', async () => {
    let resolve;
    api.post.mockReturnValue(new Promise((r) => { resolve = r; }));
    const user = userEvent.setup();
    renderPage();
    await user.click(screen.getByRole('button', { name: /resend verification email/i }));

    expect(screen.getByRole('button', { name: /sending/i })).toBeDisabled();
    resolve({ data: {} });
  });
});

// ─── Verifying mode (key present in URL) ──────────────────────────────────

describe('ConfirmEmail — verification mode (key in URL)', () => {
  beforeEach(async () => {
    const { useParams } = await import('react-router-dom');
    useParams.mockReturnValue({ key: 'abc123verificationkey' });
  });

  it('shows a verifying spinner while the API call is in flight', () => {
    api.post.mockReturnValue(new Promise(() => { }));   // never resolves
    renderPage();
    expect(screen.getByText(/verifying your email/i)).toBeInTheDocument();
  });

  it('calls /auth/confirm-email/ with the key from the URL', async () => {
    api.post.mockResolvedValue({ data: {} });
    renderPage();
    await waitFor(() =>
      expect(api.post).toHaveBeenCalledWith('/auth/confirm-email/', {
        key: 'abc123verificationkey',
      }),
    );
  });

  it('shows success state when verification succeeds', async () => {
    api.post.mockResolvedValue({ data: {} });
    renderPage();
    await waitFor(() =>
      expect(screen.getByText('Email Verified!')).toBeInTheDocument(),
    );
    expect(screen.getByRole('link', { name: /sign in/i })).toBeInTheDocument();
  });

  it('shows error state when verification fails', async () => {
    api.post.mockRejectedValue({ response: { status: 400 } });
    parseErrors.mockReturnValue({ key: 'This verification link is invalid or has already been used.' });
    renderPage();
    await waitFor(() =>
      expect(screen.getByText('Verification Failed')).toBeInTheDocument(),
    );
    expect(
      screen.getByText('This verification link is invalid or has already been used.'),
    ).toBeInTheDocument();
  });

  it('shows resend button on the error state', async () => {
    api.post.mockRejectedValue({ response: { status: 400 } });
    parseErrors.mockReturnValue({ key: 'Invalid link.' });
    renderPage();
    await waitFor(() => screen.getByText('Verification Failed'));
    expect(
      screen.getByRole('button', { name: /resend verification email/i }),
    ).toBeInTheDocument();
  });
});
