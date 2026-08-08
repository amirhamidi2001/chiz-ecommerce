// src/__tests__/Login.test.jsx
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { vi } from 'vitest';

import Login from '../pages/Login';
import api, { setTokens, parseErrors } from '../services/api';

// ─── Mocks ────────────────────────────────────────────────────────────────

const mockNavigate = vi.fn();

// Add mock functions for the auth methods
const mockLogin = vi.fn();
const mockHydrateUser = vi.fn();

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual, // This brings back the real, working useSearchParams
    useNavigate: () => mockNavigate,
  };
});

// Mock the context hook
vi.mock('../context/AuthContext', () => ({
  useAuth: () => ({
    login: mockLogin,
    hydrateUser: mockHydrateUser,
  }),
}));

vi.mock('../services/api', () => ({
  default: { post: vi.fn() },
  setTokens: vi.fn(),
  parseErrors: vi.fn(),
  isAuthenticated: vi.fn(() => false),
}));

// ─── Helpers ──────────────────────────────────────────────────────────────

const renderLogin = (search = '') =>
  render(
    <MemoryRouter initialEntries={[`/login${search}`]}>
      <Login />
    </MemoryRouter>,
  );

const fillLoginForm = async (user, email = 'a@b.com', password = 'Pass123!') => {
  await user.type(screen.getByPlaceholderText('Email address'), email);
  await user.type(screen.getByPlaceholderText('Password'), password);
};

const fillRegisterForm = async (user, overrides = {}) => {
  const defaults = {
    firstName: 'John',
    lastName: 'Doe',
    email: 'john@example.com',
    password: 'Pass123!',
    confirmPassword: 'Pass123!',
  };
  const vals = { ...defaults, ...overrides };

  // Use findBy to asynchronously wait for the register form transition to complete
  const firstNameInput = await screen.findByPlaceholderText('First name');
  await user.type(firstNameInput, vals.firstName);

  // Once the first input is present, the rest are rendered, so getBy is perfectly fine here
  await user.type(screen.getByPlaceholderText('Last name'), vals.lastName);
  await user.type(screen.getByPlaceholderText('Email address'), vals.email);
  await user.type(screen.getByPlaceholderText('Create password'), vals.password);
  await user.type(screen.getByPlaceholderText('Confirm password'), vals.confirmPassword);
};

// ─── Tests ─────────────────────────────────────────────────────────────────

describe('Login page — login form', () => {
  it('renders the login form by default', () => {
    renderLogin();
    expect(screen.getByText('Welcome Back')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Email address')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Password')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /sign in/i })).toBeInTheDocument();
  });

  it('navigates to /account on successful login', async () => {
    const user = userEvent.setup();
    // Resolve the context login method instead of api.post
    mockLogin.mockResolvedValue({ id: 1, email: 'a@b.com' });
    renderLogin();

    await fillLoginForm(user);
    await user.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() => {
      expect(mockLogin).toHaveBeenCalledWith({
        email: 'a@b.com',
        password: 'Pass123!',
      });
      expect(mockNavigate).toHaveBeenCalledWith('/account');
    });
  });

  it('calls the login context method with correct payload', async () => {
    const user = userEvent.setup();
    mockLogin.mockResolvedValue({ id: 1, email: 'test@example.com' });
    renderLogin();

    await fillLoginForm(user, 'test@example.com', 'MyPass123!');
    await user.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() => {
      expect(mockLogin).toHaveBeenCalledWith({
        email: 'test@example.com',
        password: 'MyPass123!',
      });
    });
  });

  it('displays backend error banner on invalid credentials', async () => {
    const user = userEvent.setup();
    mockLogin.mockRejectedValue(new Error('Unauthorized'));
    parseErrors.mockReturnValue({
      detail: 'No active account found with the given credentials',
    });
    renderLogin();
    await fillLoginForm(user);
    await user.click(screen.getByRole('button', { name: /sign in/i }));
    await waitFor(() => {
      expect(
        screen.getByText('No active account found with the given credentials'),
      ).toBeInTheDocument();
    });
  });

  it('shows fallback error message when detail field is absent', async () => {
    const user = userEvent.setup();
    mockLogin.mockRejectedValue(new Error('Unauthorized'));
    parseErrors.mockReturnValue({});
    renderLogin();
    await fillLoginForm(user);
    await user.click(screen.getByRole('button', { name: /sign in/i }));
    await waitFor(() => {
      expect(screen.getByText('Invalid email or password.')).toBeInTheDocument();
    });
  });

  it('disables submit button while request is in flight', async () => {
    const user = userEvent.setup();
    let resolveLogin;
    mockLogin.mockReturnValue(new Promise((res) => { resolveLogin = res; }));
    renderLogin();
    await fillLoginForm(user);
    await user.click(screen.getByRole('button', { name: /sign in/i }));
    const loadingButton = await screen.findByRole('button', { name: /signing in/i });
    expect(loadingButton).toBeDisabled();
    resolveLogin({ id: 1, email: 'a@b.com' });
  });

  it('toggles password visibility', async () => {
    const user = userEvent.setup();
    renderLogin();
    const input = screen.getByPlaceholderText('Password');
    const toggle = screen.getAllByRole('button', { name: /toggle/i })[0];

    expect(input).toHaveAttribute('type', 'password');
    await user.click(toggle);
    expect(input).toHaveAttribute('type', 'text');
    await user.click(toggle);
    expect(input).toHaveAttribute('type', 'password');
  });

  it('switches to register form when "Create account" is clicked', async () => {
    const user = userEvent.setup();
    renderLogin();
    await user.click(screen.getByRole('button', { name: /create account/i }));
    expect(screen.getByRole('heading', { name: 'Create Account', level: 3 })).toBeInTheDocument();
  });
});

