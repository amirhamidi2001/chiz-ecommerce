import { useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import api, { parseErrors } from '../services/api';

const Spinner = () => (
  <svg className="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
  </svg>
);

const FieldError = ({ msg }) =>
  msg ? <p className="text-red-500 text-xs mt-1">{msg}</p> : null;

const ResetPassword = () => {
  const navigate = useNavigate();
  // Both uid (base64-encoded PK) and token come from the emailed link.
  const { uid, token } = useParams();

  const [formData, setFormData] = useState({ password: '', confirmPassword: '' });
  const [errors, setErrors]     = useState({});
  const [isLoading, setIsLoading] = useState(false);
  const [isSuccess, setIsSuccess] = useState(false);
  const [showPw, setShowPw]       = useState({ password: false, confirm: false });

  // Validate that the URL contains the required params before the user submits.
  const invalidLink = !uid || !token;

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
    if (errors[name]) setErrors((prev) => ({ ...prev, [name]: '' }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setErrors({});

    if (!formData.password) {
      setErrors({ password: 'Password is required.' });
      return;
    }
    if (formData.password.length < 8) {
      setErrors({ password: 'Password must be at least 8 characters.' });
      return;
    }
    if (formData.password !== formData.confirmPassword) {
      setErrors({ confirmPassword: 'Passwords do not match.' });
      return;
    }

    setIsLoading(true);
    try {
      // POST /api/auth/password-reset/confirm/
      await api.post('/auth/password-reset/confirm/', {
        uid,
        token,
        new_password:     formData.password,
        confirm_password: formData.confirmPassword,
      });
      setIsSuccess(true);
      setTimeout(() => navigate('/login'), 3000);
    } catch (err) {
      const errs = parseErrors(err);
      setErrors({
        // Show token / uid errors as a top-level message
        non_field_errors:
          errs.token    ||
          errs.uid      ||
          errs.non_field_errors ||
          'Failed to reset password. The link may have expired.',
        new_password:     errs.new_password,
        confirm_password: errs.confirm_password,
      });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <>
      {/* Breadcrumb */}
      <div className="bg-gray-50 py-12 border-b">
        <div className="container mx-auto px-4 flex flex-col md:flex-row justify-between items-center">
          <h1 className="text-3xl font-bold text-gray-900 mb-2 md:mb-0">Reset Password</h1>
          <nav className="text-sm">
            <ol className="flex gap-2">
              <li><Link to="/" className="text-teal-700 hover:underline">Home</Link></li>
              <li className="text-gray-400">/</li>
              <li className="text-gray-600">Reset Password</li>
            </ol>
          </nav>
        </div>
      </div>

      <section className="py-16 bg-white">
        <div className="container mx-auto px-4">
          <div className="max-w-md mx-auto">
            <div className="bg-white rounded-2xl shadow-xl border border-gray-100 p-6 md:p-8">

              <div className="text-center mb-6">
                <i className="bi bi-key text-4xl text-teal-600 mb-2 block" />
                <h3 className="text-2xl font-bold text-gray-800">Set New Password</h3>
                <p className="text-gray-500 text-sm mt-1">Enter your new password below.</p>
              </div>

              {/* Invalid link guard */}
              {invalidLink && (
                <div className="text-center space-y-4 py-2">
                  <i className="bi bi-exclamation-triangle text-4xl text-amber-500" />
                  <p className="text-gray-700 font-medium">Invalid reset link</p>
                  <p className="text-gray-500 text-sm">
                    This link is missing required parameters. Please request a new one.
                  </p>
                  <Link
                    to="/forgot-password"
                    className="inline-block mt-2 px-5 py-2 bg-teal-600 text-white rounded-lg font-semibold hover:bg-teal-700 transition text-sm"
                  >
                    Request new link
                  </Link>
                </div>
              )}

              {/* Success state */}
              {!invalidLink && isSuccess && (
                <div className="text-center space-y-4 py-2">
                  <i className="bi bi-check-circle-fill text-5xl text-emerald-500" />
                  <div>
                    <p className="text-gray-700 font-medium">Password reset successfully!</p>
                    <p className="text-gray-500 text-sm mt-1">Redirecting to login…</p>
                  </div>
                  <Link to="/login" className="inline-block text-teal-600 hover:underline text-sm font-medium">
                    Go to Login now
                  </Link>
                </div>
              )}

              {/* Reset form */}
              {!invalidLink && !isSuccess && (
                <form onSubmit={handleSubmit} noValidate className="space-y-4">
                  {errors.non_field_errors && (
                    <div className="px-4 py-3 bg-red-50 border border-red-200 rounded-lg text-red-600 text-sm flex items-start gap-2">
                      <i className="bi bi-exclamation-circle mt-0.5 shrink-0" />
                      <span>{errors.non_field_errors}</span>
                    </div>
                  )}

                  {/* New password */}
                  <div className="relative">
                    <label className="block text-sm font-medium mb-1">New Password</label>
                    <i className="bi bi-lock absolute left-3 top-[2.15rem] text-gray-400 pointer-events-none" />
                    <input
                      type={showPw.password ? 'text' : 'password'}
                      name="password"
                      value={formData.password}
                      onChange={handleChange}
                      className={`w-full border rounded-lg pl-10 pr-10 py-3 focus:outline-none focus:border-teal-500 transition ${errors.password || errors.new_password ? 'border-red-400' : 'border-gray-300'}`}
                      placeholder="New password (min. 8 characters)"
                      autoComplete="new-password"
                      required
                    />
                    <button
                      type="button"
                      onClick={() => setShowPw((p) => ({ ...p, password: !p.password }))}
                      className="absolute right-3 top-[2.15rem] text-gray-400 hover:text-teal-600 transition"
                      aria-label="Toggle"
                    >
                      <i className={`bi ${showPw.password ? 'bi-eye-slash' : 'bi-eye'}`} />
                    </button>
                    <FieldError msg={errors.password || errors.new_password} />
                  </div>

                  {/* Confirm password */}
                  <div className="relative">
                    <label className="block text-sm font-medium mb-1">Confirm Password</label>
                    <i className="bi bi-lock-fill absolute left-3 top-[2.15rem] text-gray-400 pointer-events-none" />
                    <input
                      type={showPw.confirm ? 'text' : 'password'}
                      name="confirmPassword"
                      value={formData.confirmPassword}
                      onChange={handleChange}
                      className={`w-full border rounded-lg pl-10 pr-10 py-3 focus:outline-none focus:border-teal-500 transition ${errors.confirmPassword || errors.confirm_password ? 'border-red-400' : 'border-gray-300'}`}
                      placeholder="Confirm new password"
                      autoComplete="new-password"
                      required
                    />
                    <button
                      type="button"
                      onClick={() => setShowPw((p) => ({ ...p, confirm: !p.confirm }))}
                      className="absolute right-3 top-[2.15rem] text-gray-400 hover:text-teal-600 transition"
                      aria-label="Toggle"
                    >
                      <i className={`bi ${showPw.confirm ? 'bi-eye-slash' : 'bi-eye'}`} />
                    </button>
                    <FieldError msg={errors.confirmPassword || errors.confirm_password} />
                  </div>

                  <button
                    type="submit"
                    disabled={isLoading}
                    className="w-full bg-teal-600 text-white py-3 rounded-lg font-semibold hover:bg-teal-700 transition flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {isLoading ? <><Spinner /> Resetting…</> : 'Reset Password'}
                  </button>
                </form>
              )}

              {!isSuccess && (
                <div className="text-center mt-6 text-sm">
                  <Link to="/login" className="text-teal-600 hover:underline">
                    <i className="bi bi-arrow-left me-1" /> Back to Login
                  </Link>
                </div>
              )}
            </div>
          </div>
        </div>
      </section>
    </>
  );
};

export default ResetPassword;
