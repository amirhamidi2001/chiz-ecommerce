// src/__tests__/ChangePassword.test.jsx
import { render, screen, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { vi } from 'vitest';

import ChangePassword from '../pages/ChangePassword';
import api, { parseErrors } from '../services/api';

const mockNavigate = vi.fn();

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

vi.mock('../services/api', () => ({
  default: { post: vi.fn() },
  parseErrors: vi.fn(),
}));

const renderPage = () =>
  render(
    <MemoryRouter>
      <ChangePassword />
    </MemoryRouter>
  );

const fillForm = async (user, current = 'OldPass123!', next = 'NewPass456!', conf = 'NewPass456!') => {
  await user.type(screen.getByPlaceholderText(/current password/i), current);
  await user.type(screen.getByPlaceholderText(/^new password/i), next);
  await user.type(screen.getByPlaceholderText(/confirm password/i), conf);
};

describe('ChangePassword', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useRealTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('renders all three password fields', () => {
    renderPage();
    expect(screen.getByPlaceholderText(/current password/i)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/^new password/i)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/confirm password/i)).toBeInTheDocument();
  });

  it('shows error when current password is empty', async () => {
    const user = userEvent.setup();
    renderPage();
    await user.click(screen.getByRole('button', { name: /update password/i }));
    expect(screen.getByText(/current password is required/i)).toBeInTheDocument();
    expect(api.post).not.toHaveBeenCalled();
  });

  it('shows error when new password is less than 8 characters', async () => {
    const user = userEvent.setup();
    renderPage();
    await fillForm(user, 'OldPass123!', 'short', 'short');
    await user.click(screen.getByRole('button', { name: /update password/i }));
    expect(screen.getByText(/at least 8 characters/i)).toBeInTheDocument();
    expect(api.post).not.toHaveBeenCalled();
  });

  it('shows mismatch error without API call when new passwords differ', async () => {
    const user = userEvent.setup();
    renderPage();
    await fillForm(user, 'OldPass123!', 'NewPass456!', 'Different789!');
    await user.click(screen.getByRole('button', { name: /update password/i }));
    expect(screen.getByText(/do not match/i)).toBeInTheDocument();
    expect(api.post).not.toHaveBeenCalled();
  });

  it('POSTs to /auth/change-password/ with snake_case fields', async () => {
    api.post.mockResolvedValue({ data: { detail: 'Password updated successfully.' } });
    const user = userEvent.setup();
    renderPage();
    await fillForm(user);
    await user.click(screen.getByRole('button', { name: /update password/i }));

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith('/auth/change-password/', {
        current_password: 'OldPass123!',
        new_password: 'NewPass456!',
        confirm_password: 'NewPass456!',
      });
    });
  });

  it('shows success state and navigates to /account after update', async () => {
    vi.useRealTimers();

    api.post.mockResolvedValue({ data: { detail: 'Password updated successfully.' } });

    const user = userEvent.setup();
    renderPage();
    await fillForm(user);

    await user.click(screen.getByRole('button', { name: /update password/i }));

    await waitFor(() => {
      expect(api.post).toHaveBeenCalled();
    });

    const successMessage = await screen.findByText('Password changed successfully!');
    expect(successMessage).toBeInTheDocument();

    const accountLink = await screen.findByRole('link', { name: /go to account now/i });
    expect(accountLink).toHaveAttribute('href', '/account');

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith('/account');
    }, { timeout: 3000 });
  }, 15000);

  it('shows backend error for wrong current password under the correct field', async () => {
    const errorResponse = {
      response: {
        status: 400,
        data: {}
      }
    };
    api.post.mockRejectedValue(errorResponse);
    parseErrors.mockReturnValue({ current_password: 'Current password is incorrect.' });

    const user = userEvent.setup();
    renderPage();
    await fillForm(user);

    await user.click(screen.getByRole('button', { name: /update password/i }));

    await waitFor(() => {
      expect(screen.getByText('Current password is incorrect.')).toBeInTheDocument();
    });
  });

  it('toggles password visibility for each field independently', async () => {
    const user = userEvent.setup();
    renderPage();

    const toggles = screen.getAllByRole('button', { name: /toggle visibility/i });

    const currentPasswordInput = screen.getByPlaceholderText(/current password/i);
    const newPasswordInput = screen.getByPlaceholderText(/^new password/i);
    const confirmPasswordInput = screen.getByPlaceholderText(/confirm password/i);

    expect(currentPasswordInput).toHaveAttribute('type', 'password');
    await user.click(toggles[0]);
    expect(currentPasswordInput).toHaveAttribute('type', 'text');

    await user.click(toggles[0]);
    expect(currentPasswordInput).toHaveAttribute('type', 'password');

    expect(newPasswordInput).toHaveAttribute('type', 'password');
    await user.click(toggles[1]);
    expect(newPasswordInput).toHaveAttribute('type', 'text');

    expect(confirmPasswordInput).toHaveAttribute('type', 'password');
    await user.click(toggles[2]);
    expect(confirmPasswordInput).toHaveAttribute('type', 'text');
  });

  it('disables the submit button while API call is in flight', async () => {
    let resolvePromise;
    const mockPromise = new Promise((resolve) => {
      resolvePromise = resolve;
    });
    api.post.mockReturnValue(mockPromise);

    const user = userEvent.setup();
    renderPage();
    await fillForm(user);

    const clickPromise = user.click(screen.getByRole('button', { name: /update password/i }));

    const loadingButton = await screen.findByRole('button', { name: /updating/i });
    expect(loadingButton).toBeDisabled();

    resolvePromise({ data: {} });
    await clickPromise;

    expect(api.post).toHaveBeenCalledTimes(1);
  });
});
