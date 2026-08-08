// src/pages/Privacy.jsx
import { Link } from 'react-router-dom';

const Privacy = () => {
  return (
    <>
      {/* Page Title */}
      <div className="bg-gray-50 py-12 border-b">
        <div className="container mx-auto px-4 flex flex-col md:flex-row justify-between items-center">
          <h1 className="text-3xl font-bold text-gray-900 mb-2 md:mb-0">Privacy</h1>
          <nav className="text-sm">
            <ol className="flex gap-2">
              <li><Link to="/" className="text-teal-700 hover:underline">Home</Link></li>
              <li className="text-gray-500">/</li>
              <li className="text-gray-600">Privacy</li>
            </ol>
          </nav>
        </div>
      </div>

      {/* Privacy Section */}
      <section className="py-16 bg-white">
        <div className="container mx-auto px-4">
          {/* Header */}
          <div className="text-center max-w-3xl mx-auto mb-16">
            <span className="inline-block bg-teal-100 text-teal-700 px-4 py-1 rounded-full text-sm mb-4">
              Last Updated: February 27, 2025
            </span>
            <h2 className="text-3xl md:text-4xl font-bold text-gray-800 mb-4">Privacy Policy</h2>
            <p className="text-gray-600">
              We respect your privacy and are committed to protecting your personal data. This privacy policy explains how we handle your information.
            </p>
            <div className="flex flex-wrap justify-center gap-4 mt-6">
              <div className="flex items-center gap-2 bg-gray-100 px-4 py-2 rounded-full">
                <i className="bi bi-shield-check text-teal-600"></i>
                <span className="text-sm">Data Protection</span>
              </div>
              <div className="flex items-center gap-2 bg-gray-100 px-4 py-2 rounded-full">
                <i className="bi bi-lock text-teal-600"></i>
                <span className="text-sm">Secure Storage</span>
              </div>
              <div className="flex items-center gap-2 bg-gray-100 px-4 py-2 rounded-full">
                <i className="bi bi-person-lock text-teal-600"></i>
                <span className="text-sm">Privacy First</span>
              </div>
            </div>
          </div>

          {/* Three Info Cards */}
          <div className="grid md:grid-cols-3 gap-8 mb-20">
            {/* Card 1: Information We Collect */}
            <div className="bg-white border border-gray-100 rounded-2xl shadow-sm hover:shadow-md transition">
              <div className="p-6 border-b border-gray-100 flex items-center gap-3">
                <i className="bi bi-collection text-2xl text-teal-600"></i>
                <h3 className="text-xl font-bold text-gray-800">Information We Collect</h3>
              </div>
              <div className="p-6">
                <ul className="space-y-3">
                  <li className="flex items-start gap-2">
                    <i className="bi bi-check-circle text-teal-500 mt-1"></i>
                    <span>Name and contact information</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <i className="bi bi-check-circle text-teal-500 mt-1"></i>
                    <span>Account credentials</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <i className="bi bi-check-circle text-teal-500 mt-1"></i>
                    <span>Payment details</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <i className="bi bi-check-circle text-teal-500 mt-1"></i>
                    <span>Device information</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <i className="bi bi-check-circle text-teal-500 mt-1"></i>
                    <span>Usage data and preferences</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <i className="bi bi-check-circle text-teal-500 mt-1"></i>
                    <span>Communication records</span>
                  </li>
                </ul>
              </div>
            </div>

            {/* Card 2: How We Use Data */}
            <div className="bg-white border border-gray-100 rounded-2xl shadow-sm hover:shadow-md transition">
              <div className="p-6 border-b border-gray-100 flex items-center gap-3">
                <i className="bi bi-graph-up text-2xl text-teal-600"></i>
                <h3 className="text-xl font-bold text-gray-800">How We Use Data</h3>
              </div>
              <div className="p-6">
                <ul className="space-y-3">
                  <li className="flex items-start gap-2">
                    <i className="bi bi-check-circle text-teal-500 mt-1"></i>
                    <span>Provide and improve services</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <i className="bi bi-check-circle text-teal-500 mt-1"></i>
                    <span>Process transactions</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <i className="bi bi-check-circle text-teal-500 mt-1"></i>
                    <span>Send updates and notifications</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <i className="bi bi-check-circle text-teal-500 mt-1"></i>
                    <span>Personalize user experience</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <i className="bi bi-check-circle text-teal-500 mt-1"></i>
                    <span>Analyze service usage</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <i className="bi bi-check-circle text-teal-500 mt-1"></i>
                    <span>Ensure security</span>
                  </li>
                </ul>
              </div>
            </div>

            {/* Card 3: Information Sharing */}
            <div className="bg-white border border-gray-100 rounded-2xl shadow-sm hover:shadow-md transition">
              <div className="p-6 border-b border-gray-100 flex items-center gap-3">
                <i className="bi bi-share text-2xl text-teal-600"></i>
                <h3 className="text-xl font-bold text-gray-800">Information Sharing</h3>
              </div>
              <div className="p-6">
                <ul className="space-y-3">
                  <li className="flex items-start gap-2">
                    <i className="bi bi-check-circle text-teal-500 mt-1"></i>
                    <span>Service providers</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <i className="bi bi-check-circle text-teal-500 mt-1"></i>
                    <span>Business partners</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <i className="bi bi-check-circle text-teal-500 mt-1"></i>
                    <span>Legal requirements</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <i className="bi bi-check-circle text-teal-500 mt-1"></i>
                    <span>With user consent</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <i className="bi bi-check-circle text-teal-500 mt-1"></i>
                    <span>Business transactions</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <i className="bi bi-check-circle text-teal-500 mt-1"></i>
                    <span>Analytics partners</span>
                  </li>
                </ul>
              </div>
            </div>
          </div>

          {/* Security Measures */}
          <div className="text-center mb-16">
            <h3 className="text-2xl font-bold text-gray-800 mb-3">Data Security Measures</h3>
            <p className="text-gray-500 mb-10">We implement appropriate security measures to protect your data</p>
            <div className="grid md:grid-cols-4 gap-6">
              <div className="bg-gray-50 p-6 rounded-xl text-center hover:shadow-md transition">
                <i className="bi bi-shield-lock text-4xl text-teal-600 mb-3 block"></i>
                <h4 className="font-semibold text-lg mb-2">Encryption</h4>
                <p className="text-gray-500 text-sm">All data is encrypted during transmission and storage using industry-standard protocols</p>
              </div>
              <div className="bg-gray-50 p-6 rounded-xl text-center hover:shadow-md transition">
                <i className="bi bi-fingerprint text-4xl text-teal-600 mb-3 block"></i>
                <h4 className="font-semibold text-lg mb-2">Access Control</h4>
                <p className="text-gray-500 text-sm">Strict access controls and authentication measures protect your information</p>
              </div>
              <div className="bg-gray-50 p-6 rounded-xl text-center hover:shadow-md transition">
                <i className="bi bi-eye-slash text-4xl text-teal-600 mb-3 block"></i>
                <h4 className="font-semibold text-lg mb-2">Data Privacy</h4>
                <p className="text-gray-500 text-sm">Regular privacy assessments and data minimization practices</p>
              </div>
              <div className="bg-gray-50 p-6 rounded-xl text-center hover:shadow-md transition">
                <i className="bi bi-patch-check text-4xl text-teal-600 mb-3 block"></i>
                <h4 className="font-semibold text-lg mb-2">Compliance</h4>
                <p className="text-gray-500 text-sm">Adherence to international data protection regulations</p>
              </div>
            </div>
          </div>

          {/* User Rights */}
          <div className="max-w-4xl mx-auto mb-20">
            <div className="bg-gray-50 rounded-2xl p-8 text-center">
              <h3 className="text-2xl font-bold text-gray-800 mb-3">Your Privacy Rights</h3>
              <p className="text-gray-600 mb-8">You have several rights regarding your personal data:</p>
              <div className="grid md:grid-cols-4 gap-6">
                <div>
                  <i className="bi bi-eye text-3xl text-teal-600 mb-2 block"></i>
                  <h4 className="font-semibold">Right to Access</h4>
                  <p className="text-gray-500 text-sm mt-1">You can request a copy of your personal data</p>
                </div>
                <div>
                  <i className="bi bi-pencil-square text-3xl text-teal-600 mb-2 block"></i>
                  <h4 className="font-semibold">Right to Rectification</h4>
                  <p className="text-gray-500 text-sm mt-1">You can update or correct your information</p>
                </div>
                <div>
                  <i className="bi bi-trash text-3xl text-teal-600 mb-2 block"></i>
                  <h4 className="font-semibold">Right to Erasure</h4>
                  <p className="text-gray-500 text-sm mt-1">Request deletion of your personal data</p>
                </div>
                <div>
                  <i className="bi bi-download text-3xl text-teal-600 mb-2 block"></i>
                  <h4 className="font-semibold">Right to Data Portability</h4>
                  <p className="text-gray-500 text-sm mt-1">Transfer your data to another service</p>
                </div>
              </div>
            </div>
          </div>

          {/* Additional Info */}
          <div className="grid md:grid-cols-3 gap-6 mb-20">
            <div className="bg-white border border-gray-100 rounded-xl p-6 shadow-sm">
              <h4 className="text-xl font-semibold mb-3">Cookies Policy</h4>
              <p className="text-gray-600">We use cookies to enhance your browsing experience. You can control cookie preferences through your browser settings.</p>
            </div>
            <div className="bg-white border border-gray-100 rounded-xl p-6 shadow-sm">
              <h4 className="text-xl font-semibold mb-3">Children's Privacy</h4>
              <p className="text-gray-600">Our services are not intended for children under 13. We do not knowingly collect data from children.</p>
            </div>
            <div className="bg-white border border-gray-100 rounded-xl p-6 shadow-sm">
              <h4 className="text-xl font-semibold mb-3">Policy Updates</h4>
              <p className="text-gray-600">We may update this policy periodically. We will notify you of any material changes.</p>
            </div>
          </div>

          {/* Contact Section */}
          <div className="bg-gradient-to-r from-teal-50 to-indigo-50 rounded-2xl p-8 flex flex-col md:flex-row items-center gap-6 max-w-3xl mx-auto">
            <div className="w-16 h-16 bg-teal-600 rounded-xl flex items-center justify-center flex-shrink-0">
              <i className="bi bi-envelope-open text-white text-2xl"></i>
            </div>
            <div className="text-center md:text-left">
              <h4 className="text-xl font-bold text-gray-800 mb-2">Privacy Questions?</h4>
              <p className="text-gray-600 mb-3">If you have any questions about this Privacy Policy, please contact our Data Protection Officer</p>
              <Link to="/contact" className="inline-block bg-teal-600 text-white px-6 py-2 rounded-lg font-semibold hover:bg-teal-700 transition">
                Contact DPO
              </Link>
            </div>
          </div>
        </div>
      </section>
    </>
  );
};

export default Privacy;