// src/pages/Contact.jsx
import { useState, useCallback } from 'react';
import { Link } from 'react-router-dom';
import api, { parseErrors } from '../services/api';

// ─── constants ────────────────────────────────────────────────────────────────

const INITIAL_FORM = { name: '', email: '', subject: '', message: '' };

// ─── sub-components ───────────────────────────────────────────────────────────

const FieldError = ({ message }) =>
  message ? (
    <p className="mt-1 text-sm text-red-500 flex items-center gap-1">
      <i className="bi bi-exclamation-circle text-xs" />
      {message}
    </p>
  ) : null;

const inputClass = (hasError) =>
  [
    'w-full border rounded-lg pl-10 pr-4 py-3 transition',
    'focus:outline-none focus:ring-1',
    hasError
      ? 'border-red-400 focus:border-red-500 focus:ring-red-500'
      : 'border-gray-300 focus:border-teal-500 focus:ring-teal-500',
  ].join(' ');

// ─── main component ───────────────────────────────────────────────────────────

const Contact = () => {
  const [formData, setFormData] = useState(INITIAL_FORM);
  const [errors, setErrors] = useState({});
  const [successMessage, setSuccess] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  // ── handlers ────────────────────────────────────────────────────────────

  const handleChange = useCallback((e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
    // Clear the field error as the user corrects it
    setErrors((prev) => {
      if (!prev[name]) return prev;
      const next = { ...prev };
      delete next[name];
      return next;
    });
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsSubmitting(true);
    setErrors({});
    setSuccess('');

    try {
      await api.post('/contact/', formData);
      setSuccess("Your message has been sent. We'll get back to you shortly!");
      setFormData(INITIAL_FORM);
    } catch (err) {
      const parsed = parseErrors(err);
      setErrors(parsed);
    } finally {
      setIsSubmitting(false);
    }
  };

  // ── render ──────────────────────────────────────────────────────────────

  return (
    <>
      {/* ── Page Title ── */}
      <div className="bg-gray-50 py-12 border-b">
        <div className="container mx-auto px-4 flex flex-col md:flex-row justify-between items-center">
          <h1 className="text-3xl font-bold text-gray-900 mb-2 md:mb-0">Contact</h1>
          <nav className="text-sm">
            <ol className="flex gap-2">
              <li><Link to="/" className="text-teal-700 hover:underline">Home</Link></li>
              <li className="text-gray-500">/</li>
              <li className="text-gray-600">Contact</li>
            </ol>
          </nav>
        </div>
      </div>

      {/* ── Info Cards ── */}
      <section className="py-12 bg-white">
        <div className="container mx-auto px-4">
          <div className="grid md:grid-cols-3 gap-6 mb-12">
            <div className="bg-gray-50 rounded-xl p-6 flex items-start gap-4 shadow-sm hover:shadow-md transition">
              <div className="bg-teal-100 text-teal-700 w-12 h-12 rounded-full flex items-center justify-center flex-shrink-0">
                <i className="bi bi-geo-alt text-xl" />
              </div>
              <div>
                <h4 className="font-semibold text-lg mb-1">Our Address</h4>
                <p className="text-gray-600 text-sm">1842 Maple Avenue, Portland, Oregon 97204</p>
              </div>
            </div>

            <div className="bg-gray-50 rounded-xl p-6 flex items-start gap-4 shadow-sm hover:shadow-md transition">
              <div className="bg-teal-100 text-teal-700 w-12 h-12 rounded-full flex items-center justify-center flex-shrink-0">
                <i className="bi bi-envelope text-xl" />
              </div>
              <div>
                <h4 className="font-semibold text-lg mb-1">Email Address</h4>
                <p className="text-gray-600 text-sm">info@example.com</p>
                <p className="text-gray-600 text-sm">contact@example.com</p>
              </div>
            </div>

            <div className="bg-gray-50 rounded-xl p-6 flex items-start gap-4 shadow-sm hover:shadow-md transition">
              <div className="bg-teal-100 text-teal-700 w-12 h-12 rounded-full flex items-center justify-center flex-shrink-0">
                <i className="bi bi-headset text-xl" />
              </div>
              <div>
                <h4 className="font-semibold text-lg mb-1">Hours of Operation</h4>
                <p className="text-gray-600 text-sm">Sunday–Fri: 9 AM – 6 PM</p>
                <p className="text-gray-600 text-sm">Saturday: 9 AM – 4 PM</p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── Map ── */}
      <div className="w-full">
        <iframe
          src="https://www.google.com/maps/embed?pb=!1m14!1m8!1m3!1d48389.78314118045!2d-74.006138!3d40.710059!3m2!1i1024!2i768!4f13.1!3m3!1m2!1s0x89c25a22a3bda30d%3A0xb89d1fe6bc499443!2sDowntown%20Conference%20Center!5e0!3m2!1sen!2sus!4v1676961268712!5m2!1sen!2sus"
          width="100%"
          height="500"
          style={{ border: 0 }}
          allowFullScreen
          loading="lazy"
          referrerPolicy="no-referrer-when-downgrade"
          title="Google Map"
          className="w-full"
        />
      </div>

      {/* ── Contact Form (overlapping map) ── */}
      <div className="container mx-auto px-4 relative -mt-20 z-10 pb-16">
        <div className="max-w-4xl mx-auto">
          <div className="bg-white rounded-2xl shadow-xl p-6 md:p-8">
            <h2 className="text-2xl md:text-3xl font-bold text-center text-gray-800 mb-6">
              Get in Touch
            </h2>

            {/* ── Global / non-field error ── */}
            {errors.non_field_errors && (
              <div className="mb-5 flex items-center gap-2 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                <i className="bi bi-exclamation-triangle-fill flex-shrink-0" />
                <span>{errors.non_field_errors}</span>
              </div>
            )}

            {/* ── Success banner ── */}
            {successMessage && (
              <div className="mb-5 flex items-center gap-2 rounded-lg border border-teal-200 bg-teal-50 px-4 py-3 text-sm text-teal-800">
                <i className="bi bi-check-circle-fill flex-shrink-0" />
                <span>{successMessage}</span>
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-5" noValidate>
              {/* Name + Email */}
              <div className="grid md:grid-cols-2 gap-5">
                {/* Name */}
                <div>
                  <div className="relative">
                    <i className="bi bi-person absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none" />
                    <input
                      type="text"
                      name="name"
                      value={formData.name}
                      onChange={handleChange}
                      placeholder="Full Name"
                      autoComplete="name"
                      className={inputClass(!!errors.name)}
                    />
                  </div>
                  <FieldError message={errors.name} />
                </div>

                {/* Email */}
                <div>
                  <div className="relative">
                    <i className="bi bi-envelope absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none" />
                    <input
                      type="email"
                      name="email"
                      value={formData.email}
                      onChange={handleChange}
                      placeholder="Email Address"
                      autoComplete="email"
                      className={inputClass(!!errors.email)}
                    />
                  </div>
                  <FieldError message={errors.email} />
                </div>
              </div>

              {/* Subject */}
              <div>
                <div className="relative">
                  <i className="bi bi-text-left absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none" />
                  <input
                    type="text"
                    name="subject"
                    value={formData.subject}
                    onChange={handleChange}
                    placeholder="Subject"
                    className={inputClass(!!errors.subject)}
                  />
                </div>
                <FieldError message={errors.subject} />
              </div>

              {/* Message */}
              <div>
                <div className="relative">
                  <i className="bi bi-chat-dots absolute left-3 top-4 text-gray-400 pointer-events-none" />
                  <textarea
                    name="message"
                    value={formData.message}
                    onChange={handleChange}
                    placeholder="Write your message…"
                    rows={5}
                    className={inputClass(!!errors.message)}
                  />
                </div>
                <FieldError message={errors.message} />
              </div>

              {/* Submit */}
              <div className="text-center">
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="inline-flex items-center gap-2 bg-teal-600 hover:bg-teal-700 active:bg-teal-800
                             text-white font-semibold py-3 px-8 rounded-lg transition duration-200
                             disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {isSubmitting ? (
                    <>
                      <svg
                        className="animate-spin h-4 w-4"
                        xmlns="http://www.w3.org/2000/svg"
                        fill="none"
                        viewBox="0 0 24 24"
                        aria-hidden="true"
                      >
                        <circle
                          className="opacity-25"
                          cx="12" cy="12" r="10"
                          stroke="currentColor" strokeWidth="4"
                        />
                        <path
                          className="opacity-75"
                          fill="currentColor"
                          d="M4 12a8 8 0 018-8v8H4z"
                        />
                      </svg>
                      Sending…
                    </>
                  ) : (
                    'Send Message'
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      </div>
    </>
  );
};

export default Contact;
