// src/pages/About.jsx
import { Link } from 'react-router-dom';
import StatsCounter from '../components/StatsCounter';
import TestimonialCard from '../components/TestimonialCard';

const About = () => {
  // دیتای تستیمونیال‌ها
  const testimonials = [
    {
      id: 1,
      text: "Implementing innovative strategies has revolutionized our approach to market challenges and competitive positioning.",
      name: "Rachel Bennett",
      position: "Strategy Director",
      image: "/assets/img/person/person-f-1.webp",
      highlight: false,
    },
    {
      id: 2,
      text: "Exceptional service delivery and innovative solutions have transformed our business operations, leading to remarkable growth and enhanced customer satisfaction across all touchpoints.",
      name: "Daniel Morgan",
      position: "Chief Innovation Officer",
      image: "/assets/img/person/person-f-2.webp",
      highlight: true,
    },
    {
      id: 3,
      text: "Strategic partnership has enabled seamless digital transformation and operational excellence.",
      name: "Emma Thompson",
      position: "Digital Lead",
      image: "/assets/img/person/person-f-3.webp",
      highlight: false,
    },
    {
      id: 4,
      text: "Professional expertise and dedication have significantly improved our project delivery timelines and quality metrics.",
      name: "Christopher Lee",
      position: "Technical Director",
      image: "/assets/img/person/person-f-4.webp",
      highlight: false,
    },
    {
      id: 5,
      text: "Collaborative approach and industry expertise have revolutionized our product development cycle, resulting in faster time-to-market and increased customer engagement levels.",
      name: "Olivia Carter",
      position: "Product Manager",
      image: "/assets/img/person/person-f-5.webp",
      highlight: true,
    },
    {
      id: 6,
      text: "Innovative approach to user experience design has significantly enhanced our platform's engagement metrics and customer retention rates.",
      name: "Nathan Brooks",
      position: "UX Director",
      image: "/assets/img/person/person-f-6.webp",
      highlight: false,
    },
  ];

  return (
    <>
      {/* ========== Page Title ========== */}
      <div className="bg-gray-50 py-12 border-b">
        <div className="container mx-auto px-4 flex flex-col md:flex-row justify-between items-center">
          <h1 className="text-3xl font-bold text-gray-900 mb-2 md:mb-0">About</h1>
          <nav className="text-sm">
            <ol className="flex gap-2">
              <li><Link to="/" className="text-teal-700 hover:underline">Home</Link></li>
              <li className="text-gray-500">/</li>
              <li className="text-gray-600">About</li>
            </ol>
          </nav>
        </div>
      </div>

      {/* ========== About 2 Section ========== */}
      <section className="py-16 bg-white">
        <div className="container mx-auto px-4">
          <span className="inline-flex items-center gap-2 bg-teal-100 text-teal-700 px-4 py-1 rounded-full text-sm mb-6">
            <i className="bi bi-info-circle"></i> About Us
          </span>
          <div className="grid md:grid-cols-2 gap-12">
            <div>
              <h2 className="text-3xl md:text-4xl font-bold text-gray-900 mb-4">
                Nemo enim ipsam voluptatem quia voluptas aspernatur
              </h2>
              <p className="text-gray-600 leading-relaxed">
                Temporibus autem quibusdam et aut officiis debitis aut rerum necessitatibus saepe eveniet ut et voluptates repudiandae sint et molestiae non recusandae.
              </p>
            </div>
            <div className="space-y-4">
              <p className="text-gray-600">
                Itaque earum rerum hic tenetur a sapiente delectus, ut aut reiciendis voluptatibus maiores alias consequatur aut perferendis doloribus asperiores repellat.
              </p>
              <p className="text-gray-600">
                Amet eos ut. Officiis soluta ab id dolor non sint. Corporis omnis consequatur quisquam ex consequuntur quo omnis. Quo eligendi cum. Amet mollitia qui quidem dolores praesentium quasi ut et.
              </p>
            </div>
          </div>

          {/* Features Boxes */}
          <div className="grid md:grid-cols-3 gap-8 mt-16">
            <div className="text-center p-6 rounded-2xl bg-gray-50 hover:shadow-lg transition">
              <div className="w-16 h-16 bg-teal-100 rounded-2xl flex items-center justify-center mx-auto mb-4">
                <i className="bi bi-bullseye text-2xl text-teal-700"></i>
              </div>
              <h3 className="text-xl font-semibold mb-2">
                <a href="#" className="hover:text-teal-700">At vero eos</a>
              </h3>
              <p className="text-gray-500 text-sm">
                Nam libero tempore, cum soluta nobis est eligendi optio cumque nihil impedit quo minus id quod maxime placeat.
              </p>
            </div>
            <div className="text-center p-6 rounded-2xl bg-gray-50 hover:shadow-lg transition">
              <div className="w-16 h-16 bg-teal-100 rounded-2xl flex items-center justify-center mx-auto mb-4">
                <i className="bi bi-person-check text-2xl text-teal-700"></i>
              </div>
              <h3 className="text-xl font-semibold mb-2">
                <a href="#" className="hover:text-teal-700">Sed ut perspiciatis</a>
              </h3>
              <p className="text-gray-500 text-sm">
                At vero eos et accusamus et iusto odio dignissimos ducimus qui blanditiis praesentium voluptatum deleniti atque.
              </p>
            </div>
            <div className="text-center p-6 rounded-2xl bg-gray-50 hover:shadow-lg transition">
              <div className="w-16 h-16 bg-teal-100 rounded-2xl flex items-center justify-center mx-auto mb-4">
                <i className="bi bi-clipboard-data text-2xl text-teal-700"></i>
              </div>
              <h3 className="text-xl font-semibold mb-2">
                <a href="#" className="hover:text-teal-700">Nemo enim ipsam</a>
              </h3>
              <p className="text-gray-500 text-sm">
                Neque porro quisquam est, qui dolorem ipsum quia dolor sit amet, consectetur, adipisci velit, sed quia non numquam.
              </p>
            </div>
          </div>

          {/* Video Box */}
          <div className="mt-16 relative rounded-2xl overflow-hidden shadow-xl">
            <img
              src="/assets/img/about/about-wide-1.webp"
              alt="Video Thumbnail"
              className="w-full h-auto"
            />
            <a
              href="https://www.youtube.com/watch?v=Y7f98aduVJ8"
              className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-20 h-20 bg-teal-700 rounded-full flex items-center justify-center shadow-lg hover:scale-110 transition"
              target="_blank"
              rel="noopener noreferrer"
            >
              <i className="bi bi-play-fill text-white text-3xl ml-1"></i>
            </a>
          </div>
        </div>
      </section>

      {/* ========== Stats Section ========== */}
      <section className="py-16 bg-gray-50">
        <div className="container mx-auto px-4">
          <div className="grid md:grid-cols-4 gap-8">
            <div className="text-center">
              <i className="bi bi-emoji-smile text-4xl text-teal-700 mb-3 block"></i>
              <div className="text-4xl font-bold text-gray-900">
                <StatsCounter end={232} />
              </div>
              <p className="text-gray-600 mt-2">
                <strong>Happy Clients</strong><br />consequuntur quae
              </p>
            </div>
            <div className="text-center">
              <i className="bi bi-journal-richtext text-4xl text-teal-700 mb-3 block"></i>
              <div className="text-4xl font-bold text-gray-900">
                <StatsCounter end={521} />
              </div>
              <p className="text-gray-600 mt-2">
                <strong>Projects</strong><br />adipisci atque cum quia aut
              </p>
            </div>
            <div className="text-center">
              <i className="bi bi-headset text-4xl text-teal-700 mb-3 block"></i>
              <div className="text-4xl font-bold text-gray-900">
                <StatsCounter end={1453} />
              </div>
              <p className="text-gray-600 mt-2">
                <strong>Hours Of Support</strong><br />aut commodi quaerat
              </p>
            </div>
            <div className="text-center">
              <i className="bi bi-people text-4xl text-teal-700 mb-3 block"></i>
              <div className="text-4xl font-bold text-gray-900">
                <StatsCounter end={32} />
              </div>
              <p className="text-gray-600 mt-2">
                <strong>Hard Workers</strong><br />rerum asperiores dolor
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ========== Testimonials Section (Masonry Layout) ========== */}
      <section className="py-16 bg-white">
        <div className="container mx-auto px-4">
          <div className="columns-1 md:columns-2 lg:columns-3 gap-6 space-y-6">
            {testimonials.map((item) => (
              <div key={item.id} className="break-inside-avoid">
                <TestimonialCard {...item} />
              </div>
            ))}
          </div>
        </div>
      </section>
    </>
  );
};

export default About;