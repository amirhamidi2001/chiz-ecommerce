// src/pages/ShippingInfo.jsx
import { useState } from 'react';
import { Link } from 'react-router-dom';

const ShippingInfo = () => {
  // State for FAQ accordion (store which item is open)
  const [openFaq, setOpenFaq] = useState(null);

  const faqs = [
    {
      id: 1,
      question: 'How can I track my order?',
      answer: 'You can track your order using the tracking number provided in your shipping confirmation email.',
    },
    {
      id: 2,
      question: 'What if I\'m not home for delivery?',
      answer: 'The carrier will leave a notification and attempt delivery again or leave your package at a secure location.',
    },
    {
      id: 3,
      question: 'Do you offer weekend delivery?',
      answer: 'Weekend delivery is available for express shipping in select areas.',
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
          <h1 className="text-3xl font-bold text-gray-900 mb-2 md:mb-0">Shipping Info</h1>
          <nav className="text-sm">
            <ol className="flex gap-2">
              <li><Link to="/" className="text-teal-700 hover:underline">Home</Link></li>
              <li className="text-gray-500">/</li>
              <li className="text-gray-600">Shipping Info</li>
            </ol>
          </nav>
        </div>
      </div>

      {/* Shipping Info Section */}
      <section className="py-16 bg-white">
        <div className="container mx-auto px-4">
          {/* Delivery Options */}
          <div className="mb-16">
            <div className="text-center mb-10">
              <i className="bi bi-truck text-3xl text-teal-600 mb-2 block"></i>
              <h3 className="text-2xl font-bold text-gray-800">Delivery Options</h3>
              <p className="text-gray-500">Choose the delivery option that best suits your needs</p>
            </div>
            <div className="grid md:grid-cols-3 gap-6">
              <div className="bg-white border border-gray-100 rounded-2xl p-6 shadow-sm hover:shadow-md transition">
                <div className="w-12 h-12 bg-teal-100 rounded-xl flex items-center justify-center mb-4">
                  <i className="bi bi-lightning-charge text-teal-600 text-xl"></i>
                </div>
                <h4 className="text-xl font-bold mb-2">Express Delivery</h4>
                <p className="text-gray-500 mb-4">Delivery within 1-2 business days.</p>
                <div className="flex items-center gap-2 text-teal-600">
                  <i className="bi bi-clock"></i>
                  <span className="text-sm">1-2 Business Days</span>
                </div>
              </div>
              <div className="bg-white border border-gray-100 rounded-2xl p-6 shadow-sm hover:shadow-md transition">
                <div className="w-12 h-12 bg-teal-100 rounded-xl flex items-center justify-center mb-4">
                  <i className="bi bi-box-seam text-teal-600 text-xl"></i>
                </div>
                <h4 className="text-xl font-bold mb-2">Standard Shipping</h4>
                <p className="text-gray-500 mb-4">Delivery within 3-5 business days.</p>
                <div className="flex items-center gap-2 text-teal-600">
                  <i className="bi bi-clock"></i>
                  <span className="text-sm">3-5 Business Days</span>
                </div>
              </div>
              <div className="bg-white border border-gray-100 rounded-2xl p-6 shadow-sm hover:shadow-md transition">
                <div className="w-12 h-12 bg-teal-100 rounded-xl flex items-center justify-center mb-4">
                  <i className="bi bi-pin-map text-teal-600 text-xl"></i>
                </div>
                <h4 className="text-xl font-bold mb-2">Local Shipping</h4>
                <p className="text-gray-500 mb-4">Delivery within 2-3 business days.</p>
                <div className="flex items-center gap-2 text-teal-600">
                  <i className="bi bi-clock"></i>
                  <span className="text-sm">2-3 Business Days</span>
                </div>
              </div>
            </div>
          </div>

          {/* Shipping Costs */}
          <div className="mb-16">
            <div className="text-center mb-10">
              <i className="bi bi-cash-coin text-3xl text-teal-600 mb-2 block"></i>
              <h3 className="text-2xl font-bold text-gray-800">Shipping Costs</h3>
              <p className="text-gray-500">Transparent pricing for all shipping options</p>
            </div>
            <div className="max-w-lg mx-auto space-y-4">
              <div className="bg-white border border-gray-100 rounded-xl p-4 flex justify-between items-center shadow-sm">
                <div><span className="font-semibold">Standard Shipping</span><div className="text-sm text-gray-500">For orders under $50</div></div>
                <span className="text-lg font-bold">$5.99</span>
              </div>
              <div className="bg-teal-50 border border-teal-200 rounded-xl p-4 flex justify-between items-center shadow-sm">
                <div><span className="font-semibold text-teal-800">Free Shipping</span><div className="text-sm text-teal-600">For orders over $50</div></div>
                <span className="text-lg font-bold text-teal-700">$0.00</span>
              </div>
              <div className="bg-white border border-gray-100 rounded-xl p-4 flex justify-between items-center shadow-sm">
                <div><span className="font-semibold">Express Shipping</span><div className="text-sm text-gray-500">1-2 business days delivery</div></div>
                <span className="text-lg font-bold">$12.99</span>
              </div>
            </div>
          </div>

          {/* International Shipping */}
          <div className="mb-16">
            <div className="text-center mb-10">
              <i className="bi bi-globe text-3xl text-teal-600 mb-2 block"></i>
              <h3 className="text-2xl font-bold text-gray-800">International Shipping</h3>
              <p className="text-gray-500">We deliver worldwide with reliable carriers</p>
            </div>
            <div className="grid md:grid-cols-3 gap-6">
              <div className="bg-gray-50 p-6 rounded-xl text-center">
                <i className="bi bi-clock-history text-3xl text-teal-600 mb-3 block"></i>
                <h5 className="font-semibold text-lg mb-2">Delivery Time</h5>
                <p className="text-gray-500 text-sm">5-10 business days for most international destinations</p>
              </div>
              <div className="bg-gray-50 p-6 rounded-xl text-center">
                <i className="bi bi-currency-dollar text-3xl text-teal-600 mb-3 block"></i>
                <h5 className="font-semibold text-lg mb-2">Customs & Duties</h5>
                <p className="text-gray-500 text-sm">Import duties and taxes are not included in the shipping cost</p>
              </div>
              <div className="bg-gray-50 p-6 rounded-xl text-center">
                <i className="bi bi-shield-check text-3xl text-teal-600 mb-3 block"></i>
                <h5 className="font-semibold text-lg mb-2">Reliable Service</h5>
                <p className="text-gray-500 text-sm">Tracked shipping with leading international carriers</p>
              </div>
            </div>
          </div>

          {/* FAQ Section */}
          <div>
            <div className="text-center mb-10">
              <i className="bi bi-question-circle text-3xl text-teal-600 mb-2 block"></i>
              <h3 className="text-2xl font-bold text-gray-800">Shipping FAQ</h3>
              <p className="text-gray-500">Common questions about our shipping services</p>
            </div>
            <div className="max-w-3xl mx-auto space-y-4">
              {faqs.map((faq) => (
                <div key={faq.id} className="border border-gray-200 rounded-xl overflow-hidden">
                  <button
                    onClick={() => toggleFaq(faq.id)}
                    className="w-full flex justify-between items-center p-5 text-left font-semibold text-gray-800 hover:bg-gray-50 transition"
                  >
                    <div className="flex items-center gap-3">
                      <i className="bi bi-question-circle text-teal-600"></i>
                      <span>{faq.question}</span>
                    </div>
                    <i className={`bi bi-chevron-down text-teal-600 transition-transform duration-300 ${openFaq === faq.id ? 'rotate-180' : ''}`}></i>
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
      </section>
    </>
  );
};

export default ShippingInfo;