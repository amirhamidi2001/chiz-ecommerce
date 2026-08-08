// src/pages/Register.jsx
import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';

const Register = () => {
  const navigate = useNavigate();
  const [formData, setFormData] = useState({
    fullName: '',
    email: '',
    password: '',
    confirmPassword: '',
    country: '',
    terms: false,
    marketing: false,
  });
  const [errors, setErrors] = useState({});
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value,
    }));
    // Clear error for this field when user types
    if (errors[name]) {
      setErrors((prev) => ({ ...prev, [name]: '' }));
    }
  };

  const validate = () => {
    const newErrors = {};
    if (!formData.fullName.trim()) newErrors.fullName = 'Full name is required';
    if (!formData.email.trim()) newErrors.email = 'Email is required';
    else if (!/\S+@\S+\.\S+/.test(formData.email)) newErrors.email = 'Email is invalid';
    if (!formData.password) newErrors.password = 'Password is required';
    else if (formData.password.length < 6) newErrors.password = 'Password must be at least 6 characters';
    if (formData.password !== formData.confirmPassword) newErrors.confirmPassword = 'Passwords do not match';
    if (!formData.country) newErrors.country = 'Please select a country';
    if (!formData.terms) newErrors.terms = 'You must agree to the Terms of Service';
    return newErrors;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    const newErrors = validate();
    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }

    setIsSubmitting(true);
    // Simulate API call
    try {
      await new Promise((resolve) => setTimeout(resolve, 1000));
      console.log('Registration data:', formData);
      alert('Registration successful! Please log in.');
      navigate('/login');
    } catch (error) {
      alert('Registration failed. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleSocialLogin = (provider) => {
    alert(`Sign up with ${provider} (demo)`);
  };

  return (
    <>
      {/* Page Title */}
      <div className="bg-gray-50 py-12 border-b">
        <div className="container mx-auto px-4 flex flex-col md:flex-row justify-between items-center">
          <h1 className="text-3xl font-bold text-gray-900 mb-2 md:mb-0">Register</h1>
          <nav className="text-sm">
            <ol className="flex gap-2">
              <li><Link to="/" className="text-teal-700 hover:underline">Home</Link></li>
              <li className="text-gray-500">/</li>
              <li className="text-gray-600">Register</li>
            </ol>
          </nav>
        </div>
      </div>

      {/* Register Section */}
      <section className="py-16 bg-white relative overflow-hidden">
        {/* Decorative elements */}
        <div className="absolute top-0 right-0 w-64 h-64 bg-teal-100 rounded-full opacity-30 -translate-y-1/2 translate-x-1/2"></div>
        <div className="absolute bottom-0 left-0 w-80 h-80 bg-teal-50 rounded-full opacity-40 translate-y-1/2 -translate-x-1/2"></div>
        <div className="absolute top-1/3 left-10 w-16 h-16 bg-teal-200 rounded-full opacity-20"></div>
        <div className="absolute bottom-20 right-20 w-24 h-24 bg-teal-300 rounded-lg rotate-12 opacity-20"></div>

        <div className="container mx-auto px-4 relative z-10">
          <div className="max-w-2xl mx-auto">
            <div className="bg-white rounded-2xl shadow-xl border border-gray-100 p-6 md:p-8">
              <div className="text-center mb-6">
                <h2 className="text-2xl md:text-3xl font-bold text-gray-800">Create Your Account</h2>
                <p className="text-gray-500 mt-1">Create your account and start shopping with us</p>
              </div>

              <form onSubmit={handleSubmit} className="space-y-5">
                {/* Full Name */}
                <div className="relative">
                  <input
                    type="text"
                    name="fullName"
                    value={formData.fullName}
                    onChange={handleChange}
                    placeholder="Full Name"
                    className={`w-full border rounded-lg px-4 py-3 pt-5 pb-1 peer focus:outline-none focus:border-teal-500 ${
                      errors.fullName ? 'border-red-500' : 'border-gray-300'
                    }`}
                  />
                  <label className="absolute left-3 top-1 text-xs text-gray-500 peer-focus:text-teal-600">Full Name</label>
                  {errors.fullName && <p className="text-red-500 text-xs mt-1">{errors.fullName}</p>}
                </div>

                {/* Email */}
                <div className="relative">
                  <input
                    type="email"
                    name="email"
                    value={formData.email}
                    onChange={handleChange}
                    placeholder="Email Address"
                    className={`w-full border rounded-lg px-4 py-3 pt-5 pb-1 peer focus:outline-none focus:border-teal-500 ${
                      errors.email ? 'border-red-500' : 'border-gray-300'
                    }`}
                  />
                  <label className="absolute left-3 top-1 text-xs text-gray-500 peer-focus:text-teal-600">Email Address</label>
                  {errors.email && <p className="text-red-500 text-xs mt-1">{errors.email}</p>}
                </div>

                {/* Password & Confirm Password Row */}
                <div className="grid md:grid-cols-2 gap-4">
                  <div className="relative">
                    <input
                      type="password"
                      name="password"
                      value={formData.password}
                      onChange={handleChange}
                      placeholder="Password"
                      className={`w-full border rounded-lg px-4 py-3 pt-5 pb-1 peer focus:outline-none focus:border-teal-500 ${
                        errors.password ? 'border-red-500' : 'border-gray-300'
                      }`}
                    />
                    <label className="absolute left-3 top-1 text-xs text-gray-500 peer-focus:text-teal-600">Password</label>
                    {errors.password && <p className="text-red-500 text-xs mt-1">{errors.password}</p>}
                  </div>
                  <div className="relative">
                    <input
                      type="password"
                      name="confirmPassword"
                      value={formData.confirmPassword}
                      onChange={handleChange}
                      placeholder="Confirm Password"
                      className={`w-full border rounded-lg px-4 py-3 pt-5 pb-1 peer focus:outline-none focus:border-teal-500 ${
                        errors.confirmPassword ? 'border-red-500' : 'border-gray-300'
                      }`}
                    />
                    <label className="absolute left-3 top-1 text-xs text-gray-500 peer-focus:text-teal-600">Confirm Password</label>
                    {errors.confirmPassword && <p className="text-red-500 text-xs mt-1">{errors.confirmPassword}</p>}
                  </div>
                </div>

                {/* Country Select */}
                <div className="relative">
                  <select
                    name="country"
                    value={formData.country}
                    onChange={handleChange}
                    className={`w-full border rounded-lg px-4 py-3 pt-5 pb-1 appearance-none peer focus:outline-none focus:border-teal-500 ${
                      errors.country ? 'border-red-500' : 'border-gray-300'
                    }`}
                  >
                    <option value="" disabled>Select your country</option>
                    <option value="us">United States</option>
                    <option value="ca">Canada</option>
                    <option value="uk">United Kingdom</option>
                    <option value="au">Australia</option>
                    <option value="de">Germany</option>
                    <option value="fr">France</option>
                    <option value="jp">Japan</option>
                    <option value="other">Other</option>
                  </select>
                  <label className="absolute left-3 top-1 text-xs text-gray-500">Country</label>
                  <i className="bi bi-chevron-down absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none"></i>
                  {errors.country && <p className="text-red-500 text-xs mt-1">{errors.country}</p>}
                </div>

                {/* Terms Checkbox */}
                <div className="flex items-start gap-2">
                  <input
                    type="checkbox"
                    name="terms"
                    checked={formData.terms}
                    onChange={handleChange}
                    className="mt-1 rounded text-teal-600 focus:ring-teal-500"
                  />
                  <label className="text-sm text-gray-600">
                    I agree to the <Link to="/tos" className="text-teal-600 hover:underline">Terms of Service</Link> and{' '}
                    <Link to="/privacy" className="text-teal-600 hover:underline">Privacy Policy</Link>
                  </label>
                </div>
                {errors.terms && <p className="text-red-500 text-xs -mt-2">{errors.terms}</p>}

                {/* Marketing Checkbox */}
                <div className="flex items-start gap-2">
                  <input
                    type="checkbox"
                    name="marketing"
                    checked={formData.marketing}
                    onChange={handleChange}
                    className="mt-1 rounded text-teal-600 focus:ring-teal-500"
                  />
                  <label className="text-sm text-gray-600">
                    I would like to receive marketing communications about products, services, and promotions
                  </label>
                </div>

                {/* Submit Button */}
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="w-full bg-teal-600 text-white py-3 rounded-lg font-semibold hover:bg-teal-700 transition disabled:opacity-50"
                >
                  {isSubmitting ? 'Creating Account...' : 'Create Account'}
                </button>

                {/* Login Link */}
                <div className="text-center">
                  <p className="text-gray-600">
                    Already have an account?{' '}
                    <Link to="/login" className="text-teal-600 font-medium hover:underline">Sign in</Link>
                  </p>
                </div>
              </form>

              {/* Social Login */}
              <div className="mt-8">
                <div className="relative">
                  <div className="absolute inset-0 flex items-center">
                    <div className="w-full border-t border-gray-200"></div>
                  </div>
                  <div className="relative flex justify-center text-sm">
                    <span className="px-4 bg-white text-gray-500">or sign up with</span>
                  </div>
                </div>
                <div className="grid grid-cols-3 gap-3 mt-6">
                  <button
                    onClick={() => handleSocialLogin('Google')}
                    className="flex items-center justify-center gap-2 border border-gray-300 rounded-lg py-2 hover:bg-gray-50 transition"
                  >
                    <i className="bi bi-google text-red-500"></i> <span className="text-sm">Google</span>
                  </button>
                  <button
                    onClick={() => handleSocialLogin('Facebook')}
                    className="flex items-center justify-center gap-2 border border-gray-300 rounded-lg py-2 hover:bg-gray-50 transition"
                  >
                    <i className="bi bi-facebook text-blue-600"></i> <span className="text-sm">Facebook</span>
                  </button>
                  <button
                    onClick={() => handleSocialLogin('Apple')}
                    className="flex items-center justify-center gap-2 border border-gray-300 rounded-lg py-2 hover:bg-gray-50 transition"
                  >
                    <i className="bi bi-apple text-gray-800"></i> <span className="text-sm">Apple</span>
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>
    </>
  );
};

export default Register;