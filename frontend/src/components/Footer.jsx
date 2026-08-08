// src/components/Footer.jsx
import { Link } from 'react-router-dom';

const Footer = () => {
  return (
    <footer className="bg-emerald-900 text-emerald-300">
      {/* Main Footer */}
      <div className="container mx-auto px-4 py-12">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8">
          {/* About Column */}
          <div>
            <Link to="/" className="text-2xl font-bold text-white">Chiz</Link>
            <p className="mt-4 text-sm text-emerald-400">
              Lorem ipsum dolor sit amet, consectetur adipiscing elit. Nullam in nibh vehicula, facilisis magna ut, consectetur lorem.
            </p>
            <div className="mt-6">
              <h5 className="text-white font-semibold mb-3">Connect With Us</h5>
              <div className="flex gap-3">
                <a href="#" className="bg-emerald-800 p-2 rounded-full hover:bg-teal-700 transition"><i className="bi bi-facebook"></i></a>
                <a href="#" className="bg-emerald-800 p-2 rounded-full hover:bg-teal-700 transition"><i className="bi bi-instagram"></i></a>
                <a href="#" className="bg-emerald-800 p-2 rounded-full hover:bg-teal-700 transition"><i className="bi bi-twitter-x"></i></a>
                <a href="#" className="bg-emerald-800 p-2 rounded-full hover:bg-teal-700 transition"><i className="bi bi-youtube"></i></a>
              </div>
            </div>
          </div>

          {/* Shop Links */}
          <div>
            <h4 className="text-white font-semibold text-lg mb-4">Shop</h4>
            <ul className="space-y-2 text-sm">
              <li><Link to="/category" className="hover:text-teal-400 transition">New Arrivals</Link></li>
              <li><Link to="/category" className="hover:text-teal-400 transition">Bestsellers</Link></li>
              <li><Link to="/category" className="hover:text-teal-400 transition">Women's Clothing</Link></li>
              <li><Link to="/category" className="hover:text-teal-400 transition">Men's Clothing</Link></li>
              <li><Link to="/category" className="hover:text-teal-400 transition">Accessories</Link></li>
              <li><Link to="/category" className="hover:text-teal-400 transition">Sale</Link></li>
            </ul>
          </div>

          {/* Support Links */}
          <div>
            <h4 className="text-white font-semibold text-lg mb-4">Support</h4>
            <ul className="space-y-2 text-sm">
              <li><Link to="/support" className="hover:text-teal-400 transition">Help Center</Link></li>
              <li><Link to="/account" className="hover:text-teal-400 transition">Order Status</Link></li>
              <li><Link to="/shipping-info" className="hover:text-teal-400 transition">Shipping Info</Link></li>
              <li><Link to="/return-policy" className="hover:text-teal-400 transition">Returns & Exchanges</Link></li>
              <li><a href="#" className="hover:text-teal-400 transition">Size Guide</a></li>
              <li><Link to="/contact" className="hover:text-teal-400 transition">Contact Us</Link></li>
            </ul>
          </div>

          {/* Contact Information */}
          <div>
            <h4 className="text-white font-semibold text-lg mb-4">Contact Information</h4>
            <ul className="space-y-3 text-sm">
              <li className="flex gap-3">
                <i className="bi bi-geo-alt text-teal-400 mt-1"></i>
                <span>123 Fashion Street, New York, NY 10001</span>
              </li>
              <li className="flex gap-3">
                <i className="bi bi-telephone text-teal-400"></i>
                <span>+1 (555) 123-4567</span>
              </li>
              <li className="flex gap-3">
                <i className="bi bi-envelope text-teal-400"></i>
                <span>hello@example.com</span>
              </li>
              <li className="flex gap-3">
                <i className="bi bi-clock text-teal-400"></i>
                <span>Monday-Friday: 9am-6pm<br />Saturday: 10am-4pm<br />Sunday: Closed</span>
              </li>
            </ul>
            <div className="flex gap-3 mt-6">
              <a href="#" className="bg-emerald-800 px-4 py-2 rounded-lg flex items-center gap-2 hover:bg-emerald-700 transition">
                <i className="bi bi-apple text-xl"></i>
                <span className="text-xs">App Store</span>
              </a>
              <a href="#" className="bg-emerald-800 px-4 py-2 rounded-lg flex items-center gap-2 hover:bg-emerald-700 transition">
                <i className="bi bi-google-play text-xl"></i>
                <span className="text-xs">Google Play</span>
              </a>
            </div>
          </div>
        </div>
      </div>

      {/* Bottom Bar */}
      <div className="border-t border-emerald-800 py-6">
        <div className="container mx-auto px-4 flex flex-col md:flex-row justify-between items-center gap-4">
          <div className="text-center md:text-left text-sm">
            <p>© <span className="font-semibold">Chiz</span>. All Rights Reserved.</p>
            <p className="text-xs text-emerald-500 mt-1">Developed by Amir Hamidi</p>
          </div>
          <div className="flex flex-wrap items-center gap-6">
            <div className="flex gap-3 text-2xl">
              <i className="bi bi-credit-card hover:text-teal-400 transition"></i>
              <i className="bi bi-paypal hover:text-teal-400 transition"></i>
              <i className="bi bi-apple hover:text-teal-400 transition"></i>
              <i className="bi bi-google hover:text-teal-400 transition"></i>
            </div>
            <div className="flex gap-4 text-sm">
              <Link to="/tos" className="hover:text-teal-400 transition">Terms</Link>
              <Link to="/privacy" className="hover:text-teal-400 transition">Privacy</Link>
              <Link to="/tos" className="hover:text-teal-400 transition">Cookies</Link>
            </div>
          </div>
        </div>
      </div>
    </footer>
  );
};

export default Footer;