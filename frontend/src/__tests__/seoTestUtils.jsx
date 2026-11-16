// Shared helpers for page-level SEO tests (Task 15.1.1.2): the same provider stack App.jsx
// uses, so a test sees exactly what lands in the real document <head>.
import { HelmetProvider } from 'react-helmet-async';
import DefaultSeo from '../components/DefaultSeo';
import SeoProvider from '../context/SeoProvider';

/** Wrap `children` in HelmetProvider + SeoProvider with the sitewide <DefaultSeo> mounted. */
export const WithSeo = ({ children }) => (
  <HelmetProvider>
    <SeoProvider>
      <DefaultSeo />
      {children}
    </SeoProvider>
  </HelmetProvider>
);
