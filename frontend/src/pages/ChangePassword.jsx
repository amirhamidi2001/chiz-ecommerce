import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import api, { parseErrors } from '../services/api';

const Spinner = () => (
  <svg className="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
  </svg>
);

const FieldError = ({ msg }) =>
  msg ? <p className="text-red-500 text-xs mt-1">{msg}</p> : null;

const ChangePassword = () => {
  const navigate = useNavigate();
  const [formData, setFormData] = useState({
    currentPassword: '', newPassword: '', confirmPassword: '',
  });
  const [errors, setErrors]     = useState({});
  const [isLoading, setIsLoading] = useState(false);
  const [success, setSuccess]   = useState(false);
  const [showPw, setShowPw]     = useState({ current: false, new: false, confirm: false });

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
    if (errors[name]) setErrors((prev) => ({ ...prev, [name]: '' }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setErrors({});

    if (!formData.currentPassword) {
      setErrors({ currentPassword: 'Current password is required.' });
      return;
    }
    if (formData.newPassword.length < 8) {
      setErrors({ newPassword: 'Password must be at least 8 characters.' });
      return;
    }
    if (formData.newPassword !== formData.confirmPassword) {
      setErrors({ confirmPassword: 'Passwords do not match.' });
      return;
    }

    setIsLoading(true);
    try {
      // POST /api/auth/change-password/
      await api.post('/auth/change-password/', {
        current_password: formData.currentPassword,
        new_password:     formData.newPassword,
        confirm_password: formData.confirmPassword,
      });
      setSuccess(true);
      setTimeout(() => navigate('/account'), 2500);
    } catch (err) {
      const errs = parseErrors(err);
      setErrors({
        // Map backend field names to local form field names
        currentPassword:  errs.current_password,
        newPassword:      errs.new_password,
        confirmPassword:  errs.confirm_password,
        non_field_errors: errs.non_field_errors,
      });
    } finally {
      setIsLoading(false);
    }
  };

  const fields = [
    { name: 'currentPassword', label: 'Current Password', showKey: 'current', auto: 'current-password', icon: 'bi-lock' },
    { name: 'newPassword',     label: 'New Password',     showKey: 'new',     auto: 'new-password',     icon: 'bi-key' },
    { name: 'confirmPassword', label: 'Confirm Password', showKey: 'confirm', auto: 'new-password',     icon: 'bi-lock-fill' },
  ];

  return (
    <>
      {/* Breadcrumb */}
      <div className="bg-gray-50 py-12 border-b">
        <div className="container mx-auto px-4 flex flex-col md:flex-row justify-between items-center">
          <h1 className="text-3xl font-bold text-gray-900 mb-2 md:mb-0">Change Password</h1>
          <nav className="text-sm">
            <ol className="flex gap-2">
              <li><Link to="/" className="text-teal-700 hover:underline">Home</Link></li>
              <li className="text-gray-400">/</li>
              <li><Link to="/account" className="text-teal-700 hover:underline">Account</Link></li>
              <li className="text-gray-400">/</li>
              <li className="text-gray-600">Change Password</li>
            </ol>
          </nav>
        </div>
      </div>

      <section className="py-16 bg-white">
        <div className="container mx-auto px-4">
          <div className="max-w-md mx-auto">
            <div className="bg-white rounded-2xl shadow-xl border border-gray-100 p-6 md:p-8">

              <div className="text-center mb-6">
                <i className="bi bi-shield-lock text-4xl text-teal-600 mb-2 block" />
                <h3 className="text-2xl font-bold text-gray-800">Change Password</h3>
                <p className="text-gray-500 text-sm mt-1">Update your account password.</p>
              </div>

              {/* ── Success state ── */}
              {success ? (
                <div className="text-center space-y-4 py-2">
                  <i className="bi bi-check-circle-fill text-5xl text-emerald-500" />
                  <div>
                    <p className="text-gray-700 font-medium">Password changed successfully!</p>
                    <p className="text-gray-500 text-sm mt-1">Redirecting to your account…</p>
                  </div>
                  <Link to="/account" className="inline-block text-teal-600 hover:underline text-sm font-medium">
                    Go to Account now
                  </Link>
                </div>
              ) : (
                /* ── Form ── */
                <form onSubmit={handleSubmit} noValidate className="space-y-5">
                  {/* Top-level non-field error */}
                  {errors.non_field_errors && (
                    <div className="px-4 py-3 bg-red-50 border border-red-200 rounded-lg text-red-600 text-sm flex items-start gap-2">
                      <i className="bi bi-exclamation-circle mt-0.5 shrink-0" />
                      <span>{errors.non_field_errors}</span>
                    </div>
                  )}

                  {fields.map(({ name, label, showKey, auto, icon }) => (
                    <div key={name} className="relative">
                      <i className={`bi ${icon} absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none`} />
                      <input
                        type={showPw[showKey] ? 'text' : 'password'}
                        name={name}
                        value={formData[name]}
                        onChange={handleChange}
                        placeholder={label}
                        autoComplete={auto}
                        className={`w-full border rounded-lg pl-10 pr-10 py-3 focus:outline-none focus:border-teal-500 transition ${errors[name] ? 'border-red-400' : 'border-gray-300'}`}
                        required
                      />
                      <button
                        type="button"
                        onClick={() => setShowPw((p) => ({ ...p, [showKey]: !p[showKey] }))}
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-teal-600 transition"
                        aria-label="Toggle visibility"
                      >
                        <i className={`bi ${showPw[showKey] ? 'bi-eye-slash' : 'bi-eye'}`} />
                      </button>
                      <FieldError msg={errors[name]} />
                    </div>
                  ))}

                  <button
                    type="submit"
                    disabled={isLoading}
                    className="w-full bg-teal-600 text-white py-3 rounded-lg font-semibold hover:bg-teal-700 transition flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {isLoading ? <><Spinner /> Updating…</> : 'Update Password'}
                  </button>
                </form>
              )}

              {!success && (
                <div className="text-center mt-6 text-sm">
                  <Link to="/account" className="text-teal-600 hover:underline">
                    <i className="bi bi-arrow-left me-1" /> Back to Account
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

export default ChangePassword;
