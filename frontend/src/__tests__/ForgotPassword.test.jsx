// src/__tests__/ForgotPassword.test.jsx
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { vi } from 'vitest';

import ForgotPassword from '../pages/ForgotPassword';
import api, { parseErrors } from '../services/api';

vi.mock('../services/api', () => ({
  default: { post: vi.fn() },
  parseErrors: vi.fn(),
}));

const renderPage = () =>
  render(<MemoryRouter><ForgotPassword /></MemoryRouter>);

describe('ForgotPassword', () => {
  it('renders the email input and submit button', () => {
    renderPage();
    expect(screen.getByPlaceholderText('Email address')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /send reset link/i })).toBeInTheDocument();
  });

  it('shows validation error for invalid email format without API call', async () => {
    const user = userEvent.setup();
    renderPage();
    await user.type(screen.getByPlaceholderText('Email address'), 'not-an-email');
    await user.click(screen.getByRole('button', { name: /send reset link/i }));

    expect(screen.getByText(/valid email/i)).toBeInTheDocument();
    expect(api.post).not.toHaveBeenCalled();
  });

  it('shows success state after submission regardless of whether email exists', async () => {
    api.post.mockResolvedValue({ data: { detail: 'OK' } });
    const user = userEvent.setup();
    renderPage();
    await user.type(screen.getByPlaceholderText('Email address'), 'anyone@example.com');
    await user.click(screen.getByRole('button', { name: /send reset link/i }));

    await waitFor(() =>
      expect(screen.getByText(/check your inbox/i)).toBeInTheDocument(),
    );
    expect(screen.getByText('anyone@example.com')).toBeInTheDocument();
  });

  it('POSTs to /auth/password-reset/ with the entered email', async () => {
    api.post.mockResolvedValue({ data: {} });
    const user = userEvent.setup();
    renderPage();
    await user.type(screen.getByPlaceholderText('Email address'), 'test@example.com');
    await user.click(screen.getByRole('button', { name: /send reset link/i }));

    await waitFor(() =>
      expect(api.post).toHaveBeenCalledWith('/auth/password-reset/', {
        email: 'test@example.com',
      }),
    );
  });

  it('shows API error message on network failure', async () => {
    api.post.mockRejectedValue({ response: { status: 500 } });
    parseErrors.mockReturnValue({ non_field_errors: 'Something went wrong. Please try again.' });
    const user = userEvent.setup();
    renderPage();
    await user.type(screen.getByPlaceholderText('Email address'), 'test@example.com');
    await user.click(screen.getByRole('button', { name: /send reset link/i }));

    await waitFor(() =>
      expect(screen.getByText('Something went wrong. Please try again.')).toBeInTheDocument(),
    );
  });

  it('disables the button during submission', async () => {
    let resolve;
    api.post.mockReturnValue(new Promise((r) => { resolve = r; }));
    const user = userEvent.setup();
    renderPage();
    await user.type(screen.getByPlaceholderText('Email address'), 'a@b.com');
    await user.click(screen.getByRole('button', { name: /send reset link/i }));

    expect(screen.getByRole('button', { name: /sending/i })).toBeDisabled();
    resolve({ data: {} });
  });

  it('"try again" link resets to the input form from the success state', async () => {
    api.post.mockResolvedValue({ data: {} });
    const user = userEvent.setup();
    renderPage();
    await user.type(screen.getByPlaceholderText('Email address'), 'a@b.com');
    await user.click(screen.getByRole('button', { name: /send reset link/i }));

    await waitFor(() => screen.getByText(/try again/i));
    await user.click(screen.getByText(/try again/i));

    expect(screen.getByPlaceholderText('Email address')).toBeInTheDocument();
  });
});
