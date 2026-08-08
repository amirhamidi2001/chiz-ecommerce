// src/__tests__/SettingsTab.test.jsx
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { vi } from 'vitest';

import SettingsTab from '../components/SettingsTab';
import api, { parseErrors } from '../services/api';

vi.mock('../services/api', () => ({
  default: { get: vi.fn(), patch: vi.fn(), post: vi.fn() },
  parseErrors: vi.fn(),
}));

// ─── Fixtures ─────────────────────────────────────────────────────────────

const PROFILE = {
  email: 'jane@example.com',
  first_name: 'Jane',
  last_name: 'Doe',
  phone_number: '+12345678901',
  order_updates: true,
  promotions: false,
  newsletter: true,
};

const renderTab = () =>
  render(
    <MemoryRouter>
      <SettingsTab />
    </MemoryRouter>,
  );

// Wait until the skeleton loader is gone (i.e. data has loaded)
const waitForLoad = () =>
  waitFor(() => expect(screen.queryByRole('status')).not.toBeInTheDocument(), {
    timeout: 2000,
  });

// ─── Tests ────────────────────────────────────────────────────────────────

describe('SettingsTab — data loading', () => {
  it('shows skeleton loader while profile is being fetched', () => {
    api.get.mockReturnValue(new Promise(() => { })); // never resolves
    renderTab();
    // The skeleton is multiple animated divs — check a section header is NOT yet visible
    expect(screen.queryByText('Personal Information')).not.toBeInTheDocument();
  });

  it('populates form fields after successful fetch', async () => {
    api.get.mockResolvedValue({ data: PROFILE });
    renderTab();

    await waitFor(() =>
      expect(screen.getByDisplayValue('Jane')).toBeInTheDocument(),
    );
    expect(screen.getByDisplayValue('Doe')).toBeInTheDocument();
    expect(screen.getByDisplayValue('+12345678901')).toBeInTheDocument();
    expect(screen.getByDisplayValue('jane@example.com')).toBeInTheDocument();
  });

  it('shows error state with retry button on fetch failure', async () => {
    api.get.mockRejectedValue(new Error('Network error'));
    renderTab();

    await waitFor(() =>
      expect(screen.getByText(/failed to load/i)).toBeInTheDocument(),
    );
    expect(screen.getByRole('button', { name: /try again/i })).toBeInTheDocument();
  });

  it('retries the profile fetch when "Try again" is clicked', async () => {
    api.get
      .mockRejectedValueOnce(new Error('Network error'))
      .mockResolvedValueOnce({ data: PROFILE });

    renderTab();
    await waitFor(() => screen.getByRole('button', { name: /try again/i }));
    await userEvent.setup().click(screen.getByRole('button', { name: /try again/i }));

    await waitFor(() =>
      expect(screen.getByDisplayValue('Jane')).toBeInTheDocument(),
    );
  });
});

describe('SettingsTab — personal information', () => {
  beforeEach(async () => {
    api.get.mockResolvedValue({ data: PROFILE });
    api.patch.mockResolvedValue({ data: PROFILE });
    renderTab();
    await waitFor(() => screen.getByDisplayValue('Jane'));
  });

  it('PATCHes /auth/profile/ with updated name and phone on save', async () => {
    const user = userEvent.setup();
    const firstNameInput = screen.getByDisplayValue('Jane');
    await user.clear(firstNameInput);
    await user.type(firstNameInput, 'Janet');
    await user.click(screen.getByRole('button', { name: /save changes/i }));

    await waitFor(() => {
      expect(api.patch).toHaveBeenCalledWith(
        '/auth/profile/',
        expect.objectContaining({ first_name: 'Janet' }),
      );
    });
  });

  it('shows success alert after a successful PATCH', async () => {
    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: /save changes/i }));

    await waitFor(() =>
      expect(screen.getByText('Personal information saved.')).toBeInTheDocument(),
    );
  });

  it('shows field-level errors from backend', async () => {
    api.patch.mockRejectedValue({ response: { status: 400 } });
    parseErrors.mockReturnValue({ phone_number: 'Enter a valid phone number.' });

    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: /save changes/i }));

    await waitFor(() =>
      expect(screen.getByText('Enter a valid phone number.')).toBeInTheDocument(),
    );
  });

  it('email field is disabled (read-only)', () => {
    expect(screen.getByDisplayValue('jane@example.com')).toBeDisabled();
  });

  it('disables Save Changes button while PATCH is in flight', async () => {
    let resolve;
    api.patch.mockReturnValue(new Promise((r) => { resolve = r; }));
    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: /save changes/i }));

    expect(screen.getByRole('button', { name: /saving/i })).toBeDisabled();
    resolve({ data: PROFILE });
  });
});