describe('Login page — register form', () => {
  it('renders register form', async () => {
    const user = userEvent.setup();
    renderLogin();
    await user.click(screen.getByRole('button', { name: /create account/i }));
    expect(screen.getByPlaceholderText('First name')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Last name')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Create password')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Confirm password')).toBeInTheDocument();
  });

  it('calls POST /auth/register/ with snake_case field names', async () => {
    const user = userEvent.setup();
    api.post.mockResolvedValue({ data: { access: 'a', refresh: 'r' } });
    renderLogin();
    await user.click(screen.getByRole('button', { name: /create account/i }));
    expect(await screen.findByPlaceholderText('First name')).toBeInTheDocument();

    await fillRegisterForm(user);
    await user.click(screen.getByRole('checkbox'));   // terms
    await user.click(screen.getByRole('button', { name: /create account/i }));

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith('/auth/register/', {
        email: 'john@example.com',
        first_name: 'John',
        last_name: 'Doe',
        password: 'Pass123!',
      });
    });
  });

  it('shows password mismatch error without making an API call', async () => {
    const user = userEvent.setup();
    renderLogin();
    await user.click(screen.getByRole('button', { name: /create account/i }));

    await fillRegisterForm(user, { password: 'Pass123!', confirmPassword: 'Different!' });
    await user.click(screen.getByRole('checkbox'));
    await user.click(screen.getByRole('button', { name: /create account/i }));

    expect(screen.getByText('Passwords do not match.')).toBeInTheDocument();
    expect(api.post).not.toHaveBeenCalled();
  });

  it('shows error if terms checkbox is not ticked', async () => {
    const user = userEvent.setup();
    renderLogin();
    await user.click(screen.getByRole('button', { name: /create account/i }));

    await fillRegisterForm(user);
    // Do NOT tick the checkbox
    await user.click(screen.getByRole('button', { name: /create account/i }));

    expect(screen.getByText(/must agree/i)).toBeInTheDocument();
    expect(api.post).not.toHaveBeenCalled();
  });

  it('displays per-field backend error under the right input', async () => {
    const user = userEvent.setup();
    api.post.mockRejectedValue({ response: { status: 400 } });
    parseErrors.mockReturnValue({ email: 'A user with this email already exists.' });
    renderLogin();
    await user.click(screen.getByRole('button', { name: /create account/i }));

    await fillRegisterForm(user);
    await user.click(screen.getByRole('checkbox'));
    await user.click(screen.getByRole('button', { name: /create account/i }));

    await waitFor(() => {
      expect(
        screen.getByText('A user with this email already exists.'),
      ).toBeInTheDocument();
    });
  });

  it('stores tokens and navigates to /account after successful registration', async () => {
    const user = userEvent.setup();
    api.post.mockResolvedValue({ data: { access: 'acc', refresh: 'ref' } });
    renderLogin();
    await user.click(screen.getByRole('button', { name: /create account/i }));

    await fillRegisterForm(user);
    await user.click(screen.getByRole('checkbox'));
    await user.click(screen.getByRole('button', { name: /create account/i }));

    await waitFor(() => {
      expect(setTokens).toHaveBeenCalledWith({ access: 'acc', refresh: 'ref' });
      expect(mockNavigate).toHaveBeenCalledWith('/account');
    });
  });
});
