import { useEffect, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { setTokens, parseErrors, authAPI } from '../services/api';
import api from '../services/api';
import { useAuth } from '../context/AuthContext';

// Basic UX-nicety check matching the backend's local Iranian mobile
// format (09XXXXXXXXX, 11 digits). This is NOT a security boundary —
// it only catches obvious typos before hitting the API; the backend
// remains the source of truth for validation.
const IRANIAN_PHONE_REGEX = /^09\d{9}$/;

// ─── Reusable micro-components ─────────────────────────────────────────────
const FieldError = ({ msg }) =>
  msg ? <p className="text-red-500 text-xs mt-1">{msg}</p> : null;

const AlertBanner = ({ msg, type = 'error' }) => {
  if (!msg) return null;
  const cls =
    type === 'success'
      ? 'bg-emerald-50 border-emerald-200 text-emerald-700'
      : 'bg-red-50 border-red-200 text-red-600';
  const icon = type === 'success' ? 'bi-check-circle' : 'bi-exclamation-circle';
  return (
    <div className={`mb-4 px-4 py-3 border rounded-lg text-sm flex items-start gap-2 ${cls}`}>
      <i className={`bi ${icon} mt-0.5 shrink-0`} />
      <span>{msg}</span>
    </div>
  );
};

const Spinner = () => (
  <svg className="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
  </svg>
);

const PwToggle = ({ show, onToggle }) => (
  <button
    type="button"
    onClick={onToggle}
    className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-teal-600 transition"
    aria-label="Toggle password visibility"
  >
    <i className={`bi ${show ? 'bi-eye-slash' : 'bi-eye'}`} />
  </button>
);

// ──────────────────────────────────────────────────────────────────────────

const Login = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [activeForm, setActiveForm] = useState('login');

  // ── FIX: pull login + hydrateUser from AuthContext ──────────────────────
  // login()       → POST /auth/login/ + GET /auth/user/ + setUser()
  // hydrateUser() → GET /auth/user/ + setUser()  (used after register)
  const { login, hydrateUser } = useAuth();

  useEffect(() => {
    setActiveForm(searchParams.get('mode') === 'register' ? 'register' : 'login');
  }, [searchParams]);

  // ── Login ────────────────────────────────────────────────────────────────
  const [loginData, setLoginData] = useState({ email: '', password: '', remember: false });
  const [loginErrors, setLoginErrors] = useState({});
  const [loginLoading, setLoginLoading] = useState(false);
  const [showLoginPw, setShowLoginPw] = useState(false);

  const handleLogin = async (e) => {
    e.preventDefault();
    setLoginErrors({});
    setLoginLoading(true);
    try {
      // FIX: use context login() — it stores tokens AND sets AuthContext.user
      // before we navigate, so ProtectedRoute sees isAuthenticated = true.
      await login({
        email: loginData.email,
        password: loginData.password,
      });
      navigate('/account');
    } catch (err) {
      const errors = parseErrors(err);
      setLoginErrors({
        non_field_errors:
          errors.detail || errors.non_field_errors || 'Invalid email or password.',
      });
    } finally {
      setLoginLoading(false);
    }
  };

  // ── Register ─────────────────────────────────────────────────────────────
  const [regData, setRegData] = useState({
    firstName: '', lastName: '', email: '', password: '', confirmPassword: '', terms: false,
  });
  const [regErrors, setRegErrors] = useState({});
  const [regLoading, setRegLoading] = useState(false);
  const [showRegPw, setShowRegPw] = useState(false);
  const [showRegConf, setShowRegConf] = useState(false);

  const handleRegister = async (e) => {
    e.preventDefault();
    setRegErrors({});

    if (regData.password !== regData.confirmPassword) {
      setRegErrors({ confirmPassword: 'Passwords do not match.' });
      return;
    }
    if (!regData.terms) {
      setRegErrors({ terms: 'You must agree to the Terms of Service and Privacy Policy.' });
      return;
    }

    setRegLoading(true);
    try {
      // Step 1 — create the account; response includes access + refresh tokens
      const { data } = await api.post('/auth/register/', {
        email: regData.email,
        first_name: regData.firstName,
        last_name: regData.lastName,
        password: regData.password,
      });

      // Step 2 — persist the tokens so the Axios interceptor can attach them
      setTokens({ access: data.access, refresh: data.refresh });

      // FIX: Step 3 — hydrate AuthContext.user via GET /auth/user/
      // Without this, user stays null → isAuthenticated false → redirect loop.
      await hydrateUser();

      navigate('/account');
    } catch (err) {
      setRegErrors(parseErrors(err));
    } finally {
      setRegLoading(false);
    }
  };

  const handleGoogleLogin = () => alert('Google login demo. Implement OAuth in a real app.');

  // ── Phone / OTP login ───────────────────────────────────────────────────
  // `step` covers just this task's scope: 'phone' (enter number) ->
  // 'code' (a placeholder confirming we transitioned — the real
  // code-entry UI is built in Task 2.3.2.2). A local state toggle is
  // sufficient for a 2-step flow; no routing needed.
  const [phoneStep, setPhoneStep] = useState('phone');
  const [phone, setPhone] = useState('');
  const [phoneErrors, setPhoneErrors] = useState({});
  const [phoneLoading, setPhoneLoading] = useState(false);

  const handlePhoneSubmit = async (e) => {
    e.preventDefault();
    setPhoneErrors({});

    if (!IRANIAN_PHONE_REGEX.test(phone)) {
      setPhoneErrors({
        phone_number: 'Enter a valid mobile number (e.g. 09123456789).',
      });
      return;
    }

    setPhoneLoading(true);
    try {
      await authAPI.requestOtp(phone);
      setPhoneStep('code');
    } catch (err) {
      const errors = parseErrors(err);
      if (err.response?.status === 429) {
        // Covers both the service-level resend cooldown and the
        // DRF-level throttle — both return { detail: "..." } on a 429.
        setPhoneErrors({
          non_field_errors:
            errors.detail || 'Please wait before requesting another code.',
        });
      } else {
        // 400: field-level validation error from OTPRequestSerializer,
        // e.g. { phone_number: "Enter a valid Iranian mobile number..." }
        setPhoneErrors({
          phone_number: errors.phone_number,
          non_field_errors: !errors.phone_number
            ? errors.detail || errors.non_field_errors || 'Something went wrong. Please try again.'
            : undefined,
        });
      }
    } finally {
      setPhoneLoading(false);
    }
  };

  const pageTitle = activeForm === 'register' ? 'Register' : 'Login';

  return (
    <>
      {/* Breadcrumb bar */}
      <div className="bg-gray-50 py-12 border-b">
        <div className="container mx-auto px-4 flex flex-col md:flex-row justify-between items-center">
          <h1 className="text-3xl font-bold text-gray-900 mb-2 md:mb-0">{pageTitle}</h1>
          <nav className="text-sm">
            <ol className="flex gap-2">
              <li><Link to="/" className="text-teal-700 hover:underline">Home</Link></li>
              <li className="text-gray-400">/</li>
              <li className="text-gray-600">{pageTitle}</li>
            </ol>
          </nav>
        </div>
      </div>

      <section className="py-16 bg-white">
        <div className="container mx-auto px-4">
          <div className="max-w-md mx-auto">
            <div className="bg-white rounded-2xl shadow-xl border border-gray-100 overflow-hidden">

              {/* ════════════ LOGIN FORM ════════════ */}
              {activeForm === 'login' && (
                <div className="p-6 md:p-8">
                  <div className="text-center mb-6">
                    <h3 className="text-2xl font-bold text-gray-800">Welcome Back</h3>
                    <p className="text-gray-500 text-sm mt-1">Sign in to your account</p>
                  </div>

                  <AlertBanner msg={loginErrors.non_field_errors} />

                  <form onSubmit={handleLogin} noValidate>
                    {/* Email */}
                    <div className="relative mb-4">
                      <i className="bi bi-envelope absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none" />
                      <input
                        type="email"
                        value={loginData.email}
                        onChange={(e) => setLoginData({ ...loginData, email: e.target.value })}
                        className={`w-full border rounded-lg pl-10 pr-3 py-3 focus:outline-none focus:border-teal-500 transition ${loginErrors.email ? 'border-red-400' : 'border-gray-300'}`}
                        placeholder="Email address"
                        autoComplete="email"
                        required
                      />
                      <FieldError msg={loginErrors.email} />
                    </div>

                    {/* Password */}
                    <div className="relative mb-4">
                      <i className="bi bi-lock absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none" />
                      <input
                        type={showLoginPw ? 'text' : 'password'}
                        value={loginData.password}
                        onChange={(e) => setLoginData({ ...loginData, password: e.target.value })}
                        className="w-full border border-gray-300 rounded-lg pl-10 pr-10 py-3 focus:outline-none focus:border-teal-500 transition"
                        placeholder="Password"
                        autoComplete="current-password"
                        required
                      />
                      <PwToggle show={showLoginPw} onToggle={() => setShowLoginPw(!showLoginPw)} />
                    </div>

                    <div className="flex justify-between items-center mb-6 text-sm">
                      <label className="flex items-center gap-2 cursor-pointer select-none">
                        <input
                          type="checkbox"
                          checked={loginData.remember}
                          onChange={(e) => setLoginData({ ...loginData, remember: e.target.checked })}
                          className="rounded text-teal-600 focus:ring-teal-500"
                        />
                        <span className="text-gray-600">Remember me</span>
                      </label>
                      <Link to="/forgot-password" className="text-teal-600 hover:underline">
                        Forgot password?
                      </Link>
                    </div>

                    <button
                      type="submit"
                      disabled={loginLoading}
                      className="w-full bg-teal-600 text-white py-3 rounded-lg font-semibold hover:bg-teal-700 transition flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      {loginLoading
                        ? <><Spinner /> Signing in…</>
                        : <>Sign In <i className="bi bi-arrow-right" /></>}
                    </button>

                    <div className="relative my-6">
                      <div className="absolute inset-0 flex items-center"><div className="w-full border-t border-gray-200" /></div>
                      <div className="relative flex justify-center text-sm"><span className="px-3 bg-white text-gray-500">or</span></div>
                    </div>

                    <button type="button" onClick={handleGoogleLogin}
                      className="w-full border border-gray-300 text-gray-700 py-3 rounded-lg font-semibold hover:bg-gray-50 transition flex items-center justify-center gap-2">
                      <i className="bi bi-google" /> Continue with Google
                    </button>

                    <button
                      type="button"
                      onClick={() => { setActiveForm('phone'); setPhoneStep('phone'); setPhoneErrors({}); }}
                      className="w-full border border-gray-300 text-gray-700 py-3 rounded-lg font-semibold hover:bg-gray-50 transition flex items-center justify-center gap-2 mt-3"
                    >
                      <i className="bi bi-phone" /> Continue with Phone
                    </button>

                    <div className="text-center mt-6 text-sm">
                      <span className="text-gray-500">Don't have an account?</span>
                      <button type="button" onClick={() => setActiveForm('register')}
                        className="ml-2 text-teal-600 font-medium hover:underline">
                        Create account
                      </button>
                    </div>
                  </form>
                </div>
              )}

              {/* ════════════ REGISTER FORM ════════════ */}
              {activeForm === 'register' && (
                <div className="p-6 md:p-8">
                  <div className="text-center mb-6">
                    <h3 className="text-2xl font-bold text-gray-800">Create Account</h3>
                    <p className="text-gray-500 text-sm mt-1">Join us today and get started</p>
                  </div>

                  <AlertBanner msg={regErrors.non_field_errors} />

                  <form onSubmit={handleRegister} noValidate>
                    {/* Name row */}
                    <div className="flex flex-col sm:flex-row gap-3 mb-4">
                      {[
                        { field: 'firstName', label: 'First name', errorKey: 'first_name', auto: 'given-name' },
                        { field: 'lastName', label: 'Last name', errorKey: 'last_name', auto: 'family-name' },
                      ].map(({ field, label, errorKey, auto }) => (
                        <div key={field} className="relative flex-1">
                          <i className="bi bi-person absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none" />
                          <input
                            type="text"
                            value={regData[field]}
                            onChange={(e) => setRegData({ ...regData, [field]: e.target.value })}
                            className={`w-full border rounded-lg pl-10 pr-3 py-3 focus:outline-none focus:border-teal-500 transition ${regErrors[errorKey] ? 'border-red-400' : 'border-gray-300'}`}
                            placeholder={label}
                            autoComplete={auto}
                            required
                          />
                          <FieldError msg={regErrors[errorKey]} />
                        </div>
                      ))}
                    </div>

                    {/* Email */}
                    <div className="relative mb-4">
                      <i className="bi bi-envelope absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none" />
                      <input
                        type="email"
                        value={regData.email}
                        onChange={(e) => setRegData({ ...regData, email: e.target.value })}
                        className={`w-full border rounded-lg pl-10 pr-3 py-3 focus:outline-none focus:border-teal-500 transition ${regErrors.email ? 'border-red-400' : 'border-gray-300'}`}
                        placeholder="Email address"
                        autoComplete="email"
                        required
                      />
                      <FieldError msg={regErrors.email} />
                    </div>

                    {/* Password */}
                    <div className="relative mb-4">
                      <i className="bi bi-lock absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none" />
                      <input
                        type={showRegPw ? 'text' : 'password'}
                        value={regData.password}
                        onChange={(e) => setRegData({ ...regData, password: e.target.value })}
                        className={`w-full border rounded-lg pl-10 pr-10 py-3 focus:outline-none focus:border-teal-500 transition ${regErrors.password ? 'border-red-400' : 'border-gray-300'}`}
                        placeholder="Create password"
                        autoComplete="new-password"
                        required
                      />
                      <PwToggle show={showRegPw} onToggle={() => setShowRegPw(!showRegPw)} />
                      <FieldError msg={regErrors.password} />
                    </div>

                    {/* Confirm Password */}
                    <div className="relative mb-4">
                      <i className="bi bi-lock-fill absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none" />
                      <input
                        type={showRegConf ? 'text' : 'password'}
                        value={regData.confirmPassword}
                        onChange={(e) => setRegData({ ...regData, confirmPassword: e.target.value })}
                        className={`w-full border rounded-lg pl-10 pr-10 py-3 focus:outline-none focus:border-teal-500 transition ${regErrors.confirmPassword ? 'border-red-400' : 'border-gray-300'}`}
                        placeholder="Confirm password"
                        autoComplete="new-password"
                        required
                      />
                      <PwToggle show={showRegConf} onToggle={() => setShowRegConf(!showRegConf)} />
                      <FieldError msg={regErrors.confirmPassword} />
                    </div>

                    {/* Terms */}
                    <div className="mb-6">
                      <label className="flex items-start gap-2 cursor-pointer select-none">
                        <input
                          type="checkbox"
                          checked={regData.terms}
                          onChange={(e) => setRegData({ ...regData, terms: e.target.checked })}
                          className="mt-1 rounded text-teal-600 focus:ring-teal-500"
                          required
                        />
                        <span className="text-sm text-gray-600">
                          I agree to the{' '}
                          <Link to="/tos" className="text-teal-600 hover:underline">Terms of Service</Link>
                          {' '}and{' '}
                          <Link to="/privacy" className="text-teal-600 hover:underline">Privacy Policy</Link>
                        </span>
                      </label>
                      <FieldError msg={regErrors.terms} />
                    </div>

                    <button
                      type="submit"
                      disabled={regLoading}
                      className="w-full bg-teal-600 text-white py-3 rounded-lg font-semibold hover:bg-teal-700 transition flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      {regLoading
                        ? <><Spinner /> Creating account…</>
                        : <>Create Account <i className="bi bi-arrow-right" /></>}
                    </button>

                    <div className="relative my-6">
                      <div className="absolute inset-0 flex items-center"><div className="w-full border-t border-gray-200" /></div>
                      <div className="relative flex justify-center text-sm"><span className="px-3 bg-white text-gray-500">or</span></div>
                    </div>

                    <button type="button" onClick={handleGoogleLogin}
                      className="w-full border border-gray-300 text-gray-700 py-3 rounded-lg font-semibold hover:bg-gray-50 transition flex items-center justify-center gap-2">
                      <i className="bi bi-google" /> Sign up with Google
                    </button>

                    <div className="text-center mt-6 text-sm">
                      <span className="text-gray-500">Already have an account?</span>
                      <button type="button" onClick={() => setActiveForm('login')}
                        className="ml-2 text-teal-600 font-medium hover:underline">
                        Sign in
                      </button>
                    </div>
                  </form>
                </div>
              )}

              {/* ════════════ PHONE / OTP LOGIN ════════════ */}
              {activeForm === 'phone' && (
                <div className="p-6 md:p-8">
                  {phoneStep === 'phone' && (
                    <>
                      <div className="text-center mb-6">
                        <h3 className="text-2xl font-bold text-gray-800">Continue with Phone</h3>
                        <p className="text-gray-500 text-sm mt-1">
                          We'll text you a verification code
                        </p>
                      </div>

                      <AlertBanner msg={phoneErrors.non_field_errors} />

                      <form onSubmit={handlePhoneSubmit} noValidate>
                        <div className="relative mb-4">
                          <i className="bi bi-phone absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none" />
                          <input
                            type="tel"
                            inputMode="numeric"
                            value={phone}
                            onChange={(e) => setPhone(e.target.value.trim())}
                            className={`w-full border rounded-lg pl-10 pr-3 py-3 focus:outline-none focus:border-teal-500 transition ${phoneErrors.phone_number ? 'border-red-400' : 'border-gray-300'}`}
                            placeholder="09123456789"
                            autoComplete="tel"
                            required
                          />
                          <FieldError msg={phoneErrors.phone_number} />
                        </div>

                        <button
                          type="submit"
                          disabled={phoneLoading}
                          className="w-full bg-teal-600 text-white py-3 rounded-lg font-semibold hover:bg-teal-700 transition flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                          {phoneLoading
                            ? <><Spinner /> Sending code…</>
                            : <>Send Code <i className="bi bi-arrow-right" /></>}
                        </button>

                        <div className="text-center mt-6 text-sm">
                          <button type="button" onClick={() => setActiveForm('login')}
                            className="text-teal-600 font-medium hover:underline">
                            <i className="bi bi-arrow-left me-1" /> Back to email login
                          </button>
                        </div>
                      </form>
                    </>
                  )}

                  {phoneStep === 'code' && (
                    <>
                      <div className="text-center mb-6">
                        <i className="bi bi-check-circle text-teal-600 text-4xl mb-3 block" />
                        <h3 className="text-2xl font-bold text-gray-800">Check Your Phone</h3>
                        <p className="text-gray-500 text-sm mt-1">
                          We sent a verification code to <span className="font-medium text-gray-700">{phone}</span>
                        </p>
                      </div>

                      {/* Code-entry form is built in Task 2.3.2.2 — this
                          screen only confirms the request→transition
                          worked for this task's scope. */}

                      <div className="text-center text-sm">
                        <button
                          type="button"
                          onClick={() => { setPhoneStep('phone'); setPhoneErrors({}); }}
                          className="text-teal-600 font-medium hover:underline"
                        >
                          <i className="bi bi-arrow-left me-1" /> Use a different number
                        </button>
                      </div>
                    </>
                  )}
                </div>
              )}

            </div>
          </div>
        </div>
      </section>
    </>
  );
};

export default Login;
