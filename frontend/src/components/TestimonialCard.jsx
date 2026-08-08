// src/components/TestimonialCard.jsx
const TestimonialCard = ({ text, name, position, image, highlight = false }) => {
  return (
    <div className={`testimonial-item ${highlight ? 'highlight' : ''}`}>
      <div className="bg-white rounded-2xl p-6 relative shadow-md hover:shadow-lg transition-all duration-300 border border-gray-100">
        <div className="absolute -top-4 left-6 w-10 h-10 bg-white rounded-full flex items-center justify-center border border-gray-100">
          <i className="bi bi-quote text-teal-700 text-xl"></i>
        </div>
        <p className="text-gray-600 italic mt-4 mb-6 leading-relaxed">{text}</p>
        <div className="flex items-center gap-4 pt-4 border-t border-gray-100">
          <img
            src={image}
            alt={name}
            className="w-12 h-12 rounded-full object-cover"
          />
          <div>
            <h3 className="font-semibold text-gray-800">{name}</h3>
            <span className="text-sm text-gray-500">{position}</span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default TestimonialCard;