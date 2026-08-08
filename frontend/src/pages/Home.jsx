// src/pages/Home.jsx
import Hero from '../components/Hero';
import PromoCards from '../components/PromoCards';
import BestSellers from '../components/BestSellers';
import Cards from '../components/Cards';
import Countdown from '../components/Countdown';

const Home = () => {
  return (
    <>
      <Hero />
      <PromoCards />
      <BestSellers />
      <Cards />
      <Countdown />
    </>
  );
};

export default Home;