// src/pages/Support.jsx
import { useState } from 'react';
import { Link } from 'react-router-dom';

const Support = () => {
  // State for FAQ accordion
  const [openFaq, setOpenFaq] = useState(null);

  const faqs = [
    {
      id: 1,
      question: 'How do I track my order?',
      answer: 'You can track your order using your order number in the tracking section.',
    },
    {
      id: 2,
      question: 'Can I change my shipping address?',
      answer: 'Contact support to change your shipping address before the item ships.',
    },
    {
      id: 3,
      question: 'What payment methods do you accept?',
      answer: 'We accept all major credit cards and PayPal.',
    },
  ];

  const toggleFaq = (id) => {
    setOpenFaq(openFaq === id ? null : id);
  };

  return (
    <>
      {/* Page Title */}
      <div className="bg-gray-50 py-12 border-b">
        <div className="container mx-auto px-4 flex flex-col md:flex-row justify-between items-center">
          <h1 className="text-3xl font-bold text-gray-900 mb-2 md:mb-0">Support</h1>
          <nav className="text-sm">
            <ol className="flex gap-2">
              <li><Link to="/" className="text-teal-700 hover:underline">Home</Link></li>
              <li className="text-gray-500">/</li>
              <li className="text-gray-600">Support</li>
            </ol>
          </nav>
        </div>
      </div>

      {/* Support Section */}
      <section className="py-16 bg-white">
        <div className="container mx-auto px-4">
          {/* Header */}
          <div className="text-center max-w-2xl mx-auto mb-12">
            <h2 className="text-3xl md:text-4xl font-bold text-gray-800 mb-3">Help &amp; Support Center</h2>
            <p className="text-gray-600">Find answers, tutorials, and help from our support team</p>
          </div>

          {/* Quick Support Actions */}
          <div className="grid md:grid-cols-3 gap-6 mb-20">
            {/* Live Chat */}
            <div className="bg-white border border-gray-100 rounded-2xl p-6 text-center shadow-sm hover:shadow-md transition group">
              <i className="bi bi-chat-text text-4xl text-teal-600 mb-3 block"></i>
              <h4 className="text-xl font-bold mb-2">Live Chat</h4>
              <p className="text-gray-500 mb-4">Chat with our support team</p>
              <a href="#" className="inline-block bg-teal-600 text-white px-5 py-2 rounded-lg font-medium hover:bg-teal-700 transition">Start Chat</a>
            </div>
            {/* Call Us */}
            <div className="bg-white border border-gray-100 rounded-2xl p-6 text-center shadow-sm hover:shadow-md transition group">
              <i className="bi bi-telephone text-4xl text-teal-600 mb-3 block"></i>
              <h4 className="text-xl font-bold mb-2">Call Us</h4>
              <p className="text-gray-500 mb-4">24/7 support line</p>
              <a href="tel:+15551234567" className="inline-block bg-teal-600 text-white px-5 py-2 rounded-lg font-medium hover:bg-teal-700 transition">+1 (555) 123-4567</a>
            </div>
            {/* Email Support */}
            <div className="bg-white border border-gray-100 rounded-2xl p-6 text-center shadow-sm hover:shadow-md transition group">
              <i className="bi bi-envelope text-4xl text-teal-600 mb-3 block"></i>
              <h4 className="text-xl font-bold mb-2">Email Support</h4>
              <p className="text-gray-500 mb-4">Get email support</p>
              <a href="#" className="inline-block bg-teal-600 text-white px-5 py-2 rounded-lg font-medium hover:bg-teal-700 transition">Send Email</a>
            </div>
          </div>

          {/* Popular Help Topics */}
          <div className="mb-20">
            <h3 className="text-2xl font-bold text-center text-gray-800 mb-8">Popular Help Topics</h3>
            <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6">
              {/* Orders & Shipping */}
              <Link to="#" className="bg-white border border-gray-100 rounded-2xl p-5 flex items-start gap-3 shadow-sm hover:shadow-md transition group">
                <i className="bi bi-box-seam text-2xl text-teal-600 mt-1"></i>
                <div className="flex-1">
                  <h5 className="font-bold text-lg mb-2">Orders &amp; Shipping</h5>
                  <ul className="text-sm text-gray-500 space-y-1">
                    <li>Track your order</li>
                    <li>Shipping methods</li>
                    <li>Returns &amp; exchanges</li>
                  </ul>
                </div>
                <i className="bi bi-arrow-right text-teal-600 opacity-0 group-hover:opacity-100 transition"></i>
              </Link>
              {/* Billing & Payments */}
              <Link to="#" className="bg-white border border-gray-100 rounded-2xl p-5 flex items-start gap-3 shadow-sm hover:shadow-md transition group">
                <i className="bi bi-wallet2 text-2xl text-teal-600 mt-1"></i>
                <div className="flex-1">
                  <h5 className="font-bold text-lg mb-2">Billing &amp; Payments</h5>
                  <ul className="text-sm text-gray-500 space-y-1">
                    <li>Payment methods</li>
                    <li>Invoices</li>
                    <li>Refund status</li>
                  </ul>
                </div>
                <i className="bi bi-arrow-right text-teal-600 opacity-0 group-hover:opacity-100 transition"></i>
              </Link>
              {/* Account Settings */}
              <Link to="#" className="bg-white border border-gray-100 rounded-2xl p-5 flex items-start gap-3 shadow-sm hover:shadow-md transition group">
                <i className="bi bi-person-gear text-2xl text-teal-600 mt-1"></i>
                <div className="flex-1">
                  <h5 className="font-bold text-lg mb-2">Account Settings</h5>
                  <ul className="text-sm text-gray-500 space-y-1">
                    <li>Profile management</li>
                    <li>Password reset</li>
                    <li>Privacy settings</li>
                  </ul>
                </div>
                <i className="bi bi-arrow-right text-teal-600 opacity-0 group-hover:opacity-100 transition"></i>
              </Link>
              {/* Security */}
              <Link to="#" className="bg-white border border-gray-100 rounded-2xl p-5 flex items-start gap-3 shadow-sm hover:shadow-md transition group">
                <i className="bi bi-shield-check text-2xl text-teal-600 mt-1"></i>
                <div className="flex-1">
                  <h5 className="font-bold text-lg mb-2">Security</h5>
                  <ul className="text-sm text-gray-500 space-y-1">
                    <li>Account security</li>
                    <li>Two-factor auth</li>
                    <li>Privacy policy</li>
                  </ul>
                </div>
                <i className="bi bi-arrow-right text-teal-600 opacity-0 group-hover:opacity-100 transition"></i>
              </Link>
            </div>
          </div>

          {/* Self Help Resources & FAQ */}
          <div className="grid lg:grid-cols-2 gap-12">
            {/* Left - Self Help Resources */}
            <div>
              <h3 className="text-2xl font-bold text-gray-800 mb-3">Self-Help Resources</h3>
              <p className="text-gray-600 mb-6">Find answers quickly with our comprehensive resources</p>
              <div className="space-y-4">
                <Link to="#" className="flex items-center gap-4 p-4 bg-gray-50 rounded-xl hover:bg-teal-50 transition group">
                  <i className="bi bi-play-circle text-2xl text-teal-600"></i>
                  <div><h6 className="font-semibold">Video Tutorials</h6><p className="text-sm text-gray-500">Step-by-step video guides</p></div>
                </Link>
                <Link to="#" className="flex items-center gap-4 p-4 bg-gray-50 rounded-xl hover:bg-teal-50 transition group">
                  <i className="bi bi-file-text text-2xl text-teal-600"></i>
                  <div><h6 className="font-semibold">User Guides</h6><p className="text-sm text-gray-500">Detailed documentation</p></div>
                </Link>
                <Link to="#" className="flex items-center gap-4 p-4 bg-gray-50 rounded-xl hover:bg-teal-50 transition group">
                  <i className="bi bi-book text-2xl text-teal-600"></i>
                  <div><h6 className="font-semibold">Knowledge Base</h6><p className="text-sm text-gray-500">Articles and tutorials</p></div>
                </Link>
                <Link to="#" className="flex items-center gap-4 p-4 bg-gray-50 rounded-xl hover:bg-teal-50 transition group">
                  <i className="bi bi-tools text-2xl text-teal-600"></i>
                  <div><h6 className="font-semibold">Troubleshooting</h6><p className="text-sm text-gray-500">Common issues and fixes</p></div>
                </Link>
              </div>
            </div>

            {/* Right - FAQ Section */}
            <div>
              <h4 className="text-xl font-bold text-gray-800 mb-5">Common Questions</h4>
              <div className="space-y-4">
                {faqs.map((faq) => (
                  <div key={faq.id} className="border border-gray-200 rounded-xl overflow-hidden">
                    <button
                      onClick={() => toggleFaq(faq.id)}
                      className="w-full flex justify-between items-center p-5 text-left font-semibold text-gray-800 hover:bg-gray-50 transition"
                    >
                      <span>{faq.question}</span>
                      <i className={`bi bi-plus text-teal-600 transition-transform duration-300 ${openFaq === faq.id ? 'rotate-45' : ''}`}></i>
                    </button>
                    <div
                      className={`transition-all duration-300 ease-in-out ${
                        openFaq === faq.id ? 'max-h-40 opacity-100' : 'max-h-0 opacity-0'
                      } overflow-hidden`}
                    >
                      <div className="p-5 pt-0 text-gray-600 text-sm border-t border-gray-100">
                        {faq.answer}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </section>
    </>
  );
};

export default Support;