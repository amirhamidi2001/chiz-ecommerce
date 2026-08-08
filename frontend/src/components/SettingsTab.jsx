import { useState, useEffect, useCallback } from 'react';
import api, { parseErrors } from '../services/api';

// ─── Micro-components ──────────────────────────────────────────────────────
const FieldError = ({ msg }) =>
  msg ? <p className="text-red-500 text-xs mt-1">{msg}</p> : null;

const AlertBanner = ({ msg, type = 'error', onDismiss }) => {
  if (!msg) return null;
  const cls =
    type === 'success'
      ? 'bg-emerald-50 border-emerald-200 text-emerald-700'
      : 'bg-red-50 border-red-200 text-red-600';
  const icon = type === 'success' ? 'bi-check-circle' : 'bi-exclamation-circle';
  return (
    <div className={`px-4 py-3 border rounded-lg text-sm flex items-start gap-2 ${cls}`}>
      <i className={`bi ${icon} mt-0.5 shrink-0`} />
      <span className="flex-1">{msg}</span>
      {onDismiss && (
        <button onClick={onDismiss} className="shrink-0 hover:opacity-70" aria-label="Dismiss">
          <i className="bi bi-x" />
        </button>
      )}
    </div>
  );
};

const Spinner = () => (
  <svg className="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
  </svg>
);

const Toggle = ({ checked, onChange, disabled }) => (
  <label className="relative inline-flex items-center cursor-pointer">
    <input
      type="checkbox"
      checked={checked}
      onChange={onChange}
      disabled={disabled}
      className="sr-only peer"
    />
    <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:bg-teal-600 after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all" />
  </label>
);

// ──────────────────────────────────────────────────────────────────────────

