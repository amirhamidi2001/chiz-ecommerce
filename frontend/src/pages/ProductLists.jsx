// src/pages/ProductLists.jsx
import { useState } from 'react';
import { Link } from 'react-router-dom';

const ProductLists = () => {
  const [searchQuery, setSearchQuery] = useState('Lorem ipsum');
  const [sortBy, setSortBy] = useState('relevance');

  // Mock product data (8 products as shown in the HTML)
  const products = [
    {
      id: 1,
      name: 'Tempor Incididunt',
      category: "Women's Fashion",
      price: 129.0,
      rating: 4.8,
      reviews: 42,
      imageMain: '/assets/img/product/product-1.webp',
      imageHover: '/assets/img/product/product-2.webp',
      badge: null,
      originalPrice: null,
    },
    {
      id: 2,
      name: 'Elit Consectetur',
      category: "Men's Collection",
      price: 95.0,
      rating: 4.6,
      reviews: 28,
      imageMain: '/assets/img/product/product-1.webp',
      imageHover: '/assets/img/product/product-2.webp',
      badge: 'New',
      originalPrice: null,
    },
    {
      id: 3,
      name: 'Adipiscing Magna',
      category: 'Accessories',
      price: 75.0,
      originalPrice: 99.0,
      rating: 4.9,
      reviews: 56,
      imageMain: '/assets/img/product/product-3.webp',
      imageHover: '/assets/img/product/product-4.webp',
      badge: 'Sale',
    },
    {
      id: 4,
      name: 'Labore Dolore',
      category: 'Footwear',
      price: 145.0,
      rating: 4.7,
      reviews: 35,
      imageMain: '/assets/img/product/product-3.webp',
      imageHover: '/assets/img/product/product-4.webp',
      badge: null,
      originalPrice: null,
    },
    {
      id: 5,
      name: 'Magna Aliqua',
      category: "Men's Fashion",
      price: 89.0,
      rating: 4.5,
      reviews: 23,
      imageMain: '/assets/img/product/product-5.webp',
      imageHover: '/assets/img/product/product-1.webp',
      badge: null,
      originalPrice: null,
    },
    {
      id: 6,
      name: 'Eiusmod Tempor',
      category: "Women's Fashion",
      price: 110.0,
      originalPrice: 129.0,
      rating: 4.8,
      reviews: 47,
      imageMain: '/assets/img/product/product-5.webp',
      imageHover: '/assets/img/product/product-1.webp',
      badge: 'Sale',
    },
    {
      id: 7,
      name: 'Incididunt Labore',
      category: 'Accessories',
      price: 55.0,
      rating: 4.6,
      reviews: 31,
      imageMain: '/assets/img/product/product-1.webp',
      imageHover: '/assets/img/product/product-1.webp',
      badge: null,
      originalPrice: null,
    },
    {
      id: 8,
      name: 'Aliqua Magna',
      category: "Men's Fashion",
      price: 79.0,
      rating: 4.7,
      reviews: 39,
      imageMain: '/assets/img/product/product-1.webp',
      imageHover: '/assets/img/product/product-1.webp',
      badge: 'New',
      originalPrice: null,
    },
  ];

  // Sort products based on selected option
  const sortedProducts = [...products];
  if (sortBy === 'price_asc') sortedProducts.sort((a, b) => a.price - b.price);
  if (sortBy === 'price_desc') sortedProducts.sort((a, b) => b.price - a.price);
  if (sortBy === 'rating') sortedProducts.sort((a, b) => b.rating - a.rating);

  const handleSearchSubmit = (e) => {
    e.preventDefault();
    // In a real app, you would fetch search results
    console.log('Search:', searchQuery);
  };

  // Helper to render stars
  const renderStars = (rating) => {
    const fullStars = Math.floor(rating);
    const hasHalfStar = rating % 1 !== 0;
    return (
      <div className="flex text-yellow-400 text-sm">
        {[...Array(5)].map((_, i) => (
          <i
            key={i}
            className={`bi ${
              i < fullStars
                ? 'bi-star-fill'
                : i === fullStars && hasHalfStar
                ? 'bi-star-half'
                : 'bi-star'
            }`}
          ></i>
        ))}
      </div>
    );
  };

  return (
    <>
      {/* Page Title */}
      <div className="bg-gray-50 py-12 border-b">
        <div className="container mx-auto px-4 flex flex-col md:flex-row justify-between items-center">
          <h1 className="text-3xl font-bold text-gray-900 mb-2 md:mb-0">Product Lists</h1>
          <nav className="text-sm">
            <ol className="flex gap-2">
              <li><Link to="/" className="text-teal-700 hover:underline">Home</Link></li>
              <li className="text-gray-500">/</li>
              <li className="text-gray-600">Product Lists</li>
            </ol>
          </nav>
        </div>
      </div>

      {/* Header Section */}
      <section className="py-8 bg-white border-b">
        <div className="container mx-auto px-4">
          <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
            <div>
              <h2 className="text-2xl font-bold text-gray-800">Product Lists</h2>
              <p className="text-gray-600 mt-1">
                We found <span className="font-semibold text-teal-700">24</span> results for{' '}
                <span className="font-semibold">"{searchQuery}"</span>
              </p>
            </div>
            <form onSubmit={handleSearchSubmit} className="flex w-full md:w-auto">
              <div className="relative flex-1 md:w-80">
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Search..."
                  className="w-full border border-gray-300 rounded-l-lg px-4 py-2 focus:outline-none focus:border-teal-500"
                />
                <button
                  type="submit"
                  className="absolute right-0 top-0 h-full bg-teal-600 text-white px-4 rounded-r-lg hover:bg-teal-700"
                >
                  <i className="bi bi-search"></i>
                </button>
              </div>
            </form>
          </div>

          {/* Filters and Sort */}
          <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 mt-6 pt-4 border-t border-gray-100">
            <div className="flex flex-wrap items-center gap-3">
              <span className="text-sm font-medium text-gray-700">Filters:</span>
              <div className="flex flex-wrap gap-2">
                <span className="inline-flex items-center gap-1 bg-teal-100 text-teal-700 text-xs px-2 py-1 rounded-full">
                  Category: Blog <i className="bi bi-x-circle cursor-pointer"></i>
                </span>
                <span className="inline-flex items-center gap-1 bg-teal-100 text-teal-700 text-xs px-2 py-1 rounded-full">
                  Date: Last Month <i className="bi bi-x-circle cursor-pointer"></i>
                </span>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <label htmlFor="sort" className="text-sm text-gray-600">Sort by:</label>
              <select
                id="sort"
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value)}
                className="border border-gray-300 rounded-lg px-3 py-1 text-sm focus:outline-none focus:border-teal-500"
              >
                <option value="relevance">Relevance</option>
                <option value="price_asc">Price: Low to High</option>
                <option value="price_desc">Price: High to Low</option>
                <option value="rating">Customer Rating</option>
              </select>
            </div>
          </div>
        </div>
      </section>

      {/* Product Grid */}
      <section className="py-12 bg-white">
        <div className="container mx-auto px-4">
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6">
            {sortedProducts.map((product) => (
              <div key={product.id} className="group bg-white rounded-xl overflow-hidden shadow-sm hover:shadow-md transition">
                <div className="relative overflow-hidden">
                  {/* Main image and hover image */}
                  <img
                    src={product.imageMain}
                    alt={product.name}
                    className="w-full h-64 object-cover transition-transform duration-500 group-hover:scale-105"
                  />
                  <img
                    src={product.imageHover}
                    alt={product.name}
                    className="absolute top-0 left-0 w-full h-64 object-cover opacity-0 group-hover:opacity-100 transition-opacity duration-300"
                  />
                  {/* Overlay actions */}
                  <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity duration-300 flex items-center justify-center gap-3">
                    <button className="bg-white p-2 rounded-full hover:bg-teal-600 hover:text-white transition">
                      <i className="bi bi-eye"></i>
                    </button>
                    <button className="bg-white p-2 rounded-full hover:bg-teal-600 hover:text-white transition">
                      <i className="bi bi-cart-plus"></i>
                    </button>
                  </div>
                  {/* Badge */}
                  {product.badge && (
                    <span
                      className={`absolute top-3 left-3 text-white text-xs font-semibold px-2 py-1 rounded ${
                        product.badge === 'New' ? 'bg-teal-500' : 'bg-red-500'
                      }`}
                    >
                      {product.badge === 'New'
                        ? 'New'
                        : product.badge === 'Sale'
                        ? `${Math.round(((product.originalPrice - product.price) / product.originalPrice) * 100)}% Off`
                        : product.badge}
                    </span>
                  )}
                </div>
                <div className="p-4">
                  <div className="text-xs text-gray-500 uppercase tracking-wider">{product.category}</div>
                  <h4 className="font-semibold text-gray-800 mt-1 line-clamp-1">
                    <Link to={`/product/${product.id}`} className="hover:text-teal-600">
                      {product.name}
                    </Link>
                  </h4>
                  <div className="flex justify-between items-center mt-2">
                    <div>
                      {product.originalPrice ? (
                        <>
                          <span className="text-lg font-bold text-teal-700">${product.price}</span>
                          <span className="text-sm text-gray-400 line-through ml-2">${product.originalPrice}</span>
                        </>
                      ) : (
                        <span className="text-lg font-bold text-gray-800">${product.price}</span>
                      )}
                    </div>
                    <div className="flex items-center gap-1">
                      {renderStars(product.rating)}
                      <span className="text-xs text-gray-500 ml-1">({product.reviews})</span>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Pagination */}
          <nav className="flex justify-center mt-10">
            <ul className="flex flex-wrap items-center gap-2">
              <li>
                <a href="#" className="flex items-center gap-1 px-3 py-2 border rounded-md hover:bg-gray-50 transition">
                  <i className="bi bi-arrow-left"></i>
                  <span className="hidden sm:inline">Previous</span>
                </a>
              </li>
              <li><a href="#" className="px-3 py-2 bg-teal-600 text-white rounded-md">1</a></li>
              <li><a href="#" className="px-3 py-2 border rounded-md hover:bg-gray-50">2</a></li>
              <li><a href="#" className="px-3 py-2 border rounded-md hover:bg-gray-50">3</a></li>
              <li className="px-2 text-gray-400">...</li>
              <li><a href="#" className="px-3 py-2 border rounded-md hover:bg-gray-50">8</a></li>
              <li><a href="#" className="px-3 py-2 border rounded-md hover:bg-gray-50">9</a></li>
              <li><a href="#" className="px-3 py-2 border rounded-md hover:bg-gray-50">10</a></li>
              <li>
                <a href="#" className="flex items-center gap-1 px-3 py-2 border rounded-md hover:bg-gray-50 transition">
                  <span className="hidden sm:inline">Next</span>
                  <i className="bi bi-arrow-right"></i>
                </a>
              </li>
            </ul>
          </nav>
        </div>
      </section>
    </>
  );
};

export default ProductLists;