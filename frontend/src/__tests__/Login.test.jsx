// src/__tests__/Login.test.jsx
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { vi } from 'vitest';

import Login from '../pages/Login';
import api, { setTokens, parseErrors, authAPI } from '../services/api';

// ─── Mocks ────────────────────────────────────────────────────────────────

const mockNavigate = vi.fn();

// Add mock functions for the auth methods
const mockLogin = vi.fn();
const mockHydrateUser = vi.fn();
const mockLoginWithOtp = vi.fn();

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
    loginWithOtp: mockLoginWithOtp,
  }),
}));

vi.mock('../services/api', () => ({
  default: { post: vi.fn() },
  setTokens: vi.fn(),
  parseErrors: vi.fn(),
  isAuthenticated: vi.fn(() => false),
  authAPI: {
    requestOtp: vi.fn(),
    verifyOtp: vi.fn(),
  },
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

// ─── Phone / OTP login (Tasks 2.3.2.1–2.3.2.3) ─────────────────────────────

const goToPhoneStep = async (user) => {
  await user.click(screen.getByRole('button', { name: /continue with phone/i }));
};

describe('Login page — phone/OTP: phone-entry step', () => {
  it('valid phone calls authAPI.requestOtp with the normalized number and transitions to the code step on 200', async () => {
    const user = userEvent.setup();
    authAPI.requestOtp.mockResolvedValueOnce({ data: { detail: 'Verification code sent.' } });
    renderLogin();

    await goToPhoneStep(user);
    await user.type(screen.getByPlaceholderText('09123456789'), '09123456789');
    await user.click(screen.getByRole('button', { name: /send code/i }));

    await waitFor(() => {
      expect(authAPI.requestOtp).toHaveBeenCalledWith('09123456789');
    });
    expect(await screen.findByText(/enter verification code/i)).toBeInTheDocument();
  });

  it('invalid phone shows a validation error and does NOT call the API', async () => {
    const user = userEvent.setup();
    renderLogin();

    await goToPhoneStep(user);
    await user.type(screen.getByPlaceholderText('09123456789'), '12345');
    await user.click(screen.getByRole('button', { name: /send code/i }));

    expect(await screen.findByText(/enter a valid mobile number/i)).toBeInTheDocument();
    expect(authAPI.requestOtp).not.toHaveBeenCalled();
  });

  it('a 429 response shows the cooldown/throttle error message', async () => {
    const user = userEvent.setup();
    authAPI.requestOtp.mockRejectedValueOnce({
      response: { status: 429, data: { detail: 'Please wait before requesting another code.' } },
    });
    parseErrors.mockReturnValue({ detail: 'Please wait before requesting another code.' });
    renderLogin();

    await goToPhoneStep(user);
    await user.type(screen.getByPlaceholderText('09123456789'), '09123456789');
    await user.click(screen.getByRole('button', { name: /send code/i }));

    expect(
      await screen.findByText('Please wait before requesting another code.'),
    ).toBeInTheDocument();
    // Must not have advanced to the code step on failure.
    expect(screen.queryByText(/enter verification code/i)).not.toBeInTheDocument();
  });
});

describe('Login page — phone/OTP: code-entry step', () => {
  const goToCodeStep = async (user, phone = '09123456789') => {
    authAPI.requestOtp.mockResolvedValueOnce({ data: { detail: 'Verification code sent.' } });
    await goToPhoneStep(user);
    await user.type(screen.getByPlaceholderText('09123456789'), phone);
    await user.click(screen.getByRole('button', { name: /send code/i }));
    await screen.findByText(/enter verification code/i);
  };

  it('submitting a correct code calls loginWithOtp and navigates using is_new_user from the response', async () => {
    const user = userEvent.setup();
    mockLoginWithOtp.mockResolvedValueOnce({
      profile: { id: 1, phone_number: '09123456789' },
      isNewUser: true,
    });
    renderLogin();
    await goToCodeStep(user);

    await user.type(screen.getByPlaceholderText('••••••'), '123456');
    await user.click(screen.getByRole('button', { name: /^verify$/i }));

    await waitFor(() => {
      expect(mockLoginWithOtp).toHaveBeenCalledWith('09123456789', '123456');
    });
    // New user (is_new_user: true) is nudged toward completing their
    // profile (empty first/last name on OTP-created accounts — Task
    // 2.3.1.3) rather than the plain account overview.
    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith('/account?tab=settings');
    });
  });

  it('a returning user (is_new_user: false) navigates to the plain account page', async () => {
    const user = userEvent.setup();
    mockLoginWithOtp.mockResolvedValueOnce({
      profile: { id: 2, phone_number: '09121234567' },
      isNewUser: false,
    });
    renderLogin();
    await goToCodeStep(user, '09121234567');

    await user.type(screen.getByPlaceholderText('••••••'), '654321');
    await user.click(screen.getByRole('button', { name: /^verify$/i }));

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith('/account');
    });
  });

  it('a wrong code (400 with the backend\'s specific error shape) displays the exact inline message', async () => {
    const user = userEvent.setup();
    mockLoginWithOtp.mockRejectedValueOnce({
      response: { status: 400, data: { code: 'Incorrect code.' } },
    });
    parseErrors.mockReturnValue({ code: 'Incorrect code.' });
    renderLogin();
    await goToCodeStep(user);

    await user.type(screen.getByPlaceholderText('••••••'), '000000');
    await user.click(screen.getByRole('button', { name: /^verify$/i }));

    expect(await screen.findByText('Incorrect code.')).toBeInTheDocument();
    // Must not have navigated away on failure.
    expect(mockNavigate).not.toHaveBeenCalledWith(expect.stringMatching(/^\/account/));
  });

  it('an expired code shows the backend\'s specific expired message', async () => {
    const user = userEvent.setup();
    mockLoginWithOtp.mockRejectedValueOnce({
      response: { status: 400, data: { code: 'This code has expired. Please request a new one.' } },
    });
    parseErrors.mockReturnValue({ code: 'This code has expired. Please request a new one.' });
    renderLogin();
    await goToCodeStep(user);

    await user.type(screen.getByPlaceholderText('••••••'), '123456');
    await user.click(screen.getByRole('button', { name: /^verify$/i }));

    expect(
      await screen.findByText('This code has expired. Please request a new one.'),
    ).toBeInTheDocument();
  });

  it('resend is disabled immediately on mount and becomes enabled after the cooldown elapses', async () => {
    // shouldAdvanceTime: true lets vitest's fake timers also progress
    // automatically alongside manual advancement, so userEvent's
    // internal delays and RTL's waitFor/findBy polling (both of which
    // rely on setTimeout under the hood) don't hang waiting on a clock
    // that never otherwise moves — proven necessary for this exact
    // chained-setTimeout-via-effect countdown pattern during Task
    // 2.3.2.2's own manual verification.
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    renderLogin();
    await goToCodeStep(user);

    // Immediately after mount: countdown showing, no clickable resend button.
    expect(screen.getByText(/resend code in 1:00/i)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /^resend code$/i })).not.toBeInTheDocument();

    // Advance in 1-second increments, well past the full 60s cooldown
    // (Task 2.1.2.2's OTP_RESEND_COOLDOWN_SECONDS default, matched on
    // the frontend), so each tick's setState -> re-render -> effect
    // re-schedule fully settles before the next.
    for (let i = 0; i < 200; i += 1) {
      // eslint-disable-next-line no-await-in-loop
      await vi.advanceTimersByTimeAsync(1000);
    }

    expect(await screen.findByRole('button', { name: /^resend code$/i })).toBeEnabled();

    vi.useRealTimers();
  }, 30000);
});
