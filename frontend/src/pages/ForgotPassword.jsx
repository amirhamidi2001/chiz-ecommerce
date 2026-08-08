import { useState } from 'react';
import { Link } from 'react-router-dom';
import api, { parseErrors } from '../services/api';

const Spinner = () => (
  <svg className="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
  </svg>
);

const ForgotPassword = () => {
  const [email, setEmail]           = useState('');
  const [isSubmitted, setIsSubmitted] = useState(false);
  const [error, setError]           = useState('');
  const [isLoading, setIsLoading]   = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    if (!/\S+@\S+\.\S+/.test(email)) {
      setError('Please enter a valid email address.');
      return;
    }

    setIsLoading(true);
    try {
      // POST /api/auth/password-reset/
      // Backend always returns 200 to prevent user enumeration.
      await api.post('/auth/password-reset/', { email });
      setIsSubmitted(true);
    } catch (err) {
      const errors = parseErrors(err);
      setError(errors.email || errors.non_field_errors || 'Something went wrong. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <>
      {/* Breadcrumb */}
      <div className="bg-gray-50 py-12 border-b">
        <div className="container mx-auto px-4 flex flex-col md:flex-row justify-between items-center">
          <h1 className="text-3xl font-bold text-gray-900 mb-2 md:mb-0">Forgot Password</h1>
          <nav className="text-sm">
            <ol className="flex gap-2">
              <li><Link to="/" className="text-teal-700 hover:underline">Home</Link></li>
              <li className="text-gray-400">/</li>
              <li className="text-gray-600">Forgot Password</li>
            </ol>
          </nav>
        </div>
      </div>

      <section className="py-16 bg-white">
        <div className="container mx-auto px-4">
          <div className="max-w-md mx-auto">
            <div className="bg-white rounded-2xl shadow-xl border border-gray-100 p-6 md:p-8">

              <div className="text-center mb-6">
                <i className="bi bi-lock text-4xl text-teal-600 mb-2 block" />
                <h3 className="text-2xl font-bold text-gray-800">Forgot Password?</h3>
                <p className="text-gray-500 text-sm mt-1">
                  Enter your email and we'll send you a reset link.
                </p>
              </div>

              {/* ── Request form ── */}
              {!isSubmitted ? (
                <form onSubmit={handleSubmit} noValidate>
                  <div className="relative mb-4">
                    <i className="bi bi-envelope absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none" />
                    <input
                      type="email"
                      value={email}
                      onChange={(e) => { setEmail(e.target.value); setError(''); }}
                      className={`w-full border rounded-lg pl-10 pr-3 py-3 focus:outline-none focus:border-teal-500 transition ${error ? 'border-red-400' : 'border-gray-300'}`}
                      placeholder="Email address"
                      autoComplete="email"
                      required
                    />
                  </div>

                  {error && (
                    <div className="mb-4 px-4 py-3 bg-red-50 border border-red-200 rounded-lg text-red-600 text-sm flex items-start gap-2">
                      <i className="bi bi-exclamation-circle mt-0.5 shrink-0" />
                      <span>{error}</span>
                    </div>
                  )}

                  <button
                    type="submit"
                    disabled={isLoading}
                    className="w-full bg-teal-600 text-white py-3 rounded-lg font-semibold hover:bg-teal-700 transition flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {isLoading ? <><Spinner /> Sending…</> : 'Send Reset Link'}
                  </button>
                </form>
              ) : (
                /* ── Success state ── */
                <div className="text-center space-y-4 py-2">
                  <i className="bi bi-envelope-check text-5xl text-teal-600" />
                  <div>
                    <p className="text-gray-700 font-medium">Check your inbox</p>
                    <p className="text-gray-500 text-sm mt-1">
                      If an account exists for <strong className="text-gray-700">{email}</strong>,
                      you'll receive a reset link shortly.
                    </p>
                  </div>
                  <p className="text-xs text-gray-400">
                    Didn't receive it? Check your spam folder or{' '}
                    <button
                      onClick={() => setIsSubmitted(false)}
                      className="text-teal-600 hover:underline font-medium"
                    >
                      try again
                    </button>.
                  </p>
                  <Link to="/login" className="inline-block text-teal-600 font-medium hover:underline text-sm">
                    Back to Login
                  </Link>
                </div>
              )}

              {!isSubmitted && (
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

export default ForgotPassword;