describe('SettingsTab — email preferences (toggles)', () => {
  beforeEach(async () => {
    api.get.mockResolvedValue({ data: PROFILE });
    api.patch.mockResolvedValue({ data: PROFILE });
    renderTab();
    await waitFor(() => screen.getByDisplayValue('Jane'));
  });

  it('renders toggles reflecting backend values', () => {
    const checkboxes = screen.getAllByRole('checkbox');
    // order_updates=true, promotions=false, newsletter=true (plus the terms checkbox is absent here)
    const toggleInputs = checkboxes.filter(
      (cb) => cb.closest('label')?.className?.includes('cursor-pointer'),
    );
    expect(toggleInputs.some((cb) => cb.checked)).toBe(true);
  });

  it('PATCHes preferences immediately when a toggle is changed', async () => {
    const user = userEvent.setup();
    // Find the Promotions toggle (unchecked by default)
    const promotionsLabel = screen.getByText('Promotions').closest('div').parentElement;
    const toggle = within(promotionsLabel).getByRole('checkbox');

    await user.click(toggle);

    await waitFor(() => {
      expect(api.patch).toHaveBeenCalledWith(
        '/auth/profile/',
        expect.objectContaining({ promotions: true }),
      );
    });
  });

  it('shows "Preferences saved." after successful PATCH', async () => {
    const user = userEvent.setup();
    const promotionsLabel = screen.getByText('Promotions').closest('div').parentElement;
    const toggle = within(promotionsLabel).getByRole('checkbox');
    await user.click(toggle);

    await waitFor(() =>
      expect(screen.getByText('Preferences saved.')).toBeInTheDocument(),
    );
  });
});

describe('SettingsTab — change password', () => {
  beforeEach(async () => {
    api.get.mockResolvedValue({ data: PROFILE });
    renderTab();
    await waitFor(() => screen.getByDisplayValue('Jane'));
  });

  const fillPasswordForm = async (user, current, next, confirm) => {
    await user.type(screen.getByLabelText('Current Password'), current);
    await user.type(screen.getByLabelText('New Password'), next);
    await user.type(screen.getByLabelText('Confirm Password'), confirm);
  };

  it('POSTs to /auth/change-password/ with correct field names', async () => {
    api.post.mockResolvedValue({ data: { detail: 'Password updated successfully.' } });
    const user = userEvent.setup();
    await fillPasswordForm(user, 'OldPass123!', 'NewPass456!', 'NewPass456!');
    await user.click(screen.getByRole('button', { name: /update password/i }));

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith('/auth/change-password/', {
        current_password: 'OldPass123!',
        new_password: 'NewPass456!',
        confirm_password: 'NewPass456!',
      });
    });
  });

  it('shows success alert after password update', async () => {
    api.post.mockResolvedValue({ data: { detail: 'Password updated successfully.' } });
    const user = userEvent.setup();
    await fillPasswordForm(user, 'OldPass123!', 'NewPass456!', 'NewPass456!');
    await user.click(screen.getByRole('button', { name: /update password/i }));

    await waitFor(() =>
      expect(screen.getByText('Password updated successfully.')).toBeInTheDocument(),
    );
  });

  it('shows mismatch error without API call when passwords differ', async () => {
    const user = userEvent.setup();
    await fillPasswordForm(user, 'OldPass123!', 'NewPass456!', 'Different789!');
    await user.click(screen.getByRole('button', { name: /update password/i }));

    expect(screen.getByText('Passwords do not match.')).toBeInTheDocument();
    expect(api.post).not.toHaveBeenCalled();
  });

  it('shows backend error for wrong current password', async () => {
    api.post.mockRejectedValue({ response: { status: 400 } });
    parseErrors.mockReturnValue({ current_password: 'Current password is incorrect.' });
    const user = userEvent.setup();
    await fillPasswordForm(user, 'WrongPass!', 'NewPass456!', 'NewPass456!');
    await user.click(screen.getByRole('button', { name: /update password/i }));

    await waitFor(() => {
      const errorEl = screen.getAllByText(/current password is incorrect/i)[0];
      expect(errorEl).toBeInTheDocument();
    });
  });

  it('clears password fields after successful update', async () => {
    api.post.mockResolvedValue({ data: { detail: 'OK' } });
    const user = userEvent.setup();
    await fillPasswordForm(user, 'OldPass123!', 'NewPass456!', 'NewPass456!');
    await user.click(screen.getByRole('button', { name: /update password/i }));

    await waitFor(() => {
      expect(screen.getByLabelText('Current Password')).toHaveValue('');
      expect(screen.getByLabelText('New Password')).toHaveValue('');
    });
  });
});
