// src/pages/Home.jsx
import FlashSaleBanner from '../components/FlashSaleBanner';
import Hero from '../components/Hero';
import PromoCards from '../components/PromoCards';
import BestSellers from '../components/BestSellers';
import Cards from '../components/Cards';

// The old hardcoded <Countdown /> section (fixed end date, fixed "50% OFF")
// is no longer rendered: FlashSaleBanner shows a REAL sale, from the API, or
// nothing at all.
const Home = () => {
  return (
    <>
      <FlashSaleBanner />
      <Hero />
      <PromoCards />
      <BestSellers />
      <Cards />
    </>
  );
};

export default Home;
