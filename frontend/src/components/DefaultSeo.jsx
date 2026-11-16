// Baseline <head> content for every route (Task 15.1.1.1).
//
// react-helmet-async is pinned to 3.0.0 (first release with React 19 support). On React 19
// it renders <title>/<meta> as real elements and lets React hoist them into <head>; it does
// NOT dedupe or apply deepest-wins the way 2.x/react-helmet did, and 2.0.5 applies nothing
// under <StrictMode> (verified), so it is not an option while main.jsx uses StrictMode.
//
// Overrides therefore go through <Seo> (Task 15.1.1.2): while any page's <Seo> is mounted this
// component renders nothing, so exactly one title and one description are ever in <head>.
//
// Canonical (Task 15.1.4): every page without its own <Seo> canonicalizes to its own clean path
// (no query string, no trailing slash). The path comes from the router, not window.location, so
// it follows client-side navigation instead of going stale after the first render. Routes whose
// query string IS their identity (/category, /blog) pass their own canonical through <Seo>.

import { Helmet } from 'react-helmet-async';
import { useInRouterContext, useLocation } from 'react-router-dom';
import { useSeo } from '../context/seoContext';
import { DEFAULT_DESCRIPTION, DEFAULT_TITLE } from '../constants/seo';
import { buildPageCanonical } from '../utils/canonical';
import { defaultOgImage } from '../utils/seo';
import { hreflangLinks } from './hreflangLinks';
import { openGraphMeta } from './openGraphMeta';

const DefaultSeoTags = ({ pathname }) => {
  const { hasPageSeo } = useSeo();
  if (hasPageSeo) return null;
  const canonical = buildPageCanonical(pathname);
  return (
    <Helmet>
      <title>{DEFAULT_TITLE}</title>
      <meta name="description" content={DEFAULT_DESCRIPTION} />
      {canonical && <link rel="canonical" href={canonical} />}
      {hreflangLinks(canonical)}
      {/* Sitewide Open Graph: og:site_name / og:type / og:locale plus a branded card. */}
      {openGraphMeta({
        type: 'website',
        title: DEFAULT_TITLE,
        description: DEFAULT_DESCRIPTION,
        ...defaultOgImage(),
      })}
    </Helmet>
  );
};

// useLocation() throws outside a <Router>, and some callers (isolated tests) have none, so pick
// the variant with the public useInRouterContext() rather than calling the hook conditionally.
const RoutedDefaultSeo = () => <DefaultSeoTags pathname={useLocation().pathname} />;

const DefaultSeo = () =>
  useInRouterContext() ? (
    <RoutedDefaultSeo />
  ) : (
    <DefaultSeoTags pathname={typeof window !== 'undefined' ? window.location?.pathname : ''} />
  );

export default DefaultSeo;
