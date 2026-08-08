// src/pages/PaymentMethods.jsx
import { useState } from 'react';
import { Link } from 'react-router-dom';

const PaymentMethods = () => {
  // State for FAQ accordion (store which item is open)
  const [openFaq, setOpenFaq] = useState(null);

  const faqs = [
    {
      id: 1,
      question: 'When will I be charged?',
      answer: 'Your payment will be processed immediately after you place your order. The charge will appear on your statement within 1-2 business days.',
    },
    {
      id: 2,
      question: 'Is it safe to save my card?',
      answer: 'Yes, we use industry-standard encryption to protect your payment information. Your card details are never stored on our servers.',
    },
    {
      id: 3,
      question: 'What currencies do you accept?',
      answer: 'We accept payments in USD, EUR, GBP, and many other major currencies. The available currencies will be shown at checkout.',
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
          <h1 className="text-3xl font-bold text-gray-900 mb-2 md:mb-0">Payment Methods</h1>
          <nav className="text-sm">
            <ol className="flex gap-2">
              <li><Link to="/" className="text-teal-700 hover:underline">Home</Link></li>
              <li className="text-gray-500">/</li>
              <li className="text-gray-600">Payment Methods</li>
            </ol>
          </nav>
        </div>
      </div>

      {/* Payment Methods Section */}
      <section className="py-16 bg-white">
        <div className="container mx-auto px-4">
          {/* Header */}
          <div className="text-center mb-12">
            <h2 className="text-3xl md:text-4xl font-bold text-gray-800">Payment Methods</h2>
            <p className="text-gray-500 mt-2">Choose from our secure and convenient payment options</p>
          </div>

          {/* Payment Options Grid */}
          <div className="grid md:grid-cols-3 gap-6 mb-20">
            {/* Credit Card */}
            <div className="bg-white border border-gray-100 rounded-2xl p-6 text-center shadow-sm hover:shadow-md transition group">
              <div className="w-20 h-20 bg-teal-100 rounded-2xl flex items-center justify-center mx-auto mb-4 group-hover:bg-teal-600 transition">
                <i className="bi bi-credit-card text-3xl text-teal-600 group-hover:text-white"></i>
              </div>
              <h4 className="text-xl font-bold mb-2">Credit / Debit Cards</h4>
              <p className="text-gray-500 text-sm mb-4">Visa, Mastercard, American Express</p>
              <div className="flex justify-center gap-2">
                <span className="px-3 py-1 bg-gray-100 text-xs font-medium rounded-full">Visa</span>
                <span className="px-3 py-1 bg-gray-100 text-xs font-medium rounded-full">Mastercard</span>
                <span className="px-3 py-1 bg-gray-100 text-xs font-medium rounded-full">Amex</span>
              </div>
            </div>
            {/* PayPal */}
            <div className="bg-white border border-gray-100 rounded-2xl p-6 text-center shadow-sm hover:shadow-md transition group">
              <div className="w-20 h-20 bg-blue-100 rounded-2xl flex items-center justify-center mx-auto mb-4 group-hover:bg-blue-600 transition">
                <i className="bi bi-paypal text-3xl text-blue-600 group-hover:text-white"></i>
              </div>
              <h4 className="text-xl font-bold mb-2">PayPal</h4>
              <p className="text-gray-500 text-sm mb-4">Fast and secure online payments</p>
              <div className="flex justify-center gap-2">
                <span className="px-3 py-1 bg-gray-100 text-xs font-medium rounded-full">PayPal</span>
              </div>
            </div>
            {/* Bank Transfer */}
            <div className="bg-white border border-gray-100 rounded-2xl p-6 text-center shadow-sm hover:shadow-md transition group">
              <div className="w-20 h-20 bg-teal-100 rounded-2xl flex items-center justify-center mx-auto mb-4 group-hover:bg-teal-600 transition">
                <i className="bi bi-bank text-3xl text-teal-600 group-hover:text-white"></i>
              </div>
              <h4 className="text-xl font-bold mb-2">Bank Transfer</h4>
              <p className="text-gray-500 text-sm mb-4">Direct bank-to-bank transfers</p>
              <div className="flex justify-center gap-2">
                <span className="px-3 py-1 bg-gray-100 text-xs font-medium rounded-full">Bank</span>
              </div>
            </div>
          </div>

          {/* Security Features & Process Steps */}
          <div className="grid md:grid-cols-2 gap-12 mb-20">
            {/* Left - Security Features */}
            <div>
              <h3 className="text-2xl font-bold text-gray-800 mb-2">Secure Payments</h3>
              <p className="text-gray-500 mb-6">Your security is our top priority</p>
              <ul className="space-y-5">
                <li className="flex gap-4">
                  <i className="bi bi-shield-check text-2xl text-teal-600 flex-shrink-0"></i>
                  <div>
                    <h5 className="font-semibold text-gray-800">SSL Encryption</h5>
                    <p className="text-gray-500 text-sm">All transactions are protected with 256-bit SSL encryption</p>
                  </div>
                </li>
                <li className="flex gap-4">
                  <i className="bi bi-lock text-2xl text-teal-600 flex-shrink-0"></i>
                  <div>
                    <h5 className="font-semibold text-gray-800">PCI Compliant</h5>
                    <p className="text-gray-500 text-sm">We follow strict PCI DSS security standards</p>
                  </div>
                </li>
                <li className="flex gap-4">
                  <i className="bi bi-shield-lock text-2xl text-teal-600 flex-shrink-0"></i>
                  <div>
                    <h5 className="font-semibold text-gray-800">Fraud Protection</h5>
                    <p className="text-gray-500 text-sm">Advanced fraud detection and prevention systems</p>
                  </div>
                </li>
              </ul>
            </div>

            {/* Right - Payment Process Steps */}
            <div className="bg-gray-50 rounded-2xl p-6">
              <h4 className="text-xl font-bold text-gray-800 mb-6">Payment Process</h4>
              <div className="space-y-6">
                <div className="flex gap-4">
                  <div className="w-8 h-8 bg-teal-600 text-white rounded-full flex items-center justify-center font-bold flex-shrink-0">1</div>
                  <div>
                    <h5 className="font-semibold">Choose Payment Method</h5>
                    <p className="text-gray-500 text-sm">Select your preferred payment option at checkout</p>
                  </div>
                </div>
                <div className="flex gap-4">
                  <div className="w-8 h-8 bg-teal-600 text-white rounded-full flex items-center justify-center font-bold flex-shrink-0">2</div>
                  <div>
                    <h5 className="font-semibold">Enter Details</h5>
                    <p className="text-gray-500 text-sm">Provide your payment information securely</p>
                  </div>
                </div>
                <div className="flex gap-4">
                  <div className="w-8 h-8 bg-teal-600 text-white rounded-full flex items-center justify-center font-bold flex-shrink-0">3</div>
                  <div>
                    <h5 className="font-semibold">Confirm Payment</h5>
                    <p className="text-gray-500 text-sm">Review and confirm your payment details</p>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* FAQ Section */}
          <div className="max-w-3xl mx-auto mb-20">
            <h3 className="text-2xl font-bold text-center text-gray-800 mb-8">Payment FAQs</h3>
            <div className="space-y-4">
              {faqs.map((faq) => (
                <div key={faq.id} className="border border-gray-200 rounded-xl overflow-hidden">
                  <button
                    onClick={() => toggleFaq(faq.id)}
                    className="w-full flex justify-between items-center p-5 text-left font-semibold text-gray-800 hover:bg-gray-50 transition"
                  >
                    <span>{faq.question}</span>
                    <i
                      className={`bi bi-chevron-down text-teal-600 transition-transform duration-300 ${
                        openFaq === faq.id ? 'rotate-180' : ''
                      }`}
                    ></i>
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

          {/* Support Section */}
          <div className="bg-gradient-to-r from-teal-50 to-pink-50 rounded-2xl p-8 text-center max-w-3xl mx-auto">
            <i className="bi bi-headset text-4xl text-teal-600 mb-3 block"></i>
            <h4 className="text-xl font-bold text-gray-800 mb-2">Need Help?</h4>
            <p className="text-gray-600 mb-5">Our payment support team is available 24/7 to assist you</p>
            <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
              <Link to="/contact" className="inline-flex items-center gap-2 bg-teal-600 text-white px-6 py-2 rounded-lg font-semibold hover:bg-teal-700 transition">
                <i className="bi bi-chat-dots"></i> Chat Now
              </Link>
              <span className="text-gray-400 hidden sm:inline">or</span>
              <a href="mailto:payment.support@example.com" className="inline-flex items-center gap-2 text-teal-600 hover:underline">
                <i className="bi bi-envelope"></i> payment.support@example.com
              </a>
            </div>
          </div>
        </div>
      </section>
    </>
  );
};

export default PaymentMethods;