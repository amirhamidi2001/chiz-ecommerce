// src/pages/ReturnPolicy.jsx
import { useState } from 'react';
import { Link } from 'react-router-dom';

const ReturnPolicy = () => {
  // State for FAQ accordion (store which item is open)
  const [openFaq, setOpenFaq] = useState(null);

  const faqs = [
    {
      id: 1,
      question: 'Can I return part of my order?',
      answer: 'Yes, you can return individual items from your order. Each item will be evaluated separately for refund eligibility.',
    },
    {
      id: 2,
      question: 'How long does the refund process take?',
      answer: 'Refunds are typically processed within 2-3 business days of receiving your return. The funds may take an additional 3-5 business days to appear in your account.',
    },
    {
      id: 3,
      question: 'Can I exchange for a different size?',
      answer: 'Yes, you can request an exchange for a different size or color if the item is in stock.',
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
          <h1 className="text-3xl font-bold text-gray-900 mb-2 md:mb-0">Return Policy</h1>
          <nav className="text-sm">
            <ol className="flex gap-2">
              <li><Link to="/" className="text-teal-700 hover:underline">Home</Link></li>
              <li className="text-gray-500">/</li>
              <li className="text-gray-600">Return Policy</li>
            </ol>
          </nav>
        </div>
      </div>

      {/* Return Policy Section */}
      <section className="py-16 bg-white">
        <div className="container mx-auto px-4">
          {/* Hero Section */}
          <div className="text-center mb-16">
            <h2 className="text-3xl md:text-4xl font-bold text-gray-800 mb-4">Returns Made Simple</h2>
            <p className="text-gray-600 max-w-2xl mx-auto">Not satisfied with your purchase? Our hassle-free return process ensures a smooth experience.</p>
            <div className="inline-flex items-baseline gap-2 bg-teal-100 px-6 py-3 rounded-full mt-6">
              <span className="text-4xl font-bold text-teal-700">30</span>
              <span className="text-lg text-gray-700">Day Returns</span>
            </div>
          </div>

          {/* Three Feature Cards */}
          <div className="grid md:grid-cols-3 gap-6 mb-20">
            <div className="bg-white border border-gray-100 rounded-2xl p-6 text-center shadow-sm hover:shadow-md transition group">
              <i className="bi bi-shield-check text-4xl text-teal-600 mb-3 block"></i>
              <h4 className="text-xl font-bold mb-2">Free Returns</h4>
              <p className="text-gray-500 mb-4">We cover return shipping costs for all eligible items</p>
              <a href="#" className="text-teal-600 font-medium inline-flex items-center gap-1 group-hover:gap-2 transition">Learn More <i className="bi bi-arrow-right"></i></a>
            </div>
            <div className="bg-white border border-gray-100 rounded-2xl p-6 text-center shadow-sm hover:shadow-md transition group">
              <i className="bi bi-clock-history text-4xl text-teal-600 mb-3 block"></i>
              <h4 className="text-xl font-bold mb-2">Quick Refunds</h4>
              <p className="text-gray-500 mb-4">Get your money back within 5-7 business days</p>
              <a href="#" className="text-teal-600 font-medium inline-flex items-center gap-1 group-hover:gap-2 transition">Learn More <i className="bi bi-arrow-right"></i></a>
            </div>
            <div className="bg-white border border-gray-100 rounded-2xl p-6 text-center shadow-sm hover:shadow-md transition group">
              <i className="bi bi-arrow-repeat text-4xl text-teal-600 mb-3 block"></i>
              <h4 className="text-xl font-bold mb-2">Easy Exchange</h4>
              <p className="text-gray-500 mb-4">Simple process to exchange items for different sizes</p>
              <a href="#" className="text-teal-600 font-medium inline-flex items-center gap-1 group-hover:gap-2 transition">Learn More <i className="bi bi-arrow-right"></i></a>
            </div>
          </div>

          {/* Return Requirements & Exceptions */}
          <div className="grid lg:grid-cols-2 gap-12 mb-20">
            {/* Left - Requirements */}
            <div>
              <h3 className="text-2xl font-bold text-gray-800 mb-3">Return Requirements</h3>
              <p className="text-gray-600 mb-6">To be eligible for a return, your item must be:</p>
              <ul className="space-y-5">
                <li className="flex gap-4">
                  <div className="w-6 h-6 bg-teal-100 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5"><i className="bi bi-check-lg text-teal-600 text-sm"></i></div>
                  <div><h5 className="font-semibold">Unworn & Unwashed</h5><p className="text-gray-500 text-sm">Items must be in original condition</p></div>
                </li>
                <li className="flex gap-4">
                  <div className="w-6 h-6 bg-teal-100 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5"><i className="bi bi-check-lg text-teal-600 text-sm"></i></div>
                  <div><h5 className="font-semibold">Original Packaging</h5><p className="text-gray-500 text-sm">Include all tags and packaging</p></div>
                </li>
                <li className="flex gap-4">
                  <div className="w-6 h-6 bg-teal-100 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5"><i className="bi bi-check-lg text-teal-600 text-sm"></i></div>
                  <div><h5 className="font-semibold">Within 30 Days</h5><p className="text-gray-500 text-sm">From the delivery date</p></div>
                </li>
                <li className="flex gap-4">
                  <div className="w-6 h-6 bg-teal-100 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5"><i className="bi bi-check-lg text-teal-600 text-sm"></i></div>
                  <div><h5 className="font-semibold">Proof of Purchase</h5><p className="text-gray-500 text-sm">Order number or receipt</p></div>
                </li>
              </ul>
            </div>

            {/* Right - Exceptions */}
            <div className="bg-gray-50 rounded-2xl p-8">
              <div className="text-center mb-6">
                <i className="bi bi-exclamation-circle text-3xl text-teal-600 mb-2 block"></i>
                <h4 className="text-xl font-bold">Return Exceptions</h4>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="bg-white p-4 rounded-xl text-center"><i className="bi bi-gift text-teal-600 text-xl block mb-1"></i><span className="text-sm">Gift Cards</span></div>
                <div className="bg-white p-4 rounded-xl text-center"><i className="bi bi-bag text-teal-600 text-xl block mb-1"></i><span className="text-sm">Intimate Items</span></div>
                <div className="bg-white p-4 rounded-xl text-center"><i className="bi bi-box-seam text-teal-600 text-xl block mb-1"></i><span className="text-sm">Custom Products</span></div>
                <div className="bg-white p-4 rounded-xl text-center"><i className="bi bi-tag text-teal-600 text-xl block mb-1"></i><span className="text-sm">Sale Items</span></div>
              </div>
            </div>
          </div>

          {/* How to Return Steps */}
          <div className="mb-20">
            <h3 className="text-2xl font-bold text-center text-gray-800 mb-10">How to Return</h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
              <div className="text-center relative">
                <div className="w-12 h-12 bg-teal-600 text-white rounded-full flex items-center justify-center text-xl font-bold mx-auto mb-4">1</div>
                <h5 className="font-semibold text-lg">Start Return</h5>
                <p className="text-gray-500 text-sm">Sign in to your account and select items to return</p>
              </div>
              <div className="text-center relative">
                <div className="w-12 h-12 bg-teal-600 text-white rounded-full flex items-center justify-center text-xl font-bold mx-auto mb-4">2</div>
                <h5 className="font-semibold text-lg">Package Items</h5>
                <p className="text-gray-500 text-sm">Pack items securely in original or similar packaging</p>
              </div>
              <div className="text-center relative">
                <div className="w-12 h-12 bg-teal-600 text-white rounded-full flex items-center justify-center text-xl font-bold mx-auto mb-4">3</div>
                <h5 className="font-semibold text-lg">Ship Return</h5>
                <p className="text-gray-500 text-sm">Use our prepaid label to ship your return</p>
              </div>
              <div className="text-center relative">
                <div className="w-12 h-12 bg-teal-600 text-white rounded-full flex items-center justify-center text-xl font-bold mx-auto mb-4">4</div>
                <h5 className="font-semibold text-lg">Get Refund</h5>
                <p className="text-gray-500 text-sm">Refund issued to original payment method</p>
              </div>
            </div>
          </div>

          {/* FAQ Section */}
          <div className="grid lg:grid-cols-3 gap-10 mb-20">
            <div>
              <h3 className="text-2xl font-bold text-gray-800 mb-3">Common Questions</h3>
              <p className="text-gray-600 mb-5">Find answers to frequently asked questions about our return policy</p>
              <Link to="/contact" className="inline-flex items-center gap-2 text-teal-600 font-medium hover:gap-3 transition">
                <i className="bi bi-headset"></i> Need more help?
              </Link>
            </div>
            <div className="lg:col-span-2">
              <div className="space-y-4">
                {faqs.map((faq) => (
                  <div key={faq.id} className="border border-gray-200 rounded-xl overflow-hidden">
                    <button
                      onClick={() => toggleFaq(faq.id)}
                      className="w-full flex justify-between items-center p-5 text-left font-semibold text-gray-800 hover:bg-gray-50 transition"
                    >
                      <span>{faq.question}</span>
                      <i className={`bi bi-plus-lg text-teal-600 transition-transform duration-300 ${openFaq === faq.id ? 'rotate-45' : ''}`}></i>
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

          {/* Bottom CTA */}
          <div className="bg-gradient-to-r from-teal-50 to-pink-50 rounded-2xl p-8 text-center">
            <h4 className="text-2xl font-bold text-gray-800 mb-2">Ready to Start Your Return?</h4>
            <p className="text-gray-600 mb-6">Sign in to your account to initiate the return process</p>
            <div className="flex flex-col sm:flex-row gap-4 justify-center">
              <Link to="/account" className="bg-teal-600 text-white px-6 py-2 rounded-lg font-semibold hover:bg-teal-700 transition">
                Start Return
              </Link>
              <Link to="/account" className="border border-teal-600 text-teal-600 px-6 py-2 rounded-lg font-semibold hover:bg-teal-50 transition">
                Track Return
              </Link>
            </div>
          </div>
        </div>
      </section>
    </>
  );
};

export default ReturnPolicy;