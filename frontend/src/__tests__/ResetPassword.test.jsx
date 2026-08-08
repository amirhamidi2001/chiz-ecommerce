// src/__tests__/ResetPassword.test.jsx
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { vi } from 'vitest';

import ResetPassword from '../pages/ResetPassword';
import api, { parseErrors } from '../services/api';

const mockNavigate = vi.fn();

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
    useParams: vi.fn(() => ({ uid: 'dGVzdA', token: 'valid-token-abc' })),
  };
});

vi.mock('../services/api', () => ({
  default: { post: vi.fn() },
  parseErrors: vi.fn(),
}));

const renderPage = () =>
  render(<MemoryRouter><ResetPassword /></MemoryRouter>);

const fillForm = async (user, pw = 'NewPass123!', conf = 'NewPass123!') => {
  await user.type(screen.getByPlaceholderText(/^new password \(min\./i), pw);
  await user.type(screen.getByPlaceholderText(/^confirm new password$/i), conf);
};

describe('ResetPassword — invalid link guard', () => {
  it('shows invalid link message when uid or token is missing', async () => {
    const { useParams } = await import('react-router-dom');
    useParams.mockReturnValue({ uid: undefined, token: undefined });
    renderPage();

    expect(screen.getByText(/invalid reset link/i)).toBeInTheDocument();
    expect(screen.queryByPlaceholderText(/new password/i)).not.toBeInTheDocument();
  });


  it('shows "Request new link" button on invalid link screen', async () => {
    const { useParams } = await import('react-router-dom'); //
    useParams.mockReturnValue({}); //
    renderPage(); //

    // Change 'button' to 'link'
    expect(screen.getByRole('link', { name: /request new link/i })).toBeInTheDocument();
  });
});

describe('ResetPassword — reset form', () => {
  beforeEach(async () => {
    const { useParams } = await import('react-router-dom');
    useParams.mockReturnValue({ uid: 'dGVzdA', token: 'valid-token' });
  });

  it('renders the new password fields when uid and token are present', () => {
    renderPage();
    expect(screen.getByPlaceholderText('New password (min. 8 characters)')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Confirm new password')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /reset password/i })).toBeInTheDocument();
  });

  it('shows validation error for password shorter than 8 characters', async () => {
    const user = userEvent.setup();
    renderPage();
    await fillForm(user, 'short', 'short');
    await user.click(screen.getByRole('button', { name: /reset password/i }));

    expect(screen.getByText(/at least 8 characters/i)).toBeInTheDocument();
    expect(api.post).not.toHaveBeenCalled();
  });

  it('shows mismatch error without API call when passwords differ', async () => {
    const user = userEvent.setup();
    renderPage();
    await fillForm(user, 'NewPass123!', 'Different456!');
    await user.click(screen.getByRole('button', { name: /reset password/i }));

    expect(screen.getByText(/do not match/i)).toBeInTheDocument();
    expect(api.post).not.toHaveBeenCalled();
  });

  it('POSTs uid, token, and passwords to /auth/password-reset/confirm/', async () => {
    api.post.mockResolvedValue({ data: { detail: 'Password has been reset.' } });
    const user = userEvent.setup();
    renderPage();
    await fillForm(user);
    await user.click(screen.getByRole('button', { name: /reset password/i }));

    await waitFor(() =>
      expect(api.post).toHaveBeenCalledWith('/auth/password-reset/confirm/', {
        uid: 'dGVzdA',
        token: 'valid-token',
        new_password: 'NewPass123!',
        confirm_password: 'NewPass123!',
      }),
    );
  });

  it('shows success state after a successful reset', async () => {
    api.post.mockResolvedValue({ data: { detail: 'OK' } });
    const user = userEvent.setup();
    renderPage();
    await fillForm(user);
    await user.click(screen.getByRole('button', { name: /reset password/i }));

    await waitFor(() =>
      expect(screen.getByText(/password reset successfully/i)).toBeInTheDocument(),
    );
  });

  it('shows expired token error from backend', async () => {
    api.post.mockRejectedValue({ response: { status: 400 } });
    parseErrors.mockReturnValue({ token: 'Token is invalid or has expired.' });
    const user = userEvent.setup();
    renderPage();
    await fillForm(user);
    await user.click(screen.getByRole('button', { name: /reset password/i }));

    await waitFor(() =>
      expect(screen.getByText('Token is invalid or has expired.')).toBeInTheDocument(),
    );
  });

  it('disables submit button during API call', async () => {
    let resolve;
    api.post.mockReturnValue(new Promise((r) => { resolve = r; }));
    const user = userEvent.setup();
    renderPage();
    await fillForm(user);
    await user.click(screen.getByRole('button', { name: /reset password/i }));

    expect(screen.getByRole('button', { name: /resetting/i })).toBeDisabled();
    resolve({ data: {} });
  });
});
