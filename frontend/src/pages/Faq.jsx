// src/pages/Faq.jsx
import { useState } from 'react';
import { Link } from 'react-router-dom';

const Faq = () => {
  // داده‌های سوالات
  const faqsData = [
    {
      id: 1,
      question: 'Vivamus suscipit tortor eget felis porttitor volutpat?',
      answer: 'Nulla quis lorem ut libero malesuada feugiat. Vestibulum ac diam sit amet quam vehicula elementum sed sit amet dui. Curabitur aliquet quam id dui posuere blandit. Nulla porttitor accumsan tincidunt.',
    },
    {
      id: 2,
      question: 'Curabitur aliquet quam id dui posuere blandit?',
      answer: 'Vestibulum ante ipsum primis in faucibus orci luctus et ultrices posuere cubilia Curae; Donec velit neque, auctor sit amet aliquam vel, ullamcorper sit amet ligula. Proin eget tortor risus. Mauris blandit aliquet elit, eget tincidunt nibh pulvinar.',
    },
    {
      id: 3,
      question: 'Sed porttitor lectus nibh ullamcorper sit amet?',
      answer: 'Curabitur non nulla sit amet nisl tempus convallis quis ac lectus. Praesent sapien massa, convallis a pellentesque nec, egestas non nisi. Donec sollicitudin molestie malesuada. Vestibulum ac diam sit amet quam vehicula elementum.',
    },
    {
      id: 4,
      question: 'Nulla quis lorem ut libero malesuada feugiat?',
      answer: 'Donec sollicitudin molestie malesuada. Quisque velit nisi, pretium ut lacinia in, elementum id enim. Vestibulum ante ipsum primis in faucibus orci luctus et ultrices posuere cubilia Curae; Donec velit neque, auctor sit amet aliquam vel.',
    },
    {
      id: 5,
      question: 'Vestibulum ac diam sit amet quam vehicula elementum?',
      answer: 'Praesent sapien massa, convallis a pellentesque nec, egestas non nisi. Vestibulum ante ipsum primis in faucibus orci luctus et ultrices posuere cubilia Curae; Donec velit neque, auctor sit amet aliquam vel, ullamcorper sit amet ligula.',
    },
  ];

  // وضعیت باز بودن هر سوال (با آیدی)
  const [openFaqs, setOpenFaqs] = useState([1]); // سوال اول باز باشد

  const toggleFaq = (id) => {
    setOpenFaqs((prev) =>
      prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]
    );
  };

  return (
    <>
      {/* Page Title */}
      <div className="bg-gray-50 py-12 border-b">
        <div className="container mx-auto px-4 flex flex-col md:flex-row justify-between items-center">
          <h1 className="text-3xl font-bold text-gray-900 mb-2 md:mb-0">FAQ</h1>
          <nav className="text-sm">
            <ol className="flex gap-2">
              <li><Link to="/" className="text-teal-700 hover:underline">Home</Link></li>
              <li className="text-gray-500">/</li>
              <li className="text-gray-600">FAQ</li>
            </ol>
          </nav>
        </div>
      </div>

      {/* FAQ Section */}
      <section className="py-16 bg-white">
        <div className="container mx-auto px-4">
          <div className="flex flex-col lg:flex-row gap-8">
            {/* Left Column - FAQ List */}
            <div className="lg:w-2/3">
              <div className="space-y-4">
                {faqsData.map((faq) => {
                  const isOpen = openFaqs.includes(faq.id);
                  return (
                    <div
                      key={faq.id}
                      className={`border border-gray-100 rounded-xl overflow-hidden transition-all ${
                        isOpen ? 'shadow-md' : 'shadow-sm'
                      }`}
                    >
                      <button
                        onClick={() => toggleFaq(faq.id)}
                        className="w-full flex justify-between items-center p-5 text-left font-semibold text-gray-800 hover:bg-gray-50 transition"
                      >
                        <span className="text-lg">{faq.question}</span>
                        <i
                          className={`bi bi-plus text-xl text-teal-600 transition-transform duration-300 ${
                            isOpen ? 'rotate-45' : ''
                          }`}
                        ></i>
                      </button>
                      <div
                        className={`transition-all duration-300 ease-in-out ${
                          isOpen ? 'max-h-96 opacity-100' : 'max-h-0 opacity-0'
                        } overflow-hidden`}
                      >
                        <div className="p-5 pt-0 text-gray-600 border-t border-gray-100">
                          {faq.answer}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Right Column - Info Card */}
            <div className="lg:w-1/3">
              <div className="bg-gray-50 rounded-2xl p-8 text-center shadow-sm border border-gray-100">
                <i className="bi bi-chat-dots-fill text-5xl text-teal-600 mb-4 block"></i>
                <h3 className="text-2xl font-bold text-gray-800 mb-3">
                  Can't find answer to your question?
                </h3>
                <p className="text-gray-600 mb-6 text-sm leading-relaxed">
                  Vestibulum ante ipsum primis in faucibus orci luctus et ultrices posuere cubilia Curae; Donec velit neque, auctor sit amet aliquam vel, ullamcorper sit amet ligula. Vestibulum ac diam sit amet quam vehicula elementum sed sit amet dui.
                </p>
                <Link
                  to="/contact"
                  className="inline-block bg-teal-600 text-white px-6 py-3 rounded-lg font-semibold hover:bg-teal-700 transition"
                >
                  Contact Us
                </Link>
              </div>
            </div>
          </div>
        </div>
      </section>
    </>
  );
};

export default Faq;