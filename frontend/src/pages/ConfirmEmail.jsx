import { useState, useEffect } from 'react';
import { Link, useParams } from 'react-router-dom';
import api, { parseErrors } from '../services/api';

const Spinner = () => (
  <svg className="animate-spin h-5 w-5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
  </svg>
);

// Status values: 'pending' | 'verifying' | 'success' | 'error' | 'info'
const ConfirmEmail = () => {
  const { key } = useParams(); // present when user clicks the emailed link

  const [status, setStatus]   = useState(key ? 'verifying' : 'info');
  const [message, setMessage] = useState('');

  // ── If a key is in the URL, call the verification endpoint ─────────────
  useEffect(() => {
    if (!key) return;

    const verify = async () => {
      setStatus('verifying');
      try {
        // POST /api/auth/confirm-email/  — add this endpoint when ready
        await api.post('/auth/confirm-email/', { key });
        setStatus('success');
      } catch (err) {
        const errors = parseErrors(err);
        setMessage(
          errors.key ||
          errors.detail ||
          errors.non_field_errors ||
          'This verification link is invalid or has already been used.',
        );
        setStatus('error');
      }
    };

    verify();
  }, [key]);

  // ── Resend verification email ───────────────────────────────────────────
  const [resendLoading, setResendLoading] = useState(false);
  const [resendAlert, setResendAlert]     = useState(null);

  const handleResend = async () => {
    setResendLoading(true);
    setResendAlert(null);
    try {
      await api.post('/auth/resend-confirmation/');
      setResendAlert({ type: 'success', msg: 'A new verification email has been sent.' });
    } catch (err) {
      const errors = parseErrors(err);
      setResendAlert({
        type: 'error',
        msg: errors.non_field_errors || errors.detail || 'Failed to resend. Please try again.',
      });
    } finally {
      setResendLoading(false);
    }
  };

  // ──────────────────────────────────────────────────────────────────────
  // UI helpers
  // ──────────────────────────────────────────────────────────────────────
  const StateIcon = ({ name, colorClass }) => (
    <i className={`bi ${name} text-5xl ${colorClass} block mb-4`} />
  );

  return (
    <>
      {/* Breadcrumb */}
      <div className="bg-gray-50 py-12 border-b">
        <div className="container mx-auto px-4 flex flex-col md:flex-row justify-between items-center">
          <h1 className="text-3xl font-bold text-gray-900 mb-2 md:mb-0">Email Confirmation</h1>
          <nav className="text-sm">
            <ol className="flex gap-2">
              <li><Link to="/" className="text-teal-700 hover:underline">Home</Link></li>
              <li className="text-gray-400">/</li>
              <li className="text-gray-600">Email Confirmation</li>
            </ol>
          </nav>
        </div>
      </div>

      <section className="py-16 bg-white">
        <div className="container mx-auto px-4">
          <div className="max-w-md mx-auto">
            <div className="bg-white rounded-2xl shadow-xl border border-gray-100 p-6 md:p-8 text-center">

              {/* ── Verifying ── */}
              {status === 'verifying' && (
                <div className="space-y-4 py-4">
                  <div className="flex justify-center">
                    <div className="w-14 h-14 rounded-full bg-teal-50 flex items-center justify-center">
                      <Spinner />
                    </div>
                  </div>
                  <p className="text-gray-700 font-medium">Verifying your email…</p>
                  <p className="text-gray-500 text-sm">Please wait a moment.</p>
                </div>
              )}

              {/* ── Success ── */}
              {status === 'success' && (
                <div className="space-y-4 py-2">
                  <StateIcon name="bi-patch-check-fill" colorClass="text-emerald-500" />
                  <div>
                    <p className="text-gray-800 text-xl font-bold">Email Verified!</p>
                    <p className="text-gray-500 text-sm mt-2">
                      Your account is now active. You can sign in and start using your account.
                    </p>
                  </div>
                  <Link
                    to="/login"
                    className="inline-block mt-4 px-6 py-2.5 bg-teal-600 text-white rounded-lg font-semibold hover:bg-teal-700 transition text-sm"
                  >
                    Sign In <i className="bi bi-arrow-right ms-1" />
                  </Link>
                </div>
              )}

              {/* ── Error (invalid / expired link) ── */}
              {status === 'error' && (
                <div className="space-y-4 py-2">
                  <StateIcon name="bi-x-circle-fill" colorClass="text-red-400" />
                  <div>
                    <p className="text-gray-800 text-xl font-bold">Verification Failed</p>
                    <p className="text-gray-500 text-sm mt-2">{message}</p>
                  </div>

                  {resendAlert && (
                    <div className={`px-4 py-3 border rounded-lg text-sm flex items-start gap-2 text-left ${resendAlert.type === 'success' ? 'bg-emerald-50 border-emerald-200 text-emerald-700' : 'bg-red-50 border-red-200 text-red-600'}`}>
                      <i className={`bi ${resendAlert.type === 'success' ? 'bi-check-circle' : 'bi-exclamation-circle'} mt-0.5 shrink-0`} />
                      <span>{resendAlert.msg}</span>
                    </div>
                  )}

                  <button
                    onClick={handleResend}
                    disabled={resendLoading}
                    className="inline-flex items-center gap-2 px-5 py-2.5 bg-teal-600 text-white rounded-lg font-semibold hover:bg-teal-700 transition text-sm disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {resendLoading ? <><Spinner /> Sending…</> : <><i className="bi bi-envelope" /> Resend Verification Email</>}
                  </button>
                </div>
              )}

              {/* ── Info (shown after registration, before any link is clicked) ── */}
              {status === 'info' && (
                <div className="space-y-4 py-2">
                  <StateIcon name="bi-envelope-open" colorClass="text-teal-600" />
                  <div>
                    <p className="text-gray-800 text-xl font-bold">Check Your Inbox</p>
                    <p className="text-gray-500 text-sm mt-2">
                      We've sent a verification link to your email address.
                      Please click the link to activate your account.
                    </p>
                  </div>

                  <div className="bg-gray-50 border border-gray-200 rounded-lg p-4 text-left text-sm text-gray-600 space-y-1.5">
                    <p className="flex items-center gap-2"><i className="bi bi-clock text-gray-400" /> The link expires in <strong>24 hours</strong>.</p>
                    <p className="flex items-center gap-2"><i className="bi bi-folder2 text-gray-400" /> Check your spam or junk folder if you don't see it.</p>
                  </div>

                  {resendAlert && (
                    <div className={`px-4 py-3 border rounded-lg text-sm flex items-start gap-2 text-left ${resendAlert.type === 'success' ? 'bg-emerald-50 border-emerald-200 text-emerald-700' : 'bg-red-50 border-red-200 text-red-600'}`}>
                      <i className={`bi ${resendAlert.type === 'success' ? 'bi-check-circle' : 'bi-exclamation-circle'} mt-0.5 shrink-0`} />
                      <span>{resendAlert.msg}</span>
                    </div>
                  )}

                  <button
                    onClick={handleResend}
                    disabled={resendLoading}
                    className="text-sm text-teal-600 hover:underline font-medium flex items-center gap-1.5 mx-auto disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {resendLoading ? <><Spinner /> Sending…</> : 'Resend verification email'}
                  </button>

                  <div className="pt-2 border-t border-gray-100">
                    <Link to="/login" className="text-sm text-teal-600 hover:underline">
                      <i className="bi bi-arrow-left me-1" /> Back to Login
                    </Link>
                  </div>
                </div>
              )}

            </div>
          </div>
        </div>
      </section>
    </>
  );
};

export default ConfirmEmail;
