// src/pages/NotFound.jsx
import { Link } from 'react-router-dom';

const NotFound = () => {
  return (
    <>
      {/* Page Title */}
      <div className="bg-gray-50 py-12 border-b">
        <div className="container mx-auto px-4 flex flex-col md:flex-row justify-between items-center">
          <h1 className="text-3xl font-bold text-gray-900 mb-2 md:mb-0">404</h1>
          <nav className="text-sm">
            <ol className="flex gap-2">
              <li><Link to="/" className="text-teal-700 hover:underline">Home</Link></li>
              <li className="text-gray-500">/</li>
              <li className="text-gray-600">404</li>
            </ol>
          </nav>
        </div>
      </div>

      {/* Error 404 Section */}
      <section className="py-20 bg-white">
        <div className="container mx-auto px-4 text-center">
          {/* Error Icon */}
          <div className="mb-6">
            <i className="bi bi-exclamation-circle text-7xl text-teal-600"></i>
          </div>

          {/* Error Code */}
          <h1 className="text-7xl md:text-9xl font-bold text-gray-800 mb-4">404</h1>

          {/* Error Title */}
          <h2 className="text-2xl md:text-3xl font-bold text-gray-800 mb-3">Oops! Page Not Found</h2>

          {/* Error Description */}
          <p className="text-gray-600 max-w-md mx-auto mb-6">
            The page you are looking for might have been removed, had its name changed, or is temporarily unavailable.
          </p>

          {/* Search Box */}
          <div className="max-w-md mx-auto mb-6">
            <form className="flex border border-gray-300 rounded-full overflow-hidden shadow-sm">
              <input
                type="text"
                placeholder="Search for pages..."
                className="flex-1 px-5 py-3 outline-none text-sm"
              />
              <button type="submit" className="bg-teal-600 text-white px-5 hover:bg-teal-700 transition">
                <i className="bi bi-search"></i>
              </button>
            </form>
          </div>

          {/* Back to Home Button */}
          <div>
            <Link to="/" className="inline-block bg-teal-600 text-white px-6 py-3 rounded-lg font-semibold hover:bg-teal-700 transition">
              Back to Home
            </Link>
          </div>
        </div>
      </section>
    </>
  );
};

export default NotFound;