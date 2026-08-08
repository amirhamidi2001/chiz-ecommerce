// src/pages/Tos.jsx
import { Link } from 'react-router-dom';

const Tos = () => {
  return (
    <>
      {/* Page Title */}
      <div className="bg-gray-50 py-12 border-b">
        <div className="container mx-auto px-4 flex flex-col md:flex-row justify-between items-center">
          <h1 className="text-3xl font-bold text-gray-900 mb-2 md:mb-0">Terms of Service</h1>
          <nav className="text-sm">
            <ol className="flex gap-2">
              <li><Link to="/" className="text-teal-700 hover:underline">Home</Link></li>
              <li className="text-gray-500">/</li>
              <li className="text-gray-600">Terms of Service</li>
            </ol>
          </nav>
        </div>
      </div>

      {/* Terms of Service Section */}
      <section className="py-16 bg-white">
        <div className="container mx-auto px-4 max-w-4xl">
          {/* Header */}
          <div className="text-center mb-12">
            <span className="inline-block bg-teal-100 text-teal-700 px-4 py-1 rounded-full text-sm mb-4">
              Last Updated: February 27, 2025
            </span>
            <h2 className="text-3xl md:text-4xl font-bold text-gray-800 mb-3">Terms of Service</h2>
            <p className="text-gray-600">Please read these terms of service carefully before using our services</p>
          </div>

          {/* Content Sections */}
          <div className="space-y-10">
            {/* 1. Agreement to Terms */}
            <section id="agreement" className="scroll-mt-20">
              <h3 className="text-xl font-bold text-gray-800 mb-3">1. Agreement to Terms</h3>
              <p className="text-gray-600 mb-4">
                By accessing our website and services, you agree to be bound by these Terms of Service and all applicable laws and regulations. If you do not agree with any of these terms, you are prohibited from using or accessing our services.
              </p>
              <div className="bg-teal-50 border-l-4 border-teal-600 p-4 rounded-r-lg flex items-start gap-3">
                <i className="bi bi-info-circle text-teal-600 text-xl flex-shrink-0 mt-0.5"></i>
                <p className="text-gray-700 text-sm">These terms apply to all users, visitors, and others who access or use our services.</p>
              </div>
            </section>

            {/* 2. Intellectual Property Rights */}
            <section id="intellectual-property" className="scroll-mt-20">
              <h3 className="text-xl font-bold text-gray-800 mb-3">2. Intellectual Property Rights</h3>
              <p className="text-gray-600 mb-4">
                Our service and its original content, features, and functionality are owned by us and are protected by international copyright, trademark, patent, trade secret, and other intellectual property laws.
              </p>
              <ul className="list-disc pl-5 space-y-1 text-gray-600">
                <li>All content is our exclusive property</li>
                <li>You may not copy or modify the content</li>
                <li>Our trademarks may not be used without permission</li>
                <li>Content is for personal, non-commercial use only</li>
              </ul>
            </section>

            {/* 3. User Accounts */}
            <section id="user-accounts" className="scroll-mt-20">
              <h3 className="text-xl font-bold text-gray-800 mb-3">3. User Accounts</h3>
              <p className="text-gray-600 mb-4">
                When you create an account with us, you must provide accurate, complete, and current information. Failure to do so constitutes a breach of the Terms, which may result in immediate termination of your account.
              </p>
              <div className="bg-yellow-50 border-l-4 border-yellow-500 p-4 rounded-r-lg flex items-start gap-3">
                <i className="bi bi-exclamation-triangle text-yellow-600 text-xl flex-shrink-0 mt-0.5"></i>
                <div>
                  <h5 className="font-semibold text-gray-800">Important Notice</h5>
                  <p className="text-gray-700 text-sm">You are responsible for safeguarding the password and for all activities that occur under your account.</p>
                </div>
              </div>
            </section>

            {/* 4. Prohibited Activities */}
            <section id="prohibited" className="scroll-mt-20">
              <h3 className="text-xl font-bold text-gray-800 mb-3">4. Prohibited Activities</h3>
              <p className="text-gray-600 mb-4">
                You may not access or use the Service for any purpose other than that for which we make it available.
              </p>
              <div className="grid md:grid-cols-2 gap-3">
                <div className="flex items-center gap-2 text-gray-600"><i className="bi bi-x-circle text-red-500"></i><span>Systematic retrieval of data or content</span></div>
                <div className="flex items-center gap-2 text-gray-600"><i className="bi bi-x-circle text-red-500"></i><span>Publishing malicious content</span></div>
                <div className="flex items-center gap-2 text-gray-600"><i className="bi bi-x-circle text-red-500"></i><span>Engaging in unauthorized framing</span></div>
                <div className="flex items-center gap-2 text-gray-600"><i className="bi bi-x-circle text-red-500"></i><span>Attempting to gain unauthorized access</span></div>
              </div>
            </section>

            {/* 5. Disclaimers */}
            <section id="disclaimer" className="scroll-mt-20">
              <h3 className="text-xl font-bold text-gray-800 mb-3">5. Disclaimers</h3>
              <p className="text-gray-600 mb-4">
                Your use of our service is at your sole risk. The service is provided "AS IS" and "AS AVAILABLE" without warranties of any kind, whether express or implied.
              </p>
              <div className="bg-gray-50 p-4 rounded-lg">
                <p className="font-medium text-gray-800 mb-2">We do not guarantee that:</p>
                <ul className="list-disc pl-5 space-y-1 text-gray-600">
                  <li>The service will meet your requirements</li>
                  <li>The service will be uninterrupted or error-free</li>
                  <li>Results from using the service will be accurate</li>
                  <li>Any errors will be corrected</li>
                </ul>
              </div>
            </section>

            {/* 6. Limitation of Liability */}
            <section id="limitation" className="scroll-mt-20">
              <h3 className="text-xl font-bold text-gray-800 mb-3">6. Limitation of Liability</h3>
              <p className="text-gray-600">
                In no event shall we be liable for any indirect, punitive, incidental, special, consequential, or exemplary damages arising out of or in connection with your use of the service.
              </p>
            </section>

            {/* 7. Indemnification */}
            <section id="indemnification" className="scroll-mt-20">
              <h3 className="text-xl font-bold text-gray-800 mb-3">7. Indemnification</h3>
              <p className="text-gray-600">
                You agree to defend, indemnify, and hold us harmless from and against any claims, liabilities, damages, losses, and expenses arising out of your use of the service.
              </p>
            </section>

            {/* 8. Termination */}
            <section id="termination" className="scroll-mt-20">
              <h3 className="text-xl font-bold text-gray-800 mb-3">8. Termination</h3>
              <p className="text-gray-600">
                We may terminate or suspend your account immediately, without prior notice or liability, for any reason whatsoever, including without limitation if you breach the Terms.
              </p>
            </section>

            {/* 9. Governing Law */}
            <section id="governing-law" className="scroll-mt-20">
              <h3 className="text-xl font-bold text-gray-800 mb-3">9. Governing Law</h3>
              <p className="text-gray-600">
                These Terms shall be governed by and construed in accordance with the laws of [Your Country], without regard to its conflict of law provisions.
              </p>
            </section>

            {/* 10. Changes to Terms */}
            <section id="changes" className="scroll-mt-20">
              <h3 className="text-xl font-bold text-gray-800 mb-3">10. Changes to Terms</h3>
              <p className="text-gray-600 mb-4">
                We reserve the right to modify or replace these Terms at any time. We will provide notice of any changes by posting the new Terms on this page.
              </p>
              <div className="bg-blue-50 border-l-4 border-blue-500 p-4 rounded-r-lg flex items-start gap-3">
                <i className="bi bi-bell text-blue-600 text-xl flex-shrink-0 mt-0.5"></i>
                <p className="text-gray-700 text-sm">By continuing to access or use our service after those revisions become effective, you agree to be bound by the revised terms.</p>
              </div>
            </section>
          </div>

          {/* Contact Section */}
          <div className="mt-16 bg-gradient-to-r from-teal-50 to-indigo-50 rounded-2xl p-6 flex flex-col md:flex-row items-center gap-6">
            <div className="w-14 h-14 bg-teal-600 rounded-xl flex items-center justify-center flex-shrink-0">
              <i className="bi bi-envelope text-white text-2xl"></i>
            </div>
            <div className="text-center md:text-left">
              <h4 className="text-xl font-bold text-gray-800 mb-1">Questions About Terms?</h4>
              <p className="text-gray-600 mb-3">If you have any questions about these Terms, please contact us.</p>
              <Link to="/contact" className="inline-block bg-teal-600 text-white px-5 py-2 rounded-lg font-medium hover:bg-teal-700 transition">
                Contact Support
              </Link>
            </div>
          </div>
        </div>
      </section>
    </>
  );
};

export default Tos;