const SettingsTab = () => {
  // ── Profile state ─────────────────────────────────────────────────────
  const [profile, setProfile] = useState({
    email: '', first_name: '', last_name: '', phone_number: '',
    order_updates: true, promotions: false, newsletter: true,
  });
  const [profileLoading, setProfileLoading] = useState(true);
  const [profileFetchError, setProfileFetchError] = useState('');

  // ── Personal info save ─────────────────────────────────────────────────
  const [infoLoading, setInfoLoading]   = useState(false);
  const [infoErrors, setInfoErrors]     = useState({});
  const [infoAlert, setInfoAlert]       = useState(null); // { type, msg }

  // ── Preferences save ──────────────────────────────────────────────────
  const [prefLoading, setPrefLoading]   = useState(false);
  const [prefAlert, setPrefAlert]       = useState(null);

  // ── Password change ───────────────────────────────────────────────────
  const [pwData, setPwData] = useState({
    current_password: '', new_password: '', confirm_password: '',
  });
  const [pwErrors, setPwErrors]   = useState({});
  const [pwLoading, setPwLoading] = useState(false);
  const [pwAlert, setPwAlert]     = useState(null);
  const [showPw, setShowPw]       = useState({ current: false, new: false, confirm: false });

  // ── Fetch profile on mount ────────────────────────────────────────────
  const fetchProfile = useCallback(async () => {
    setProfileLoading(true);
    setProfileFetchError('');
    try {
      const { data } = await api.get('/auth/profile/');
      setProfile({
        email:         data.email         ?? '',
        first_name:    data.first_name    ?? '',
        last_name:     data.last_name     ?? '',
        phone_number:  data.phone_number  ?? '',
        order_updates: data.order_updates ?? true,
        promotions:    data.promotions    ?? false,
        newsletter:    data.newsletter    ?? true,
      });
    } catch {
      setProfileFetchError('Failed to load profile. Please refresh the page.');
    } finally {
      setProfileLoading(false);
    }
  }, []);

  useEffect(() => { fetchProfile(); }, [fetchProfile]);

  // ── Save personal information ─────────────────────────────────────────
  const handleSaveInfo = async (e) => {
    e.preventDefault();
    setInfoErrors({});
    setInfoAlert(null);
    setInfoLoading(true);
    try {
      await api.patch('/auth/profile/', {
        first_name:   profile.first_name,
        last_name:    profile.last_name,
        phone_number: profile.phone_number,
      });
      setInfoAlert({ type: 'success', msg: 'Personal information saved.' });
    } catch (err) {
      const errors = parseErrors(err);
      setInfoErrors(errors);
      setInfoAlert({ type: 'error', msg: errors.non_field_errors || 'Failed to save changes.' });
    } finally {
      setInfoLoading(false);
    }
  };

  // ── Save email preferences (auto-called on toggle change) ─────────────
  const savePreferences = async (updated) => {
    setPrefAlert(null);
    setPrefLoading(true);
    try {
      await api.patch('/auth/profile/', {
        order_updates: updated.order_updates,
        promotions:    updated.promotions,
        newsletter:    updated.newsletter,
      });
      setPrefAlert({ type: 'success', msg: 'Preferences saved.' });
    } catch {
      setPrefAlert({ type: 'error', msg: 'Failed to save preferences. Please try again.' });
    } finally {
      setPrefLoading(false);
    }
  };

  const handleToggle = (key) => {
    const updated = { ...profile, [key]: !profile[key] };
    setProfile(updated);
    savePreferences(updated);
  };

  // ── Change password ───────────────────────────────────────────────────
  const handleChangePassword = async (e) => {
    e.preventDefault();
    setPwErrors({});
    setPwAlert(null);

    if (pwData.new_password !== pwData.confirm_password) {
      setPwErrors({ confirm_password: 'Passwords do not match.' });
      return;
    }

    setPwLoading(true);
    try {
      await api.post('/auth/change-password/', pwData);
      setPwAlert({ type: 'success', msg: 'Password updated successfully.' });
      setPwData({ current_password: '', new_password: '', confirm_password: '' });
    } catch (err) {
      const errors = parseErrors(err);
      setPwErrors(errors);
      setPwAlert({
        type: 'error',
        msg: errors.non_field_errors || errors.current_password || 'Failed to update password.',
      });
    } finally {
      setPwLoading(false);
    }
  };

  // ── Loading / error skeleton ───────────────────────────────────────────
  if (profileLoading) {
    return (
      <div>
        <h2 className="text-2xl font-bold mb-6">Account Settings</h2>
        <div className="space-y-4">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="bg-white border rounded-xl p-6 animate-pulse">
              <div className="h-4 bg-gray-200 rounded w-1/4 mb-4" />
              <div className="grid md:grid-cols-2 gap-4">
                {[...Array(4)].map((__, j) => (
                  <div key={j} className="h-10 bg-gray-100 rounded-lg" />
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (profileFetchError) {
    return (
      <div>
        <h2 className="text-2xl font-bold mb-6">Account Settings</h2>
        <div className="bg-red-50 border border-red-200 rounded-xl p-6 flex items-start gap-3">
          <i className="bi bi-exclamation-circle text-red-500 text-xl mt-0.5" />
          <div>
            <p className="text-red-700 font-medium">{profileFetchError}</p>
            <button
              onClick={fetchProfile}
              className="mt-2 text-sm text-teal-600 hover:underline font-medium"
            >
              Try again
            </button>
          </div>
        </div>
      </div>
    );
  }

  const pwFields = [
    { key: 'current_password', label: 'Current Password', showKey: 'current', auto: 'current-password' },
    { key: 'new_password',     label: 'New Password',     showKey: 'new',     auto: 'new-password' },
    { key: 'confirm_password', label: 'Confirm Password', showKey: 'confirm', auto: 'new-password' },
  ];

  const prefToggles = [
    { key: 'order_updates', label: 'Order Updates',  desc: 'Receive notifications about your order status' },
    { key: 'promotions',    label: 'Promotions',     desc: 'Receive emails about new promotions and deals' },
    { key: 'newsletter',    label: 'Newsletter',     desc: 'Subscribe to our weekly newsletter' },
  ];

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">Account Settings</h2>

      <div className="space-y-8">
        {/* ── Personal Information ─────────────────────────────────────── */}
        <div className="bg-white border rounded-xl p-6">
          <h3 className="text-lg font-semibold mb-4">Personal Information</h3>

          {infoAlert && (
            <div className="mb-4">
              <AlertBanner
                msg={infoAlert.msg}
                type={infoAlert.type}
                onDismiss={() => setInfoAlert(null)}
              />
            </div>
          )}

          <form onSubmit={handleSaveInfo} noValidate>
            <div className="grid md:grid-cols-2 gap-4 mb-4">
              {/* First Name */}
              <div>
                <label className="block text-sm font-medium mb-1">First Name</label>
                <input
                  type="text"
                  value={profile.first_name}
                  onChange={(e) => setProfile({ ...profile, first_name: e.target.value })}
                  className={`w-full border rounded-lg px-3 py-2 focus:outline-none focus:border-teal-500 transition ${infoErrors.first_name ? 'border-red-400' : 'border-gray-300'}`}
                />
                <FieldError msg={infoErrors.first_name} />
              </div>
              {/* Last Name */}
              <div>
                <label className="block text-sm font-medium mb-1">Last Name</label>
                <input
                  type="text"
                  value={profile.last_name}
                  onChange={(e) => setProfile({ ...profile, last_name: e.target.value })}
                  className={`w-full border rounded-lg px-3 py-2 focus:outline-none focus:border-teal-500 transition ${infoErrors.last_name ? 'border-red-400' : 'border-gray-300'}`}
                />
                <FieldError msg={infoErrors.last_name} />
              </div>
              {/* Email (read-only — change via dedicated flow) */}
              <div>
                <label className="block text-sm font-medium mb-1">Email</label>
                <input
                  type="email"
                  value={profile.email}
                  disabled
                  className="w-full border border-gray-200 bg-gray-50 rounded-lg px-3 py-2 text-gray-500 cursor-not-allowed"
                />
                <p className="text-xs text-gray-400 mt-1">Contact support to change your email.</p>
              </div>
              {/* Phone */}
              <div>
                <label className="block text-sm font-medium mb-1">Phone</label>
                <input
                  type="tel"
                  value={profile.phone_number}
                  onChange={(e) => setProfile({ ...profile, phone_number: e.target.value })}
                  className={`w-full border rounded-lg px-3 py-2 focus:outline-none focus:border-teal-500 transition ${infoErrors.phone_number ? 'border-red-400' : 'border-gray-300'}`}
                  placeholder="+1 555 123 4567"
                />
                <FieldError msg={infoErrors.phone_number} />
              </div>
            </div>

            <button
              type="submit"
              disabled={infoLoading}
              className="px-5 py-2 bg-teal-600 text-white rounded-lg hover:bg-teal-700 transition flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed text-sm font-medium"
            >
              {infoLoading ? <><Spinner /> Saving…</> : 'Save Changes'}
            </button>
          </form>
        </div>

        {/* ── Email Preferences ────────────────────────────────────────── */}
        <div className="bg-white border rounded-xl p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold">Email Preferences</h3>
            {prefLoading && (
              <span className="flex items-center gap-1.5 text-xs text-gray-400">
                <Spinner /> Saving…
              </span>
            )}
          </div>

          {prefAlert && (
            <div className="mb-4">
              <AlertBanner
                msg={prefAlert.msg}
                type={prefAlert.type}
                onDismiss={() => setPrefAlert(null)}
              />
            </div>
          )}

          <div className="space-y-4">
            {prefToggles.map(({ key, label, desc }) => (
              <div key={key} className="flex justify-between items-center">
                <div>
                  <p className="font-medium text-sm">{label}</p>
                  <p className="text-xs text-gray-500">{desc}</p>
                </div>
                <Toggle
                  checked={profile[key]}
                  onChange={() => handleToggle(key)}
                  disabled={prefLoading}
                />
              </div>
            ))}
          </div>
        </div>

        {/* ── Security / Change Password ───────────────────────────────── */}
        <div className="bg-white border rounded-xl p-6">
          <h3 className="text-lg font-semibold mb-4">Security</h3>

          {pwAlert && (
            <div className="mb-4">
              <AlertBanner
                msg={pwAlert.msg}
                type={pwAlert.type}
                onDismiss={() => setPwAlert(null)}
              />
            </div>
          )}

          <form onSubmit={handleChangePassword} noValidate className="space-y-4">
            {pwFields.map(({ key, label, showKey, auto }) => (
              <div key={key} className="relative">
                <label htmlFor={key} className="block text-sm font-medium mb-1">{label}</label>
                <input
                  id={key}
                  type={showPw[showKey] ? 'text' : 'password'}
                  value={pwData[key]}
                  onChange={(e) => setPwData({ ...pwData, [key]: e.target.value })}
                  autoComplete={auto}
                  className={`w-full border rounded-lg px-3 pr-10 py-2 focus:outline-none focus:border-teal-500 transition ${pwErrors[key] ? 'border-red-400' : 'border-gray-300'}`}
                />
                <button
                  type="button"
                  onClick={() => setShowPw({ ...showPw, [showKey]: !showPw[showKey] })}
                  className="absolute right-3 top-[2.15rem] text-gray-400 hover:text-teal-600 transition"
                  aria-label="Toggle visibility"
                >
                  <i className={`bi ${showPw[showKey] ? 'bi-eye-slash' : 'bi-eye'}`} />
                </button>
                <FieldError msg={pwErrors[key]} />
              </div>
            ))}

            <button
              type="submit"
              disabled={pwLoading}
              className="px-5 py-2 bg-teal-600 text-white rounded-lg hover:bg-teal-700 transition flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed text-sm font-medium"
            >
              {pwLoading ? <><Spinner /> Updating…</> : 'Update Password'}
            </button>
          </form>
        </div>

        {/* ── Danger Zone ──────────────────────────────────────────────── */}
        <div className="border border-red-200 rounded-xl p-6 bg-red-50/30">
          <h3 className="text-lg font-semibold text-red-600 mb-2">Delete Account</h3>
          <p className="text-gray-600 text-sm mb-4">
            Once you delete your account, there is no going back. Please be certain.
          </p>
          <button className="px-5 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition text-sm font-medium">
            Delete Account
          </button>
        </div>
      </div>
    </div>
  );
};

export default SettingsTab;
